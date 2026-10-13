"""Selfish-optimal versus capacity-guided population simulation."""

from __future__ import annotations

from collections import Counter
from statistics import quantiles
from typing import Iterable

from backend.app.engine.fairness import (
    FAIRNESS_MAX_EXTRA_MIN,
    check_extra_delay,
    rank_routes,
)
from backend.app.engine.load import RouteSupply
from backend.app.engine.queue import estimate_queue

from .models import Agent, RouteOption
from .population import DEFAULT_SEED, generate_population, population_summary
from .shared_capacity import SharedResource


def _percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[94]


def _personal_rankings(agents: Iterable[Agent], routes: tuple[RouteOption, ...]) -> dict[str, list[RouteOption]]:
    rankings: dict[str, list[RouteOption]] = {}
    for agent in agents:
        ranked = rank_routes(agent, routes)
        if not ranked:
            raise ValueError(f"no accessible route for {agent.agent_id}")
        rankings[agent.agent_id] = ranked
    return rankings


def _selfish_assignments(
    agents: tuple[Agent, ...], rankings: dict[str, list[RouteOption]]
) -> dict[str, str]:
    return {agent.agent_id: rankings[agent.agent_id][0].route_id for agent in agents}


def _guided_assignments(
    agents: tuple[Agent, ...],
    routes: tuple[RouteOption, ...],
    supplies: dict[str, RouteSupply],
    rankings: dict[str, list[RouteOption]],
    window_min: float,
) -> tuple[dict[str, str], set[str]]:
    """Preserve feasible protected optima, then fill the largest route buckets."""

    route_by_id = {route.route_id: route for route in routes}
    route_order = sorted(
        routes,
        key=lambda route: (-supplies[route.route_id].capacity_per_hour, route.route_id),
    )
    # Stable input ids make fixed-seed results reproducible.  Priority prevents
    # standard users consuming every accessible place before protected users.
    agent_order = sorted(agents, key=lambda agent: (not agent.fairness_priority, agent.agent_id))
    unassigned = {agent.agent_id for agent in agents}
    assigned: dict[str, str] = {}
    protected_by_rule: set[str] = set()
    target_remaining = {
        route.route_id: supplies[route.route_id].bucket_capacity(window_min)
        for route in routes
    }
    physical_remaining = {
        route.route_id: supplies[route.route_id].service_capacity(window_min)
        for route in routes
    }

    # A capacity-first route ordering must not divert protected users from an
    # available personal best. Reserve those feasible best choices before the
    # general bucket pass; all later accounting still uses the same hard
    # physical-capacity counters.
    for agent in agent_order:
        if not agent.fairness_priority:
            break
        personal_best = rankings[agent.agent_id][0]
        route_id = personal_best.route_id
        if physical_remaining[route_id] <= 0:
            continue
        decision = check_extra_delay(agent, personal_best, personal_best)
        if not decision.allowed:
            protected_by_rule.add(agent.agent_id)
            continue
        assigned[agent.agent_id] = route_id
        unassigned.remove(agent.agent_id)
        physical_remaining[route_id] -= 1
        target_remaining[route_id] = max(0, target_remaining[route_id] - 1)

    for route in route_order:
        route_id = route.route_id
        if physical_remaining[route_id] <= 0:
            continue
        for agent in agent_order:
            if physical_remaining[route_id] == 0:
                break
            if agent.agent_id not in unassigned:
                continue
            # Standard users stop at the target bucket. Protected users may
            # consume the remaining physical service capacity when no fair
            # alternative is available; the evaluator still reports that
            # target-capacity overload instead of hiding it.
            if not agent.fairness_priority and target_remaining[route_id] == 0:
                break
            personal_best = rankings[agent.agent_id][0]
            decision = check_extra_delay(agent, route, personal_best)
            if not decision.allowed:
                if agent.fairness_priority:
                    protected_by_rule.add(agent.agent_id)
                continue
            assigned[agent.agent_id] = route.route_id
            unassigned.remove(agent.agent_id)
            physical_remaining[route_id] -= 1
            target_remaining[route_id] = max(0, target_remaining[route_id] - 1)

    # Keep route_by_id referenced here so a bad id fails close to allocation.
    if any(route_id not in route_by_id for route_id in assigned.values()):
        raise AssertionError("guided allocator produced an unknown route")
    return assigned, protected_by_rule


def _evaluate_policy(
    *,
    policy: str,
    agents: tuple[Agent, ...],
    routes: tuple[RouteOption, ...],
    supplies: dict[str, RouteSupply],
    rankings: dict[str, list[RouteOption]],
    assignments: dict[str, str],
    window_min: float,
    shared_resources: tuple[SharedResource, ...] = (),
) -> tuple[dict, set[str]]:
    route_by_id = {route.route_id: route for route in routes}
    counts = Counter(assignments.values())
    served_ids: set[str] = set()
    waits_by_route: dict[str, float] = {}
    route_load: list[dict] = []
    overloaded_routes = 0

    for route in routes:
        users = counts.get(route.route_id, 0)
        supply = supplies[route.route_id]
        bucket_capacity = supply.bucket_capacity(window_min)
        service_capacity = supply.service_capacity(window_min)
        demand_per_hour = users * 60.0 / window_min
        queue = estimate_queue(
            demand_per_hour=demand_per_hour,
            service_capacity_per_hour=supply.service_capacity_per_hour,
            headway_s=supply.headway_s,
        )
        waits_by_route[route.route_id] = queue.expected_wait_s / 60.0
        overloaded = users > bucket_capacity
        overloaded_routes += int(overloaded)
        route_load.append(
            {
                "route_id": route.route_id,
                "users": users,
                "capacity_per_hour": round(supply.capacity_per_hour, 3),
                "load_factor": round(users / bucket_capacity, 6) if bucket_capacity else 0.0,
                "overloaded": overloaded,
            }
        )
        candidates = sorted(
            (agent_id for agent_id, assigned_route in assignments.items() if assigned_route == route.route_id)
        )
        served_ids.update(candidates[:service_capacity])

    if shared_resources:
        resources_by_route = {
            route.route_id: tuple(item for item in shared_resources if route.route_id in item.route_ids)
            for route in routes
        }
        # Both policies use the same protected-first boarding rule and the
        # same physical resources. Choosing a path does not guarantee boarding.
        route_left = {key: value.service_capacity(window_min) for key, value in supplies.items()}
        segment_left = {item.resource_id: item.capacity(window_min) for item in shared_resources}
        segment_counts = {
            item.resource_id: sum(counts[rid] for rid in item.route_ids) for item in shared_resources
        }
        for item in shared_resources:
            demand = segment_counts[item.resource_id] * 60 / window_min
            if item.service_capacity_per_hour == 0:
                wait_min = window_min
            else:
                wait_min = estimate_queue(demand_per_hour=demand,
                                          service_capacity_per_hour=item.service_capacity_per_hour,
                                          headway_s=item.headway_s).expected_wait_s / 60
            for rid in item.route_ids:
                waits_by_route[rid] = max(waits_by_route[rid], wait_min)
        served_ids.clear()
        for agent in sorted(agents, key=lambda item: (not item.fairness_priority, item.agent_id)):
            rid = assignments.get(agent.agent_id)
            if rid is None or route_left[rid] <= 0:
                continue
            segments = resources_by_route[rid]
            if any(segment_left[item.resource_id] <= 0 for item in segments):
                continue
            served_ids.add(agent.agent_id)
            route_left[rid] -= 1
            for item in segments:
                segment_left[item.resource_id] -= 1

    waits: list[float] = []
    total_delay = 0.0
    for agent in agents:
        assigned_route_id = assignments.get(agent.agent_id)
        if assigned_route_id is None:
            waits.append(window_min)
            total_delay += window_min
            continue
        route = route_by_id[assigned_route_id]
        extra_travel = max(0.0, route.eta_min - rankings[agent.agent_id][0].eta_min)
        if agent.agent_id in served_ids:
            wait = waits_by_route[assigned_route_id]
        else:
            wait = window_min
        waits.append(wait)
        total_delay += extra_travel + wait

    wheelchair_ids = {agent.agent_id for agent in agents if agent.persona == "wheelchair"}
    wheelchair_served = len(wheelchair_ids & served_ids)
    population = len(agents)
    metrics = {
        "policy": policy,
        "total_delay_person_min": round(total_delay, 1),
        "avg_delay_min": round(total_delay / population, 1) if population else 0.0,
        "p95_wait_min": round(_percentile_95(waits), 1),
        "overloaded_routes": overloaded_routes,
        "served_rate": round(len(served_ids) / population, 4) if population else 0.0,
        "wheelchair_served_rate": (
            round(wheelchair_served / len(wheelchair_ids), 4) if wheelchair_ids else 1.0
        ),
        "route_load": route_load,
    }
    return metrics, served_ids


def run_simulation(
    *,
    scenario_id: str,
    routes: tuple[RouteOption, ...],
    supplies: tuple[RouteSupply, ...],
    population: int = 10_000,
    seed: int = DEFAULT_SEED,
    window_min: float = 60.0,
    time_range: tuple[str, str] = ("08:00", "09:00"),
    assumptions: list[str] | None = None,
) -> dict:
    """Compute every headline value from model inputs; no benefit is forced."""

    if not scenario_id:
        raise ValueError("scenario_id is required")
    if not routes:
        raise ValueError("at least one route is required")
    if not assumptions:
        raise ValueError("assumptions must be non-empty")
    supply_by_id = {supply.route_id: supply for supply in supplies}
    if set(supply_by_id) != {route.route_id for route in routes}:
        raise ValueError("routes and supplies must have exactly matching route_ids")

    agents = generate_population(population, seed=seed)
    rankings = _personal_rankings(agents, routes)
    selfish = _selfish_assignments(agents, rankings)
    guided, protected_by_rule = _guided_assignments(
        agents, routes, supply_by_id, rankings, window_min
    )
    baseline, _ = _evaluate_policy(
        policy="selfish",
        agents=agents,
        routes=routes,
        supplies=supply_by_id,
        rankings=rankings,
        assignments=selfish,
        window_min=window_min,
    )
    guided_metrics, _ = _evaluate_policy(
        policy="bucket",
        agents=agents,
        routes=routes,
        supplies=supply_by_id,
        rankings=rankings,
        assignments=guided,
        window_min=window_min,
    )

    guided_counts = Counter(guided.values())
    shares = []
    for route in routes:
        users = guided_counts.get(route.route_id, 0)
        if users == 0:
            continue
        capacity = supply_by_id[route.route_id].bucket_capacity(window_min)
        shares.append(
            {
                "route_id": route.route_id,
                "share": round(users / population, 6) if population else 0.0,
                "users": users,
                "capacity_per_hour": round(supply_by_id[route.route_id].capacity_per_hour, 3),
                "load_factor": round(users / capacity, 6) if capacity else 0.0,
            }
        )
    unstoppable = population - len(guided)
    guided_metrics["unstoppable_demand"] = unstoppable
    guided_metrics["shares"] = shares
    advice = []
    if unstoppable:
        advice.append(
            f"Capacity shortfall: {unstoppable:,} passengers/{int(window_min)} min; consider travelling later or waiting for additional official services."
        )
    saturated = [item["route_id"] for item in shares if item["load_factor"] >= 0.999]
    if saturated:
        advice.append("Target capacity is full: " + ", ".join(saturated))
    guided_metrics["advice"] = advice

    def reduction(before: float, after: float) -> float:
        return round((before - after) / before * 100.0, 1) if before else 0.0

    result = {
        "scenario_id": scenario_id,
        "population": population,
        "time_range": list(time_range),
        "time_step_min": 1,
        "seed": seed,
        "population_summary": population_summary(agents),
        "baseline": baseline,
        "guided": guided_metrics,
        "delta": {
            "delay_reduction_pct": reduction(
                baseline["total_delay_person_min"], guided_metrics["total_delay_person_min"]
            ),
            "p95_wait_reduction_pct": reduction(
                baseline["p95_wait_min"], guided_metrics["p95_wait_min"]
            ),
            "served_rate_gain_pp": round(
                (guided_metrics["served_rate"] - baseline["served_rate"]) * 100.0, 1
            ),
            "overloaded_routes_delta": (
                guided_metrics["overloaded_routes"] - baseline["overloaded_routes"]
            ),
        },
        "fairness": {
            "max_extra_delay_min": FAIRNESS_MAX_EXTRA_MIN,
            "protected_users": len(protected_by_rule),
            "note": "Wheelchair users and older passengers receive accessible capacity first; all allocations enforce a 15-minute additional delay limit.",
        },
        "capacity_calculations": [supply.calculation() for supply in supplies],
        "assumptions": assumptions,
        "provenance": "simulated",
    }
    return result
