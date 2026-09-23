"""Integrator-only 30-OD counts and existing module gates; no route fabrication."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from backend.app.engine import RouteEngine
from backend.app.engine.coverage import coverage_matrix
from scripts.verify_sim_multi_od_m0 import verify as verify_sim, write_report
from .audit_all import ROOT, fingerprints, run_command
from .contracts import validate_payload
from .m0_probe import probe

AT = "2026-09-22T08:20:00+08:00"


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_routes():
    matrices = {}
    issues = []
    profiles = {"normal": None, "wheelchair": {"mobility": "wheelchair"}, "event": None}
    for name, profile in profiles.items():
        engine = RouteEngine.from_seed(events_path=ROOT / "contracts/seed/event.seed.json" if name == "event" else None)
        matrix = coverage_matrix(engine, AT, profile=profile, target=10)
        for row in matrix["rows"]:
            routes = engine.query_details(row["origin"], row["destination"], AT, profile, limit=10)["routes"]
            signatures = [tuple((leg["mode"], leg.get("line"), leg["from"], leg["to"]) for leg in r["legs"]) for r in routes]
            checks = {
                "count_matches": len(routes) == row["selected"],
                "unique_ids": len({r["route_id"] for r in routes}) == len(routes),
                "unique_leg_sequences": len(set(signatures)) == len(signatures),
                "endpoints_and_continuity": all(
                    r["legs"][0]["from"] == row["origin"] and r["legs"][-1]["to"] == row["destination"]
                    and all(a["to"] == b["from"] for a,b in zip(r["legs"], r["legs"][1:])) for r in routes),
                "simulated_with_evidence": all(r.get("provenance") == "simulated" and r.get("evidence") for r in routes),
                "not_reference_seed_routes": all(not r["route_id"].startswith("r_seed_") for r in routes),
                "consumer_contract": all(not validate_payload("RouteCandidate", r) for r in routes),
            }
            row["integrator_checks"] = checks
            row["route_ids"] = [r["route_id"] for r in routes]
            if not all(checks.values()):
                issues.append({"scenario": name, "od": [row["origin"], row["destination"]], "checks": checks})
        matrices[name] = matrix
    rows = [{"origin": r["origin"], "destination": r["destination"],
             **{name: matrix["rows"][i]["selected"] for name,matrix in matrices.items()}}
            for i,r in enumerate(matrices["normal"]["rows"])]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "provenance": "simulated",
            "scope": "Three separate scenarios; aggregate counts are not unique network routes or operational certification.",
            "matrices": matrices, "rows": rows, "validation_issues": issues,
            "coverage_status": "CONDITIONAL" if any(m["at_target"] < 30 for m in matrices.values()) else "PASS"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/acceptance/evidence/m0")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    before = fingerprints(ROOT)
    commands = []
    expected = ["153f330", "f581277", "d2dec12", "b08824e", "8ab9cae"]
    commits = {}
    for commit in expected:
        full = subprocess.check_output(["git","rev-parse",commit], cwd=ROOT, text=True).strip()
        code = subprocess.run(["git","merge-base","--is-ancestor",full,"HEAD"], cwd=ROOT).returncode
        commits[full] = {"included": code == 0, "exit_code": code}
    coverage = audit_routes()
    dump(out / "corridor-30-od.json", coverage)
    commands.append({"name": "route_coverage", "command": "coverage_matrix + actual query_details checks",
                     "returncode": 1 if coverage["validation_issues"] else 0,
                     "status": "FAIL" if coverage["validation_issues"] else coverage["coverage_status"]})
    sim = verify_sim()
    write_report(sim, out / "sim-multi-od.json")
    commands.append({"name": "sim_multi_od", "command": "scripts.verify_sim_multi_od_m0.verify()",
                     "returncode": 0 if sim["status"] == "PASS" else 1, "status": sim["status"]})
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", AI_ENABLED="false", LLM_ENABLED="false", OFFLINE_MODE="true")
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT/"backend")])
    with tempfile.TemporaryDirectory(prefix="m0-multi-od-") as cache:
        env["PYTHONPYCACHEPREFIX"] = cache
        for name, command in [
            ("ai_multi_od", ["-m","pytest","-q","-p","no:cacheprovider","backend/tests/test_ai.py"]),
            ("devops_multi_od", ["-m","pytest","-q","-p","no:cacheprovider","tests/test_devops_runtime.py","tests/test_od_smoke.py"]),
        ]:
            commands.append(run_command(name, command, None, 1, ROOT, out, env, 180))
    runtime = probe(smoke_output=out/"devops-od-smoke.json")
    dump(out / "multi-od-runtime.json", runtime)
    smoke = json.loads((out/"devops-od-smoke.json").read_text(encoding="utf-8")) if (out/"devops-od-smoke.json").is_file() else {}
    same_counts = bool(smoke) and {(r["origin"],r["destination"]):r["candidate_count"] for r in smoke["rows"]} == {
        (r["origin"],r["destination"]):r["event"] for r in coverage["rows"]}
    commands.append({"name":"devops_od_smoke", "command":runtime.get("od_smoke",{}).get("command"),
                     "returncode":runtime.get("od_smoke",{}).get("returncode",1),
                     "status":"PASS" if smoke.get("failed_http_count")==0 and same_counts else "FAIL",
                     "matches_event_coverage":same_counts})
    health_ok = all(runtime.get(k,{}).get("status")==200 and runtime[k]["body"].get("ok") is True for k in ("health","deep_health"))
    commands.append({"name":"multi_od_health","status":"CONDITIONAL" if health_ok else "FAIL",
                     "returncode":0 if health_ok else 1})
    after = fingerprints(ROOT)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    code = 1 if coverage["validation_issues"] or any(c["status"] == "FAIL" for c in commands) or not all(v["included"] for v in commits.values()) else 2
    summary = {"revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
               "commits":commits,"commands":commands,"exit_code":code,
               "source_sha256":before,"files_changed_during_run":changed,
               "provenance":"simulated","note":"Exit 2 retains coverage/evidence gaps; Sim synthetic route sets are independent from actual Route coverage."}
    dump(out/"multi-od-summary.json",summary)
    for c in commands:
        print(f"{c['status']}: {c['name']}: exit={c['returncode']}",flush=True)
    print("Coverage totals:", {k:m["selected_total"] for k,m in coverage["matrices"].items()})
    return code


if __name__ == "__main__":
    raise SystemExit(main())
