"""Small OpenAI-compatible JSON adapter for the T2.6 structurer.

This adapter does not log prompts, raw responses, or API credentials. The
structurer validates the returned content and owns its one retry and fallback.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from typing import Any

from ...ai.llm_client import Provider


class StructureJsonClient:
    def __init__(self, provider: Provider) -> None:
        if not provider.api_key:
            raise ValueError("provider API key is required")
        self.provider = provider

    def generate_json(
        self, *, system_prompt: str, user_prompt: str,
        json_schema: Mapping[str, Any], timeout_seconds: float,
    ) -> str:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        payload = {
            "model": self.provider.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nRequired JSON Schema:\n"
                 + json.dumps(json_schema, ensure_ascii=False)},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.provider.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.provider.api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.load(response)
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("provider returned no JSON content")
        return content
