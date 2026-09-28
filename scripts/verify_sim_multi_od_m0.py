"""Offline C-Sim M0 acceptance for OD-scoped simulated route sets."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.sim.adapters import od_route_sets_from_simulated_fixture
from backend.app.sim.multi_od import TARGET_CANDIDATES_PER_OD, run_multi_od_simulation


FIXTURE_PATH = ROOT / "backend/tests/fixtures/multi_od_routes.simulated.json"
REPORT_PATH = ROOT / "data/sim/m0-multi-od-verification.json"
NODES = ("TAW", "KOT", "MKK", "HUH", "EXC", "ADM")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_simulated(value: object) -> bool:
    if isinstance(value, dict):
        if "provenance" in value and value["provenance"] != "simulated":
            return False
        return all(_all_simulated(child) for child in value.values())
    if isinstance(value, list):
        return all(_all_simulated(child) for child in value)
    return True


def verify(root: Path = ROOT) -> dict:
    fixture_path = root / FIXTURE_PATH.relative_to(ROOT)
    fixture = _read(fixture_path)
    route_sets = od_route_sets_from_simulated_fixture(fixture)
    kwargs = {
        "scenario_id": "scn_corridor_30_od_m0",
        "route_sets": route_sets,
        "population": 300,
        "seed": 20260922,
        "window_min": 60,
    }
    first = run_multi_od_simulation(**kwargs)
    second = run_multi_od_simulation(**kwargs)
    expected_ods = {
        (origin, destination)
        for origin in NODES
        for destination in NODES
        if origin != destination
    }
    actual_ods = {(route_set.origin, route_set.destination) for route_set in route_sets}
    fixture_candidate_total = sum(
        len(item["candidate_profiles"]) for item in fixture["od_route_sets"]
    )
    adapted_candidate_total = sum(len(route_set.routes) for route_set in route_sets)
    route_ids = [
        route.route_id for route_set in route_sets for route in route_set.routes
    ]
    invariant_values = first["invariants"]
    checks = {
        "thirty_directed_ods": actual_ods == expected_ods and len(route_sets) == 30,
        "simulated_only": _all_simulated(fixture) and first["provenance"] == "simulated",
        "fixed_seed_reproducible": first == second,
        "capacity_conserved": (
            invariant_values["capacity_conserved"]
            and invariant_values["capacity_violations"] == 0
            and first["assigned_demand"] + first["unmet_demand"] == first["population"]
        ),
        "od_scoped_assignments": invariant_values["wrong_od_assignments"] == 0,
        "wheelchair_constraints": invariant_values["wheelchair_constraint_violations"] == 0,
        "fairness_enforced": invariant_values["fairness_violations"] == 0,
        "protected_personal_best_preserved": (
            invariant_values["protected_non_best_assignments"] == 0
        ),
        "candidate_shortage_recorded": all(
            row["candidate_shortage"]
            == max(0, TARGET_CANDIDATES_PER_OD - row["candidate_count"])
            for row in first["od_results"]
        ),
        "no_candidate_padding": (
            fixture_candidate_total == adapted_candidate_total == len(set(route_ids))
        ),
        "per_od_conservation": all(
            row["assigned_demand"] + row["unmet_demand"] == row["demand"]
            for row in first["od_results"]
        ),
        "unmet_demand_reported": first["unmet_demand"] > 0,
    }
    return {
        "check_id": "c-sim-m0-multi-od-simulated",
        "command": "python scripts/verify_sim_multi_od_m0.py",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scenario_id": first["scenario_id"],
        "seed": first["seed"],
        "population": first["population"],
        "od_count": first["od_count"],
        "candidate_count": adapted_candidate_total,
        "candidate_shortage_total": first["candidate_shortage_total"],
        "assigned_demand": first["assigned_demand"],
        "unmet_demand": first["unmet_demand"],
        "od_results": first["od_results"],
        "fixture_file": str(FIXTURE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "provenance": "simulated",
        "scope": "Multi-OD algorithm and adapter evidence only; no verified routes or transport data.",
    }


def write_report(report: dict, path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    try:
        report = verify()
    except Exception as exc:
        report = {
            "check_id": "c-sim-m0-multi-od-simulated",
            "command": "python scripts/verify_sim_multi_od_m0.py",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "provenance": "simulated",
            "scope": "Multi-OD algorithm and adapter evidence only; no verified routes or transport data.",
        }
    output = write_report(report)
    print(f"{report['status']} C-Sim M0 multi-OD simulated acceptance: {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
