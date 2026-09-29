from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.engine.score import CRITERIA as ENGINE_CRITERIA
from backend.app.engine.service import RouteEngine
from backend.app.main import create_app
from backend.app.services.persona import CRITERIA, PERSONAS, UserProfile, load_personas


class PersonaTests(unittest.TestCase):
    def test_exactly_five_strict_contract_profiles(self) -> None:
        profiles = load_personas()
        self.assertEqual(len(profiles), 5)
        self.assertEqual({profile.persona for profile in profiles}, PERSONAS)
        self.assertEqual(len({profile.user_id for profile in profiles}), 5)
        self.assertEqual(CRITERIA, set(ENGINE_CRITERIA))
        for profile in profiles:
            with self.subTest(persona=profile.persona):
                self.assertEqual(set(profile.weights), CRITERIA)
                self.assertAlmostEqual(sum(profile.weights.values()), 1.0)
                self.assertIn("模拟", profile.note)
                self.assertEqual(profile, UserProfile.model_validate(profile.model_dump()))

    def test_wheelchair_hard_constraints_cannot_be_relaxed(self) -> None:
        wheelchair = next(p for p in load_personas() if p.persona == "wheelchair")
        self.assertEqual(wheelchair.mobility, "wheelchair")
        self.assertLessEqual(wheelchair.max_walk_m, 400)
        self.assertTrue({"no_stairs", "no_minibus", "no_non_lowfloor_bus"}.issubset(wheelchair.hard_flags))
        with self.assertRaises(ValidationError):
            UserProfile.model_validate({**wheelchair.model_dump(), "hard_flags": []})

    def test_invalid_weights_and_extra_fields_are_rejected(self) -> None:
        profile = load_personas()[0].model_dump()
        for weights in (
            {**profile["weights"], "time": -0.1},
            {**profile["weights"], "time": float("nan")},
            {**profile["weights"], "time": 0.5},
            {key: value for key, value in profile["weights"].items() if key != "time"},
        ):
            with self.subTest(weights=weights), self.assertRaises(ValidationError):
                UserProfile.model_validate({**profile, "weights": weights})
        with self.assertRaises(ValidationError):
            UserProfile.model_validate({**profile, "unknown_field": True})

    def test_loading_returns_fresh_models_not_mutable_shared_presets(self) -> None:
        first = load_personas()
        first[0].weights["time"] = 0.0
        second = load_personas()
        self.assertEqual(second[0].weights["time"], 0.40)

    def test_get_personas_returns_contract_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(db_path=Path(directory) / "test.sqlite3")) as client:
                response = client.get("/api/personas")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)
        self.assertEqual({item["persona"] for item in response.json()}, PERSONAS)
        self.assertEqual([UserProfile.model_validate(item).user_id for item in response.json()],
                         [profile.user_id for profile in load_personas()])

    def test_existing_seed_route_engine_exposes_top1_acceptance_gap(self) -> None:
        engine = RouteEngine.from_seed()
        top_ids = {}
        for profile in load_personas():
            routes = engine.query("TAW", "ADM", "2026-09-22T08:20:00+08:00", profile.model_dump())
            top_ids[profile.persona] = routes[0]["route_id"] if routes else None
            if profile.persona == "wheelchair":
                for route in routes:
                    self.assertTrue(all(leg["accessible"] is True and leg["mode"] != "MINIBUS"
                                        for leg in route["legs"]))
        # This records the present C seed/engine limitation; do not manufacture
        # five distinct routes or weaken accessibility limits to satisfy the DoD.
        self.assertLess(len(set(top_ids.values())), 5, top_ids)
        self.assertIsNone(top_ids["elderly"])


if __name__ == "__main__":
    unittest.main()
