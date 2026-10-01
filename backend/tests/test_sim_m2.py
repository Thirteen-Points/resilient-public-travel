from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from backend.app.sim.adapters import od_route_sets_from_contract
from backend.app.sim.m2 import run_m2_multi_od


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data/sim/m2-route-input.json"


class M2MultiODSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input_doc = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
        cls.route_sets = od_route_sets_from_contract(cls.input_doc, fixture=True)

    def run_small_scenario(self, route_sets=None):
        return run_m2_multi_od(
            scenario_id=self.input_doc["scenario_id"],
            route_sets=tuple(route_sets or self.route_sets),
            population=300,
            seed=self.input_doc["seed"],
            window_min=self.input_doc["window_min"],
            time_range=tuple(self.input_doc["time_range"]),
            assumptions=self.input_doc["assumptions"],
        )

    def test_six_station_input_is_reproducible_and_conserves_demand(self) -> None:
        first = self.run_small_scenario()
        second = self.run_small_scenario()
        self.assertEqual(first, second)
        self.assertEqual(first["od_count"], 30)
        self.assertEqual(first["population"], 300)
        self.assertEqual(first["provenance"], "simulated")
        for policy in ("baseline", "guided"):
            metrics = first[policy]
            self.assertEqual(metrics["assigned_demand"] + metrics["unassigned_demand"], 300)
            self.assertEqual(metrics["served_demand"] + metrics["unmet_demand"], 300)
            for route in metrics["route_load"]:
                self.assertGreaterEqual(route["target_capacity_excess"], 0)
                self.assertGreaterEqual(route["physical_capacity_excess"], 0)

    def test_duplicate_ods_and_mismatched_capacity_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate OD route set"):
            self.run_small_scenario((*self.route_sets, self.route_sets[0]))

        first = self.route_sets[0]
        bad_supplies = (replace(first.supplies[0], route_id="wrong-route-id"), *first.supplies[1:])
        with self.assertRaisesRegex(ValueError, "matching unique route_ids"):
            self.run_small_scenario((replace(first, supplies=bad_supplies), *self.route_sets[1:]))

    def test_same_capacity_bucket_must_have_identical_supply_inputs(self) -> None:
        first = self.route_sets[0]
        shared_route = first.routes[0]
        second = self.route_sets[1]
        shared_supply = replace(first.supplies[0], headway_s=first.supplies[0].headway_s + 1)
        second = replace(
            second,
            routes=(shared_route, *second.routes),
            supplies=(shared_supply, *second.supplies),
        )
        with self.assertRaisesRegex(ValueError, "conflicting supply inputs"):
            self.run_small_scenario((first, second, *self.route_sets[2:]))


if __name__ == "__main__":
    unittest.main()
