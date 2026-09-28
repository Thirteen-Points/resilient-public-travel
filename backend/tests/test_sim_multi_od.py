from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from backend.app.sim.adapters import od_route_sets_from_simulated_fixture
from backend.app.sim.multi_od import TARGET_CANDIDATES_PER_OD, run_multi_od_simulation
from scripts.verify_sim_multi_od_m0 import REPORT_PATH, verify


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "backend/tests/fixtures/multi_od_routes.simulated.json"


class MultiODSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_adapts_all_thirty_directed_od_sets_without_padding(self) -> None:
        route_sets = od_route_sets_from_simulated_fixture(self.fixture)
        self.assertEqual(len(route_sets), 30)
        self.assertEqual(len({route_set.od for route_set in route_sets}), 30)
        route_ids = [
            route.route_id for route_set in route_sets for route in route_set.routes
        ]
        self.assertEqual(len(route_ids), len(set(route_ids)))
        self.assertTrue(
            all(
                len(route_set.routes) < TARGET_CANDIDATES_PER_OD
                for route_set in route_sets
            )
        )
        self.assertTrue(all(route_set.provenance == "simulated" for route_set in route_sets))
        self.assertTrue(any(not route_set.routes for route_set in route_sets))

    def test_multi_od_run_is_reproducible_scoped_and_conservative(self) -> None:
        route_sets = od_route_sets_from_simulated_fixture(self.fixture)
        kwargs = {
            "scenario_id": "scn_corridor_30_od_m0",
            "route_sets": route_sets,
            "population": 300,
            "seed": 20260922,
            "window_min": 60,
        }
        first = run_multi_od_simulation(**kwargs)
        second = run_multi_od_simulation(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["assigned_demand"] + first["unmet_demand"], 300)
        self.assertGreater(first["unmet_demand"], 0)
        self.assertTrue(first["invariants"]["capacity_conserved"])
        for key, value in first["invariants"].items():
            if key != "capacity_conserved":
                self.assertEqual(value, 0, key)
        self.assertTrue(
            all(row["assigned_demand"] + row["unmet_demand"] == row["demand"]
                for row in first["od_results"])
        )
        inaccessible_only = next(
            row
            for row in first["od_results"]
            if (row["origin"], row["destination"]) == ("MKK", "EXC")
        )
        self.assertGreater(inaccessible_only["wheelchair_unmet_demand"], 0)
        empty_od = next(
            row
            for row in first["od_results"]
            if (row["origin"], row["destination"]) == ("ADM", "EXC")
        )
        self.assertEqual(empty_od["candidate_count"], 0)
        self.assertEqual(empty_od["unmet_demand"], empty_od["demand"])

    def test_fixture_cannot_duplicate_candidates_or_upgrade_provenance(self) -> None:
        duplicate = deepcopy(self.fixture)
        duplicate["od_route_sets"][0]["candidate_profiles"].append(
            duplicate["od_route_sets"][0]["candidate_profiles"][0]
        )
        with self.assertRaisesRegex(ValueError, "must not duplicate candidates"):
            od_route_sets_from_simulated_fixture(duplicate)

        upgraded = deepcopy(self.fixture)
        upgraded["od_route_sets"][0]["provenance"] = "real-derived"
        with self.assertRaisesRegex(ValueError, "must remain simulated"):
            od_route_sets_from_simulated_fixture(upgraded)

    def test_checked_in_multi_od_report_matches_verifier(self) -> None:
        self.assertEqual(json.loads(REPORT_PATH.read_text(encoding="utf-8")), verify(ROOT))


if __name__ == "__main__":
    unittest.main()
