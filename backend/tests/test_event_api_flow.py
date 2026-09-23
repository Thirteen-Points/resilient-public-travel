from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.api.stream import event_frames
from backend.app.main import create_app


ROOT = Path(__file__).resolve().parents[2]
SEED = json.loads((ROOT / "contracts/seed/event.seed.json").read_text(encoding="utf-8"))
TEXT = "【模拟】东铁线红磡至会展信号故障，暂停服务。"


class EventApiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(
            db_path=Path(self.directory.name) / "events.sqlite3",
            review_token="local-review-secret",
        )
        context = TestClient(self.app)
        self.client = context.__enter__()
        self.addCleanup(lambda: context.__exit__(None, None, None))
        self.headers = {"X-Review-Token": "local-review-secret"}

    def report(self, author: str) -> str:
        response = self.client.post("/api/signals", json={"raw_text": TEXT, "author_hint": author})
        self.assertEqual(response.status_code, 202)
        return response.json()["signal_id"]

    def initial_card(self, signal_id: str) -> dict:
        signal = self.app.state.signal_store.get_signal(signal_id)
        payload = dict(SEED["events"][0])
        created = signal.received_at
        payload.update(
            event_id="evt-api-flow-001",
            version=1,
            created_at=created.isoformat(),
            updated_at=created.isoformat(),
            window={"start": created.isoformat(), "end": None, "end_confidence": "unknown"},
            signals=[signal_id],
            audit_log=[],
            confidence=0.90,  # The API must replace this untrusted value.
        )
        return payload

    def test_signal_merge_review_publish_and_sse_change(self) -> None:
        first_id = self.report("passenger-one")
        first_draft = self.client.post("/api/events/ingest", json={"signal_id": first_id}, headers=self.headers)
        self.assertEqual(first_draft.status_code, 200)
        self.assertEqual(first_draft.json()["state"], "needs_review")
        self.assertIsNone(first_draft.json()["event"])

        unauthenticated = self.client.post("/api/events", json=self.initial_card(first_id))
        self.assertEqual(unauthenticated.status_code, 401)
        created = self.client.post("/api/events", json=self.initial_card(first_id), headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["confidence"], 0.20)

        for expected, author in ((0.35, "passenger-two"), (0.55, "passenger-three")):
            signal_id = self.report(author)
            response = self.client.post("/api/events/ingest", json={"signal_id": signal_id}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["state"], "merged")
            self.assertEqual(response.json()["event"]["confidence"], expected)

        self.assertEqual(self.client.get("/api/events").status_code, 401)
        self.assertEqual(self.client.post("/api/events/ingest", json={"signal_id": first_id}).status_code, 401)
        self.assertEqual(len(self.client.get("/api/events", headers=self.headers).json()), 1)
        self.assertEqual(self.client.get("/api/events/published").json(), [])
        forbidden = self.client.post(
            "/api/events/evt-api-flow-001/review",
            json={"action": "approve", "actor": "admin"},
        )
        self.assertEqual(forbidden.status_code, 401)
        approved = self.client.post(
            "/api/events/evt-api-flow-001/review",
            json={"action": "approve", "actor": "admin"}, headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "published")
        self.assertEqual(approved.json()["confidence"], 0.60)
        self.assertEqual(len(self.client.get("/api/events/published").json()), 1)

        changes = self.app.state.event_store.list_changes()
        self.assertEqual(len(changes), 4)
        self.assertEqual([entry["confidence_after"] for entry in approved.json()["audit_log"]],
                         [0.2, 0.35, 0.55, 0.6])

        async def read_frame() -> str:
            frames = event_frames(self.app.state.event_store, after_id=changes[-2][0])
            try:
                return await asyncio.wait_for(anext(frames), timeout=1)
            finally:
                await frames.aclose()

        frame = asyncio.run(read_frame())
        self.assertIn(f"id: {changes[-1][0]}\n", frame)
        self.assertIn('"status":"published"', frame)
        self.assertIn('"confidence_after":0.6', frame)

        async def wait_for_live_update() -> tuple[str, float]:
            frames = event_frames(self.app.state.event_store, after_id=changes[-1][0])
            started = time.monotonic()
            pending = asyncio.create_task(anext(frames))
            try:
                await asyncio.sleep(0.02)
                edited = self.client.post(
                    "/api/events/evt-api-flow-001/review",
                    json={"action": "edit", "actor": "admin", "edits": {"title": "复审中"}},
                    headers=self.headers,
                )
                self.assertEqual(edited.status_code, 200, edited.text)
                live_frame = await asyncio.wait_for(pending, timeout=1)
                return live_frame, time.monotonic() - started
            finally:
                if not pending.done():
                    pending.cancel()
                await frames.aclose()

        live_frame, elapsed = asyncio.run(wait_for_live_update())
        self.assertIn('"status":"updated"', live_frame)
        self.assertLess(elapsed, 1.0)

    def test_review_rejects_illegal_transitions_and_low_confidence(self) -> None:
        signal_id = self.report("first")
        created = self.client.post("/api/events", json=self.initial_card(signal_id), headers=self.headers)
        self.assertEqual(created.status_code, 201)
        path = "/api/events/evt-api-flow-001/review"
        low = self.client.post(path, json={"action": "approve", "actor": "admin"}, headers=self.headers)
        self.assertEqual(low.status_code, 409)
        self.assertEqual(self.app.state.event_store.get_event("evt-api-flow-001").version, 1)
        rejected = self.client.post(path, json={"action": "reject", "actor": "admin"}, headers=self.headers)
        self.assertEqual(rejected.status_code, 200)
        illegal = self.client.post(path, json={"action": "approve", "actor": "admin"}, headers=self.headers)
        self.assertEqual(illegal.status_code, 409)
        self.assertEqual(self.app.state.event_store.get_event("evt-api-flow-001").version, 2)

    def test_edit_whitelist_and_unconfigured_token(self) -> None:
        signal_id = self.report("first")
        self.client.post("/api/events", json=self.initial_card(signal_id), headers=self.headers)
        path = "/api/events/evt-api-flow-001/review"
        forbidden_edit = self.client.post(
            path,
            json={"action": "edit", "actor": "admin", "edits": {"confidence": 0.99}},
            headers=self.headers,
        )
        self.assertEqual(forbidden_edit.status_code, 422)
        allowed = self.client.post(
            path,
            json={"action": "edit", "actor": "admin", "edits": {"title": "人工核实中"}},
            headers=self.headers,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["title"], "人工核实中")
        self.app.state.review_token = None
        closed = self.client.post(path, json={"action": "reject", "actor": "admin"}, headers=self.headers)
        self.assertEqual(closed.status_code, 503)


if __name__ == "__main__":
    unittest.main()
