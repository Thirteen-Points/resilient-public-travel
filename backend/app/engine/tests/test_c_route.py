"""Run with: python -m unittest discover -s backend/app/engine/tests -v"""
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
import subprocess
import sys
from datetime import timedelta

from backend.app.graph import SnapshotStore, build_graph, next_departure
from backend.app.graph.build import timestamp
from backend.app.engine import RouteEngine
from backend.app.engine.load_provider import FixtureLoadProvider


def make_engine(store, **kwargs):
    scenario = json.loads((ROOT / 'backend/app/engine/fixtures/seed_policy.json').read_text(encoding='utf-8'))['load']
    return RouteEngine(store, load_provider=FixtureLoadProvider(scenario), **kwargs)

from backend.app.engine.cache import QueryCache
from backend.app.engine.candidates import intermediate_nodes, jaccard, search_paths, select_diverse, transfer_nodes
from backend.app.engine.constraints import normalize_profile
from backend.app.engine.eco import estimates
from backend.app.engine.score import score_routes
from backend.app.engine.walk import walking_matrix, walking_seconds

ROOT = Path(__file__).resolve().parents[4]
AT = "2026-09-22T08:20:00+08:00"


def network(lines=None, walk_links=None):
    return {"meta": {"built_at": "2026-09-22T08:00:00+08:00", "provenance": "simulated"},
            "nodes": [{"id": n, "lat": 22.3 + i * .001, "lng": 114.1, "accessible": True, "provenance": "simulated"}
                      for i, n in enumerate("ABCD")],
            "lines": lines or [line()], "walk_links": [{"provenance": "simulated", **link} for link in (walk_links or [])]}


def line(id="L", mode="MTR", stops=None, **extra):
    stops = stops or ["A", "B", "C"]
    return {"id": id, "mode": mode, "stops": stops, "seg_time_s": [60] * (len(stops) - 1),
            "headway_s": 180, "capacity_per_vehicle": 100, "accessible": True,
            "bidirectional": True, "fare_hkd": 5, "provenance": "simulated", **extra}


def event(**extra):
    return {"event_id": "e1", "version": 1, "status": "published", "line": "L", "direction": "both",
            "window": {"start": "2026-09-22T08:00:00+08:00", "end": None}, "provenance": "simulated",
            "affected_segments": [{"from_node": "A", "to_node": "B", "impact": "closed", "capacity_factor": 0}],
            **extra}


class GraphTests(unittest.TestCase):
    def test_headway_and_offsets_only_wait_once(self):
        self.assertEqual(next_departure(181, 180), 360)
        self.assertEqual(next_departure(180, 180), 180)
        self.assertEqual(next_departure(181, 180, 60), 240)
        engine = make_engine(SnapshotStore(build_graph(network())))
        r = engine.query("A", "C", "2026-09-22T08:00:01+08:00")[0]
        self.assertEqual(len(r["legs"]), 1)
        self.assertEqual(r["total"]["time_s"], 299)
        self.assertEqual(r["legs"][0]["in_vehicle_s"], 120)
        self.assertEqual(r["total"]["transfers"], 0)
        with self.assertRaises(ValueError):
            next_departure(10, 0)

    def test_calendars_and_timezone(self):
        schedule = {"weekday_peak": 180, "weekday_offpeak": None, "saturday": 240, "sunday_ph": None}
        graph = build_graph(network([line(headway_s=schedule)]), holidays=["2026-09-22"])
        self.assertIsNone(graph.boarding(graph.edges[0], timestamp(AT)))
        graph = build_graph(network([line(headway_s=schedule)]))
        for at in ["2026-09-22T10:00:00+08:00", "2026-09-27T08:00:00+08:00"]:
            self.assertIsNone(graph.boarding(graph.edges[0], timestamp(at)))
        self.assertEqual(graph.boarding(graph.edges[0], timestamp(AT)),
                         graph.boarding(graph.edges[0], timestamp("2026-09-22T00:20:00Z")))
        self.assertEqual(graph.boarding(graph.edges[0], timestamp("2026-09-26T08:00:00+08:00"))[1], 240)

    def test_operating_hours_including_overnight(self):
        for hours, allowed, disallowed in [("06:00-23:50", "08:00", "02:00"), ("22:00-02:00", "01:00", "12:00")]:
            graph = build_graph(network([line(service_hours=hours)]))
            edge = graph.edges[0]
            self.assertIsNotNone(graph.boarding(edge, timestamp(f"2026-09-22T{allowed}:00+08:00")))
            self.assertIsNone(graph.boarding(edge, timestamp(f"2026-09-22T{disallowed}:00+08:00")))

    def test_first_last_train_uses_boarding_station_and_direction(self):
        graph = build_graph(network([line(service_hours="22:00-00:05",
                                          service_hours_reverse="21:00-23:00")]))
        outbound = next(edge for edge in graph.edges if edge.source == "A" and edge.target == "B")
        downstream = next(edge for edge in graph.edges if edge.source == "B" and edge.target == "C")
        inbound = next(edge for edge in graph.edges if edge.source == "C" and edge.target == "B")
        self.assertIsNone(graph.boarding(outbound, timestamp("2026-09-22T21:59:59+08:00")))
        self.assertEqual(graph.boarding(outbound, timestamp("2026-09-23T00:05:00+08:00"))[0],
                         timestamp("2026-09-23T00:05:00+08:00"))
        self.assertIsNone(graph.boarding(outbound, timestamp("2026-09-23T00:05:01+08:00")))
        self.assertEqual(graph.boarding(downstream, timestamp("2026-09-23T00:06:00+08:00"))[0],
                         timestamp("2026-09-23T00:06:00+08:00"))
        self.assertIsNone(graph.boarding(downstream, timestamp("2026-09-23T00:06:01+08:00")))
        self.assertIsNone(graph.boarding(inbound, timestamp("2026-09-23T00:00:00+08:00")))
        self.assertTrue(make_engine(SnapshotStore(graph)).query("A", "C", "2026-09-23T00:05:00+08:00"))

    def test_transfer_after_last_service_is_rejected_but_overnight_bus_can_run(self):
        first = line(id="FIRST", stops=["A", "B"], seg_time_s=[600], service_hours="22:00-00:15")
        second = line(id="SECOND", stops=["B", "C"], seg_time_s=[60], service_hours="22:00-00:05")
        engine = make_engine(SnapshotStore(build_graph(network([first, second]))))
        self.assertEqual(engine.query("A", "C", "2026-09-23T00:00:00+08:00"), [])
        night_bus = line(id="NIGHT", mode="BUS", stops=["A", "C"], seg_time_s=[600],
                         service_hours="22:00-04:00")
        engine = make_engine(SnapshotStore(build_graph(network([night_bus]))))
        self.assertTrue(engine.query("A", "C", "2026-09-23T03:00:00+08:00"))

    def test_headway_period_transition(self):
        graph = build_graph(network([line(headway_s={"weekday_peak": 700, "weekday_offpeak": 300})]))
        dep, headway = graph.boarding(graph.edges[0], timestamp("2026-09-22T08:59:59+08:00"))
        self.assertEqual(dep, timestamp("2026-09-22T09:00:00+08:00"))
        self.assertEqual(headway, 300)
        peak_only = build_graph(network([line(service_calendar="weekday_peak_only",
                                               headway_s={"weekday_peak": 700, "weekday_offpeak": None})]))
        self.assertIsNone(peak_only.boarding(peak_only.edges[0], timestamp("2026-09-22T08:59:59+08:00")))

    def test_eta_is_independent_of_intermediate_stop_count(self):
        split = make_engine(SnapshotStore(build_graph(network())))
        direct = make_engine(SnapshotStore(build_graph(network([line(stops=["A", "C"], seg_time_s=[120])]))))
        self.assertEqual(split.query("A", "C", AT)[0]["total"]["time_range_s"],
                         direct.query("A", "C", AT)[0]["total"]["time_range_s"])

    def test_parallel_edges_and_snapshot_line_scope(self):
        store = SnapshotStore(build_graph(network([line(), line(id="OTHER")])))
        pinned = store.current
        store.update_event(event())
        self.assertNotEqual(store.current.snapshot_id, pinned.snapshot_id)
        self.assertTrue(all(pinned.impact(e, timestamp(AT))[0] == 1 for e in pinned.network.edges))
        for edge in store.network.edges:
            f = store.current.impact(edge, timestamp(AT))[0]
            self.assertEqual(f, 0 if edge.line == "L" and {edge.source, edge.target} == {"A", "B"} else 1)
        routes = make_engine(store).query("A", "C", AT)
        self.assertTrue(routes)
        self.assertEqual(routes[0]["legs"][0]["line"], "OTHER")

    def test_publication_expiry_and_version(self):
        store = SnapshotStore(build_graph(network()))
        edge = store.network.edges[0]
        store.update_event(event(status="pending_review"))
        self.assertEqual(store.current.impact(edge, timestamp(AT))[0], 1)
        published = store.update_event(event(version=2))
        store.update_event(event(version=1, status="expired"))
        self.assertIs(store.current, published)
        store.update_event(event(version=3, expires_at="2026-09-22T08:21:00+08:00"))
        self.assertEqual(store.current.impact(edge, timestamp(AT))[0], 0)
        self.assertEqual(store.current.impact(edge, timestamp("2026-09-22T08:21:00+08:00"))[0], 1)
        store.update_event(event(version=4, status="expired"))
        self.assertEqual(store.current.impact(edge, timestamp(AT))[0], 1)

    def test_directed_degradation_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SnapshotStore(build_graph(network()), path=Path(directory) / "graph.json")
            reduced = event(direction="forward", affected_segments=[{"from_node": "A", "to_node": "B",
                            "impact": "slow", "capacity_factor": .5}])
            before = time.perf_counter()
            store.update_event(reduced)
            self.assertLess(time.perf_counter() - before, 2)
            restored = SnapshotStore.restore(store.path)
            self.assertEqual(restored.current.snapshot_id, store.current.snapshot_id)
            fwd = next(e for e in store.network.edges if e.source == "A")
            rev = next(e for e in store.network.edges if e.source == "B" and e.target == "A")
            self.assertEqual(restored.current.impact(fwd, timestamp(AT))[:2], (.5, 2))
            self.assertEqual(restored.current.impact(rev, timestamp(AT))[:2], (1, 1))
            result = make_engine(restored).query_details("A", "C", AT)
            route = result["routes"][0]
            self.assertEqual(route["legs"][0]["in_vehicle_s"], 180)
            self.assertAlmostEqual(result["route_parameters"][route["route_id"]]["capacity_per_hour"], 850)

    def test_onboard_capacity_remains_valid_after_last_boarding(self):
        store = SnapshotStore(build_graph(network([line(service_hours="08:00-08:00")])))
        store.update_event(event(affected_segments=[{"from_node": "B", "to_node": "C",
                                                     "impact": "reduced_capacity", "capacity_factor": .25}]))
        result = make_engine(store).query_details("A", "C", "2026-09-22T08:00:00+08:00")
        route = result["routes"][0]
        self.assertEqual(route["total"]["time_s"], 120)
        self.assertAlmostEqual(route["load_estimate"]["capacity_per_hour"], 425)
        self.assertEqual(result["route_parameters"][route["route_id"]]["headway_s"], 720)

    def test_immutable_snapshot_and_invalid_factor(self):
        original = network()
        store = SnapshotStore(build_graph(original))
        original["lines"][0]["seg_time_s"][0] = 999
        self.assertEqual(store.network.edges[0].travel_s, 60)
        with self.assertRaises(TypeError):
            store.network.nodes["A"]["accessible"] = False
        prior = store.current
        malformed = event()
        malformed["affected_segments"][0]["capacity_factor"] = float("nan")
        with self.assertRaises(ValueError):
            store.update_event(malformed)
        self.assertIs(store.current, prior)

    def test_closure_starting_during_ride_or_wait(self):
        for start in ["08:00:30", "08:03:30"]:
            store = SnapshotStore(build_graph(network()))
            store.update_event(event(window={"start": f"2026-09-22T{start}+08:00"}))
            self.assertEqual(make_engine(store).query("A", "C", "2026-09-22T08:00:01+08:00"), [])
        store = SnapshotStore(build_graph(network()))
        store.update_event(event(published_at="2026-09-22T08:03:30+08:00"))
        self.assertEqual(make_engine(store).query("A", "C", "2026-09-22T08:00:01+08:00"), [])


class RouteTests(unittest.TestCase):
    def test_cli_emits_utf8_json(self):
        raw = subprocess.check_output([sys.executable, "-B", "-m", "backend.app.engine", "--events",
                                       "contracts/seed/event.seed.json"], cwd=ROOT)
        output = json.loads(raw.decode("utf-8"))
        self.assertGreaterEqual(len(output["routes"]), 8)

    def seed_engine(self):
        return RouteEngine.from_seed(events_path=ROOT / "contracts/seed/event.seed.json")

    def test_seed_at_least_eight_diverse_candidates(self):
        engine = self.seed_engine()
        profile = normalize_profile()
        paths = select_diverse(search_paths(engine.snapshots.current, "TAW", "ADM", AT, profile).paths)
        self.assertGreaterEqual(len(paths), 8)
        self.assertGreaterEqual(len({t.edge.mode for p in paths for t in p} - {"WALK"}), 2)
        counts = {}
        for i, path in enumerate(paths):
            for other in paths[i + 1:]:
                self.assertLess(jaccard(intermediate_nodes(path), intermediate_nodes(other)), .7)
            for node in transfer_nodes(path):
                counts[node] = counts.get(node, 0) + 1
            for t in path:
                self.assertGreater(engine.snapshots.current.impact(t.edge, t.depart)[0], 0)
        self.assertLessEqual(max(counts.values()), 2)

    def test_wheelchair_and_explicit_flags(self):
        for kwargs in [dict(mode="MINIBUS"), dict(mode="BUS", low_floor=False),
                       dict(mode="BUS", accessible=False), dict(stairs=True),
                       dict(accessible="partial")]:
            engine = make_engine(SnapshotStore(build_graph(network([line(**kwargs)]))))
            self.assertEqual(engine.query("A", "C", AT, {"mobility": "wheelchair"}), [])
        for mode in ("MTR", "BUS"):
            data = network([line(mode=mode)])
            for node in data["nodes"]:
                node.pop("accessible")
            engine = make_engine(SnapshotStore(build_graph(data)))
            routes = engine.query("A", "C", AT, {"mobility": "wheelchair"})
            self.assertTrue(routes)
            self.assertTrue(all(route["legs"][0]["accessible"] for route in routes))
            self.assertTrue(all(any("assumed usable" in warning for warning in route["warnings"])
                                for route in routes))
        for p in ({"mobility": "wheelchair", "max_walk_m": 999}, {"mobility": "reduced"}):
            for route in self.seed_engine().query("TAW", "ADM", AT, p):
                self.assertLessEqual(route["total"]["walk_m"], 400)
                self.assertTrue(all(l["accessible"] and l["mode"] not in {"MINIBUS", "BUS"} for l in route["legs"]))

    def test_walk_transfer_bounds_and_speed(self):
        data = network([line(stops=["B", "C"])], [{"from": "A", "to": "B", "walk_m": 350, "accessible": True}])
        engine = make_engine(SnapshotStore(build_graph(data)))
        self.assertEqual(engine.query("A", "C", AT, {"max_walk_m": 349}), [])
        r = engine.query("A", "C", AT, {"walking_speed_mps": .7})[0]
        self.assertAlmostEqual(r["legs"][0]["in_vehicle_s"], 500)
        self.assertEqual(engine.query("A", "C", AT, {"mobility": "wheelchair", "max_walk_m": 100}), [])
        data = network([line(stops=["A", "B"]), line(id="L2", stops=["B", "C"])])
        engine = make_engine(SnapshotStore(build_graph(data)))
        self.assertEqual(engine.query("A", "C", AT, {"max_transfers": 0}), [])
        self.assertEqual(engine.query("A", "C", AT, {"max_transfers": 1})[0]["total"]["transfers"], 1)

    def test_scoring_reproducible_and_finite(self):
        engine = self.seed_engine()
        for preset in ["fastest", "most_stable", "fewest_transfers"]:
            routes = engine.query("TAW", "ADM", AT, {"preset": preset})
            for r in routes:
                self.assertEqual(sum(row["contribution"] for row in r["score_breakdown"]), r["score"])
                self.assertAlmostEqual(sum(row["weight"] for row in r["score_breakdown"]), 1)
                for row in r["score_breakdown"]:
                    self.assertTrue(0 <= row["normalized"] <= 1)
                    self.assertEqual(row["weight"] * row["normalized"], row["contribution"])
                self.assertLessEqual(r["total"]["time_range_s"][0], r["total"]["time_s"])
                self.assertGreaterEqual(r["total"]["time_range_s"][1], r["total"]["time_s"])
                self.assertTrue(r["explain"] and r["evidence"] and r["warnings"])
                self.assertNotIn("_metrics", r)
                json.dumps(r, allow_nan=False)
            self.assertEqual(routes, engine.query("TAW", "ADM", AT, {"preset": preset}))
            rescored = score_routes(
                routes,
                normalize_profile({"preset": preset}),
                baseline_fare=engine.baseline_fare,
            )
            self.assertEqual(routes, rescored)

    def test_cache_revision_profile_and_copy_isolation(self):
        engine = make_engine(SnapshotStore(build_graph(network())))
        first = engine.query("A", "C", AT)
        first[0]["legs"].clear()
        self.assertTrue(engine.query("A", "C", AT)[0]["legs"])
        self.assertEqual(engine.cache.hits, 1)
        engine.query("A", "C", AT, {"preset": "most_stable"})
        self.assertEqual(engine.cache.misses, 2)
        engine.snapshots.update_event(event())
        self.assertEqual(engine.query("A", "C", AT, event_ids=[]), [])
        engine.snapshots.update_event(event(version=2, status="expired"))
        self.assertTrue(engine.query("A", "C", AT))
        cache = QueryCache(1)
        cache.put("one", [])
        cache.put("two", [2])
        self.assertIsNone(cache.get("one"))

    def test_validation_and_search_shortfall(self):
        engine = make_engine(SnapshotStore(build_graph(network())))
        for args in [{"weights": {"time": -1}}, {"weights": {"time": 0}}, {"walking_speed_mps": 0}]:
            with self.assertRaises(ValueError):
                engine.query("A", "C", AT, args)
        with self.assertRaises(ValueError):
            engine.query("unknown", "C", AT)
        with self.assertRaises(ValueError):
            engine.query("A", "C", AT, modes=["PLANE"])
        with self.assertRaises(ValueError):
            engine.query("A", "C", AT, event_ids=["unknown"])
        details = engine.query_details("A", "C", AT)
        self.assertEqual(len(details["routes"]), 1)
        self.assertTrue(any("Only 1" in d for d in details["diagnostics"]))

    def test_walk_and_eco_models(self):
        self.assertEqual(walking_seconds(140, 1.4), 100)
        nodes = network()["nodes"]
        matrix = walking_matrix(nodes)
        self.assertEqual(len(matrix), 12)
        self.assertTrue(all(r["provenance"] == "simulated" for r in matrix))
        self.assertEqual(estimates("WALK", 1000, 600)["co2_g"], 0)
        self.assertGreater(estimates("BUS", 1000, 600)["co2_g"], estimates("MTR", 1000, 600)["co2_g"])
        self.assertLess(estimates("BUS", 1000, 3600)["comfort"], estimates("BUS", 1000, 600)["comfort"])

    def test_cold_query_p95(self):
        durations = []
        for i in range(25):
            start = time.perf_counter()
            engine = self.seed_engine()
            engine.query("TAW", "ADM", timestamp(AT) + timedelta(seconds=i))
            durations.append(time.perf_counter() - start)
        p95 = sorted(durations)[math.ceil(.95 * len(durations)) - 1]
        print(f"\nC-Route cold P95 (25 seed queries, includes build): {p95:.4f}s")
        self.assertLess(p95, 1.5)


if __name__ == "__main__":
    unittest.main()
