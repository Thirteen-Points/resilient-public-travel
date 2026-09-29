"""User Signal submission endpoint."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from ..services.signal_models import Signal
from ..services.signal_store import SignalAlreadyExistsError, SignalNotFoundError, SignalStore
from .review import require_reviewer


MAX_REPORT_LENGTH = 2000
MAX_AUTHOR_LENGTH = 100
ANONYMOUS_AUTHOR = "anonymous"
USER_SOURCE_NAME = "ResilientRoute 用户上报（未经核实）"

ReportText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REPORT_LENGTH),
]
AuthorHint = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_AUTHOR_LENGTH),
]


class UserSignalSubmission(BaseModel):
    """Only untrusted user-editable fields accepted by the endpoint."""

    model_config = ConfigDict(extra="forbid")

    raw_text: ReportText
    author_hint: AuthorHint | None = None
    lang: Literal["zh-HK", "en"] = "zh-HK"


class SignalAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str


router = APIRouter(prefix="/api", tags=["signals"])


def get_signal_store(request: Request) -> SignalStore:
    return request.app.state.signal_store


@router.get("/signals", response_model=list[Signal])
def list_signals(
    request: Request,
    unlinked_only: bool = False,
    x_review_token: str | None = Header(default=None),
) -> list[Signal]:
    """Expose raw reports only to reviewers; linked reports remain stored."""
    require_reviewer(request, x_review_token)
    signals = request.app.state.signal_store.list_signals()
    if not unlinked_only:
        return signals
    linked = {
        signal_id
        for event in request.app.state.event_store.list_events()
        for signal_id in event.signals
    }
    return [signal for signal in signals if signal.signal_id not in linked]


@router.get("/signals/{signal_id}", response_model=Signal)
def get_signal(
    signal_id: str, request: Request,
    x_review_token: str | None = Header(default=None),
) -> Signal:
    """Read the original evidence alongside a structured draft or Event."""
    require_reviewer(request, x_review_token)
    try:
        return request.app.state.signal_store.get_signal(signal_id)
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Signal not found") from exc


def build_user_signal(
    submission: UserSignalSubmission,
    *,
    received_at: datetime | None = None,
    unique_suffix: str | None = None,
) -> Signal:
    """Build a Signal without interpreting the user's report text."""

    timestamp = received_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")
    suffix = unique_suffix or uuid4().hex[:12]
    stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Signal(
        signal_id=f"user-report-{stamp}-{suffix}",
        received_at=timestamp,
        source_type="user",
        source_name=USER_SOURCE_NAME,
        author_hint=submission.author_hint or ANONYMOUS_AUTHOR,
        raw_text=submission.raw_text,
        raw_url=None,
        lang=submission.lang,
        provenance="real",
    )


@router.post(
    "/signals",
    response_model=SignalAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_signal(
    submission: UserSignalSubmission,
    store: SignalStore = Depends(get_signal_store),
) -> SignalAcceptedResponse:
    """Validate and persist one unverified user report before responding."""

    signal = build_user_signal(submission)
    try:
        stored = store.create_signal(signal)
    except (sqlite3.Error, OSError, SignalAlreadyExistsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal inbox is temporarily unavailable",
        ) from exc
    return SignalAcceptedResponse(signal_id=stored.signal_id)
