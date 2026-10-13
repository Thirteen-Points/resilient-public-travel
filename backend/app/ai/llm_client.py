"""OpenAI-compatible, optional LLM client with provider fallback and audit data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .fallback import no_ai_message
from .schemas import SchemaValidationError, validate_chat_response
from .tools import ToolRegistry

LOG = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a wording assistant for a transit system. You never generate routes,
stations, times, fares, headways, capacities, loads, delays, or simulation figures.
Use only function tools to obtain those facts. Do not invent numeric facts. Cite data
freshness and provenance supplied by tools. If a tool fails, say data is unavailable.
Write interface explanations in English. Preserve quoted source evidence in its original language.
Return a JSON object with exactly: message (string), tool_calls (array)."""


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    timeout_s: float = 10.0
    max_retries: int = 1
    cache_ttl_s: int = 900
    budget_cny: float = 50.0
    providers: tuple[Provider, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        def provider(prefix: str, default_url: str, default_model: str) -> Provider | None:
            key = os.getenv(f"{prefix}_API_KEY", "")
            if not key:
                return None
            return Provider(prefix.lower(), os.getenv(f"{prefix}_BASE_URL", default_url).rstrip("/"), key,
                            os.getenv(f"{prefix}_MODEL", default_model),
                            float(os.getenv(f"{prefix}_INPUT_COST_PER_MILLION", "0")),
                            float(os.getenv(f"{prefix}_OUTPUT_COST_PER_MILLION", "0")))
        providers = tuple(filter(None, (
            provider("DEEPSEEK", "https://api.deepseek.com", "deepseek-flash"),
            provider("QWEN", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.7-flash"),
            provider("GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4.5-flash"),
        )))
        return cls(enabled=os.getenv("AI_ENABLED", "false").lower() == "true", providers=providers,
                   timeout_s=float(os.getenv("AI_TIMEOUT_S", "10")),
                   cache_ttl_s=int(os.getenv("AI_CACHE_TTL_S", "900")),
                   budget_cny=float(os.getenv("AI_BUDGET_CNY", "50")))


@dataclass
class LLMResult:
    response: dict[str, Any]
    provider: str | None
    fallback: bool
    cached: bool = False
    tool_results: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    def __init__(self, config: LLMConfig | None = None, registry: ToolRegistry | None = None) -> None:
        self.config = config or LLMConfig.from_env()
        self.registry = registry
        self._cache: dict[str, tuple[float, LLMResult]] = {}
        self.call_log: list[dict[str, Any]] = []
        self.total_cost_cny = 0.0

    async def chat(self, user_message: str, *, tool_results: list[dict[str, Any]] | None = None) -> LLMResult:
        """Return language only; failure always yields the deterministic fallback."""
        supplied_tools = tool_results or []
        cache_key = self._cache_key(user_message, supplied_tools)
        cached = self._cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            result = cached[1]
            return LLMResult(result.response, result.provider, result.fallback, cached=True, tool_results=result.tool_results)
        if not self.config.enabled or not self.config.providers or self.total_cost_cny >= self.config.budget_cny:
            return LLMResult(no_ai_message(supplied_tools), None, True, tool_results=supplied_tools)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]
        if supplied_tools:
            messages.append({"role": "system", "content": "Deterministic tool results:\n" + json.dumps(supplied_tools, ensure_ascii=False)})
        for provider in self.config.providers:
            for attempt in range(self.config.max_retries + 1):
                try:
                    raw, usage = await self._request(provider, messages)
                    response = validate_chat_response(raw, supplied_tools)
                    cost = self._cost(provider, usage)
                    self.total_cost_cny += cost
                    result = LLMResult(response, provider.name, False, tool_results=supplied_tools)
                    self._cache[cache_key] = (time.monotonic() + self.config.cache_ttl_s, result)
                    self._log(provider.name, attempt, "ok", usage, cost)
                    return result
                except (OSError, urllib.error.URLError, urllib.error.HTTPError, asyncio.TimeoutError, SchemaValidationError, ValueError) as exc:
                    self._log(provider.name, attempt, "failed", {}, 0.0, str(exc))
                    LOG.warning("AI provider %s attempt %s failed: %s", provider.name, attempt + 1, exc)
        return LLMResult(no_ai_message(supplied_tools), None, True, tool_results=supplied_tools)

    async def call_tool(self, name: str, arguments: Mapping[str, Any] | str | None = None) -> dict[str, Any]:
        if self.registry is None:
            return {"ok": False, "error": "tool_registry_unavailable"}
        return await self.registry.call(name, arguments)

    def cost_summary(self) -> dict[str, Any]:
        """Expose a cheap-to-persist summary for the API health/metrics layer."""
        return {
            "spent_cny": round(self.total_cost_cny, 6),
            "budget_cny": self.config.budget_cny,
            "remaining_cny": round(max(0.0, self.config.budget_cny - self.total_cost_cny), 6),
            "calls": len(self.call_log),
        }

    async def _request(self, provider: Provider, messages: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {"model": provider.model, "messages": messages, "response_format": {"type": "json_object"}}
        if self.registry:
            payload["tools"] = self.registry.schemas()
        response = await asyncio.wait_for(asyncio.to_thread(self._post, provider, payload), timeout=self.config.timeout_s)
        choice = response["choices"][0]["message"]
        # Tool calls are deliberately returned to the API layer for deterministic execution.
        content = choice.get("content") or json.dumps({"message": "", "tool_calls": choice.get("tool_calls", [])})
        return json.loads(content), response.get("usage", {})

    @staticmethod
    def _post(provider: Provider, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(provider.base_url + "/chat/completions", data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())

    @staticmethod
    def _cache_key(message: str, tools: Iterable[dict[str, Any]]) -> str:
        return hashlib.sha256(json.dumps([message, list(tools)], sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _cost(provider: Provider, usage: Mapping[str, Any]) -> float:
        return (float(usage.get("prompt_tokens", 0)) * provider.input_cost_per_million + float(usage.get("completion_tokens", 0)) * provider.output_cost_per_million) / 1_000_000

    def _log(self, provider: str, attempt: int, status: str, usage: Mapping[str, Any], cost: float, error: str | None = None) -> None:
        self.call_log.append({"at": time.time(), "provider": provider, "attempt": attempt + 1, "status": status,
                              "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
                              "cost_cny": cost, "error": error})
