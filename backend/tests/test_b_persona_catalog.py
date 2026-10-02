"""B-owned profile catalog and optional parser wiring checks."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import build_preference_client, create_app
from backend.app.services.persona import load_personas, load_presets


class FakeClient:
    def __init__(self, response):
        self.response = response

    def generate_json(self, **_kwargs):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class PersonaCatalogTests(unittest.TestCase):
    def test_three_presets_match_current_engine_weights(self):
        from backend.app.engine.score import CRITERIA, PRESETS

        presets = load_presets()
        self.assertEqual(set(presets), set(PRESETS))
        for name, weights in presets.items():
            total = sum(PRESETS[name])
            for criterion, raw in zip(CRITERIA, PRESETS[name]):
                self.assertAlmostEqual(weights[criterion], raw / total)

    def test_five_personas_have_valid_distinct_defaults_and_wheelchair_limits(self):
        profiles = load_personas()
        self.assertEqual([profile.persona for profile in profiles],
                         ["commuter", "student", "tourist", "elderly", "wheelchair"])
        self.assertEqual(len({tuple(profile.weights.values()) for profile in profiles}), 5)
        self.assertEqual(profiles[-1].max_walk_m, 400)
        self.assertEqual(set(profiles[-1].hard_flags),
                         {"no_stairs", "no_minibus", "no_non_lowfloor_bus"})

    def test_catalog_is_public_and_model_is_off_by_default(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "AI_ENABLED": "true", "PERSONA_PARSE_AI_ENABLED": "false", "DEEPSEEK_API_KEY": "test-only"
        }):
            self.assertIsNone(build_preference_client())
            with TestClient(create_app(db_path=Path(directory) / "catalog.sqlite3", review_token="test")) as client:
                response = client.get("/api/personas")
                presets = client.get("/api/personas/presets")
                parsed = client.post("/api/persona/parse", json={"free_text": "腿脚不便、别太贵"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)
        self.assertEqual(presets.status_code, 200)
        self.assertEqual(len(presets.json()), 3)
        self.assertEqual(parsed.json()["method"], "rule_fallback")

    def test_explicit_model_switch_selects_configured_provider_without_calling_it(self):
        with patch.dict(os.environ, {
            "AI_ENABLED": "true", "PERSONA_PARSE_AI_ENABLED": "true", "DEEPSEEK_API_KEY": "test-only",
            "QWEN_API_KEY": "", "GLM_API_KEY": "",
        }):
            configured = build_preference_client()
        self.assertIsNotNone(configured)
        self.assertEqual(configured.model, "deepseek-chat")

    def test_shared_app_uses_model_and_preserves_explicit_restrictions(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(db_path=Path(directory) / "model.sqlite3",
                                       preference_client=FakeClient({"mobility": "standard", "hard_flags": []}))) as client:
                response = client.post("/api/persona/parse", json={"free_text": "轮椅，别太贵"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["method"], "llm")
        self.assertEqual(response.json()["patch"]["mobility"], "wheelchair")
        self.assertEqual(response.json()["patch"]["max_walk_m"], 400)
        self.assertIn("no_minibus", response.json()["patch"]["hard_flags"])

    def test_shared_app_falls_back_when_model_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(db_path=Path(directory) / "failure.sqlite3",
                                       preference_client=FakeClient(TimeoutError()))) as client:
                response = client.post("/api/persona/parse", json={"free_text": "腿脚不便、别太贵"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["method"], "rule_fallback")
        self.assertEqual(response.json()["patch"]["max_walk_m"], 400)


if __name__ == "__main__":
    unittest.main()
