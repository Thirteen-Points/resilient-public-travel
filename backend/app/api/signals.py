"""User Signal submission endpoint."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from ..services.signal_models import Signal
from ..services.signal_store import SignalAlreadyExistsError, SignalStore


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
