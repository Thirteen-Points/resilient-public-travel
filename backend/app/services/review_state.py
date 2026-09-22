"""Minimal, deterministic review state machine for stored Events."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Literal

from .event_models import Event
from .event_store import EventStore


ReviewAction = Literal["approve", "edit", "reject", "expire"]


class InvalidReviewTransitionError(ValueError):
    """Raised when an action is not allowed from the Event's current status."""


class InvalidReviewUpdateError(ValueError):
    """Raised when an edit attempts to change review-managed fields."""


class EventReviewService:
    """Apply M0 review transitions while EventStore handles persistence/audit."""

    _EDITABLE_STATUSES = {"draft", "pending_review", "published", "updated"}
    _EDIT_FORBIDDEN_FIELDS = {
        "event_id",
        "version",
        "created_at",
        "updated_at",
        "audit_log",
        "status",
        "published_at",
        "reviewed_by",
    }

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def approve(
        self, event_id: str, *, actor: str, at: datetime | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("approve", current, {"pending_review", "updated"})
        return self.store.update_event(
            event_id,
            {
                "status": "published",
                "published_at": timestamp,
                "reviewed_by": actor.strip(),
            },
            actor=actor.strip(),
            action="review_approved",
            at=timestamp,
        )

    def edit(
        self,
        event_id: str,
        updates: Mapping[str, Any],
        *,
        actor: str,
        at: datetime | None = None,
    ) -> Event:
        current = self.store.get_event(event_id)
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("edit", current, self._EDITABLE_STATUSES)
        if not updates:
            raise InvalidReviewUpdateError("edit requires at least one field")
        forbidden = self._EDIT_FORBIDDEN_FIELDS.intersection(updates)
        if forbidden:
            fields = ", ".join(sorted(forbidden))
            raise InvalidReviewUpdateError(
                f"review-managed fields cannot be edited: {fields}"
            )

        effective_updates = dict(updates)
        if current.status == "published":
            effective_updates["status"] = "updated"
        return self.store.update_event(
            event_id,
            effective_updates,
            actor=actor.strip(),
            action="review_edited",
            at=timestamp,
        )

    def reject(
        self, event_id: str, *, actor: str, at: datetime | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("reject", current, {"draft", "pending_review", "updated"})
        return self.store.update_event(
            event_id,
            {"status": "rejected", "reviewed_by": actor.strip()},
            actor=actor.strip(),
            action="review_rejected",
            at=timestamp,
        )

    def expire(
        self, event_id: str, *, actor: str, at: datetime | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("expire", current, {"published", "updated"})
        return self.store.update_event(
            event_id,
            {
                "status": "expired",
                "expires_at": timestamp,
                "reviewed_by": actor.strip(),
            },
            actor=actor.strip(),
            action="review_expired",
            at=timestamp,
        )

    @staticmethod
    def _require_actor(actor: str) -> None:
        if not actor or not actor.strip():
            raise InvalidReviewUpdateError("review actor must not be empty")

    @staticmethod
    def _review_time(value: datetime | None) -> datetime:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidReviewUpdateError("review time must include a timezone")
        return timestamp

    @staticmethod
    def _require_status(
        action: ReviewAction, current: Event, allowed_statuses: set[str]
    ) -> None:
        if current.status not in allowed_statuses:
            raise InvalidReviewTransitionError(
                f"cannot {action} Event in status {current.status}"
            )
