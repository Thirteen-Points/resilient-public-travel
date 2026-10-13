"""Framework-neutral service functions behind the simulation endpoints."""

from __future__ import annotations

from pathlib import Path
import math
from uuid import uuid5, NAMESPACE_URL

from backend.app.engine.load import RouteSupply, allocate_capacity_buckets
from backend.app.engine.queue import estimate_queue

from .cache import PrecomputedResultStore
from .shared_capacity import SharedResource, allocate_shared_buckets


def build_diversion_plan(payload: dict) -> dict:
    raw_demand = payload["demand"]
    if isinstance(raw_demand, bool) or not isinstance(raw_demand, int) or raw_demand < 0:
        raise ValueError("demand must be a non-negative integer")
    demand = raw_demand
    window_min = float(payload.get("window_min", 60))
    if not math.isfinite(window_min) or window_min <= 0:
        raise ValueError("window_min must be finite and positive")
    event_id = str(payload["event_id"])
    unique_supplies: dict[str, RouteSupply] = {}
    for item in payload["routes"]:
        supply = RouteSupply.from_route_output(item)
        previous = unique_supplies.get(supply.route_id)
        if previous is not None and previous != supply:
            raise ValueError(f"conflicting supply inputs for route_id {supply.route_id}")
        unique_supplies.setdefault(supply.route_id, supply)
    supplies = tuple(unique_supplies.values())
    # Optional private integration metadata: public response names stay frozen.
    resources = tuple(SharedResource(
        resource_id=item["resource_id"], route_ids=tuple(item["route_ids"]),
        service_capacity_per_hour=float(item["service_capacity_per_hour"]),
        headway_s=float(item["headway_s"]), target_factor=float(item.get("target_factor", 0.85)),
        provenance=item.get("provenance", "simulated"),
    ) for item in payload.get("shared_resources", ()))
    allocation = (allocate_shared_buckets(demand, supplies, resources, window_min) if resources else
                  allocate_capacity_buckets(demand, supplies, window_min=window_min))
    supply_by_id = {supply.route_id: supply for supply in supplies}
    allocated_counts = {share.route_id: share.users for share in allocation.shares}
    resource_waits = {}
    for resource in resources:
        if resource.service_capacity_per_hour <= 0:
            resource_waits[resource.resource_id] = window_min * 60
            continue
        users = sum(allocated_counts.get(rid, 0) for rid in resource.route_ids)
        resource_waits[resource.resource_id] = estimate_queue(
            demand_per_hour=users * 60 / window_min,
            service_capacity_per_hour=resource.service_capacity_per_hour,
            headway_s=resource.headway_s,
        ).expected_wait_s
    shares = []
    for share in allocation.shares:
        supply = supply_by_id[share.route_id]
        demand_per_hour = share.users * 60.0 / window_min
        queue = estimate_queue(
            demand_per_hour=demand_per_hour,
            service_capacity_per_hour=supply.service_capacity_per_hour,
            headway_s=supply.headway_s,
        )
        item = share.to_contract(demand)
        item.update(
            {
                "expected_wait_s": round(max([queue.expected_wait_s,
                    *(resource_waits[resource.resource_id] for resource in resources if share.route_id in resource.route_ids)]), 3),
                "board_refusal_prob": round(queue.board_refusal_prob, 6),
            }
        )
        shares.append(item)
    advice = []
    if allocation.unstoppable_demand:
        advice.append(
            f"Capacity shortfall: {allocation.unstoppable_demand:,} passengers/{int(window_min)} min; consider travelling later or waiting for additional official services."
        )
    stable_key = f"{event_id}:{demand}:{window_min}:" + ",".join(
        f"{item.route_id}:{item.capacity_per_hour:.6f}" for item in supplies
    )
    if resources:
        stable_key += ":" + repr(tuple(sorted((item.resource_id, tuple(sorted(item.route_ids)),
                                                item.service_capacity_per_hour, item.target_factor)
                                               for item in resources)))
    return {
        "plan_id": "dp_" + uuid5(NAMESPACE_URL, stable_key).hex[:16],
        "event_id": event_id,
        "demand": demand,
        "window_min": window_min,
        "shares": shares,
        "unstoppable_demand": allocation.unstoppable_demand,
        "advice": advice,
        "fairness": {
            "max_extra_delay_min": 15,
            "protected_users": 0,
            "note": "The aggregate endpoint has no individual profiles; fairness constraints are enforced in the 10,000-person simulation allocation.",
        },
        "provenance": "simulated",
    }


def default_result_store(repository_root: Path) -> PrecomputedResultStore:
    return PrecomputedResultStore(repository_root / "data" / "sim")
