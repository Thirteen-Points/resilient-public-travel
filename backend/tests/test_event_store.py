from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from backend.app.services.event_store import EventStore


class EventStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary_directory.name) / "events.sqlite3"
        self.store = EventStore(self.db_path)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def event_payload(event_id: str = "evt_test_001") -> dict:
        created_at = datetime(2026, 9, 22, 8, 3, 20, tzinfo=timezone.utc)
        return {
            "event_id": event_id,
            "version": 1,
            "status": "draft",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
            "published_at": None,
            "expires_at": None,
            "event_type": "signal_failure",
            "title": "东铁线过海段疑似信号故障",
            "summary": "单一来源报告，等待审核。",
            "mode": "MTR",
            "line": "ERL",
            "direction": "both",
            "affected_segments": [
                {
                    "from_node": "HUH",
                    "to_node": "EXC",
                    "impact": "closed",
                    "capacity_factor": 0.0,
                }
            ],
            "window": {
                "start": created_at.isoformat(),
                "end": None,
                "end_confidence": "unknown",
            },
            "severity": 3,
            "confidence": 0.2,
            "confidence_factors": [
                {
                    "factor": "source_authority",
                    "weight": 0.35,
                    "score": 0.15,
                    "note": "单一社媒来源",
                }
            ],
            "signals": ["sig_test_001"],
            "reviewed_by": None,
            "audit_log": [],
            "provenance": "simulated",
        }

    def test_create_and_read_event(self) -> None:
        created = self.store.create_event(self.event_payload())
        fetched = self.store.get_event(created.event_id)

        self.assertEqual(fetched.event_id, "evt_test_001")
        self.assertEqual(fetched.title, "东铁线过海段疑似信号故障")
        self.assertEqual(fetched.version, 1)
        self.assertEqual(len(fetched.audit_log), 1)
        self.assertEqual(fetched.audit_log[0].action, "created")

    def test_update_event_increments_version_and_appends_audit(self) -> None:
        self.store.create_event(self.event_payload())
        changed_at = datetime(2026, 9, 22, 8, 5, 2, tzinfo=timezone.utc)

        updated = self.store.update_event(
            "evt_test_001",
            {
                "status": "pending_review",
                "confidence": 0.55,
                "title": "东铁线过海段信号故障（多源一致）",
            },
            actor="pipeline",
            action="merged_signal",
            at=changed_at,
        )

        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.status, "pending_review")
        self.assertEqual(updated.confidence, 0.55)
        self.assertEqual(len(updated.audit_log), 2)
        self.assertEqual(updated.audit_log[-1].actor, "pipeline")
        self.assertEqual(updated.audit_log[-1].action, "merged_signal")
        self.assertEqual(updated.audit_log[-1].confidence_after, 0.55)

    def test_each_change_adds_exactly_one_audit_record(self) -> None:
        self.store.create_event(self.event_payload())
        first_update = datetime(2026, 9, 22, 8, 4, tzinfo=timezone.utc)
        second_update = first_update + timedelta(minutes=1)

        self.store.update_event(
            "evt_test_001",
            {"confidence": 0.35},
            actor="pipeline",
            action="merged_signal",
            at=first_update,
        )
        result = self.store.update_event(
            "evt_test_001",
            {"confidence": 0.55},
            actor="pipeline",
            action="merged_signal",
            at=second_update,
        )

        self.assertEqual([entry.action for entry in result.audit_log], [
            "created",
            "merged_signal",
            "merged_signal",
        ])

    def test_audit_rows_cannot_be_updated_or_deleted(self) -> None:
        self.store.create_event(self.event_payload())

        with closing(sqlite3.connect(self.db_path)) as connection:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    "UPDATE audit_log SET action = 'tampered' WHERE event_id = ?",
                    ("evt_test_001",),
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    "DELETE FROM audit_log WHERE event_id = ?",
                    ("evt_test_001",),
                )

    def test_invalid_status_is_rejected(self) -> None:
        payload = self.event_payload()
        payload["status"] = "approved"

        with self.assertRaises(ValidationError):
            self.store.create_event(payload)

    def test_invalid_confidence_is_rejected(self) -> None:
        payload = self.event_payload()
        payload["confidence"] = 1.1

        with self.assertRaises(ValidationError):
            self.store.create_event(payload)

    def test_list_events_can_filter_by_status(self) -> None:
        self.store.create_event(self.event_payload("evt_test_001"))
        second = self.event_payload("evt_test_002")
        second["status"] = "published"
        second["published_at"] = second["created_at"]
        self.store.create_event(second, actor="admin_demo")

        self.assertEqual(len(self.store.list_events()), 2)
        published = self.store.list_events(status="published")
        self.assertEqual([event.event_id for event in published], ["evt_test_002"])

    def test_initialize_is_idempotent_and_preserves_data(self) -> None:
        self.store.create_event(self.event_payload())

        self.store.initialize()

        self.assertEqual(self.store.get_event("evt_test_001").version, 1)

    def test_immutable_fields_cannot_be_updated(self) -> None:
        self.store.create_event(self.event_payload())

        with self.assertRaisesRegex(ValueError, "immutable fields"):
            self.store.update_event(
                "evt_test_001",
                {"event_id": "evt_changed"},
                actor="admin_demo",
            )


if __name__ == "__main__":
    unittest.main()
