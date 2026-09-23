"""Authenticated human review endpoints for the Event state machine."""

from __future__ import annotations

from hmac import compare_digest
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.event_models import AffectedSegment, Event, EventType, EventWindow, TransportMode
from ..services.event_store import EventNotFoundError
from ..services.review_state import (
    EventReviewService,
    InvalidReviewTransitionError,
    InvalidReviewUpdateError,
)


class ReviewEdits(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: EventType | None = None
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    mode: TransportMode | None = None
    line: str | None = Field(default=None, min_length=1)
    direction: str | None = Field(default=None, min_length=1)
    affected_segments: list[AffectedSegment] | None = None
    window: EventWindow | None = None
    severity: int | None = Field(default=None, ge=1, le=5)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["approve", "edit", "reject", "expire"]
    actor: str = Field(min_length=1, max_length=100)
    edits: ReviewEdits | None = None


router = APIRouter(prefix="/api/events", tags=["review"])


def require_reviewer(request: Request, supplied: str | None) -> None:
    expected: str | None = request.app.state.review_token
    if not expected:
        raise HTTPException(status_code=503, detail="Review token is not configured")
    if supplied is None or not compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Reviewer authorization required")


@router.post("/{event_id}/review", response_model=Event)
def review_event(
    event_id: str,
    body: ReviewRequest,
    request: Request,
    x_review_token: str | None = Header(default=None),
) -> Event:
    require_reviewer(request, x_review_token)
    reviews = EventReviewService(request.app.state.event_store)
    if body.action == "edit":
        if body.edits is None:
            raise HTTPException(status_code=422, detail="edit requires edits")
        changes = body.edits.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise HTTPException(status_code=422, detail="edit requires at least one change")
    elif body.edits is not None:
        raise HTTPException(status_code=422, detail="edits are only allowed with edit")
    try:
        if body.action == "approve":
            return reviews.approve(event_id, actor=body.actor)
        if body.action == "edit":
            return reviews.edit(event_id, changes, actor=body.actor)
        if body.action == "reject":
            return reviews.reject(event_id, actor=body.actor)
        return reviews.expire(event_id, actor=body.actor)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Event not found") from exc
    except InvalidReviewTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidReviewUpdateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
