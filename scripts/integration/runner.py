"""CLI suites and an explicit adapter boundary for unmerged module implementations."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import math
from pathlib import Path
import time

from .checks import (Report, check_events, check_network, check_route, check_sim,
                     closed_crossings, fields, load_json, require)

ROOT = Path(__file__).resolve().parents[2]
ODS = [("TAW", "ADM"), ("KOT", "ADM"), ("MKK", "ADM"),
       ("HUH", "ADM"), ("TAW", "EXC"), ("KOT", "EXC")]
SEED = 20260922


def static_suite(report, root, schema_map=None):
    data = {}
    for name in ("network", "event", "routes", "sim"):
        try:
            path = root / "contracts" / "seed" / f"{name}.seed.json"
            data[name] = load_json(path)
            report.add("json." + name, "PASS", "Strict JSON parsed (not domain acceptance)",
                       input_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        except Exception as exc:
            report.add("json." + name, "FAIL", str(exc))
    if len(data) != 4:
        return
    network, events, bundle, sim = (data[n] for n in ("network", "event", "routes", "sim"))
    report.run("network.references", lambda: check_network(network))
    report.run("event.references", lambda: check_events(events, network))
    od = bundle.get("meta", {}).get("od", {})
    routes = bundle.get("routes", [])
    def routes_check():
        findings = []
        ids = [r.get("route_id") for r in routes]
        require(len(ids) == len(set(ids)), "UNIQUE", "routes", "Duplicate route IDs", findings)
        require(len(routes) >= 8, "CANDIDATES", "routes", "Agent 3 minimum: 8; contract target: 10", findings)
        for route in routes:
            findings.extend(check_route(route, network, od.get("origin"), od.get("destination")))
            findings.extend(closed_crossings(route, network, events["events"]))
        return findings
    report.run("route.boundary", routes_check)
    def personas_check():
        findings, firsts = [], {}
        by_id = {r["route_id"]: r for r in routes}
        for p in bundle.get("persona_top_picks", []):
            picks = p.get("top", [])
            require(bool(picks), "PERSONA_EMPTY", p.get("profile_id", "?"), "Missing top picks", findings)
            if picks:
                firsts[p["persona"]] = picks[0]
            for rid in picks:
                require(rid in by_id, "ROUTE_REF", p["profile_id"], f"Unknown route {rid}", findings)
                if rid in by_id and p.get("persona") == "wheelchair":
                    findings.extend(check_route(by_id[rid], network, wheelchair=True))
        require("commuter" in firsts and "wheelchair" in firsts and firsts["commuter"] != firsts["wheelchair"],
                "PERSONA_DIFFERENCE", "personas", "Commuter and wheelchair first picks must differ", findings)
        return findings
    report.run("persona.hard_constraints", personas_check)
    report.run("simulation.integrity", lambda: check_sim(sim, {r["route_id"] for r in routes}))
    report.add("provenance.ledger", "PASS" if (root / "data/PROVENANCE.md").is_file() else "PENDING",
               "Ledger presence only; source/field/date audit of 10 entries remains manual")
    if not schema_map:
        report.add("schema.validation", "PENDING", "B must supply official schemas and --schema-map; boundary checks are not JSON Schema validation")
    else:
        def schemas_check():
            from jsonschema import Draft202012Validator, FormatChecker
            mapping = load_json(schema_map)
            findings = []
            for name in ("network", "event", "routes", "sim"):
                require(name in mapping, "SCHEMA_MAP", name, "No seed-envelope schema mapped", findings)
                if name not in mapping:
                    continue
                schema = load_json(root / mapping[name])
                Draft202012Validator.check_schema(schema)
                validator = Draft202012Validator(schema, format_checker=FormatChecker())
                for error in validator.iter_errors(data[name]):
                    require(False, "SCHEMA", f"{name}.{error.json_path}", error.message, findings)
            return findings
        report.run("schema.validation", schemas_check)


def adapter_load(report, specification):
    if not specification:
        report.add("adapter", "PENDING", "No module adapter provided; runtime implementation not verified")
        return None
    try:
        module, factory = specification.split(":", 1)
        return getattr(importlib.import_module(module), factory)()
    except Exception as exc:
        report.add("adapter", "FAIL", f"{type(exc).__name__}: {exc}")
        return None


def runtime_suite(report, adapter):
    """Adapter mutates only its isolated test fixture. See docs/acceptance/README.md."""
    def lifecycle():
        f = []
        adapter.reset(llm_enabled=False)
        network = adapter.network()
        before = adapter.query("TAW", "ADM", "commuter")
        original = adapter.snapshot()
        fields(original, "snapshot_id affected_edges", "snapshot", f)
        event = adapter.stage_event("pending_review")
        require(adapter.snapshot() == original, "UNPUBLISHED_SNAPSHOT", "snapshot", "Pending event changed graph", f)
        require(adapter.query("TAW", "ADM", "commuter") == before, "UNPUBLISHED_ROUTE", "routes", "Pending event changed routes", f)
        adapter.review(event["event_id"], "reject")
        require(adapter.snapshot() == original, "REJECTED_SNAPSHOT", "snapshot", "Rejected event changed graph", f)
        require(adapter.query("TAW", "ADM", "commuter") == before, "REJECTED_ROUTE", "routes", "Rejected event changed routes", f)
        event = adapter.stage_event("pending_review")
        started = time.perf_counter()
        published = adapter.review(event["event_id"], "approve")
        deadline = started + 2
        after = adapter.snapshot()
        while after.get("snapshot_id") == original.get("snapshot_id") and time.perf_counter() < deadline:
            time.sleep(0.02)
            after = adapter.snapshot()
        elapsed = time.perf_counter() - started
        require(elapsed <= 2 and after.get("snapshot_id") != original.get("snapshot_id"),
                "PUBLISH_LATENCY", "snapshot", f"Snapshot publication took {elapsed:.3f}s or did not change", f)
        require(bool(after.get("affected_edges")), "AFFECTED_EDGES", "snapshot", "Published closure missing from snapshot", f)
        profiles = {}
        for persona in ("commuter", "wheelchair"):
            routes = adapter.query("TAW", "ADM", persona)
            require(bool(routes), "EMPTY", persona, "No routes for required demo OD", f)
            profiles[persona] = routes
            for route in routes:
                f.extend(check_route(route, network, "TAW", "ADM", persona == "wheelchair"))
                f.extend(closed_crossings(route, network, [published]))
        if all(profiles.values()):
            require(profiles["commuter"][0]["route_id"] != profiles["wheelchair"][0]["route_id"],
                    "PERSONA_DIFFERENCE", "routes", "Same first pick for required personas", f)
        for origin, destination in ODS[1:]:
            routes = adapter.query(origin, destination, "wheelchair")
            require(bool(routes), "EMPTY", f"{origin}->{destination}", "No wheelchair result; owner must document infeasibility", f)
            for route in routes:
                f.extend(check_route(route, network, origin, destination, True))
                f.extend(closed_crossings(route, network, [published]))
        adapter.review(event["event_id"], "expire")
        require(adapter.query("TAW", "ADM", "commuter") == before, "EXPIRE", "routes", "Expired closure not restored", f)
        return f
    report.run("B.publish_to_C_route.no_llm", lifecycle)

    def simulation():
        adapter.reset(llm_enabled=False)
        event = adapter.stage_event("pending_review")
        adapter.review(event["event_id"], "approve")
        routes = adapter.query("TAW", "ADM", "commuter")
        if not routes:
            raise ValueError("No C-Route output to feed C-Sim")
        first = adapter.simulate(seed=SEED, population=10000, routes=routes)
        second = adapter.simulate(seed=SEED, population=10000, routes=routes)
        f = check_sim(first, {r["route_id"] for r in routes})
        require(first == second, "REPRODUCIBILITY", "sim", "Same seed/inputs differ (adapter removes timestamps only)", f)
        return f
    report.run("C_route_to_C_sim.fixed_seed", simulation)
    # These must never turn green merely because an API/fixture check passed.
    for name in ("A.publish_to_map_and_cards.3_runs_5s", "B.confidence_ladder.3_sources",
                 "C_sim.fairness.per_person_15min_and_protected_users", "C_ai.failure_timeout_schema_and_numeric_trace",
                 "A.provenance_freshness_disclaimer", "A.offline_5min_rehearsal"):
        report.add(name, "PENDING", "Requires owner-specific regression or recorded UI evidence; see acceptance matrix")


def percentile95(samples):
    if not samples:
        raise ValueError("No timing samples")
    return sorted(samples)[math.ceil(0.95 * len(samples)) - 1]


def performance_suite(report, adapter, samples):
    """Measure cold query, cached read and fixed-seed simulation separately."""
    if samples < 20:
        raise ValueError("Use at least 20 samples for P95")
    workloads = [("route.cold_p95", 1.5), ("sim.cached_p95", 0.3), ("sim.10000_runtime", 30)]
    for name, threshold in workloads:
        times = []
        try:
            adapter.reset(llm_enabled=False)
            routes = adapter.query("TAW", "ADM", "commuter")
            if name == "sim.cached_p95":
                warm = adapter.simulate(seed=SEED, population=10000, routes=routes)
                if check_sim(warm):
                    raise ValueError("Invalid simulation warmup result")
            for _ in range(1 if name == "sim.10000_runtime" else samples):
                if name == "route.cold_p95":
                    adapter.clear_route_cache()
                start = time.perf_counter()
                if name == "route.cold_p95":
                    value = adapter.query("TAW", "ADM", "commuter")
                elif name == "sim.cached_p95":
                    value = adapter.cached_simulation()
                else:
                    value = adapter.simulate(seed=SEED, population=10000, routes=routes)
                times.append(time.perf_counter() - start)
                if name == "route.cold_p95":
                    if not value or any(check_route(r, adapter.network(), "TAW", "ADM") for r in value):
                        raise ValueError("Fast but invalid route result")
                elif check_sim(value):
                    raise ValueError("Fast but invalid simulation result")
            p95 = percentile95(times)
            report.add(name, "PASS" if p95 < threshold else "FAIL", f"{p95:.6f}s < {threshold}s",
                       samples_s=times, percentile="nearest-rank P95", threshold_s=threshold)
        except Exception as exc:
            report.add(name, "FAIL", str(exc), samples_s=times)


def fallback_suite(report, adapter):
    for fault in ("llm_disabled", "llm_timeout", "llm_invalid_schema", "upstream_unavailable"):
        def check(fault=fault):
            f = []
            adapter.reset(llm_enabled=True)
            adapter.full_query("TAW", "ADM", "commuter")  # Prime the last successful cache.
            adapter.set_fault(fault)
            result = adapter.full_query("TAW", "ADM", "commuter")
            fields(result, "routes meta fault_observed fallback_used", fault, f)
            require(result.get("fault_observed") == fault and result.get("fallback_used") is True,
                    "FAULT_NOT_EXERCISED", fault, "Adapter must attest actual fault interception and fallback", f)
            routes = result.get("routes", [])
            require(bool(routes), "EMPTY", fault, "Full query must still return routes", f)
            for route in routes:
                f.extend(check_route(route, adapter.network(), "TAW", "ADM"))
            fields(result.get("meta", {}), "generated_at sources disclaimer", fault + ".meta", f)
            if fault == "upstream_unavailable":
                require(result.get("stale") is True, "STALE_LABEL", fault, "Cached data must expose stale state", f)
            return f
        report.run("fallback." + fault, check)
    report.add("fallback.UI_stale_badge_no_blank_screen", "PENDING", "Record UI behavior against failed API/SSE/tiles; API result alone is insufficient")


def offline_suite(report, root, manifest):
    if not manifest:
        report.add("offline.manifest", "PENDING", "No offline bundle manifest supplied by C-DevOps")
        return
    def check():
        data = load_json(manifest)
        f, roles = [], set()
        base = root.resolve()
        for item in data.get("files", []):
            path = (base / item["path"]).resolve()
            require(path.is_relative_to(base), "BUNDLE_PATH", item["path"], "File outside bundle root", f)
            if not path.is_relative_to(base):
                continue
            require(path.is_file(), "BUNDLE_MISSING", item["path"], "Missing offline asset", f)
            if not path.is_file():
                continue
            require(path.stat().st_size > 0, "BUNDLE_EMPTY", item["path"], "Empty offline asset", f)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            require(digest == item.get("sha256"), "BUNDLE_HASH", item["path"], "SHA-256 mismatch", f)
            roles.add(item.get("role"))
            if item.get("role") == "sim":
                f.extend(check_sim(load_json(path)))
            if item.get("role") == "network":
                f.extend(check_network(load_json(path)))
        for role in ("frontend", "network", "routes", "sim", "tiles", "explanations", "meta"):
            require(role in roles, "BUNDLE_ROLE", role, "Missing offline asset role", f)
        return f
    report.run("offline.files_and_hashes", check)
    report.add("offline.disconnected_browser", "PENDING", "Asset presence does not prove offline operation. Record a full disconnected 5-minute rehearsal")


def main(default_suite=None):
    parser = argparse.ArgumentParser(description="C-Integrator acceptance: exit 0 pass, 1 fail, 2 pending")
    parser.add_argument("--suite", choices=("fixtures", "contracts", "runtime", "performance", "fallback", "offline", "preflight"), default=default_suite or "contracts")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--adapter", help="Importable module:factory implementing the documented test adapter")
    parser.add_argument("--schema-map", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    report = Report(args.suite)
    try:
        if args.suite == "fixtures":
            from .fixture_source import FixtureSource, DEFAULT_FIXTURE, validate_fixture
            fixture_path = args.fixture or DEFAULT_FIXTURE
            report.run("simulated.consumer_contracts", lambda: validate_fixture(FixtureSource(fixture_path)))
            if fixture_path.is_file():
                report.add("fixture.identity", "PASS", str(fixture_path),
                           input_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest())
            report.add("evidence_scope", "PASS", "Invented contract fixtures only; no product simulation, performance or real-data acceptance claim")
        if args.suite in {"contracts", "preflight"}:
            static_suite(report, args.root, args.schema_map)
        if args.suite in {"runtime", "performance", "fallback", "preflight"}:
            adapter = adapter_load(report, args.adapter)
            if adapter is not None:
                try:
                    if args.suite in {"runtime", "preflight"}:
                        runtime_suite(report, adapter)
                    if args.suite in {"performance", "preflight"}:
                        performance_suite(report, adapter, args.samples)
                    if args.suite in {"fallback", "preflight"}:
                        fallback_suite(report, adapter)
                finally:
                    adapter.close()
        if args.suite in {"offline", "preflight"}:
            offline_suite(report, args.root, args.manifest)
    except Exception as exc:
        report.add("runner", "FAIL", f"{type(exc).__name__}: {exc}")
    return report.finish(args.output)
