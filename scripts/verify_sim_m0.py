"""One-command, offline C-Sim M0 acceptance check using simulated data only."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.sim.adapters import adapt_b_update, apply_b_update, routes_from_contract
from backend.app.sim.cache import PrecomputedResultStore
from backend.app.sim.models import Agent, RouteOption
from backend.app.sim.replanning import ReplanningMonitor
from backend.app.sim.run import _guided_assignments, _personal_rankings, run_simulation
from backend.app.sim.service import build_diversion_plan
from backend.app.engine.load import RouteSupply


CONFIG_PATH = ROOT / "data/sim/scn_huh_exc_closed_am_peak.input.json"
RESULT_PATH = ROOT / "data/sim/scn_huh_exc_closed_am_peak.json"
ROUTE_FIXTURE_PATH = ROOT / "backend/tests/fixtures/c_route_output.simulated.json"
EVENT_FIXTURE_PATH = ROOT / "backend/tests/fixtures/b_updates.simulated.json"
REPORT_PATH = ROOT / "data/sim/m0-verification.json"


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
    config = _read(root / CONFIG_PATH.relative_to(ROOT))
    route_fixture = _read(root / ROUTE_FIXTURE_PATH.relative_to(ROOT))
    event_fixture = _read(root / EVENT_FIXTURE_PATH.relative_to(ROOT))
    stored = _read(root / RESULT_PATH.relative_to(ROOT))
    routes, supplies = routes_from_contract(
        route_fixture, config["route_supply"], fixture=True
    )
    kwargs = dict(
        scenario_id=config["scenario_id"],
        routes=routes,
        supplies=supplies,
        population=int(config["population"]),
        seed=int(config["seed"]),
        window_min=float(config["window_min"]),
        time_range=tuple(config["time_range"]),
        assumptions=list(config["assumptions"]),
    )
    first = run_simulation(**kwargs)
    second = run_simulation(**kwargs)

    plan = build_diversion_plan(
        {
            "event_id": config["scenario_id"],
            "demand": config["population"],
            "window_min": config["window_min"],
            "routes": config["route_supply"],
        }
    )
    monitor = ReplanningMonitor()
    event_decisions = [
        apply_b_update(monitor, adapt_b_update(item, fixture=True))
        for item in event_fixture["event_updates"]
    ]

    store = PrecomputedResultStore(root / "data/sim")
    started = perf_counter()
    cached = store.read(config["scenario_id"])
    cache_under_target = (perf_counter() - started) * 1000 < 300

    guided_users = sum(item["users"] for item in first["guided"]["shares"])
    plan_users = sum(item["users"] for item in plan["shares"])
    physical_capacity_by_route = {
        supply.route_id: supply.service_capacity(float(config["window_min"]))
        for supply in supplies
    }
    protected = Agent("sim_protected", "O", "D", "wheelchair", "wheelchair", 400)
    protected_best = RouteOption("best", 10, 0, 0, 0, 0.9, ("MTR",), True)
    protected_slower = RouteOption("slower", 11, 0, 0, 0, 0.9, ("MTR",), True)
    protected_routes = (protected_best, protected_slower)
    protected_supplies = {
        route.route_id: RouteSupply(
            route.route_id,
            3600,
            capacity,
            provenance="simulated",
            note="Synthetic protected personal-best acceptance fixture",
        )
        for route, capacity in ((protected_best, 10), (protected_slower, 20))
    }
    protected_rankings = _personal_rankings((protected,), protected_routes)
    protected_assignments, _ = _guided_assignments(
        (protected,),
        protected_routes,
        protected_supplies,
        protected_rankings,
        60,
    )
    checks = {
        "route_fields": all(
            route.route_id
            and route.eta_min > 0
            and route.freshness_s >= 0
            and supply.headway_s > 0
            and supply.capacity_per_hour > 0
            for route, supply in zip(routes, supplies)
        ),
        "simulated_only": all(
            _all_simulated(value)
            for value in (config, route_fixture, event_fixture, first, plan)
        ),
        "fixed_seed_reproducible": first == second,
        "precomputed_matches_model": first == stored == cached,
        "capacity_conserved": guided_users + first["guided"]["unstoppable_demand"] == first["population"],
        "physical_capacity_respected": all(
            item["users"] <= physical_capacity_by_route[item["route_id"]]
            for item in first["guided"]["shares"]
        ),
        "diversion_plan_conserved": plan_users + plan["unstoppable_demand"] == plan["demand"],
        "fairness_enforced": (
            first["fairness"]["max_extra_delay_min"] == 15.0
            and first["fairness"]["protected_users"] > 0
        ),
        "protected_personal_best_preserved": (
            protected_assignments.get(protected.agent_id) == protected_best.route_id
        ),
        "unmet_demand_reported": first["guided"]["unstoppable_demand"] > 0,
        "event_change_replans": len(event_decisions) >= 2 and event_decisions[-1].should_replan,
        "cache_read_under_300ms": cache_under_target,
    }
    return {
        "check_id": "c-sim-m0-simulated",
        "command": "python scripts/verify_sim_m0.py",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scenario_id": config["scenario_id"],
        "seed": config["seed"],
        "population": first["population"],
        "route_ids": [route.route_id for route in routes],
        "unstoppable_demand": first["guided"]["unstoppable_demand"],
        "fixture_files": [
            str(ROUTE_FIXTURE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(EVENT_FIXTURE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        ],
        "provenance": "simulated",
        "scope": "Algorithm and adapter acceptance only; no verified C-Data is connected.",
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
            "check_id": "c-sim-m0-simulated",
            "command": "python scripts/verify_sim_m0.py",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "provenance": "simulated",
            "scope": "Algorithm and adapter acceptance only; no verified C-Data is connected.",
        }
    output = write_report(report)
    print(f"{report['status']} C-Sim M0 simulated acceptance: {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
