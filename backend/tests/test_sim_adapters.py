from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from backend.app.sim.adapters import (
    BEventUpdate,
    BLoadUpdate,
    BWeatherUpdate,
    adapt_b_update,
    apply_b_update,
    routes_from_c_route_output,
)
from backend.app.sim.population import generate_population
from backend.app.sim.replanning import ReplanningMonitor, dispatch_replan
from backend.app.engine import RouteEngine


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CRouteAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output = load_fixture("c_route_output.simulated.json")

    def test_standard_output_fields_are_adapted(self) -> None:
        routes, supplies = routes_from_c_route_output(self.output, fixture=True)
        self.assertEqual([route.route_id for route in routes], ["sim_route_rail", "sim_route_bus"])
        self.assertEqual(routes[0].eta_min, 30)
        self.assertEqual(routes[0].transfers, 0)
        self.assertEqual(routes[0].walk_m, 420)
        self.assertEqual(routes[0].fare_hkd, 12.5)
        self.assertEqual(routes[0].reliability, 0.9)
        self.assertEqual(routes[0].freshness_s, 0)
        self.assertEqual(routes[0].modes, ("MTR",))
        self.assertTrue(routes[0].accessible)
        self.assertTrue(routes[1].accessible)
        self.assertEqual(supplies[0].headway_s, 180)
        self.assertEqual(supplies[0].capacity_per_hour, 3400)
        self.assertEqual(supplies[0].provenance, "simulated")

    def test_live_c_route_query_details_shape_is_accepted(self) -> None:
        engine = RouteEngine.from_seed(
            network_path=ROOT / "backend/app/engine/fixtures/network.synthetic.json",
            events_path=ROOT / "backend/app/engine/fixtures/events.synthetic.json",
        )
        output = engine.query_details("O", "D", "2026-09-22T08:20:00+08:00")
        routes, supplies = routes_from_c_route_output(output, fixture=True)
        self.assertGreaterEqual(len(routes), 8)
        self.assertEqual({route.route_id for route in routes},
                         {supply.route_id for supply in supplies})
        self.assertTrue(all(supply.capacity_per_hour > 0 for supply in supplies))

    def test_missing_route_field_is_rejected(self) -> None:
        required_paths = [
            ("route_id",),
            ("total", "time_s"),
            ("total", "transfers"),
            ("total", "walk_m"),
            ("total", "fare_hkd"),
            ("total", "reliability"),
            ("total", "freshness_s"),
            ("legs", 0, "mode"),
            ("legs", 0, "accessible"),
        ]
        for path in required_paths:
            with self.subTest(path=path):
                payload = deepcopy(self.output)
                target = payload["routes"][0]
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]
                with self.assertRaises(ValueError):
                    routes_from_c_route_output(payload, fixture=True)

    def test_empty_routes_are_rejected(self) -> None:
        payload = deepcopy(self.output)
        payload["routes"] = []
        with self.assertRaisesRegex(ValueError, "non-empty"):
            routes_from_c_route_output(payload, fixture=True)

    def test_missing_capacity_field_is_rejected(self) -> None:
        payload = deepcopy(self.output)
        del payload["route_parameters"]["sim_route_rail"]["capacity_per_hour"]
        with self.assertRaisesRegex(ValueError, "capacity_per_hour"):
            routes_from_c_route_output(payload, fixture=True)

    def test_missing_headway_and_mismatched_route_ids_are_rejected(self) -> None:
        payload = deepcopy(self.output)
        del payload["route_parameters"]["sim_route_rail"]["headway_s"]
        with self.assertRaisesRegex(ValueError, "headway_s"):
            routes_from_c_route_output(payload, fixture=True)
        payload = deepcopy(self.output)
        payload["route_parameters"]["unknown"] = payload["route_parameters"].pop("sim_route_bus")
        with self.assertRaisesRegex(ValueError, "route/supply ids differ"):
            routes_from_c_route_output(payload, fixture=True)

    def test_fixture_provenance_cannot_be_upgraded(self) -> None:
        for mutate in (
            lambda payload: payload["routes"][0].update(provenance="real"),
            lambda payload: payload["routes"][0]["legs"][0].update(provenance="real-derived"),
            lambda payload: payload["route_parameters"]["sim_route_rail"].update(provenance="real"),
        ):
            with self.subTest(mutate=mutate):
                payload = deepcopy(self.output)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, "must remain simulated"):
                    routes_from_c_route_output(payload, fixture=True)


class BUpdateAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture("b_updates.simulated.json")

    def test_all_b_fields_are_adapted(self) -> None:
        event = adapt_b_update(self.fixture["event_updates"][1], fixture=True)
        load = adapt_b_update(self.fixture["load_updates"][0], fixture=True)
        weather = adapt_b_update(self.fixture["weather_updates"][1], fixture=True)
        self.assertIsInstance(event, BEventUpdate)
        self.assertEqual((event.event_id, event.version, event.status, event.confidence),
                         ("sim_evt_001", 2, "published", 0.9))
        self.assertIsInstance(load, BLoadUpdate)
        self.assertEqual((load.route_id, load.load_factor), ("sim_route_rail", 0.96))
        self.assertIsInstance(weather, BWeatherUpdate)
        self.assertEqual(weather.weather_warning_code, "BLACK_RAIN")
        self.assertTrue(all(update.provenance == "simulated" for update in (event, load, weather)))

    def test_event_status_change_dispatches_recalculation(self) -> None:
        monitor = ReplanningMonitor()
        decisions = [
            apply_b_update(monitor, adapt_b_update(payload, fixture=True))
            for payload in self.fixture["event_updates"]
        ]
        self.assertFalse(decisions[0].should_replan)
        self.assertTrue(decisions[1].should_replan)
        calls = []
        execution = dispatch_replan(decisions[1], lambda decision: calls.append(decision.trigger))
        self.assertTrue(execution.recomputed)
        self.assertEqual(calls, ["event_changed"])

    def test_load_and_weather_updates_trigger(self) -> None:
        load_monitor = ReplanningMonitor()
        load_decisions = [
            apply_b_update(load_monitor, adapt_b_update(payload, fixture=True))
            for payload in self.fixture["load_updates"]
        ]
        self.assertFalse(load_decisions[0].should_replan)
        self.assertTrue(load_decisions[1].should_replan)
        weather_monitor = ReplanningMonitor()
        weather_decisions = [
            apply_b_update(weather_monitor, adapt_b_update(payload, fixture=True))
            for payload in self.fixture["weather_updates"]
        ]
        self.assertFalse(weather_decisions[0].should_replan)
        self.assertTrue(weather_decisions[1].should_replan)

    def test_missing_fields_naive_time_and_non_simulated_fixture_are_rejected(self) -> None:
        cases = [
            {"event_id": "e", "version": 1, "status": "published", "observed_at": "2026-09-22T08:00:00+08:00", "provenance": "simulated"},
            {"route_id": "r", "load_factor": 1.0, "observed_at": "2026-09-22T08:00:00", "provenance": "simulated"},
            {"weather_warning_code": "T8", "observed_at": "2026-09-22T08:00:00+08:00", "provenance": "real"},
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                adapt_b_update(payload, fixture=True)

    def test_fixed_seed_remains_reproducible(self) -> None:
        self.assertEqual(generate_population(1000, seed=20260922),
                         generate_population(1000, seed=20260922))
        self.assertNotEqual(generate_population(1000, seed=20260922),
                            generate_population(1000, seed=7))


if __name__ == "__main__":
    unittest.main()
