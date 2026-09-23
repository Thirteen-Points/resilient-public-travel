"""Conservative deduplication and evidence merge for existing Event cards.

The first full Event is assembled by the ingestion/review pipeline, which owns
numeric fields that a text extractor must not invent.  This service finds a
matching card and merges later Signals into it with one version and audit
increment per merge.  It never silently changes event facts or publishes a
card.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .confidence import ConfidenceObservation, score_confidence
from .event_models import Event
from .event_store import EventStore
from .signal_models import Signal
from .signal_store import SignalNotFoundError, SignalStore
from .structure.llm_structurer import StructuredEventDraft


ACTIVE_STATUSES = frozenset({"draft", "pending_review", "published", "updated"})


class AmbiguousEventMatchError(ValueError):
    """More than one active card matches; a reviewer must choose one."""


class UnrelatedSignalError(ValueError):
    """A signal cannot be safely attached to this event."""


@dataclass(frozen=True)
class StructuredObservation:
    signal: Signal
    draft: StructuredEventDraft
    verified_official_notice: bool = False


def _edges(event: Event | StructuredEventDraft) -> dict[frozenset[str], str]:
    return {
        frozenset((segment.from_node, segment.to_node)): segment.impact
        for segment in event.affected_segments
    }


class EventAggregator:
    """Find one matching Event and append new evidence without duplicate cards."""

    def __init__(
        self,
        events: EventStore,
        signals: SignalStore,
        *,
        max_gap: timedelta = timedelta(hours=2),
    ) -> None:
        if max_gap <= timedelta(0):
            raise ValueError("max_gap must be positive")
        self.events = events
        self.signals = signals
        self.max_gap = max_gap

    def find_match(self, observation: StructuredObservation) -> Event | None:
        """Return one same-incident card, or require review if ambiguous."""

        matches = [
            event for event in self.events.list_events()
            if self._same_incident(event, observation)
        ]
        if len(matches) > 1:
            raise AmbiguousEventMatchError("multiple events match this signal")
        return matches[0] if matches else None

    def merge(
        self,
        event_id: str,
        observations: Sequence[StructuredObservation],
        *,
        at: datetime | None = None,
    ) -> Event:
        """Merge complete evidence for one card; every old signal must be supplied.

        The caller provides the structured interpretation of existing Signals
        again because the Event contract stores only signal ids, not their
        classifications.  This makes agreement and official verification
        explicit rather than reconstructing them from possibly ambiguous text.
        """

        event = self.events.get_event(event_id)
        if event.status not in ACTIVE_STATUSES:
            raise ValueError("cannot merge into a terminal event")
        ids = [item.signal.signal_id for item in observations]
        if len(ids) != len(set(ids)):
            raise ValueError("signal ids must be unique")
        if not set(event.signals).issubset(ids):
            raise ValueError("all existing event signals must be supplied")
        if not observations:
            raise ValueError("at least one observation is required")
        for item in observations:
            if not self._same_incident(event, item):
                raise UnrelatedSignalError(item.signal.signal_id)

        new_items = [item for item in observations if item.signal.signal_id not in event.signals]
        # Validate every source before writing any new Signal.  A pre-existing
        # id with different content is a conflict, never an overwrite.
        for item in observations:
            try:
                stored = self.signals.get_signal(item.signal.signal_id)
            except SignalNotFoundError:
                if item.signal.signal_id in event.signals:
                    raise ValueError("event references a signal absent from the inbox")
                continue
            if stored != item.signal:
                raise ValueError("signal id already exists with different content")

        if not new_items:
            return event

        timestamp = at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("merge timestamp must have a timezone")
        if timestamp < event.updated_at:
            raise ValueError("merge timestamp cannot precede last event update")

        evidence = [
            ConfidenceObservation(
                signal=item.signal,
                role="conflict" if self._impact_conflicts(event, item.draft) else "agree",
                verified_official_notice=item.verified_official_notice,
            )
            for item in observations
        ]
        # Previous approval is retained as audit provenance, but new evidence
        # invalidates its confidence bonus until a reviewer approves again.
        result = score_confidence(evidence, admin_confirmed=False)

        for item in new_items:
            try:
                self.signals.get_signal(item.signal.signal_id)
            except SignalNotFoundError:
                self.signals.create_signal(item.signal)

        has_conflict = any(item.role == "conflict" for item in evidence)
        updates: dict[str, object] = {
            "signals": [*event.signals, *(item.signal.signal_id for item in new_items)],
            "confidence": result.score,
            "confidence_factors": [factor.model_dump() for factor in result.factors],
        }
        if event.status == "published":
            updates["status"] = "updated"  # Requires a new human approval.
        return self.events.update_event(
            event_id,
            updates,
            actor="system",
            action="merged_conflict" if has_conflict else "merged_signal",
            at=timestamp,
        )

    def _same_incident(self, event: Event, item: StructuredObservation) -> bool:
        draft = item.draft
        observed = item.signal.received_at
        if event.status not in ACTIVE_STATUSES:
            return False
        if observed.tzinfo is None or observed.utcoffset() is None:
            return False
        if event.event_type == "other" or draft.event_type != event.event_type:
            return False
        if draft.mode != event.mode or draft.line != event.line:
            return False
        if not draft.affected_segments or not (_edges(event).keys() & _edges(draft).keys()):
            return False
        if draft.direction not in (None, "unknown", "both") and event.direction not in ("both", "unknown", draft.direction):
            return False
        if observed < event.window.start - self.max_gap:
            return False
        latest = event.window.end or event.updated_at
        if observed > latest + self.max_gap:
            return False
        return True

    @staticmethod
    def _impact_conflicts(event: Event, draft: StructuredEventDraft) -> bool:
        current = _edges(event)
        return any(edge in current and current[edge] != impact for edge, impact in _edges(draft).items())
