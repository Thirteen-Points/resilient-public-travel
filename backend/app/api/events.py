"""Event inbox, conservative signal ingestion, and reviewed-card queries."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .review import require_reviewer
from ..services.aggregate import (
    AmbiguousEventMatchError,
    EventAggregator,
    StructuredObservation,
    UnrelatedSignalError,
)
from ..services.confidence import ConfidenceObservation, score_confidence
from ..services.event_models import Event, EventStatus
from ..services.event_store import EventAlreadyExistsError, EventNotFoundError
from ..services.review_state import EventReviewService
from ..services.signal_store import SignalNotFoundError
from ..services.structure.llm_structurer import LlmEventStructurer, StructuredEventDraft


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str = Field(min_length=1)


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str
    state: Literal["merged", "needs_review"]
    draft: StructuredEventDraft
    event: Event | None


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[Event])
def list_events(
    request: Request, status: EventStatus | None = None,
    x_review_token: str | None = Header(default=None),
) -> list[Event]:
    require_reviewer(request, x_review_token)
    EventReviewService(request.app.state.event_store).expire_due()
    return request.app.state.event_store.list_events(status=status)


@router.get("/published", response_model=list[Event])
def published_events(request: Request) -> list[Event]:
    EventReviewService(request.app.state.event_store).expire_due()
    return request.app.state.event_store.list_events(status="published")


@router.get("/{event_id}", response_model=Event)
def get_event(
    event_id: str, request: Request,
    x_review_token: str | None = Header(default=None),
) -> Event:
    require_reviewer(request, x_review_token)
    try:
        return request.app.state.event_store.get_event(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Event not found") from exc


@router.post("", response_model=Event, status_code=201)
def create_review_candidate(
    event: Event,
    request: Request,
    x_review_token: str | None = Header(default=None),
) -> Event:
    """A reviewer supplies explicit numeric facts for the first card.

    The server still owns confidence.  A candidate cannot be pre-published or
    claim official verification through this endpoint.
    """

    require_reviewer(request, x_review_token)
    if (event.status != "pending_review" or event.version != 1 or
            event.published_at is not None or event.reviewed_by is not None or
            len(event.signals) != 1):
        raise HTTPException(status_code=422, detail="Expected one unreviewed signal and a version-1 pending card")
    try:
        signal = request.app.state.signal_store.get_signal(event.signals[0])
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Signal not found") from exc
    result = score_confidence([ConfidenceObservation(signal)])
    candidate = event.model_copy(update={
        "confidence": result.score,
        "confidence_factors": list(result.factors),
        "provenance": signal.provenance,
    })
    try:
        return request.app.state.event_store.create_event(candidate, actor="system")
    except EventAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Event already exists") from exc


@router.post("/ingest", response_model=IngestResult)
def ingest_signal(
    body: IngestRequest, request: Request,
    x_review_token: str | None = Header(default=None),
) -> IngestResult:
    """Structure a stored signal and merge only into an unambiguous existing card."""

    require_reviewer(request, x_review_token)
    signals = request.app.state.signal_store
    events = request.app.state.event_store
    try:
        signal = signals.get_signal(body.signal_id)
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Signal not found") from exc
    structurer = LlmEventStructurer(request.app.state.llm_client)
    draft = structurer.structure(signal).draft
    observation = StructuredObservation(signal=signal, draft=draft)
    aggregator = EventAggregator(events, signals)
    try:
        match = aggregator.find_match(observation)
    except AmbiguousEventMatchError as exc:
        raise HTTPException(status_code=409, detail="Ambiguous event match; reviewer required") from exc
    if match is None:
        return IngestResult(signal_id=signal.signal_id, state="needs_review", draft=draft, event=None)

    # Existing signal interpretations are rebuilt with deterministic rules;
    # the inbox keeps originals, while Event stores their ids only.
    from ..services.structure.rule_extractor import RuleEventExtractor

    rules = RuleEventExtractor()
    observations = [
        StructuredObservation(signal=old, draft=rules.extract(old))
        for signal_id in match.signals
        for old in [signals.get_signal(signal_id)]
    ]
    if signal.signal_id not in match.signals:
        observations.append(observation)
    try:
        merged = aggregator.merge(match.event_id, observations)
    except (UnrelatedSignalError, ValueError, SignalNotFoundError) as exc:
        raise HTTPException(status_code=409, detail="Signal requires manual review") from exc
    return IngestResult(signal_id=signal.signal_id, state="merged", draft=draft, event=merged)
