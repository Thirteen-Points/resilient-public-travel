"""Safe templates used whenever AI is disabled, unavailable, or invalid."""

from __future__ import annotations

from typing import Any


def no_ai_message(tool_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    successful = [item for item in tool_results or [] if item.get("ok")]
    if successful:
        return {"message": "Results use deterministic journey data. Check the route cards for sources, update times and data limitations.", "tool_calls": []}
    return {"message": "Current information is unavailable. Route calculation can continue; check the route cards for sources and update times.", "tool_calls": []}


def parse_preference_rule_based(text: str) -> dict[str, Any]:
    """Conservative, explainable preference extraction with no made-up values."""
    lowered = text.lower()
    flags: list[str] = []
    if any(word in lowered for word in ("wheelchair", "轮椅")):
        flags.extend(["no_stairs", "no_minibus", "no_non_lowfloor_bus"])
    elif any(word in lowered for word in ("楼梯", "行动不便", "长者", "elderly")):
        flags.append("no_stairs")
    return {"patch": {"hard_flags": flags}, "explanation": "Deterministic rules applied the accessibility preferences explicitly stated in your text."}
