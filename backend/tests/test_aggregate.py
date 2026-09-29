from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from backend.app.services.aggregate import (
    AmbiguousEventMatchError,
    EventAggregator,
    StructuredObservation,
    UnrelatedSignalError,
)
from backend.app.services.event_models import Event
from backend.app.services.event_store import EventStore
from backend.app.services.signal_models import Signal
from backend.app.services.signal_store import SignalStore
from backend.app.services.structure.llm_structurer import StructuredEventDraft


ROOT = Path(__file__).resolve().parents[2]
SEED = json.loads((ROOT / "contracts/seed/event.seed.json").read_text(encoding="utf-8"))
BASE_TIME = datetime.fromisoformat("2026-09-22T08:03:20+08:00")


def observation(number: int, *, impact: str = "closed", author: str | None = None,
                line: str = "ERL") -> StructuredObservation:
    signal = Signal(
        signal_id=f"sig-aggregate-{number}",
        received_at=BASE_TIME + timedelta(minutes=number),
        source_type="social",
        source_name="模拟社媒流",
        author_hint=author or f"乘客{number}",
        raw_text="【模拟】东铁线红磡至会展信号故障，服务暂停。",
        raw_url=None,
        lang="zh-HK",
        provenance="simulated",
    )
    draft = StructuredEventDraft(
        event_type="signal_failure",
        title="东铁线过海段信号故障（待核实）",
        summary=signal.raw_text,
        mode="MTR",
        line=line,
        direction="both",
        affected_segments=[{"from_node": "HUH", "to_node": "EXC", "impact": impact}],
    )
    return StructuredObservation(signal=signal, draft=draft)


class EventAggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        db = Path(self.directory.name) / "events.sqlite3"
        self.events = EventStore(db)
        self.signals = SignalStore(db)
        self.events.initialize()
        self.signals.initialize()
        self.aggregator = EventAggregator(self.events, self.signals)

    def create_first_card(self, first: StructuredObservation | None = None) -> Event:
        item = first or observation(1)
        self.signals.create_signal(item.signal)
        payload = dict(SEED["events"][0])
        payload.update(
            event_id="evt-aggregate-001",
            created_at=BASE_TIME.isoformat(),
            updated_at=BASE_TIME.isoformat(),
            window={"start": BASE_TIME.isoformat(), "end": None, "end_confidence": "unknown"},
            signals=[item.signal.signal_id],
            audit_log=[],
        )
        return self.events.create_event(Event.model_validate(payload))

    def test_four_same_incident_texts_merge_to_one_card_with_rising_confidence(self) -> None:
        items = [observation(number) for number in range(1, 5)]
        first = self.create_first_card(items[0])
        self.assertEqual(first.confidence, 0.20)
        for count in range(2, 5):
            self.assertEqual(self.aggregator.find_match(items[count - 1]).event_id, first.event_id)
            updated = self.aggregator.merge(
                first.event_id, items[:count], at=BASE_TIME + timedelta(minutes=count)
            )
            self.assertEqual(updated.version, count)

        self.assertEqual(len(self.events.list_events()), 1)
        self.assertEqual(updated.confidence, 0.55)
        self.assertEqual(updated.signals, [item.signal.signal_id for item in items])
        self.assertEqual([entry.action for entry in updated.audit_log],
                         ["created", "merged_signal", "merged_signal", "merged_signal"])
        self.assertEqual([entry.confidence_after for entry in updated.audit_log],
                         [0.2, 0.55, 0.55, 0.55])

    def test_repeated_same_account_merges_without_inflating_confidence(self) -> None:
        first, second = observation(1, author="same"), observation(2, author="same")
        event = self.create_first_card(first)
        updated = self.aggregator.merge(event.event_id, [first, second],
                                        at=BASE_TIME + timedelta(minutes=2))
        self.assertEqual(updated.confidence, 0.20)
        self.assertEqual(updated.version, 2)

    def test_different_impact_deducts_confidence_and_requires_reapproval(self) -> None:
        first, second = observation(1), observation(2, impact="slow")
        event = self.create_first_card(first)
        self.events.update_event(event.event_id, {"status": "published", "reviewed_by": "admin"},
                                 actor="admin", action="published",
                                 at=BASE_TIME + timedelta(seconds=30))
        updated = self.aggregator.merge(event.event_id, [first, second],
                                        at=BASE_TIME + timedelta(minutes=2))
        self.assertEqual(updated.status, "updated")
        self.assertEqual(updated.confidence, 0.05)  # Prior approval no longer counts.
        self.assertEqual(updated.audit_log[-1].action, "merged_conflict")
        self.assertEqual(updated.affected_segments[0].impact, "closed")

    def test_published_card_loses_old_approval_bonus_on_new_evidence(self) -> None:
        first, second = observation(1), observation(2)
        event = self.create_first_card(first)
        self.events.update_event(event.event_id, {"status": "published", "reviewed_by": "admin"},
                                 actor="admin", action="published",
                                 at=BASE_TIME + timedelta(seconds=30))
        updated = self.aggregator.merge(event.event_id, [first, second],
                                        at=BASE_TIME + timedelta(minutes=2))
        self.assertEqual(updated.status, "updated")
        self.assertEqual(updated.confidence, 0.55)
        self.assertEqual(updated.reviewed_by, "admin")  # Historical reviewer remains visible.

    def test_unrelated_or_ambiguous_signal_is_not_auto_merged(self) -> None:
        first = observation(1)
        event = self.create_first_card(first)
        unrelated = observation(2, line="ERL", impact="crowded")
        unrelated = StructuredObservation(
            signal=unrelated.signal,
            draft=unrelated.draft.model_copy(update={"event_type": "crowd"}),
        )
        self.assertIsNone(self.aggregator.find_match(unrelated))
        with self.assertRaises(UnrelatedSignalError):
            self.aggregator.merge(event.event_id, [first, unrelated],
                                  at=BASE_TIME + timedelta(minutes=2))
        self.assertEqual(self.events.get_event(event.event_id).version, 1)

        duplicate = self.events.get_event(event.event_id).model_dump(mode="python")
        duplicate["event_id"] = "evt-aggregate-002"
        duplicate["audit_log"] = []
        self.events.create_event(duplicate)
        with self.assertRaises(AmbiguousEventMatchError):
            self.aggregator.find_match(observation(3))

    def test_idempotent_retry_does_not_increment_version(self) -> None:
        first, second = observation(1), observation(2)
        event = self.create_first_card(first)
        once = self.aggregator.merge(event.event_id, [first, second],
                                     at=BASE_TIME + timedelta(minutes=2))
        twice = self.aggregator.merge(event.event_id, [first, second],
                                      at=BASE_TIME + timedelta(minutes=3))
        self.assertEqual(twice.version, once.version)
        self.assertEqual(len(twice.audit_log), 2)

        tampered = StructuredObservation(
            signal=second.signal.model_copy(update={"raw_text": "different content"}),
            draft=second.draft,
        )
        with self.assertRaisesRegex(ValueError, "different content"):
            self.aggregator.merge(event.event_id, [first, tampered],
                                  at=BASE_TIME + timedelta(minutes=4))


if __name__ == "__main__":
    unittest.main()
