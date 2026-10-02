"""Deterministic tools exposed to a function-calling model.

Tools are adapters, not an alternative route engine: application startup injects
the real engine functions.  Every successful result gets trace metadata.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping


ToolHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def openai_schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


class ToolRegistry:
    def __init__(self, *, timeout_s: float | None = None) -> None:
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}
        self.audit_log: list[dict[str, Any]] = []
        self.timeout_s = timeout_s

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = (spec, handler)

    def schemas(self) -> list[dict[str, Any]]:
        return [item[0].openai_schema() for item in self._tools.values()]

    async def call(self, name: str, arguments: Mapping[str, Any] | str | None = None) -> dict[str, Any]:
        started = time.monotonic()
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
        except (ValueError, TypeError):
            return self._record(name, {}, started, {"ok": False, "error": "invalid_arguments"})
        if name not in self._tools:
            return self._record(name, args, started, {"ok": False, "error": "unknown_tool"})
        spec, handler = self._tools[name]
        missing = set(spec.parameters.get("required", [])) - set(args)
        if missing:
            return self._record(name, args, started, {"ok": False, "error": "missing_arguments", "missing": sorted(missing)})
        try:
            value = handler(**args)
            if inspect.isawaitable(value):
                value = await (asyncio.wait_for(value, self.timeout_s) if self.timeout_s else value)
            return self._record(name, args, started, {"ok": True, "data": value})
        except asyncio.TimeoutError:
            return self._record(name, args, started, {"ok": False, "error": "tool_timeout"})
        except Exception as exc:  # tools must never break chat/main route flow
            return self._record(name, args, started, {"ok": False, "error": "tool_unavailable", "detail": str(exc)})

    def _record(self, name: str, args: dict[str, Any], started: float, result: dict[str, Any]) -> dict[str, Any]:
        provenance, freshness_s = _metadata_from(result.get("data"))
        trace = {"tool": name, "arguments": args, "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "result": result,
                 "provenance": provenance, "freshness_s": freshness_s}
        self.audit_log.append(trace)
        del self.audit_log[:-512]
        return {**result, "trace": {"tool": name, "freshness_s": freshness_s, "provenance": provenance}}


def _metadata_from(value: Any) -> tuple[str, float]:
    """Keep source truth on an audit trace; computation itself is deterministic."""
    if isinstance(value, Mapping):
        provenance = value.get("provenance")
        freshness_s = value.get("freshness_s")
        if provenance in {"real", "real-derived", "simulated"} and isinstance(freshness_s, (int, float)):
            return provenance, float(freshness_s)
        for key in ("routes", "loads", "access_points"):
            if isinstance(value.get(key), list):
                return _metadata_from(value[key])
    if isinstance(value, list) and value:
        rows = [_metadata_from(item) for item in value]
        provenances = {row[0] for row in rows}
        # Mixed data must not be described as more authoritative than its least
        # verified constituent.  This mirrors the route/sim adapters' policy.
        provenance = "simulated" if "simulated" in provenances else ("real-derived" if "real-derived" in provenances else "real")
        return provenance, max(row[1] for row in rows)
    return "deterministic", 0.0


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def build_default_registry(handlers: Mapping[str, ToolHandler] | None = None) -> ToolRegistry:
    """Build the contract tool list; handlers can be replaced by real engines."""
    handlers = dict(handlers or {})
    registry = ToolRegistry()
    definitions = [
        ("geocode_place", "Resolve a place using deterministic local data.", _schema({"query": {"type": "string"}}, ["query"])),
        ("find_access_points", "Find deterministic station, bus or ferry access points.", _schema({"lat": {"type": "number"}, "lng": {"type": "number"}, "radius_m": {"type": "number", "default": 800}}, ["lat", "lng"])),
        ("search_transit_routes", "Search routes computed by the transit engine; never invent a route.", _schema({"from": {"type": "string"}, "to": {"type": "string"}, "depart_at": {"type": "string", "format": "date-time"}, "modes": {"type": "array", "items": {"type": "string"}}, "profile_id": {"type": "string"}}, ["from", "to", "depart_at"])),
        ("score_routes", "Return deterministic score breakdowns for existing route ids.", _schema({"route_ids": {"type": "array", "items": {"type": "string"}}, "weights": {"type": "object"}}, ["route_ids"])),
        ("estimate_load", "Return deterministic load estimates for existing route ids.", _schema({"route_ids": {"type": "array", "items": {"type": "string"}}, "horizon_min": {"type": "integer"}}, ["route_ids", "horizon_min"])),
        ("get_diversion_plan", "Return the deterministic diversion plan for an event and demand.", _schema({"event_id": {"type": "string"}, "demand": {"type": "integer"}}, ["event_id", "demand"])),
        ("get_published_events", "Read only reviewer-approved events active at the requested time.", _schema({"at": {"type": "string", "format": "date-time"}}, [])),
        ("parse_user_preference", "Extract explicit preferences without relaxing accessibility limits.", _schema({"text": {"type": "string", "maxLength": 500}, "current_profile": {"type": "object"}}, ["text"])),
        ("explain_route", "Explain an existing computed route using its score and source facts.", _schema({"route_id": {"type": "string"}}, ["route_id"])),
    ]
    for name, description, parameters in definitions:
        if name == 'search_transit_routes':
            parameters['properties']['profile'] = {'type': 'object', 'description': 'Explicit routing profile and hard accessibility constraints.'}
        registry.register(ToolSpec(name, description, parameters), handlers.get(name, _unconfigured_tool))
    return registry


def _unconfigured_tool(**_: Any) -> Any:
    raise RuntimeError("deterministic engine tool is not configured")
