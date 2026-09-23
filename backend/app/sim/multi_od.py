"""Internal multi-OD simulation path built on the existing C-Sim allocator."""

from __future__ import annotations

from collections import Counter

from backend.app.engine.fairness import check_extra_delay, is_accessible, rank_routes

from .adapters import ODRouteSet
from .population import DEFAULT_SEED, generate_population
from .run import _guided_assignments


TARGET_CANDIDATES_PER_OD = 10


def run_multi_od_simulation(
    *,
    scenario_id: str,
    route_sets: tuple[ODRouteSet, ...],
    population: int = 300,
    seed: int = DEFAULT_SEED,
    window_min: float = 60.0,
) -> dict:
    """Run OD-scoped allocation without changing the public ``SimResult``.

    Route ids must already be unique across OD sets. Candidate shortages and
    per-OD unmet demand are returned as internal M0 diagnostics rather than as
    new public-contract fields.
    """

    if not scenario_id:
        raise ValueError("scenario_id is required")
    if not route_sets:
        raise ValueError("at least one OD route set is required")
    if population < 0:
        raise ValueError("population cannot be negative")
    if window_min <= 0:
        raise ValueError("window_min must be positive")

    raw_weights = {route_set.od: route_set.demand_weight for route_set in route_sets}
    if len(raw_weights) != len(route_sets):
        raise ValueError("OD route sets must be unique")
    weight_total = sum(raw_weights.values())
    od_weights = {od: weight / weight_total for od, weight in raw_weights.items()}
    agents = generate_population(population, seed=seed, od_weights=od_weights)
    agents_by_od = {
        route_set.od: tuple(
            agent
            for agent in agents
            if (agent.origin, agent.destination) == route_set.od
        )
        for route_set in route_sets
    }

    assigned_by_agent: dict[str, str] = {}
    wrong_od_assignments = 0
    wheelchair_constraint_violations = 0
    fairness_violations = 0
    protected_non_best_assignments = 0
    capacity_violations = 0
    od_results: list[dict] = []

    for route_set in route_sets:
        od_agents = agents_by_od[route_set.od]
        rankings = {
            agent.agent_id: rank_routes(agent, route_set.routes)
            for agent in od_agents
        }
        eligible_agents = tuple(
            agent for agent in od_agents if rankings[agent.agent_id]
        )
        supply_by_id = {supply.route_id: supply for supply in route_set.supplies}
        assignments, protected_by_rule = _guided_assignments(
            eligible_agents,
            route_set.routes,
            supply_by_id,
            rankings,
            window_min,
        )
        assigned_by_agent.update(assignments)
        eligible_route_ids = {route.route_id for route in route_set.routes}
        route_by_id = {route.route_id: route for route in route_set.routes}
        route_counts = Counter(assignments.values())
        capacity_violations += sum(
            int(route_counts[route_id] > supply.service_capacity(window_min))
            for route_id, supply in supply_by_id.items()
        )

        for agent in eligible_agents:
            route_id = assignments.get(agent.agent_id)
            if route_id is None:
                continue
            if route_id not in eligible_route_ids:
                wrong_od_assignments += 1
                continue
            route = route_by_id[route_id]
            personal_best = rankings[agent.agent_id][0]
            if not check_extra_delay(agent, route, personal_best).allowed:
                fairness_violations += 1
            if agent.fairness_priority and route_id != personal_best.route_id:
                protected_non_best_assignments += 1
            if agent.mobility == "wheelchair" and not is_accessible(agent, route).allowed:
                wheelchair_constraint_violations += 1

        unmet = len(od_agents) - len(assignments)
        wheelchair_agents = {
            agent.agent_id for agent in od_agents if agent.mobility == "wheelchair"
        }
        od_results.append(
            {
                "origin": route_set.origin,
                "destination": route_set.destination,
                "demand": len(od_agents),
                "candidate_count": len(route_set.routes),
                "candidate_shortage": max(
                    0, TARGET_CANDIDATES_PER_OD - len(route_set.routes)
                ),
                "eligible_demand": len(eligible_agents),
                "assigned_demand": len(assignments),
                "unmet_demand": unmet,
                "wheelchair_unmet_demand": len(wheelchair_agents - assignments.keys()),
                "protected_by_rule": len(protected_by_rule),
                "provenance": route_set.provenance,
            }
        )

    assigned = len(assigned_by_agent)
    unmet = population - assigned
    return {
        "check_id": "c-sim-m0-multi-od-simulated",
        "scenario_id": scenario_id,
        "population": population,
        "seed": seed,
        "od_count": len(route_sets),
        "assigned_demand": assigned,
        "unmet_demand": unmet,
        "candidate_shortage_total": sum(
            row["candidate_shortage"] for row in od_results
        ),
        "od_results": od_results,
        "invariants": {
            "capacity_conserved": assigned + unmet == population,
            "wrong_od_assignments": wrong_od_assignments,
            "capacity_violations": capacity_violations,
            "wheelchair_constraint_violations": wheelchair_constraint_violations,
            "fairness_violations": fairness_violations,
            "protected_non_best_assignments": protected_non_best_assignments,
        },
        "provenance": (
            "simulated"
            if all(route_set.provenance == "simulated" for route_set in route_sets)
            else "mixed"
        ),
    }
