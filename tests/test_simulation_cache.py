from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from backend.app.sim.adapters import routes_from_contract
from backend.app.sim.cache import PrecomputedResultStore, write_precomputed
from backend.app.sim.run import run_simulation


ROOT = Path(__file__).resolve().parents[1]


def scenario_inputs():
    config = json.loads((ROOT / "data/sim/scn_huh_exc_closed_am_peak.input.json").read_text(encoding="utf-8"))
    routes_payload = json.loads((ROOT / config["route_source"]).read_text(encoding="utf-8"))
    routes, supplies = routes_from_contract(routes_payload, config["route_supply"])
    return config, routes, supplies


class SimulationAndCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config, cls.routes, cls.supplies = scenario_inputs()

    def run_result(self) -> dict:
        return run_simulation(
            scenario_id=self.config["scenario_id"],
            routes=self.routes,
            supplies=self.supplies,
            population=self.config["population"],
            seed=self.config["seed"],
            window_min=self.config["window_min"],
            time_range=tuple(self.config["time_range"]),
            assumptions=self.config["assumptions"],
        )

    def test_simulation_is_reproducible_and_accounting_is_honest(self) -> None:
        first = self.run_result()
        second = self.run_result()
        self.assertEqual(first, second)
        assigned = sum(item["users"] for item in first["guided"]["shares"])
        self.assertEqual(assigned + first["guided"]["unstoppable_demand"], 10_000)
        self.assertTrue(first["assumptions"])
        self.assertEqual(first["provenance"], "simulated")
        self.assertGreater(first["fairness"]["protected_users"], 0)
        self.assertGreaterEqual(first["guided"]["wheelchair_served_rate"], first["baseline"]["wheelchair_served_rate"])

    def test_checked_in_result_is_generated_by_the_model(self) -> None:
        expected = self.run_result()
        actual = json.loads((ROOT / "data/sim/scn_huh_exc_closed_am_peak.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_cached_read_is_under_300_ms(self) -> None:
        result = self.run_result()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_precomputed(result, output)
            store = PrecomputedResultStore(output)
            started = time.perf_counter()
            store.read(result["scenario_id"])
            cold_elapsed_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            store.read(result["scenario_id"])
            warm_elapsed_ms = (time.perf_counter() - started) * 1000
            self.assertLess(cold_elapsed_ms, 300)
            self.assertLess(warm_elapsed_ms, 300)

    def test_cache_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = PrecomputedResultStore(Path(directory))
            with self.assertRaises(ValueError):
                store.read("../secret")


if __name__ == "__main__":
    unittest.main()
