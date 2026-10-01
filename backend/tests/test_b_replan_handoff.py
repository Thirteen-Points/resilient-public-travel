"""B's event receipt sequence for C's replan consumer."""

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.api.stream import event_frames
from backend.app.main import create_app
from backend.app.services.event_store import EventStore
from backend.app.services.review_state import EventReviewService


AT = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)


def event_payload():
    return {
        "event_id": "evt_replan_b", "version": 1, "status": "pending_review",
        "created_at": AT.isoformat(), "updated_at": AT.isoformat(),
        "published_at": None, "expires_at": None,
        "event_type": "signal_failure", "title": "过海段故障", "summary": "待审核",
        "mode": "MTR", "line": "ERL", "direction": "both",
        "affected_segments": [{"from_node": "HUH", "to_node": "EXC", "impact": "closed", "capacity_factor": 0}],
        "window": {"start": AT.isoformat(), "end": None, "end_confidence": "unknown"},
        "severity": 3, "confidence": 0.55, "confidence_factors": [],
        "signals": ["sig_replan_b"], "reviewed_by": None,
        "audit_log": [], "provenance": "simulated",
    }


class ReplanHandoffTests(unittest.TestCase):
    def test_auto_expiry_restores_shared_app_snapshot_routes_and_sse(self):
        """A public read expires one reviewed card across B, C, and SSE."""
        now = datetime.now(timezone.utc)
        hkt = timezone(timedelta(hours=8))
        departure = (now.astimezone(hkt) + timedelta(days=1)).replace(
            hour=8, minute=20, second=0, microsecond=0)
        query = {"origin": "TAW", "destination": "ADM", "depart_at": departure.isoformat()}
        deadline = departure + timedelta(hours=1)

        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(db_path=Path(directory) / "api.sqlite3", review_token="test")) as client:
                baseline = client.post("/api/routes/query", json=query)
                self.assertEqual(baseline.status_code, 200)
                baseline_ids = {route["route_id"] for route in baseline.json()}
                self.assertTrue(baseline_ids)

                payload = event_payload()
                payload.update(status="published", created_at=now.isoformat(),
                               updated_at=now.isoformat(), published_at=now.isoformat(),
                               expires_at=deadline.isoformat())
                payload["window"]["start"] = now.isoformat()
                client.app.state.event_store.create_event(payload)

                active = client.get("/api/graph/snapshot").json()
                self.assertTrue(any(edge["from_node"] == "HUH" and edge["to_node"] == "EXC"
                                    for edge in active["affected_edges"]))
                disrupted = client.post("/api/routes/query", json=query)
                self.assertEqual(disrupted.status_code, 200)
                self.assertNotEqual(baseline_ids, {route["route_id"] for route in disrupted.json()})

                # The read triggers reconciliation; no real clock wait or scheduler is needed.
                with patch.object(EventReviewService, "_review_time", return_value=deadline + timedelta(minutes=1)):
                    self.assertEqual(client.get("/api/events/published").json(), [])
                    self.assertEqual(client.get("/api/events/published").json(), [])
                    restored = client.get("/api/graph/snapshot").json()
                    self.assertFalse(any(edge["from_node"] == "HUH" and edge["to_node"] == "EXC"
                                         for edge in restored["affected_edges"]))
                    routes = client.post("/api/routes/query", json=query)
                    self.assertEqual(routes.status_code, 200)
                    self.assertEqual({route["route_id"] for route in routes.json()}, baseline_ids)

                    changes = client.app.state.event_store.list_changes(after_id=0)
                    self.assertEqual([entry.action for _, _, entry in changes], ["created", "auto_expired"])

                    async def replay():
                        frames = event_frames(client.app.state.event_store, after_id=1)
                        try:
                            return await anext(frames)
                        finally:
                            await frames.aclose()

                    frame = asyncio.run(replay())
                    self.assertIn("id: 2\n", frame)
                    self.assertIn('"action":"auto_expired"', frame)
                    self.assertIn('"status":"expired"', frame)

    def test_published_api_reconciles_due_card_once(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(db_path=Path(directory) / "api.sqlite3", review_token="test")) as client:
                payload = event_payload()
                past = datetime(2026, 9, 22, 8, tzinfo=timezone.utc)
                payload["created_at"] = past.isoformat()
                payload["updated_at"] = past.isoformat()
                payload["window"]["start"] = past.isoformat()
                payload["status"] = "published"
                payload["published_at"] = past.isoformat()
                payload["expires_at"] = (past + timedelta(minutes=1)).isoformat()
                client.app.state.event_store.create_event(payload)
                self.assertEqual(client.get("/api/events/published").json(), [])
                self.assertEqual(client.get("/api/events/published").json(), [])
                changes = client.app.state.event_store.list_changes(after_id=0)
                self.assertEqual([entry.action for _, _, entry in changes], ["created", "auto_expired"])

    def test_audit_cursor_replays_public_changes_with_contract_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "events.sqlite3")
            store.initialize()
            reviews = EventReviewService(store)
            store.create_event(event_payload())
            reviews.approve("evt_replan_b", actor="reviewer", at=AT + timedelta(minutes=1))
            reviews.edit("evt_replan_b", {"summary": "修订待复审"}, actor="reviewer",
                         at=AT + timedelta(minutes=2))
            reviews.approve("evt_replan_b", actor="reviewer", at=AT + timedelta(minutes=3))
            reviews.expire("evt_replan_b", actor="reviewer", at=AT + timedelta(minutes=4))
            changes = store.list_changes(after_id=0)
            self.assertEqual([entry.action for _, _, entry in changes],
                             ["created", "review_approved", "review_edited", "review_approved", "review_expired"])
            self.assertEqual([audit_id for audit_id, _, _ in store.list_changes(after_id=2)], [3, 4, 5])
            latest = store.get_event("evt_replan_b")
            self.assertEqual(latest.status, "expired")
            self.assertEqual(latest.version, 5)
            self.assertEqual(latest.affected_segments[0].from_node, "HUH")
            self.assertEqual(latest.window.start, AT)

            async def first_replay():
                frames = event_frames(store, after_id=4)
                try:
                    return await anext(frames)
                finally:
                    await frames.aclose()

            frame = asyncio.run(first_replay())
            self.assertIn("id: 5\n", frame)
            payload = json.loads(frame.split("data: ", 1)[1])
            self.assertEqual(payload["change"]["action"], "review_expired")
            self.assertEqual(payload["event"]["event_id"], "evt_replan_b")
            self.assertEqual(payload["event"]["version"], 5)
            self.assertEqual(payload["event"]["status"], "expired")
            self.assertEqual(payload["event"]["affected_segments"][0]["from_node"], "HUH")


if __name__ == "__main__":
    unittest.main()
