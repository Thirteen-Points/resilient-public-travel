"""M2 multi-OD simulation with one fixed population and shared route-id buckets."""

from __future__ import annotations

from collections import Counter
import math
from typing import Any

from backend.app.engine.fairness import check_extra_delay, rank_routes
from backend.app.sim.adapters import ODRouteSet
from backend.app.sim.models import Agent, RouteOption
from backend.app.sim.population import generate_population, population_summary
from backend.app.sim.run import _evaluate_policy


def _guided_multi_od(
    agents: tuple[Agent, ...],
    route_sets: tuple[ODRouteSet, ...],
    rankings: dict[str, list[RouteOption]],
    window_min: float,
) -> tuple[dict[str, str], set[str]]:
    """Allocate OD-local choices against globally shared route-id capacity."""
    routes_by_od = {item.od: item.routes for item in route_sets}
    supplies = {
        supply.route_id: supply
        for item in route_sets
        for supply in item.supplies
    }
    target_left = {key: value.bucket_capacity(window_min) for key, value in supplies.items()}
    physical_left = {key: value.service_capacity(window_min) for key, value in supplies.items()}
    assigned: dict[str, str] = {}
    protected: set[str] = set()
    ordered_agents = sorted(agents, key=lambda a: (not a.fairness_priority, a.agent_id))

    # Reserve an accessible personal best for protected users when available.
    for agent in ordered_agents:
        choices = rankings.get(agent.agent_id, [])
        if not agent.fairness_priority or not choices:
            continue
        best = choices[0]
        if physical_left[best.route_id] <= 0:
            continue
        if check_extra_delay(agent, best, best).allowed:
            assigned[agent.agent_id] = best.route_id
            physical_left[best.route_id] -= 1
            target_left[best.route_id] = max(0, target_left[best.route_id] - 1)
        else:
            protected.add(agent.agent_id)

    # Fill global buckets in capacity order, but only from the route set for
    # each passenger's OD. A route_id's supply is consumed exactly once.
    route_order = sorted(supplies, key=lambda key: (-supplies[key].capacity_per_hour, key))
    for route_id in route_order:
        if physical_left[route_id] <= 0:
            continue
        eligible_for_route = [
            agent for agent in ordered_agents
            if agent.agent_id not in assigned
            and any(route.route_id == route_id for route in routes_by_od.get((agent.origin, agent.destination), ()))
        ]
        for agent in eligible_for_route:
            if physical_left[route_id] <= 0:
                break
            if not agent.fairness_priority and target_left[route_id] <= 0:
                break
            route = next(route for route in routes_by_od[(agent.origin, agent.destination)] if route.route_id == route_id)
            personal_best = rankings[agent.agent_id][0]
            if not check_extra_delay(agent, route, personal_best).allowed:
                if agent.fairness_priority:
                    protected.add(agent.agent_id)
                continue
            assigned[agent.agent_id] = route_id
            physical_left[route_id] -= 1
            target_left[route_id] = max(0, target_left[route_id] - 1)
    return assigned, protected


def run_m2_multi_od(
    *,
    scenario_id: str,
    route_sets: tuple[ODRouteSet, ...],
    population: int,
    seed: int,
    window_min: float,
    time_range: tuple[str, str],
    assumptions: list[str],
) -> dict[str, Any]:
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id is required")
    if not route_sets:
        raise ValueError("at least one OD route set is required")
    if not assumptions:
        raise ValueError("assumptions must be non-empty")
    if isinstance(population, bool) or not isinstance(population, int) or population < 0:
        raise ValueError("population must be a non-negative integer")
    if not math.isfinite(window_min) or window_min <= 0:
        raise ValueError("window_min must be finite and positive")

    route_by_id: dict[str, RouteOption] = {}
    supply_by_id = {}
    seen_ods: set[tuple[str, str]] = set()
    for route_set in route_sets:
        if route_set.od in seen_ods:
            raise ValueError(f"duplicate OD route set: {route_set.origin}->{route_set.destination}")
        seen_ods.add(route_set.od)
        if not math.isfinite(route_set.demand_weight) or route_set.demand_weight <= 0:
            raise ValueError(f"{route_set.origin}->{route_set.destination} demand_weight must be finite and positive")
        route_ids = [route.route_id for route in route_set.routes]
        supply_ids = [supply.route_id for supply in route_set.supplies]
        if len(route_ids) != len(set(route_ids)) or set(route_ids) != set(supply_ids) or len(supply_ids) != len(set(supply_ids)):
            raise ValueError(
                f"{route_set.origin}->{route_set.destination} routes and supplies must have matching unique route_ids"
            )
        for route, supply in zip(route_set.routes, route_set.supplies, strict=True):
            old_route = route_by_id.get(route.route_id)
            if old_route and old_route != route:
                raise ValueError(f"shared route_id {route.route_id} has conflicting route semantics")
            old_supply = supply_by_id.get(supply.route_id)
            if old_supply and old_supply != supply:
                raise ValueError(f"shared route_id {supply.route_id} has conflicting supply inputs; cannot pool safely")
            route_by_id.setdefault(route.route_id, route)
            supply_by_id.setdefault(supply.route_id, supply)

    route_tuple = tuple(route_by_id.values())
    od_weights_raw = {item.od: item.demand_weight for item in route_sets}
    weight_total = sum(od_weights_raw.values())
    od_weights = {od: weight / weight_total for od, weight in od_weights_raw.items()}
    agents = generate_population(population, seed=seed, od_weights=od_weights)
    route_set_by_od = {item.od: item for item in route_sets}
    rankings: dict[str, list[RouteOption]] = {}
    for agent in agents:
        route_set = route_set_by_od[(agent.origin, agent.destination)]
        ranking = rank_routes(agent, route_set.routes)
        if ranking:
            rankings[agent.agent_id] = ranking

    baseline_assignments = {
        agent.agent_id: rankings[agent.agent_id][0].route_id
        for agent in agents if rankings.get(agent.agent_id)
    }
    guided_assignments, protected_blocked = _guided_multi_od(
        agents, route_sets, rankings, window_min
    )
    baseline, baseline_served = _evaluate_policy(
        policy="baseline_selfish", agents=agents, routes=route_tuple,
        supplies=supply_by_id, rankings=rankings, assignments=baseline_assignments,
        window_min=window_min,
    )
    guided, guided_served = _evaluate_policy(
        policy="guided_capacity_fair", agents=agents, routes=route_tuple,
        supplies=supply_by_id, rankings=rankings, assignments=guided_assignments,
        window_min=window_min,
    )

    def enrich(metrics: dict, assignments: dict[str, str], served_ids: set[str]) -> dict:
        counts = Counter(assignments.values())
        wheelchair_ids = {agent.agent_id for agent in agents if agent.persona == "wheelchair"}
        protected_ids = {agent.agent_id for agent in agents if agent.fairness_priority}
        return {
            **metrics,
            "assigned_demand": len(assignments),
            "served_demand": len(served_ids),
            "unmet_demand": population - len(served_ids),
            "unassigned_demand": population - len(assignments),
            "wheelchair_assigned": len(wheelchair_ids & assignments.keys()),
            "wheelchair_unmet": len(wheelchair_ids - served_ids),
            "protected_assigned": len(protected_ids & assignments.keys()),
            "protected_unmet": len(protected_ids - served_ids),
            "route_load": [
                {
                    **row,
                    "assigned_users": counts.get(row["route_id"], 0),
                    "target_capacity_excess": max(
                        0,
                        counts.get(row["route_id"], 0)
                        - supply_by_id[row["route_id"]].bucket_capacity(window_min),
                    ),
                    "physical_capacity_excess": max(
                        0,
                        counts.get(row["route_id"], 0)
                        - supply_by_id[row["route_id"]].service_capacity(window_min),
                    ),
                }
                for row in metrics["route_load"]
            ],
        }

    baseline = enrich(baseline, baseline_assignments, baseline_served)
    guided = enrich(guided, guided_assignments, guided_served)
    wheelchair_total = sum(agent.persona == "wheelchair" for agent in agents)
    protected_total = sum(agent.fairness_priority for agent in agents)
    return {
        "scenario_id": scenario_id,
        "population": population,
        "seed": seed,
        "time_range": list(time_range),
        "window_min": window_min,
        "od_count": len(route_sets),
        "candidate_count": sum(len(item.routes) for item in route_sets),
        "unique_route_id_count": len(route_by_id),
        "shared_route_id_count": sum(
            max(0, sum(route.route_id == rid for item in route_sets for route in item.routes) - 1)
            for rid in route_by_id
        ),
        "od_results": [
            {"origin": item.origin, "destination": item.destination,
             "demand_weight": item.demand_weight,
             "demand": sum((agent.origin, agent.destination) == item.od for agent in agents),
             "candidate_count": len(item.routes),
             "wheelchair_candidate_count": sum(route.accessible for route in item.routes),
             "provenance": item.provenance}
            for item in route_sets
        ],
        "baseline": baseline,
        "guided": guided,
        "delta": {
            "delay_reduction_pct": round((baseline["total_delay_person_min"] - guided["total_delay_person_min"]) / baseline["total_delay_person_min"] * 100, 1) if baseline["total_delay_person_min"] else 0,
            "served_rate_gain_pp": round((guided["served_rate"] - baseline["served_rate"]) * 100, 1),
            "wheelchair_served_rate_gain_pp": round((guided["wheelchair_served_rate"] - baseline["wheelchair_served_rate"]) * 100, 1),
            "overloaded_routes_delta": guided["overloaded_routes"] - baseline["overloaded_routes"],
        },
        "fairness": {
            "max_extra_delay_min": 15,
            "wheelchair_population": wheelchair_total,
            "protected_population": protected_total,
            "guided_protected_blocked_by_fairness_rule": len(protected_blocked),
            "wheelchair_accessibility_is_hard_filter": True,
        },
        "capacity_model": {
            "shared_route_id_supply_counted_once": True,
            "route_ids_are_capacity_buckets": True,
            "partial_segment_overlap_modelled": False,
            "shared_line_overlap": {},
            "note": "C-Route exposes route-level bottleneck capacity, not segment-level shared-service identities; distinct route_ids with overlapping legs cannot be safely pooled from current fields alone.",
        },
        "population_summary": population_summary(agents),
        "capacity_calculations": [item.calculation() for item in supply_by_id.values()],
        "assumptions": assumptions,
        "provenance": (
            route_sets[0].provenance
            if len({item.provenance for item in route_sets}) == 1
            else "mixed"
        ),
    }
