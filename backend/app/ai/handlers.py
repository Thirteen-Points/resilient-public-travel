"""Bindings from AI tool names to C-Route/C-Sim deterministic services.

No network, route, capacity, ETA, or simulation value is calculated here.  The
adapter only selects already computed engine output and preserves its metadata.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable

from .tools import ToolHandler
from ..engine.constraints import normalize_profile


def build_engine_handlers(engine: Any, diversion_builder: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, ToolHandler]:
    """Return nine contract handlers bound to C engines and B preference rules."""
    state: dict[str, Any] = {"routes": {}, "parameters": {}}

    def metadata(records: list[dict[str, Any]]) -> tuple[str, float]:
        provenance = {record.get("provenance", "simulated") for record in records}
        result = "simulated" if "simulated" in provenance else ("real-derived" if "real-derived" in provenance else "real")
        ages = [record.get("total", {}).get("freshness_s", record.get("freshness_s", 0)) for record in records]
        return result, max(ages, default=0)

    def geocode_place(query: str) -> dict[str, Any]:
        needle = query.strip().casefold()
        nodes = engine.snapshots.current.network.nodes.values()
        node = next((item for item in nodes if needle in {str(item.get("id", "")).casefold(), str(item.get("name_zh", "")).casefold(), str(item.get("name_en", "")).casefold()}), None)
        if node is None:
            raise ValueError("place_not_found")
        return {"lat": node["lat"], "lng": node["lng"], "label": node.get("name_zh") or node["id"],
                "provenance": node["provenance"], "freshness_s": 0}

    def find_access_points(lat: float, lng: float, radius_m: float = 800) -> dict[str, Any]:
        if radius_m < 0:
            raise ValueError("radius_m must be nonnegative")
        points = []
        for node in engine.snapshots.current.network.nodes.values():
            # Equirectangular distance is deterministic filtering, never route generation.
            dx = (float(node["lng"]) - lng) * 111_320 * math.cos(math.radians(lat))
            dy = (float(node["lat"]) - lat) * 110_540
            if math.hypot(dx, dy) <= radius_m:
                points.append({"id": node["id"], "label": node.get("name_zh") or node["id"], "kind": node.get("kind"),
                               "lat": node["lat"], "lng": node["lng"], "accessible": node.get("accessible"),
                               "provenance": node["provenance"], "freshness_s": 0})
        provenance, freshness_s = metadata(points)
        return {"access_points": points, "provenance": provenance, "freshness_s": freshness_s}

    def search_transit_routes(**arguments: Any) -> dict[str, Any]:
        profile_id = arguments.get("profile_id")
        profiles = getattr(getattr(engine, "routing_data", None), "profiles", {}) or {}
        from ..graph.build import thaw
        profile = thaw(profiles.get(profile_id, {})) if profile_id else {}
        if profile_id in {"fastest", "most_stable", "fewest_transfers"}:
            profile["preset"] = profile_id
        elif profile_id and profile_id not in profiles:
            raise ValueError("unknown_profile_id")
        explicit = arguments.get("profile") or {}
        if not isinstance(explicit, dict):
            raise ValueError('profile must be an object')
        original = deepcopy(profile)
        profile.update(explicit)
        if original.get('mobility') in {'reduced', 'wheelchair'}:
            ranks = {'standard': 0, 'reduced': 1, 'wheelchair': 2}
            profile['mobility'] = max((original['mobility'], profile.get('mobility', 'standard')), key=ranks.__getitem__)
            profile['hard_flags'] = sorted(set(original.get('hard_flags', [])) | set(profile.get('hard_flags', [])))
            profile['max_walk_m'] = min(original.get('max_walk_m', 400), profile.get('max_walk_m', 400))
        pinned = engine.snapshots.current
        effective = normalize_profile(profile or None)
        details = engine.query_details(arguments["from"], arguments["to"], arguments["depart_at"],
                                       effective,
                                       modes=arguments.get("modes"))
        routes = deepcopy(details["routes"])
        state["routes"] = {route["route_id"]: route for route in routes}
        state["parameters"] = deepcopy(details["route_parameters"])
        state['details'] = deepcopy(details)
        state['snapshot'] = pinned
        state['depart_at'] = arguments['depart_at']
        provenance, freshness_s = metadata(routes)
        # graph_snapshot/effective_profile describe what the engine actually
        # used, so chat metadata can never drift from the computation.
        return {"routes": routes, "graph_snapshot": details["graph_snapshot"],
                "effective_profile": effective,
                "provenance": provenance, "freshness_s": freshness_s}

    def score_routes(route_ids: list[str], weights: dict[str, float] | None = None) -> dict[str, Any]:
        from ..engine.constraints import normalize_profile
        from ..engine.score import score_routes as native_score_routes
        routes = [state["routes"][route_id] for route_id in route_ids]
        scored = native_score_routes(routes, normalize_profile({"weights": weights} if weights else {}), baseline_fare=engine.baseline_fare)
        state["routes"] = {route["route_id"]: route for route in scored}
        provenance, freshness_s = metadata(scored)
        return {"routes": scored, "provenance": provenance, "freshness_s": freshness_s}

    def estimate_load(route_ids: list[str], horizon_min: int) -> dict[str, Any]:
        if horizon_min <= 0:
            raise ValueError("horizon_min must be positive")
        estimates = []
        for route_id in route_ids:
            route = state["routes"][route_id]
            estimate = deepcopy(route.get("load_estimate"))
            if estimate is None:
                raise ValueError("load_estimate_unavailable")
            estimate.update({"route_id": route_id, "provenance": route["provenance"], "freshness_s": route["total"]["freshness_s"]})
            estimates.append(estimate)
        provenance, freshness_s = metadata(estimates)
        return {"loads": estimates, "provenance": provenance, "freshness_s": freshness_s}

    def get_diversion_plan(event_id: str, demand: int) -> dict[str, Any]:
        supplies = []
        for route_id, route in state["routes"].items():
            parameters = deepcopy(state["parameters"].get(route_id, {}))
            if not parameters:
                raise ValueError("route_supply_unavailable")
            parameters.update({"route_id": route_id, "provenance": route["provenance"]})
            supplies.append(parameters)
        from dataclasses import asdict
        from ..sim.shared_capacity import resources_from_snapshot
        shared = resources_from_snapshot(state['snapshot'], state['details'], state['depart_at'])
        result = diversion_builder({"event_id": event_id, "demand": demand, "routes": supplies,
                                    "shared_resources": [asdict(resource) for resource in shared]})
        result["freshness_s"] = 0
        return result

    def get_published_events(at: str | None = None) -> dict[str, Any]:
        from datetime import datetime, timezone
        from ..graph.snapshot import active
        from ..graph.build import timestamp, thaw
        instant = timestamp(at) if at else datetime.now(timezone.utc)
        events = [thaw(event) for event in engine.snapshots.current.events if active(event, instant)]
        provenance, freshness_s = metadata(events)
        return {"events": events, "graph_snapshot": engine.snapshots.current.snapshot_id,
                "provenance": provenance, "freshness_s": freshness_s}

    def parse_user_preference(text: str, current_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        from ..services.persona import parse_preference
        return {**parse_preference(text, current_profile=current_profile).model_dump(),
                "provenance": "real-derived", "freshness_s": 0}

    def explain_route(route_id: str) -> dict[str, Any]:
        route = deepcopy(state["routes"][route_id])
        return {"route_id": route_id, "message": "The deterministic engine calculated this route. The scores below explain its ranking; check the warnings for capacity and weather assumptions.",
                "score": route.get("score"), "score_breakdown": route.get("score_breakdown", []),
                "notes": route.get("notes", []), "total": route["total"], "warnings": route.get("warnings", []),
                "graph_snapshot": route.get("graph_snapshot"), "provenance": route["provenance"],
                "freshness_s": route["total"]["freshness_s"]}

    return {"geocode_place": geocode_place, "find_access_points": find_access_points,
            "search_transit_routes": search_transit_routes, "score_routes": score_routes,
            "estimate_load": estimate_load, "get_diversion_plan": get_diversion_plan,
            "get_published_events": get_published_events, "parse_user_preference": parse_user_preference,
            "explain_route": explain_route}
