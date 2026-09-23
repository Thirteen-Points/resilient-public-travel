"""Bindings from AI tool names to C-Route/C-Sim deterministic services.

No network, route, capacity, ETA, or simulation value is calculated here.  The
adapter only selects already computed engine output and preserves its metadata.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable

from .tools import ToolHandler


def build_engine_handlers(engine: Any, diversion_builder: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, ToolHandler]:
    """Return six contract handlers bound to a C-Route engine and C-Sim builder."""
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
        details = engine.query_details(arguments["from"], arguments["to"], arguments["depart_at"],
                                       {"profile_id": arguments.get("profile_id")} if arguments.get("profile_id") else None,
                                       modes=arguments.get("modes"))
        routes = deepcopy(details["routes"])
        state["routes"] = {route["route_id"]: route for route in routes}
        state["parameters"] = deepcopy(details["route_parameters"])
        provenance, freshness_s = metadata(routes)
        return {"routes": routes, "graph_snapshot": details["graph_snapshot"], "provenance": provenance, "freshness_s": freshness_s}

    def score_routes(route_ids: list[str], weights: dict[str, float] | None = None) -> dict[str, Any]:
        from backend.app.engine.constraints import normalize_profile
        from backend.app.engine.score import score_routes as native_score_routes
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
        result = diversion_builder({"event_id": event_id, "demand": demand, "routes": supplies})
        result["freshness_s"] = 0
        return result

    return {"geocode_place": geocode_place, "find_access_points": find_access_points,
            "search_transit_routes": search_transit_routes, "score_routes": score_routes,
            "estimate_load": estimate_load, "get_diversion_plan": get_diversion_plan}
