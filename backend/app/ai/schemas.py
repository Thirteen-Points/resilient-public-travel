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
    return result
