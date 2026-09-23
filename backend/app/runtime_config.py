"""Small, dependency-free runtime configuration for the local M0 service."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    ai_enabled: bool = _bool("AI_ENABLED", False)
    offline_mode: bool = _bool("OFFLINE_MODE", True)
    seed_network: str = os.getenv("SEED_NETWORK", "contracts/seed/network.seed.json")
    seed_events: str = os.getenv("SEED_EVENTS", "contracts/seed/event.seed.json")
    deep_health_origin: str = os.getenv("DEEP_HEALTH_ORIGIN", "TAW")
    deep_health_destination: str = os.getenv("DEEP_HEALTH_DESTINATION", "ADM")
    deep_health_depart_at: str = os.getenv(
        "DEEP_HEALTH_DEPART_AT", "2026-09-22T08:20:00+08:00"
    )

    def missing_runtime_config(self) -> list[str]:
        problems: list[str] = []
        if self.ai_enabled and not any(
            os.getenv(f"{provider}_API_KEY") for provider in ("DEEPSEEK", "QWEN", "GLM")
        ):
            problems.append(
                "AI_ENABLED=true but no *_API_KEY is configured; using deterministic fallback"
            )
        if not 1 <= self.port <= 65535:
            problems.append("PORT must be between 1 and 65535")
        return problems


settings = Settings()
