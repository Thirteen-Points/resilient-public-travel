"""Safe templates used whenever AI is disabled, unavailable, or invalid."""

from __future__ import annotations

from typing import Any


def no_ai_message(tool_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    successful = [item for item in tool_results or [] if item.get("ok")]
    if successful:
        return {"message": "已使用确定性出行数据生成结果；请查看路线卡中的来源、更新时间和免责声明。", "tool_calls": []}
    return {"message": "暂时取不到实时资料。路线计算仍可继续，请以路线卡中的来源和更新时间为准。", "tool_calls": []}


def parse_preference_rule_based(text: str) -> dict[str, Any]:
    """Conservative, explainable preference extraction with no made-up values."""
    lowered = text.lower()
    flags: list[str] = []
    if any(word in lowered for word in ("wheelchair", "轮椅")):
        flags.extend(["no_stairs", "no_minibus", "no_non_lowfloor_bus"])
    elif any(word in lowered for word in ("楼梯", "行动不便", "长者", "elderly")):
        flags.append("no_stairs")
    return {"patch": {"hard_flags": flags}, "explanation": "已按文本中的无障碍偏好应用确定性规则。"}
