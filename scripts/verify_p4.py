"""Reproduce frozen scenarios and measure local engine/optional loopback HTTP performance."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.precompute_sim_p3 import simulation_inputs, stress_inputs
from scripts.p4_readiness import text_sha256, simulation_readiness
from backend.app.engine.service import RouteEngine
from backend.app.sim.m2 import run_m2_multi_od


def timings(values):
    ordered = sorted(values)
    return {"samples": len(values), "p95_ms": round(ordered[math.ceil(len(values) * .95) - 1], 3),
            "max_ms": round(max(values), 3), "raw_ms": [round(value, 3) for value in values]}


def request_context(origin, destination, index=0):
    at = datetime.fromisoformat("2026-09-22T08:20:00+08:00") + timedelta(seconds=index)
    return {"origin": origin, "destination": destination, "depart_at": at.isoformat(),
            "profile": {"mobility": "standard", "preset": "fastest"}}


def http_query(base, context):
    started = perf_counter()
    request = Request(base + "/api/routes/query", data=json.dumps(context).encode(), headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(request, timeout=10) as response:
        body = json.load(response)
    if not isinstance(body, list) or not body:
        raise ValueError("HTTP query returned no route candidates")
    return (perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/p4-c/performance.json")
    parser.add_argument("--api-base-url", help="Optional existing loopback API; this script never starts or mutates it.")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Evidence output must stay inside the local project")
    if args.api_base_url:
        url = urlsplit(args.api_base_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            parser.error("Performance probes are restricted to a loopback HTTP origin")
    readiness = simulation_readiness(ROOT)
    if not readiness["ok"]:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
        return 1
    payload, _, resources, common = simulation_inputs()
    stress_common, stressed_resources = stress_inputs(common, resources)
    cases = []
    for label, inputs, supplies in (("normal", common, resources), ("stress_10pct", stress_common, stressed_resources)):
        durations, outputs = [], []
        for _ in range(3):
            started = perf_counter()
            outputs.append(run_m2_multi_od(**inputs, shared_resources=supplies))
            durations.append(perf_counter() - started)
        actual = outputs[0]
        recorded = json.loads((ROOT / "data/sim" / f"{inputs['scenario_id']}.json").read_text(encoding="utf-8"))
        ids = [resource.resource_id for resource in supplies]
        equal = outputs[0] == outputs[1] == outputs[2]
        matches_recorded = actual == {key: recorded[key] for key in actual}
        cases.append({"case": label, "scenario_id": inputs["scenario_id"], "repeat_equal": equal,
                      "matches_checked_in": matches_recorded, "unique_shared_resources": len(set(ids)),
                      "resource_count": len(ids), "run_seconds": [round(value, 4) for value in durations],
                      "baseline": {key: actual["baseline"][key] for key in ("total_delay_person_min", "p95_wait_min", "overloaded_routes", "overloaded_shared_resources", "served_demand", "unmet_demand", "unassigned_demand")},
                      "guided": {key: actual["guided"][key] for key in ("total_delay_person_min", "p95_wait_min", "overloaded_routes", "overloaded_shared_resources", "served_demand", "unmet_demand", "unassigned_demand")},
                      "fairness": actual["fairness"], "delta": actual["delta"]})
    pairs = list(itertools.permutations(payload["stations"], 2))
    fresh = []
    for index, (origin, destination) in enumerate(pairs * 2):
        started = perf_counter()
        engine = RouteEngine.from_seed()
        routes = engine.query(**request_context(origin, destination, index))
        if not routes:
            raise ValueError(f"No candidates for {origin}->{destination}")
        fresh.append((perf_counter() - started) * 1000)
    engine = RouteEngine.from_seed()
    cached = []
    context = request_context("TAW", "ADM")
    engine.query(**context)
    for _ in range(60):
        started = perf_counter()
        engine.query(**context)
        cached.append((perf_counter() - started) * 1000)
    query = {"fresh_engine_plus_query": timings(fresh), "cached_engine_query": timings(cached)}
    if args.api_base_url:
        base = args.api_base_url.rstrip("/")
        contexts = [request_context(a, b, i + 1000) for i, (a, b) in enumerate(pairs * 2)]
        query["loopback_http_sequential"] = timings([http_query(base, context) for context in contexts])
        with ThreadPoolExecutor(max_workers=4) as pool:
            query["loopback_http_four_workers"] = timings(list(pool.map(lambda context: http_query(base, context), [request_context(a, b, i + 2000) for i, (a, b) in enumerate(pairs)])))
    gate = query.get("loopback_http_sequential", query["fresh_engine_plus_query"])
    checks = {"fixed_seed_reproducible": all(row["repeat_equal"] and row["matches_checked_in"] for row in cases),
              "shared_resource_ids_unique": all(row["unique_shared_resources"] == row["resource_count"] for row in cases),
              "simulation_under_30_seconds": all(max(row["run_seconds"]) <= 30 for row in cases),
              "local_query_p95_under_1500_ms": gate["p95_ms"] <= 1500,
              "concurrent_query_p95_under_1500_ms": query.get("loopback_http_four_workers", gate)["p95_ms"] <= 1500}
    report = {"ok": all(checks.values()), "environment": "CI isolated" if os.getenv("CI") else "local isolated",
              "limitations": "Simulated inputs; production/network WAN latency not measured",
              "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "generator_sha256": text_sha256(ROOT / "scripts/precompute_sim_p3.py"),
              "input_sha256": readiness["input_sha256"], "checks": checks, "simulation": cases, "query": query}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "checks": checks, "output": str(output.relative_to(ROOT)), "query_p95_ms": gate["p95_ms"]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
