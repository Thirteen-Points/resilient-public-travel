"""Bounded loopless time-dependent search with strict node-set diversity."""
from __future__ import annotations

import hashlib
import heapq
import itertools
import math
from dataclasses import dataclass
from datetime import timedelta

from ..graph.build import timestamp
from ..graph.snapshot import active
from .constraints import allows_edge, edge_accessible
from .eco import estimates
from .walk import distance_m, walking_seconds


@dataclass(frozen=True)
class Traversal:
    edge: object
    depart: object
    arrive: object
    headway_s: float
    factor: float
    events: tuple
    boarding: bool
    nominal_headway_s: float


@dataclass
class SearchResult:
    paths: list
    expanded: int
    truncated: bool


def search_paths(snapshot, origin, destination, depart_at, profile, *, modes=None,
                 max_expansions=30000, max_paths=500):
    network, depart_at = snapshot.network, timestamp(depart_at)
    if origin not in network.nodes or destination not in network.nodes:
        raise ValueError("Unknown origin or destination node")
    if origin == destination:
        return SearchResult([], 0, False)
    allowed_modes = set(modes or {"MTR", "BUS", "MINIBUS", "FERRY", "WALK"}) | {"WALK"}
    serial = itertools.count()
    # elapsed, deterministic tie-breaker, node, visited, path, walk, boardings, onboard
    queue = [(0.0, next(serial), origin, frozenset({origin}), (), 0.0, 0, None)]
    found, expanded = [], 0
    while queue and expanded < max_expansions and len(found) < max_paths:
        elapsed, _, node, visited, path, walked, boardings, onboard = heapq.heappop(queue)
        if node == destination:
            found.append(path)
            continue
        expanded += 1
        at = depart_at + timedelta(seconds=elapsed)
        for edge in network.adjacency[node]:
            if edge.target in visited or edge.mode not in allowed_modes or not allows_edge(edge, network, profile):
                continue
            walk = walked + edge.walk_m
            boarding = edge.mode != "WALK" and onboard != edge.line
            next_boardings = boardings + boarding
            walk_limit = profile.get("max_walk_m")
            if (walk_limit is not None and walk > walk_limit) or max(0, next_boardings - 1) > profile["max_transfers"]:
                continue
            factor, slow, event_ids = snapshot.impact(edge, at)
            if factor == 0:
                continue
            departure, headway = at, (path[-1].headway_s if path and not boarding and edge.mode != "WALK" else 0)
            if boarding:
                schedule = network.boarding(edge, at, factor)
                if schedule is None:
                    continue
                departure, headway = schedule
                # A scheduled closure/reduction may begin during the platform wait.
                new_factor, slow, event_ids = snapshot.impact(edge, departure)
                if new_factor == 0:
                    continue
                if new_factor != factor:
                    schedule = network.boarding(edge, departure, new_factor)
                    if schedule is None:
                        continue
                    departure, headway = schedule
                    factor = new_factor
            duration = walking_seconds(edge.walk_m, profile["walking_speed_mps"]) if edge.mode == "WALK" else edge.travel_s * slow
            arrival = departure + timedelta(seconds=duration)
            end_factor, _, end_ids = snapshot.impact(edge, departure, arrival)
            if end_factor == 0:
                continue
            nominal_headway = headway * factor if boarding else (path[-1].nominal_headway_s if path and edge.mode != "WALK" else 0)
            traversal = Traversal(edge, departure, arrival, headway, min(factor, end_factor),
                                  tuple(sorted(set(event_ids + end_ids))), boarding, nominal_headway)
            heapq.heappush(queue, ((arrival - depart_at).total_seconds(), next(serial), edge.target,
                                  visited | {edge.target}, path + (traversal,), walk, next_boardings,
                                  edge.line if edge.mode != "WALK" else None))
    return SearchResult(found, expanded, bool(queue))


def intermediate_nodes(path):
    return frozenset(t.edge.target for t in path[:-1])


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def transfer_nodes(path):
    previous = None
    nodes = set()
    walked_since = False
    for step in path:
        if step.edge.mode == "WALK":
            walked_since = True
        else:
            if previous is not None and (previous != step.edge.line or walked_since):
                nodes.add(step.edge.source)
            previous, walked_since = step.edge.line, False
    return nodes


def select_diverse(paths, limit=10):
    """Exclude OD endpoints from intermediate-node Jaccard (< 0.7).

    Reserve early selection for an additional transit mode when feasible. Never
    pad with duplicates or relax hard constraints to meet a requested count.
    """
    selected, node_sets, interchange_counts = [], [], {}
    remaining = list(paths)
    covered_modes = set()
    while remaining and len(selected) < limit:
        feasible = []
        for path in remaining:
            nodes, transfers = intermediate_nodes(path), transfer_nodes(path)
            if any(jaccard(nodes, old) >= .7 for old in node_sets):
                continue
            if any(interchange_counts.get(n, 0) >= 2 for n in transfers):
                continue
            modes = {t.edge.mode for t in path if t.edge.mode != "WALK"}
            priority = 0 if covered_modes and len(covered_modes) < 2 and modes - covered_modes else 1
            feasible.append((priority, path, nodes, transfers, modes))
        if not feasible:
            break
        _, path, nodes, transfers, modes = min(feasible, key=lambda x: x[0])
        selected.append(path)
        node_sets.append(nodes)
        covered_modes |= modes
        for n in transfers:
            interchange_counts[n] = interchange_counts.get(n, 0) + 1
        remaining.remove(path)
    return selected


def route_from_path(path, snapshot, depart_at, *, fares, profile=None):
    network, depart_at = snapshot.network, timestamp(depart_at)
    legs, warnings, evidence, notes = [], [], [], []
    co2, comfort_sum, moving_time, fare, freshness = 0., 0., 0., 0., 0.
    leg_sigmas, leg_factors = [], []
    freshness_scores, capacities, event_ids = [], [], set()
    boardings = 0
    previous_fare_group = None
    for step in path:
        edge, data = step.edge, step.edge.data
        duration = (step.arrive - step.depart).total_seconds()
        length = edge.walk_m if edge.mode == "WALK" else distance_m(network.nodes[edge.source], network.nodes[edge.target])
        weather = any(e.get("event_type") == "weather" and e["event_id"] in step.events for e in snapshot.events)
        model = estimates(edge.mode, length, duration, step.factor, weather)
        co2 += model["co2_g"]
        if legs and edge.mode != "WALK" and not step.boarding and legs[-1].get("line") == edge.line:
            leg_sigmas[-1] += model["sigma_s"]
            leg_factors[-1] = min(leg_factors[-1], step.factor)
        else:
            leg_sigmas.append(model["sigma_s"])
            leg_factors.append(step.factor)
        moving_time += duration
        event_ids.update(step.events)
        amount = 0.
        if step.boarding:
            boardings += 1
            tariff = fares[edge.line]
            group = tariff['group']
            amount = tariff['fare_hkd'] if group is None or group != previous_fare_group else 0
            previous_fare_group = group
            if tariff['note']:
                warnings.append(tariff['note'])
        fare += amount
        built_at = data.get("updated_at") or network.source.get("meta", {}).get("built_at")
        if built_at:
            age = max(0., (step.depart - timestamp(built_at)).total_seconds())
        else:
            age = float(data.get("freshness_s", 86400))
            warnings.append("缺少数据时间，按至少 24 小时旧数据估算")
        freshness = max(freshness, age)
        tau = 900 if data.get("realtime", False) else 21600
        freshness_scores.append(math.exp(-age / tau))
        if age > tau:
            warnings.append(f"{edge.line or '步行通道'} 数据较旧")
        if step.events:
            warnings.append(f"{edge.line or '步行通道'} 受事件影响，运力系数 {step.factor:g}")
        if data.get("note"):
            warnings.append(data["note"])
        if edge.mode != "WALK":
            capacity = data["capacity_per_vehicle"]
            # Preserve the boarded service's headway after the final boarding time.
            capacities.append(3600 / step.nominal_headway_s * capacity * step.factor * .85)
        mobility = (profile or {}).get("mobility", "standard")
        accessible = edge_accessible(edge, network, mobility)
        assumed_fare = edge.mode != "WALK" and fares[edge.line]["provenance"] == "simulated"
        leg = {"mode": edge.mode, "from": edge.source, "to": edge.target,
               "depart": step.depart.isoformat(), "arrive": step.arrive.isoformat(),
               "headway_s": step.headway_s, "in_vehicle_s": duration, "walk_m": edge.walk_m,
               "fare_hkd": amount, "accessible": accessible,
               "provenance": "simulated" if assumed_fare or data.get("provenance") == "simulated" else "real-derived"}
        if edge.mode == "WALK":
            leg.pop("headway_s")  # No vehicle service interval or boarding wait.
        if edge.line:
            leg["line"] = edge.line
        if legs and edge.mode != "WALK" and not step.boarding and legs[-1].get("line") == edge.line:
            legs[-1]["to"] = edge.target
            legs[-1]["arrive"] = leg["arrive"]
            legs[-1]["in_vehicle_s"] += duration
            legs[-1]["fare_hkd"] += amount
            legs[-1]["accessible"] &= accessible
        else:
            legs.append(leg)
        evidence.append({"source": edge.line or edge.id, "freshness_s": age})
    elapsed = (path[-1].arrive - depart_at).total_seconds()
    sigma = math.sqrt(sum(s * s for s in leg_sigmas))
    comfort_sum = sum(estimates(leg["mode"], 0, leg["in_vehicle_s"], factor)["comfort"] * leg["in_vehicle_s"]
                      for leg, factor in zip(legs, leg_factors))
    # Published closure evidence explains why alternatives were selected.
    event_ids |= {e["event_id"] for e in snapshot.events if active(e, depart_at)}
    evidence.extend({"event_id": eid, "used": True} for eid in sorted(event_ids))
    evidence.append({"source": "route_model_v1", "freshness_s": 0})
    warnings.append("碳排放、舒适度和 ETA 方差采用模拟系数；距离使用节点直线距离推算")
    if (profile or {}).get("mobility") == "wheelchair":
        warnings.append("轮椅 M0 演示规则：MTR/大巴默认可用、小巴排除；明确不可达或部分可达标记仍排除")
    walked = sum(t.edge.walk_m for t in path)
    if walked > 500:
        warnings.append(f"较长步行：全程累计 {walked:g} 米，请预留时间")
    signature = "|".join(t.edge.id for t in path)
    return {
        "route_id": "r_" + hashlib.sha256(signature.encode()).hexdigest()[:16],
        "label": " + ".join(leg.get("line", "步行") for leg in legs), "legs": legs,
        "total": {"time_s": elapsed, "time_range_s": [max(0, elapsed - 1.28155 * sigma), elapsed + 1.28155 * sigma],
                  "transfers": max(0, boardings - 1), "walk_m": sum(t.edge.walk_m for t in path),
                  "fare_hkd": fare, "co2_g": co2, "reliability": max(0, 1 - sigma / elapsed) if elapsed else 1,
                  "freshness_s": freshness},
        "score": 0, "score_breakdown": [], "load_estimate": None,
        "warnings": list(dict.fromkeys(warnings)), "notes": notes, "explain": "", "evidence": evidence,
        "provenance": "simulated",
        "_metrics": {"comfort": comfort_sum / moving_time if moving_time else 1,
                     "freshness_score": min(freshness_scores, default=0),
                     "capacity_per_hour": min(capacities, default=0),
                     "service_capacity_per_hour": min(capacities, default=0) / .85,
                     "headway_s": max((t.nominal_headway_s / t.factor for t in path), default=0),
                     "provenance": "simulated"},
    }
