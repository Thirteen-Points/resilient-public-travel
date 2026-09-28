"""Deterministic, no-LLM query orchestration for the chat endpoint."""

from __future__ import annotations

from typing import Any

from .fallback import no_ai_message
from .tools import ToolRegistry


class NoLLMQueryService:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def query(self, *, user_input: str, origin: str, destination: str, depart_at: str,
                    profile_id: str | None = None, event_id: str | None = None, demand: int | None = None) -> dict[str, Any]:
        routes = await self.registry.call("search_transit_routes", {"from": origin, "to": destination,
                                          "depart_at": depart_at, "profile_id": profile_id} if profile_id else
                                         {"from": origin, "to": destination, "depart_at": depart_at})
        if not routes["ok"]:
            return {"message": no_ai_message([routes]), "tool_calls": [routes], "fallback": True}
        route_data = routes["data"]
        # C-Route's production handlers return RouteCandidate[], while the
        # early AI adapter returns {routes: RouteCandidate[]}.  Both are read
        # only formats and normalization here avoids a second route engine.
        route_list = route_data["routes"] if isinstance(route_data, dict) else route_data
        route_ids = [route["route_id"] for route in route_list]
        loads = await self.registry.call("estimate_load", {"route_ids": route_ids, "horizon_min": 60})
        tool_calls = [routes, loads]
        diversion = None
        if event_id and demand is not None:
            diversion = await self.registry.call("get_diversion_plan", {"event_id": event_id, "demand": demand})
            tool_calls.append(diversion)
        message = no_ai_message(tool_calls)["message"]
        # The route engine targets roughly ten diverse candidates.  When its
        # deterministic constraints leave fewer, say so plainly; never pad the
        # response with an invented alternative.
        if len(route_list) < 10:
            message += " 当前 OD 的可行候选少于目标数量；系统仅展示引擎计算出的候选，不补造路线。"
        return {"message": message, "tool_calls": tool_calls, "routes": route_list,
                "loads": loads.get("data"), "diversion": diversion.get("data") if diversion else None, "fallback": True,
                "user_input": user_input}
