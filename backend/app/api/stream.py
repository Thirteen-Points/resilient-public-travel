"""Durable Server-Sent Events stream backed by Event audit sequence."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from .review import require_reviewer
from ..services.event_store import EventStore


router = APIRouter(prefix="/api/stream", tags=["stream"])


async def event_frames(store: EventStore, after_id: int, *, poll_seconds: float = 0.1) -> AsyncIterator[str]:
    """Replay audit changes, then tail them without an in-memory-only bus."""

    cursor = after_id
    while True:
        changes = store.list_changes(after_id=cursor)
        if changes:
            for audit_id, event, change in changes:
                cursor = audit_id
                payload = json.dumps(
                    {"event": event.model_dump(mode="json"), "change": change.model_dump(mode="json")},
                    ensure_ascii=False, separators=(",", ":"),
                )
                yield f"id: {audit_id}\nevent: event\ndata: {payload}\n\n"
        else:
            await asyncio.sleep(poll_seconds)


@router.get("/events")
def stream_events(
    request: Request,
    after_id: int | None = None,
    last_event_id: str | None = Header(default=None),
    x_review_token: str | None = Header(default=None),
) -> StreamingResponse:
    require_reviewer(request, x_review_token)
    if after_id is not None and after_id < 0:
        raise HTTPException(status_code=422, detail="after_id must be non-negative")
    if after_id is None:
        try:
            after_id = int(last_event_id) if last_event_id is not None else 0
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid Last-Event-ID") from exc
    if after_id < 0:
        raise HTTPException(status_code=422, detail="Invalid Last-Event-ID")
    return StreamingResponse(
        event_frames(request.app.state.event_store, after_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
