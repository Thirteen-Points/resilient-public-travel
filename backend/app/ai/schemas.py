"""Small, dependency-light validators for AI boundary objects."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping


class SchemaValidationError(ValueError):
    """The model response was not a safe response envelope."""


CHAT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["message", "tool_calls"],
    "properties": {
        "message": {"type": "string"},
        "tool_calls": {"type": "array"},
    },
    "additionalProperties": False,
}


def parse_json_object(value: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError("model response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise SchemaValidationError("model response must be a JSON object")
    return parsed


def validate_chat_response(value: str | Mapping[str, Any], tool_results: list[Any] | None = None) -> dict[str, Any]:
    """Validate the response and prohibit newly invented numeric facts.

    Numbers are permitted only when their literal representation appears in a
    deterministic tool result supplied for this response.  This deliberately
    errs on the safe side: if a model reformats a number it must omit it rather
    than make the route flow depend on unverified prose.
    """
    result = parse_json_object(value)
    if set(result) - {"message", "tool_calls"} or set(CHAT_RESPONSE_SCHEMA["required"]) - set(result):
        raise SchemaValidationError("response does not match the chat response schema")
    if not isinstance(result["message"], str) or not isinstance(result["tool_calls"], list):
        raise SchemaValidationError("invalid message or tool_calls type")
    if any(not isinstance(call, Mapping) for call in result["tool_calls"]):
        raise SchemaValidationError("tool_calls entries must be objects")

    allowed = set(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", json.dumps(tool_results or [], ensure_ascii=False)))
    produced = set(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", result["message"]))
    if produced - allowed:
        raise SchemaValidationError("model introduced a numeric fact not returned by a tool")
    evidence = json.dumps(tool_results or [], ensure_ascii=False).casefold()
    route_ids = re.findall(r"(?<![\w])r_[a-z0-9_-]+", result["message"], flags=re.IGNORECASE)
    line_names = re.findall(r"\b(?:[A-Z][a-z]+\s+){1,2}Line\b|[\u4e00-\u9fff]{2,}(?<!路)(?:线|綫)", result["message"])
    def grounded_line(token: str) -> bool:
        if token.casefold() in evidence:
            return True
        # Chinese sentences have no word boundary: "乘坐东铁线" may include
        # a grounded "东铁线" after an ordinary verb.
        return token.endswith(("线", "綫")) and any(token.endswith(suffix) and suffix in evidence
                for length in range(3, min(6, len(token)) + 1) for suffix in [token[-length:]])

    if any(token.casefold() not in evidence for token in route_ids) or any(not grounded_line(token) for token in line_names):
        raise SchemaValidationError("model introduced a route or line absent from tool results")
    if ('"provenance": "simulated"' in evidence and '"provenance": "real"' not in evidence
            and re.search(r"(?<!非)(?<!未)(?:实测客流|实时客流|已核实的客流|measured live ridership)", result["message"], re.IGNORECASE)):
        raise SchemaValidationError("model presented simulated data as measured ridership")
    return result
