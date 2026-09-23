from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.services.event_store import EventStore
from backend.app.services.review_state import (
    EventReviewService,
    InvalidReviewTransitionError,
    InvalidReviewUpdateError,
)


BASE_TIME = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


class ReviewStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = EventStore(
            Path(self.temporary_directory.name) / "review.sqlite3"
        )
        self.store.initialize()
        self.reviews = EventReviewService(self.store)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def payload(status: str, event_id: str = "evt_review_001") -> dict:
        published_at = BASE_TIME if status in {"published", "updated", "expired"} else None
        expires_at = BASE_TIME + timedelta(hours=2) if status == "expired" else None
        return {
            "event_id": event_id,
            "version": 1,
            "status": status,
            "created_at": BASE_TIME.isoformat(),
            "updated_at": BASE_TIME.isoformat(),
            "published_at": published_at.isoformat() if published_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "event_type": "signal_failure",
            "title": "待审核事件",
            "summary": "用于审核状态机测试。",
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
                "start": BASE_TIME.isoformat(),
                "end": None,
                "end_confidence": "unknown",
            },
            "severity": 3,
            "confidence": 0.55,
            "confidence_factors": [],
            "signals": ["sig_review_001"],
            "reviewed_by": "previous_reviewer" if published_at else None,
            "audit_log": [],
            "provenance": "simulated",
        }

    def create(self, status: str):
        return self.store.create_event(self.payload(status))

    def assert_one_change(self, before, after, action: str) -> None:
        self.assertEqual(after.version, before.version + 1)
        self.assertEqual(len(after.audit_log), len(before.audit_log) + 1)
        self.assertEqual(after.audit_log[-1].action, action)

    def assert_invalid_without_change(self, event_id: str, operation) -> None:
        before = self.store.get_event(event_id)
        with self.assertRaises((InvalidReviewTransitionError, InvalidReviewUpdateError)):
            operation()
        after = self.store.get_event(event_id)
        self.assertEqual(after.version, before.version)
        self.assertEqual(after.audit_log, before.audit_log)

    def test_approve_pending_review_publishes_and_audits_once(self) -> None:
        before = self.create("pending_review")
        at = BASE_TIME + timedelta(minutes=5)
        after = self.reviews.approve(before.event_id, actor="admin_b", at=at)
        self.assertEqual(after.status, "published")
        self.assertEqual(after.published_at, at)
        self.assertEqual(after.reviewed_by, "admin_b")
        self.assertEqual(after.confidence, 0.60)
        self.assert_one_change(before, after, "review_approved")

    def test_approve_updated_republishes(self) -> None:
        before = self.create("updated")
        at = BASE_TIME + timedelta(minutes=6)
        after = self.reviews.approve(before.event_id, actor="admin_b", at=at)
        self.assertEqual(after.status, "published")
        self.assertEqual(after.published_at, at)
        self.assert_one_change(before, after, "review_approved")

    def test_approve_rejects_all_other_statuses_without_mutation(self) -> None:
        for status in ("draft", "published", "expired", "rejected"):
            with self.subTest(status=status):
                event_id = f"evt_approve_{status}"
                self.store.create_event(self.payload(status, event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id: self.reviews.approve(
                        event_id, actor="admin_b"
                    ),
                )

    def test_edit_keeps_draft_and_pending_review_statuses(self) -> None:
        for status in ("draft", "pending_review"):
            with self.subTest(status=status):
                event_id = f"evt_edit_{status}"
                before = self.store.create_event(self.payload(status, event_id))
                after = self.reviews.edit(
                    event_id, {"title": "人工修订标题"}, actor="admin_b"
                )
                self.assertEqual(after.status, status)
                self.assertEqual(after.title, "人工修订标题")
                self.assert_one_change(before, after, "review_edited")

    def test_edit_published_becomes_updated_and_preserves_publication_data(self) -> None:
        before = self.create("published")
        after = self.reviews.edit(
            before.event_id, {"summary": "发布后人工修订。"}, actor="editor_b"
        )
        self.assertEqual(after.status, "updated")
        self.assertEqual(after.published_at, before.published_at)
        self.assertEqual(after.reviewed_by, before.reviewed_by)
        self.assertEqual(after.confidence, 0.55)
        self.assert_one_change(before, after, "review_edited")

    def test_edit_updated_remains_updated(self) -> None:
        before = self.create("updated")
        after = self.reviews.edit(
            before.event_id, {"title": "再次修订"}, actor="editor_b"
        )
        self.assertEqual(after.status, "updated")
        self.assert_one_change(before, after, "review_edited")

    def test_edit_terminal_statuses_is_rejected_without_mutation(self) -> None:
        for status in ("expired", "rejected"):
            with self.subTest(status=status):
                event_id = f"evt_terminal_{status}"
                self.store.create_event(self.payload(status, event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id: self.reviews.edit(
                        event_id, {"title": "不应成功"}, actor="editor_b"
                    ),
                )

    def test_edit_requires_changes_and_blocks_review_managed_fields(self) -> None:
        protected_updates = [
            {},
            {"event_id": "evt_fake"},
            {"version": 99},
            {"created_at": BASE_TIME},
            {"updated_at": BASE_TIME},
            {"audit_log": []},
            {"status": "published"},
            {"published_at": BASE_TIME},
            {"reviewed_by": "fake"},
            {"confidence": 1.0},
            {"confidence_factors": []},
            {"signals": ["fake"]},
            {"provenance": "real"},
        ]
        for updates in protected_updates:
            with self.subTest(updates=updates):
                event_id = f"evt_protected_{len(self.store.list_events())}"
                self.store.create_event(self.payload("pending_review", event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id, updates=updates: self.reviews.edit(
                        event_id, updates, actor="editor_b"
                    ),
                )

    def test_consecutive_legal_actions_increment_version_once_each(self) -> None:
        created = self.create("pending_review")
        approved = self.reviews.approve(created.event_id, actor="admin_b")
        edited = self.reviews.edit(
            created.event_id, {"summary": "批准后的修订。"}, actor="editor_b"
        )
        republished = self.reviews.approve(created.event_id, actor="admin_b")

        self.assertEqual(
            [created.version, approved.version, edited.version, republished.version],
            [1, 2, 3, 4],
        )
        self.assertEqual(
            [entry.action for entry in republished.audit_log],
            ["created", "review_approved", "review_edited", "review_approved"],
        )

    def test_reject_allowed_statuses_and_audits_once(self) -> None:
        for status in ("draft", "pending_review", "updated"):
            with self.subTest(status=status):
                event_id = f"evt_reject_{status}"
                before = self.store.create_event(self.payload(status, event_id))
                after = self.reviews.reject(event_id, actor="admin_b")
                self.assertEqual(after.status, "rejected")
                self.assertEqual(after.reviewed_by, "admin_b")
                self.assert_one_change(before, after, "review_rejected")

    def test_reject_disallowed_statuses_without_mutation(self) -> None:
        for status in ("published", "expired", "rejected"):
            with self.subTest(status=status):
                event_id = f"evt_no_reject_{status}"
                self.store.create_event(self.payload(status, event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id: self.reviews.reject(
                        event_id, actor="admin_b"
                    ),
                )

    def test_expire_published_and_updated(self) -> None:
        for status in ("published", "updated"):
            with self.subTest(status=status):
                event_id = f"evt_expire_{status}"
                before = self.store.create_event(self.payload(status, event_id))
                at = BASE_TIME + timedelta(hours=3)
                after = self.reviews.expire(event_id, actor="admin_b", at=at)
                self.assertEqual(after.status, "expired")
                self.assertEqual(after.expires_at, at)
                self.assertEqual(after.reviewed_by, "admin_b")
                self.assert_one_change(before, after, "review_expired")

    def test_expire_disallowed_statuses_without_mutation(self) -> None:
        for status in ("draft", "pending_review", "rejected", "expired"):
            with self.subTest(status=status):
                event_id = f"evt_no_expire_{status}"
                self.store.create_event(self.payload(status, event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id: self.reviews.expire(
                        event_id, actor="admin_b"
                    ),
                )

    def test_actor_must_be_non_empty_and_time_timezone_aware(self) -> None:
        for actor, at in (("  ", None), ("admin_b", BASE_TIME.replace(tzinfo=None))):
            with self.subTest(actor=actor, at=at):
                event_id = f"evt_actor_{len(self.store.list_events())}"
                self.store.create_event(self.payload("pending_review", event_id))
                self.assert_invalid_without_change(
                    event_id,
                    lambda event_id=event_id, actor=actor, at=at: self.reviews.approve(
                        event_id, actor=actor, at=at
                    ),
                )


if __name__ == "__main__":
    unittest.main()
