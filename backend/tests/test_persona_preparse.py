"""B's standalone parser and router checks before shared-app wiring."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.persona import router
from backend.app.main import create_app
from backend.app.services.persona import parse_preference


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.prompt = None

    def generate_json(self, **kwargs):
        self.prompt = kwargs["user_prompt"]
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class PersonaPreparseTests(unittest.TestCase):
    def test_rule_example_is_safe_and_price_weighted(self):
        result = parse_preference("腿脚不便、别太贵")
        self.assertEqual(result.patch.mobility, "reduced")
        self.assertIn("no_stairs", result.patch.hard_flags)
        self.assertEqual(result.patch.max_walk_m, 400)
        self.assertGreater(result.patch.weights["price"], result.patch.weights["time"])

    def test_invalid_model_output_falls_back_without_relaxing_wheelchair(self):
        client = FakeClient({"mobility": "standard", "hard_flags": ["invented"]})
        result = parse_preference("轮椅，别太贵", client=client)
        self.assertEqual(result.method, "rule_fallback")
        self.assertEqual(result.patch.mobility, "wheelchair")
        self.assertIn("no_minibus", result.patch.hard_flags)

    def test_timeout_and_unrelated_text_preserve_existing_limits(self):
        result = parse_preference("看看路线", client=FakeClient(TimeoutError()),
                                  current_profile={"mobility": "wheelchair", "max_walk_m": 250,
                                                   "hard_flags": ["no_stairs"]})
        self.assertEqual(result.patch.max_walk_m, 250)
        self.assertEqual(result.patch.mobility, "wheelchair")
        self.assertIn("no_non_lowfloor_bus", result.patch.hard_flags)

    def test_model_input_redacts_contact_details(self):
        client = FakeClient({"hard_flags": []})
        parse_preference("别太贵，联系 me@example.com，电话 12345678901", client=client)
        self.assertNotIn("me@example.com", client.prompt)
        self.assertNotIn("12345678901", client.prompt)

    def test_standalone_router_exposes_documented_path(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post("/api/persona/parse", json={"free_text": "腿脚不便、别太贵"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("no_stairs", response.json()["patch"]["hard_flags"])

    def test_shared_app_exposes_persona_parse_with_rule_fallback(self):
        with TemporaryDirectory() as temp_dir:
            app = create_app(db_path=Path(temp_dir) / "test.db")
            with TestClient(app) as client:
                response = client.post("/api/persona/parse", json={"free_text": "腿脚不便、别太贵"})
                invalid = client.post("/api/persona/parse", json={"free_text": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["method"], "rule_fallback")
        self.assertEqual(response.json()["patch"]["mobility"], "reduced")
        self.assertIn("no_stairs", response.json()["patch"]["hard_flags"])
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
