from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.sim.service import build_diversion_plan
from scripts.precompute_sim import validate_fixture_config


ROOT = Path(__file__).resolve().parents[1]


class FrozenSimulationContractTests(unittest.TestCase):
    """Guard the public fields frozen in docs/plan/03-contracts.md section 3.5."""

    def test_precomputed_sim_result_has_required_contract_fields(self) -> None:
        result = json.loads(
            (ROOT / "data/sim/scn_huh_exc_closed_am_peak.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            {
                "scenario_id",
                "population",
                "time_range",
                "baseline",
                "guided",
                "delta",
                "assumptions",
                "provenance",
            }.issubset(result)
        )
        self.assertTrue(
            {
                "policy",
                "total_delay_person_min",
                "p95_wait_min",
                "overloaded_routes",
                "served_rate",
            }.issubset(result["baseline"])
        )
        self.assertTrue(
            {
                "policy",
                "total_delay_person_min",
                "p95_wait_min",
                "overloaded_routes",
                "served_rate",
                "unstoppable_demand",
                "wheelchair_served_rate",
            }.issubset(result["guided"])
        )
        self.assertTrue(
            {"delay_reduction_pct", "p95_wait_reduction_pct"}.issubset(result["delta"])
        )
        self.assertEqual(result["provenance"], "simulated")
        self.assertTrue(result["assumptions"])

    def test_fixture_capacity_inputs_are_all_explicitly_simulated(self) -> None:
        fixture = json.loads(
            (ROOT / "data/sim/scn_huh_exc_closed_am_peak.input.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(fixture["fixture"])
        self.assertEqual(fixture["provenance"], "simulated")
        self.assertTrue(fixture["route_supply"])
        self.assertTrue(
            all(item["provenance"] == "simulated" for item in fixture["route_supply"])
        )
        validate_fixture_config(fixture)

    def test_fixture_validator_rejects_unverified_real_label(self) -> None:
        fixture = {
            "fixture": True,
            "provenance": "simulated",
            "route_supply": [{"route_id": "r", "provenance": "real-derived"}],
        }
        with self.assertRaises(ValueError):
            validate_fixture_config(fixture)

    def test_diversion_plan_preserves_frozen_field_names(self) -> None:
        result = build_diversion_plan(
            {
                "event_id": "evt_fixture",
                "demand": 20,
                "window_min": 60,
                "routes": [
                    {
                        "route_id": "fixture_route",
                        "headway_s": 600,
                        "capacity_per_hour": 10,
                        "provenance": "simulated",
                    }
                ],
            }
        )
        self.assertTrue(
            {
                "plan_id",
                "event_id",
                "demand",
                "window_min",
                "shares",
                "unstoppable_demand",
                "advice",
                "fairness",
                "provenance",
            }.issubset(result)
        )
        self.assertTrue(
            {
                "route_id",
                "share",
                "users",
                "capacity_per_hour",
                "load_factor",
            }.issubset(result["shares"][0])
        )


if __name__ == "__main__":
    unittest.main()
