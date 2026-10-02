"""Explicit, simulated directed-segment capacity shared by distinct paths.

This private scenario input does not extend RouteCandidate or SimResult.
Passengers consume one place on every used segment; opposite directions and
non-overlapping segments are separate resources. No observed residual load is
inferred from a route's capacity or from a line name alone.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import floor, isfinite

from backend.app.engine.load import BucketAllocation, BucketShare, RouteSupply


@dataclass(frozen=True, slots=True)
class SharedResource:
    resource_id: str
    route_ids: tuple[str, ...]
    service_capacity_per_hour: float
    headway_s: float
    target_factor: float = 0.85
    provenance: str = "simulated"

    def __post_init__(self) -> None:
        if not self.resource_id or not self.route_ids or len(set(self.route_ids)) != len(self.route_ids):
            raise ValueError("shared resource requires an id and unique non-empty route_ids")
        if any(not isinstance(rid, str) or not rid for rid in self.route_ids):
            raise ValueError("shared resource route_ids must be non-empty strings")
        if not isfinite(self.service_capacity_per_hour) or self.service_capacity_per_hour < 0:
            raise ValueError("shared resource service capacity must be finite and non-negative")
        if not isfinite(self.headway_s) or self.headway_s <= 0:
            raise ValueError("shared resource headway must be finite and positive")
        if not isfinite(self.target_factor) or not 0 < self.target_factor <= 1:
            raise ValueError("shared resource target factor must be within (0, 1]")
        if self.provenance not in {"real", "real-derived", "simulated"}:
            raise ValueError("unsupported shared resource provenance")

    def capacity(self, window_min: float, *, target: bool = False) -> int:
        return floor(self.service_capacity_per_hour * window_min / 60 * (self.target_factor if target else 1))


def validate_resources(resources: tuple[SharedResource, ...], route_ids: set[str]) -> None:
    if len({item.resource_id for item in resources}) != len(resources):
        raise ValueError("duplicate shared resource_id")
    for item in resources:
        if not set(item.route_ids) <= route_ids:
            raise ValueError(f"shared resource {item.resource_id} references unknown routes")


def allocate_shared_buckets(demand: int, supplies: tuple[RouteSupply, ...],
                            resources: tuple[SharedResource, ...], window_min: float) -> BucketAllocation:
    """Aggregate diversion with explicit shared resources and no persona data."""
    if demand < 0 or not isfinite(window_min) or window_min <= 0:
        raise ValueError("demand must be non-negative and window_min finite and positive")
    validate_resources(resources, {item.route_id for item in supplies})
    left = {item.resource_id: item.capacity(window_min, target=True) for item in resources}
    remaining = demand
    shares = []
    for supply in sorted(supplies, key=lambda item: (-item.capacity_per_hour, item.route_id)):
        shared = tuple(item for item in resources if supply.route_id in item.route_ids)
        route_capacity = supply.bucket_capacity(window_min)
        users = min(remaining, route_capacity, *(left[item.resource_id] for item in shared))
        if users:
            shares.append(BucketShare(supply.route_id, users, supply.capacity_per_hour,
                                      users / route_capacity if route_capacity else 0))
        remaining -= users
        for item in shared:
            left[item.resource_id] -= users
        if not remaining:
            break
    return BucketAllocation(demand, window_min, tuple(shares), remaining)


def resource_load(resources: tuple[SharedResource, ...], assignments: dict[str, str], window_min: float) -> list[dict]:
    counts = Counter(assignments.values())
    rows = []
    for item in resources:
        users = sum(counts[rid] for rid in item.route_ids)
        physical, target = item.capacity(window_min), item.capacity(window_min, target=True)
        rows.append({"resource_id": item.resource_id, "route_ids": list(item.route_ids),
                     "assigned_users": users, "service_capacity_per_hour": item.service_capacity_per_hour,
                     "physical_capacity": physical, "target_capacity": target,
                     "physical_capacity_excess": max(0, users - physical),
                     "target_capacity_excess": max(0, users - target), "provenance": item.provenance})
    return rows


def resources_from_seed(network: dict, od_payloads: list[dict], service_key: str) -> tuple[SharedResource, ...]:
    """Resolve actual route legs to seed stop-order segments, fail on ambiguity.

    Headways come from each leg, so calendar/weather-adjusted C-Route output
    is honored. The minimum observed throughput for a shared segment is used
    when legs disagree, an explicitly conservative stationary-window model.
    """
    lines = {line["id"]: line for line in network["lines"]}
    members: dict[str, set[str]] = {}
    inputs: dict[str, list[tuple[float, float]]] = {}
    for od in od_payloads:
        for route in od["routes"]:
            seen = set()
            for leg in route["legs"]:
                if leg["mode"] == "WALK":
                    continue
                line_id = leg.get("line")
                if line_id not in lines:
                    raise ValueError(f"unknown transit line {line_id}; explicit segment model required")
                line = lines[line_id]
                stops = line["stops"]
                start, end = stops.index(leg["from"]), stops.index(leg["to"])
                step = 1 if end > start else -1
                if end == start:
                    raise ValueError("transit leg must use distinct stops")
                headway = float(leg.get("headway_s") or line["headway_s"][service_key])
                physical = float(line["capacity_per_vehicle"]) * 3600 / headway
                for index in range(start, end, step):
                    key = f"{line_id}:{stops[index]}->{stops[index + step]}"
                    if key in seen:
                        raise ValueError(f"route {route['route_id']} traverses segment twice; multiplicity required")
                    seen.add(key)
                    members.setdefault(key, set()).add(route["route_id"])
                    inputs.setdefault(key, []).append((physical, headway))
    return tuple(SharedResource(key, tuple(sorted(members[key])),
                                min(cap for cap, _ in inputs[key]),
                                max(headway for _, headway in inputs[key])) for key in sorted(members))


def resources_from_snapshot(snapshot, route_details: dict, depart_at) -> tuple[SharedResource, ...]:
    """Project runtime route legs onto one pinned graph's shared resources.

    Uses graph boarding/calendar and approved segment/weather effects. This
    stationary-window projection is still a simulation, with no inferred
    residual occupancy. A graph revision mismatch fails instead of pairing a
    stale path with new supply. Walking-only candidates are omitted.
    """
    from backend.app.graph.build import timestamp

    if route_details.get("graph_snapshot") != snapshot.snapshot_id:
        raise ValueError("route and shared-capacity graph snapshots differ")
    at = timestamp(depart_at)
    lines = {line["id"]: line for line in snapshot.network.source["lines"]}
    edges = {(edge.line, edge.source, edge.target): edge for edge in snapshot.network.edges
             if edge.mode != "WALK"}
    members: dict[str, set[str]] = {}
    values: dict[str, tuple[float, float]] = {}
    for route in route_details["routes"]:
        rid = route["route_id"]
        parameters = route_details["route_parameters"].get(rid, {})
        if parameters.get("headway_s", 0) <= 0:
            continue
        seen = set()
        for leg in route["legs"]:
            if leg["mode"] == "WALK":
                continue
            line_id = leg.get("line")
            if line_id not in lines:
                raise ValueError(f"unknown transit line {line_id}; explicit shared resources required")
            stops = lines[line_id]["stops"]
            start, end = stops.index(leg["from"]), stops.index(leg["to"])
            if start == end:
                raise ValueError("transit leg must use distinct stops")
            step = 1 if end > start else -1
            for index in range(start, end, step):
                source, target = stops[index], stops[index + step]
                key = f"{line_id}:{source}->{target}"
                if key in seen:
                    raise ValueError(f"route {rid} repeats shared segment; multiplicity required")
                seen.add(key)
                edge = edges.get((line_id, source, target))
                if edge is None:
                    raise ValueError(f"route segment {key} absent from pinned graph")
                factor = snapshot.impact(edge, at)[0]
                weather_open = snapshot.weather_effect(edge.mode, at)[0] > 0
                boarding = snapshot.network.boarding(edge, at, factor) if factor > 0 and weather_open else None
                if boarding is None:
                    physical, headway = 0.0, float(leg.get("headway_s", 1) or 1)
                else:
                    _, headway = boarding
                    physical = float(edge.data["capacity_per_vehicle"]) * 3600 / headway
                members.setdefault(key, set()).add(rid)
                previous = values.get(key)
                values[key] = (min(physical, previous[0]), max(headway, previous[1])) if previous else (physical, headway)
    return tuple(SharedResource(key, tuple(sorted(members[key])), *values[key]) for key in sorted(members))
