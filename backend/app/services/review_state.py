"""Minimal, deterministic review state machine for stored Events."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Literal

from .event_models import ConfidenceFactor, Event
from .event_store import EventStore


ReviewAction = Literal["approve", "edit", "reject", "expire"]


class InvalidReviewTransitionError(ValueError):
    """Raised when an action is not allowed from the Event's current status."""


class InvalidReviewUpdateError(ValueError):
    """Raised when an edit attempts to change review-managed fields."""


class InsufficientConfidenceError(InvalidReviewTransitionError):
    """The reviewed card still misses the contract's publication threshold."""


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
        "confidence",
        "confidence_factors",
        "signals",
        "provenance",
    }

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def approve(
        self, event_id: str, *, actor: str, at: datetime | None = None, expected_version: int | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        if expected_version is not None and current.version != expected_version:
            raise RuntimeError("Event changed. Reload before reviewing.")
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("approve", current, {"pending_review", "updated"})
        already_confirmed = any(
            factor.factor == "admin_confirmation" and factor.score == 1.0
            for factor in current.confidence_factors
        )
        confidence = round(min(1.0, current.confidence + (0 if already_confirmed else 0.05)), 2)
        if confidence < 0.60:
            raise InsufficientConfidenceError("confidence below publish minimum 0.60")
        factors = [
            factor for factor in current.confidence_factors
            if factor.factor != "admin_confirmation"
        ]
        factors.append(ConfidenceFactor(
            factor="admin_confirmation", weight=0.05, score=1.0,
            note="Reviewer confirmed.",
        ))
        return self.store.update_event(
            event_id,
            {
                "status": "published",
                "published_at": timestamp,
                "reviewed_by": actor.strip(),
                "confidence": confidence,
                "confidence_factors": factors,
            },
            actor=actor.strip(),
            action="review_approved",
            at=timestamp,
            expected_version=current.version,
        )

    def edit(
        self,
        event_id: str,
        updates: Mapping[str, Any],
        *,
        actor: str,
        at: datetime | None = None,
        expected_version: int | None = None,
    ) -> Event:
        current = self.store.get_event(event_id)
        if expected_version is not None and current.version != expected_version:
            raise RuntimeError("Event changed. Reload before reviewing.")
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
            if any(factor.factor == "admin_confirmation" and factor.score == 1.0
                   for factor in current.confidence_factors):
                effective_updates["confidence"] = round(max(0.0, current.confidence - 0.05), 2)
                effective_updates["confidence_factors"] = [
                    factor.model_copy(update={"score": 0.0, "note": "Edited; awaiting reapproval."})
                    if factor.factor == "admin_confirmation" else factor
                    for factor in current.confidence_factors
                ]
        return self.store.update_event(
            event_id,
            effective_updates,
            actor=actor.strip(),
            action="review_edited",
            at=timestamp,
            expected_version=current.version,
        )

    def reject(
        self, event_id: str, *, actor: str, at: datetime | None = None, expected_version: int | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        if expected_version is not None and current.version != expected_version:
            raise RuntimeError("Event changed. Reload before reviewing.")
        timestamp = self._review_time(at)
        self._require_actor(actor)
        self._require_status("reject", current, {"draft", "pending_review", "updated"})
        return self.store.update_event(
            event_id,
            {"status": "rejected", "reviewed_by": actor.strip()},
            actor=actor.strip(),
            action="review_rejected",
            at=timestamp,
            expected_version=current.version,
        )

    def expire(
        self, event_id: str, *, actor: str, at: datetime | None = None, expected_version: int | None = None
    ) -> Event:
        current = self.store.get_event(event_id)
        if expected_version is not None and current.version != expected_version:
            raise RuntimeError("Event changed. Reload before reviewing.")
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
            expected_version=current.version,
        )

    def expire_due(self, *, at: datetime | None = None) -> list[Event]:
        """Reconcile timed-out public cards on demand and emit audit changes.

        API reads and the event stream call this method, so it needs no
        separate scheduler. A repeated read cannot append a second expiry.
        """
        now = self._review_time(at)
        expired: list[Event] = []
        for current in self.store.list_events():
            if current.status not in {"published", "updated"}:
                continue
            deadlines = [value for value in (current.expires_at, current.window.end) if value]
            if not deadlines or min(deadlines) > now:
                continue
            try:
                expired.append(self.store.update_event(
                    current.event_id,
                    {"status": "expired", "expires_at": now},
                    actor="system", action="auto_expired", at=now,
                ))
            except RuntimeError:
                # Another reader won the optimistic write. Its audit entry is
                # already durable and will be delivered by the SSE cursor.
                if self.store.get_event(current.event_id).status not in {"expired", "rejected"}:
                    raise
        return expired

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
