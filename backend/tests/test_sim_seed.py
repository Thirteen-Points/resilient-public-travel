from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from scripts.integration.checks import check_sim


ROOT = Path(__file__).resolve().parents[2]
SIM_PATH = ROOT / "contracts/seed/sim.seed.json"
ROUTES_PATH = ROOT / "contracts/seed/routes.seed.json"


class SimulationSeedCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = json.loads(SIM_PATH.read_text(encoding="utf-8"))
        routes = json.loads(ROUTES_PATH.read_text(encoding="utf-8"))
        self.route_ids = {route["route_id"] for route in routes["routes"]}

    def test_placeholder_is_simulated_and_has_contract_scenario_id(self) -> None:
        self.assertEqual(self.sim["provenance"], "simulated")
        self.assertEqual(self.sim["meta"]["provenance"], "simulated")
        self.assertTrue(self.sim["meta"]["placeholder"])
        self.assertIn("SIMULATED PLACEHOLDER", self.sim["meta"]["status"])
        self.assertEqual(self.sim["scenario_id"], self.sim["meta"]["scenario_id"])

    def test_route_references_and_aggregates_are_internally_consistent(self) -> None:
        baseline = self.sim["baseline"]
        guided = self.sim["guided"]
        baseline_rows = baseline["route_load"]
        guided_rows = guided["shares"]
        self.assertTrue(
            {row["route_id"] for row in baseline_rows + guided_rows} <= self.route_ids
        )
        self.assertEqual(sum(row["users"] for row in baseline_rows), self.sim["population"])
        self.assertEqual(
            baseline["overloaded_routes"],
            sum(row["load_factor"] > 1 for row in baseline_rows),
        )
        for row in baseline_rows:
            self.assertEqual(row["overloaded"], row["load_factor"] > 1)
            self.assertTrue(
                math.isclose(
                    row["load_factor"],
                    row["users"] / row["capacity_per_hour"],
                    abs_tol=0.01,
                )
            )
        baseline_served = sum(
            min(row["users"], row["capacity_per_hour"]) for row in baseline_rows
        )
        self.assertTrue(
            math.isclose(
                baseline["served_rate"],
                baseline_served / self.sim["population"],
                abs_tol=1e-9,
            )
        )
        assigned = sum(row["users"] for row in guided_rows)
        self.assertEqual(assigned + guided["unstoppable_demand"], self.sim["population"])
        self.assertTrue(
            math.isclose(
                sum(row["share"] for row in guided_rows),
                assigned / self.sim["population"],
                abs_tol=1e-9,
            )
        )
        for row in guided_rows:
            self.assertTrue(
                math.isclose(
                    row["share"], row["users"] / self.sim["population"], abs_tol=1e-9
                )
            )
            self.assertTrue(
                math.isclose(
                    row["load_factor"],
                    row["users"] / row["capacity_per_hour"],
                    abs_tol=0.01,
                )
            )
        self.assertTrue(
            math.isclose(
                guided["served_rate"], assigned / self.sim["population"], abs_tol=1e-9
            )
        )
        self.assertEqual(
            self.sim["delta"]["served_rate_gain_pp"],
            round(100 * (guided["served_rate"] - baseline["served_rate"]), 1),
        )
        self.assertEqual(
            self.sim["delta"]["overloaded_routes_delta"],
            guided["overloaded_routes"] - baseline["overloaded_routes"],
        )

    def test_formal_result_audit_still_rejects_only_the_placeholder_boundary(self) -> None:
        findings = check_sim(self.sim, self.route_ids)
        self.assertEqual(
            [(finding.code, finding.path) for finding in findings],
            [("PLACEHOLDER", "sim")],
        )


if __name__ == "__main__":
    unittest.main()
