"""Framework-neutral service functions behind the simulation endpoints."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from backend.app.engine.load import RouteSupply, allocate_capacity_buckets
from backend.app.engine.queue import estimate_queue

from .cache import PrecomputedResultStore


def build_diversion_plan(payload: dict) -> dict:
    demand = int(payload["demand"])
    window_min = float(payload.get("window_min", 60))
    event_id = str(payload["event_id"])
    supplies = tuple(RouteSupply.from_route_output(item) for item in payload["routes"])
    allocation = allocate_capacity_buckets(demand, supplies, window_min=window_min)
    supply_by_id = {supply.route_id: supply for supply in supplies}
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
                "expected_wait_s": round(queue.expected_wait_s, 3),
                "board_refusal_prob": round(queue.board_refusal_prob, 6),
            }
        )
        shares.append(item)
    advice = []
    if allocation.unstoppable_demand:
        advice.append(
            f"运力缺口 {allocation.unstoppable_demand:,} 人/{int(window_min)}分钟，建议错峰出发或等待官方加开服务"
        )
    stable_key = f"{event_id}:{demand}:{window_min}:" + ",".join(
        f"{item.route_id}:{item.capacity_per_hour:.6f}" for item in supplies
    )
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
            "note": "聚合端点未收到逐人画像；公平约束在 1 万人仿真分配中执行",
        },
        "provenance": "simulated",
    }


def default_result_store(repository_root: Path) -> PrecomputedResultStore:
    return PrecomputedResultStore(repository_root / "data" / "sim")
