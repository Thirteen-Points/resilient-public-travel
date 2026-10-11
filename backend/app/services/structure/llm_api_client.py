"""Synchronous OpenAI-compatible JSON client for the event structurer.

The structurer boundary (LlmJsonClient) is deliberately narrow: one call that
returns JSON text or a mapping.  Providers follow the same environment
convention as the AI chat layer (AI_ENABLED plus DEEPSEEK_/QWEN_/GLM_ keys);
any failure raises so the structurer can retry once and then fall back to
deterministic rules.  No key is configured -> from_env() yields None and the
process stays fully offline.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

_PROVIDERS = (
    # (env prefix, default base_url, default model)
    ("DEEPSEEK", "https://api.deepseek.com", "deepseek-flash"),
    ("QWEN", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
    ("GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
)


class OpenAiCompatJsonClient:
    """Minimal adapter; retries and validation stay with the structurer."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        connect_timeout_s: float = 5.0,
        opener=None,
        request_timeout_s: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.connect_timeout_s = connect_timeout_s
        self.opener = opener or urllib.request.urlopen
        self.request_timeout_s = request_timeout_s
        self.usage = None

    @classmethod
    def from_env(cls) -> "OpenAiCompatJsonClient | None":
        for prefix, default_url, default_model in _PROVIDERS:
            api_key = os.getenv(f"{prefix}_API_KEY", "").strip()
            if api_key:
                return cls(
                    base_url=os.getenv(f"{prefix}_BASE_URL", default_url),
                    api_key=api_key,
                    model=os.getenv(f"{prefix}_MODEL", default_model),
                )
        return None

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any],
        timeout_seconds: float,
    ) -> str | Mapping[str, Any]:
        self.usage = None
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nRequired JSON schema:\n" + json.dumps(dict(json_schema), ensure_ascii=False)},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            # The schema is advisory context; strict validation happens in the
            # structurer, which owns the retry-once-then-fallback policy.
            "temperature": 0,
            "max_tokens": min(8192, max(1, int(os.getenv("AI_MAX_OUTPUT_TOKENS", "2048")))),
        }
        if self.base_url in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            payload["thinking"] = {"type": "disabled"}
        body = json.dumps(payload, ensure_ascii=False).encode()
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(
                request, timeout=min(timeout_seconds, self.request_timeout_s or (self.connect_timeout_s + 25))
            ) as response:
                result = json.loads(response.read().decode())
                self.usage = result.get("usage")
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise TimeoutError("provider timeout") from exc
            raise
        content = result["choices"][0]["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("provider returned no JSON content")
        json.loads(content)  # fail fast on malformed JSON text
        return content
