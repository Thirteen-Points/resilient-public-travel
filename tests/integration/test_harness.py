"""Regression tests of the gate itself. Synthetic fixtures are not product evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from integration.checks import (Report, check_events, check_network, check_route,
                                check_sim, closed_crossings, load_json)
from integration.runner import (adapter_load, fallback_suite, offline_suite, percentile95,
                                performance_suite, runtime_suite, static_suite)


def network():
    return {"meta": {"catchment_m": 800},
            "nodes": [{"id": node, "kind": "mtr_station", "lat": 22, "lng": 114, "provenance": "simulated"}
                      for node in ("TAW", "HUH", "EXC", "ADM")],
            "lines": [{"id": "ERL", "mode": "MTR", "stops": ["TAW", "HUH", "EXC", "ADM"],
                       "seg_time_s": [100, 100, 100], "headway_s": {"weekday_peak": 120, "sunday_ph": None},
                       "capacity_per_vehicle": 100, "provenance": "simulated"}], "walk_links": []}


def route():
    return {"route_id": "synthetic", "label": "Harness fixture", "provenance": "simulated",
            "legs": [{"mode": "MTR", "line": "ERL", "from": "TAW", "to": "ADM", "in_vehicle_s": 300,
                      "walk_m": 100, "accessible": True, "provenance": "simulated"}],
            "total": {"time_s": 400, "time_range_s": [300, 500], "transfers": 0, "walk_m": 100,
                      "fare_hkd": 10, "freshness_s": 0, "reliability": 0.9},
            "score": 0.5, "score_breakdown": [
                {"criterion": k, "normalized": 0.5, "weight": w, "contribution": w * 0.5}
                for k, w in (("time", 0.5), ("walk", 0.3), ("reliability", 0.2))],
            "warnings": [], "notes": [], "explain": "Synthetic explanation", "evidence": [{"source": "synthetic"}]}


def simulation():
    return {"scenario_id": "synthetic", "population": 10000, "assumptions": ["synthetic harness only"],
            "provenance": "simulated", "baseline": {"total_delay_person_min": 100, "p95_wait_min": 20,
            "overloaded_routes": 1, "served_rate": 0.8}, "guided": {"total_delay_person_min": 80,
            "p95_wait_min": 10, "overloaded_routes": 0, "served_rate": 0.9, "unstoppable_demand": 1000},
            "delta": {"delay_reduction_pct": 20, "p95_wait_reduction_pct": 50}}


def codes(findings):
    return {f.code for f in findings}


class BoundaryTests(unittest.TestCase):
    def test_valid_synthetic_objects(self):
        self.assertEqual(check_network(network()), [])
        self.assertEqual(check_route(route(), network(), "TAW", "ADM", True), [])
        self.assertEqual(check_sim(simulation()), [])

    def test_unknown_stop_and_count(self):
        n = network()
        n["lines"][0]["stops"][-1] = "MISSING"
        n["meta"]["counts"] = {"lines": 99}
        self.assertTrue({"NODE_REF", "COUNT"} <= codes(check_network(n)))

    def test_unverified_real(self):
        n = network()
        n["lines"][0].update(provenance="real", capacity_note="待核实")
        self.assertIn("UNVERIFIED_REAL", codes(check_network(n)))

    def test_finite_numbers_and_calendar(self):
        n = network()
        n["lines"][0]["headway_s"]["weekday_peak"] = 0
        n["nodes"][0]["lat"] = float("nan")
        self.assertTrue({"HEADWAY", "NUMBER"} <= codes(check_network(n)))

    def test_contract_drift_is_not_silently_aliased(self):
        r = route()
        r["legs"][0]["travel_s"] = r["legs"][0].pop("in_vehicle_s")
        self.assertIn("REQUIRED", codes(check_route(r, network())))

    def test_wheelchair_all_results_not_only_top_one(self):
        for change in ({"mode": "MINIBUS"}, {"accessible": "partial"}, {"stairs": True}):
            with self.subTest(change=change):
                r = route()
                r["legs"][0].update(change)
                self.assertIn("WHEELCHAIR_LEG", codes(check_route(r, network(), wheelchair=True)))
        r = route()
        r["total"]["walk_m"] = 420
        self.assertIn("WHEELCHAIR_WALK", codes(check_route(r, network(), wheelchair=True)))

    def test_compressed_leg_closure_both_directions_and_status(self):
        event = {"line": "ERL", "status": "published", "direction": "both", "affected_segments": [
            {"from_node": "HUH", "to_node": "EXC", "impact": "closed"}]}
        r = route()
        self.assertIn("CLOSED_EDGE", codes(closed_crossings(r, network(), [event])))
        r["legs"][0].update({"from": "ADM", "to": "TAW"})
        self.assertIn("CLOSED_EDGE", codes(closed_crossings(r, network(), [event])))
        for status in ("draft", "pending_review", "rejected", "expired"):
            event["status"] = status
            self.assertEqual(closed_crossings(r, network(), [event]), [])

    def test_disconnected_route_and_wrong_destination(self):
        r = route()
        r["legs"].append(dict(r["legs"][0], **{"from": "EXC", "to": "HUH"}))
        self.assertTrue({"CONTINUITY", "DESTINATION"} <= codes(check_route(r, network(), "TAW", "ADM")))

    def test_tampered_score(self):
        r = route()
        r["score"] = 0.9
        r["score_breakdown"][0]["contribution"] = 0.4
        self.assertTrue({"SCORE_TERM", "SCORE_SUM"} <= codes(check_route(r, network())))

    def test_missing_signal_and_unreviewed_publication(self):
        event = {"event_id": "e", "version": 1, "status": "published", "confidence": 0.9,
                 "affected_segments": [], "audit_log": [], "signals": ["missing"], "provenance": "simulated"}
        self.assertTrue({"SIGNAL_REF", "REVIEW", "AUDIT"} <= codes(check_events({"events": [event]}, network())))

    def test_placeholder_delta_and_overload_are_rejected(self):
        s = simulation()
        s["meta"] = {"placeholder": True}
        s["delta"]["delay_reduction_pct"] = 99
        s["baseline"]["route_load"] = [{"route_id": "r", "load_factor": 0.5}]
        self.assertTrue({"PLACEHOLDER", "DELTA", "OVERLOAD_COUNT"} <= codes(check_sim(s)))

    def test_no_benefit_can_be_reported_honestly(self):
        s = simulation()
        s["guided"]["total_delay_person_min"] = 110
        s["delta"]["delay_reduction_pct"] = -10
        self.assertEqual(check_sim(s), [])  # R6: do not force model numbers to improve.

    def test_json_rejects_nan(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text('{"score": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_json(path)


class RunnerTests(unittest.TestCase):
    def test_cli_missing_inputs_exit_two(self):
        root = Path(__file__).resolve().parents[2]
        for script in ("runtime", "performance", "fallback", "offline"):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, "-m", "scripts.integration", "--suite", script],
                                        capture_output=True, text=True, cwd=root, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("PENDING", result.stdout)

    def test_nearest_rank_p95(self):
        self.assertEqual(percentile95(list(range(1, 21))), 19)
        with self.assertRaises(ValueError):
            percentile95([])

    def test_missing_modules_never_pass(self):
        report = Report("synthetic")
        self.assertIsNone(adapter_load(report, None))
        self.assertEqual(report.finish(), 2)
        self.assertIsNone(adapter_load(report, "nonexistent_module:factory"))
        self.assertEqual(report.finish(), 1)

    def test_report_error_is_failure_not_skip(self):
        report = Report("synthetic")
        report.run("exception", lambda: 1 / 0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            self.assertEqual(report.finish(path), 1)
            self.assertEqual(load_json(path)["checks"][0]["status"], "FAIL")

    def test_missing_seed_is_failure(self):
        report = Report("synthetic")
        with tempfile.TemporaryDirectory() as d:
            static_suite(report, Path(d))
        self.assertTrue(all(c["status"] == "FAIL" for c in report.checks))

    def test_offline_corruption_and_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset = root / "app.js"
            asset.write_text("synthetic", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"files": [
                {"path": "app.js", "role": "frontend", "sha256": "bad"},
                {"path": "../escape", "role": "tiles", "sha256": "bad"}]}), encoding="utf-8")
            report = Report("synthetic")
            offline_suite(report, root, manifest)
            found = {f["code"] for f in report.checks[0]["detail"]}
            self.assertTrue({"BUNDLE_HASH", "BUNDLE_PATH", "BUNDLE_ROLE"} <= found)
            self.assertEqual(report.checks[1]["status"], "PENDING")


class SyntheticAdapter:
    """Only tests runner wiring. Never expose this as a product acceptance adapter."""
    def reset(self, llm_enabled):
        self.active = False
        self.fault = None
        self.clears = 0

    def network(self):
        n = network()
        n["nodes"].extend(dict(n["nodes"][0], id=node) for node in ("KOT", "MKK"))
        n["lines"].append(dict(n["lines"][0], id="TML"))
        return n

    def query(self, origin, destination, persona):
        r = route()
        r["route_id"] = persona
        r["legs"][0].update({"from": origin, "to": destination, "line": "TML" if self.active else "ERL"})
        return [r]

    def snapshot(self):
        return {"snapshot_id": "closed" if self.active else "normal", "affected_edges": ["HUH-EXC"] if self.active else []}

    def stage_event(self, status):
        return {"event_id": "e", "status": status}

    def review(self, event_id, action):
        self.active = action == "approve"
        return {"event_id": event_id, "status": "published" if self.active else "expired", "line": "ERL",
                "direction": "both", "affected_segments": [{"from_node": "HUH", "to_node": "EXC", "impact": "closed"}]}

    def simulate(self, seed, population, routes):
        return simulation()

    def cached_simulation(self):
        return simulation()

    def clear_route_cache(self):
        self.clears += 1

    def set_fault(self, fault):
        self.fault = fault

    def full_query(self, origin, destination, persona):
        return {"routes": self.query(origin, destination, persona), "meta": {
            "generated_at": "synthetic", "sources": ["synthetic"], "disclaimer": "Harness only"},
            "fault_observed": self.fault, "fallback_used": self.fault is not None, "stale": self.fault == "upstream_unavailable"}


class WiringTests(unittest.TestCase):
    def test_lifecycle_runs_and_ui_remains_pending(self):
        report = Report("synthetic-wiring")
        runtime_suite(report, SyntheticAdapter())
        self.assertEqual([c["status"] for c in report.checks[:2]], ["PASS", "PASS"])
        self.assertTrue(all(c["status"] == "PENDING" for c in report.checks[2:]))

    def test_runtime_catches_cross_module_closure_leak(self):
        class Broken(SyntheticAdapter):
            def query(self, *args):
                routes = super().query(*args)
                routes[0]["legs"][0]["line"] = "ERL"
                return routes
        report = Report("synthetic-wiring")
        runtime_suite(report, Broken())
        self.assertIn("CLOSED_EDGE", {f["code"] for f in report.checks[0]["detail"]})

    def test_fallback_requires_observed_injection(self):
        class Broken(SyntheticAdapter):
            def set_fault(self, fault):
                pass
        report = Report("synthetic-wiring")
        fallback_suite(report, Broken())
        self.assertTrue(all(c["status"] == "FAIL" for c in report.checks[:4]))
        report = Report("synthetic-wiring")
        fallback_suite(report, SyntheticAdapter())
        self.assertTrue(all(c["status"] == "PASS" for c in report.checks[:4]))

    def test_performance_rejects_fast_invalid_response(self):
        class Broken(SyntheticAdapter):
            def query(self, *args):
                return []
        report = Report("synthetic-wiring")
        performance_suite(report, Broken(), 20)
        self.assertEqual(report.checks[0]["status"], "FAIL")
        with self.assertRaises(ValueError):
            performance_suite(report, SyntheticAdapter(), 1)


if __name__ == "__main__":
    unittest.main()
