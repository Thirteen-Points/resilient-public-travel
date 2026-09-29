"""B's request-level no-LLM gate; browser acceptance remains separate."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import create_app, runtime


class NoAiQueryTests(unittest.TestCase):
    def test_disabled_llm_still_returns_real_query_candidates(self):
        self.assertIsNotNone(runtime.engine, runtime.error)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"AI_ENABLED": "false"}):
            with TestClient(create_app(db_path=Path(directory) / "no-ai.sqlite3")) as client:
                query = client.post("/api/routes/query", json={
                    "origin": "TAW", "destination": "ADM",
                    "depart_at": "2026-09-22T08:20:00+08:00",
                    "profile": {"mobility": "wheelchair"},
                })
                self.assertEqual(query.status_code, 200, query.text)
                routes = query.json()
                self.assertTrue(routes)
                self.assertTrue(all(route.get("route_id") and route.get("legs") for route in routes))
                self.assertTrue(all(leg["mode"] != "MINIBUS" for route in routes for leg in route["legs"]))

                explanation = client.post("/api/ai/chat", json={
                    "message": "请解释可行路线", "origin": "TAW", "destination": "ADM",
                    "depart_at": "2026-09-22T08:20:00+08:00",
                    "profile_id": "wheelchair",
                })
                self.assertEqual(explanation.status_code, 200, explanation.text)
                body = explanation.json()
                self.assertTrue(body["fallback"])
                self.assertTrue(body.get("routes"))
                self.assertTrue(body.get("message"))
                self.assertTrue(body.get("tool_calls"))


if __name__ == "__main__":
    unittest.main()
