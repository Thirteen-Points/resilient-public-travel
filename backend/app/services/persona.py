"""Conservative preference extraction; route computation remains deterministic."""

from __future__ import annotations

import re
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


CRITERIA = {"time", "transfers", "walk", "price", "comfort", "reliability", "carbon", "freshness"}
PRICE_WEIGHTS = {"time": 0.25, "transfers": 0.10, "walk": 0.10, "price": 0.35,
                 "comfort": 0.05, "reliability": 0.10, "carbon": 0.025, "freshness": 0.025}
MOBILITY_RANK = {"standard": 0, "reduced": 1, "wheelchair": 2}


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobility: str | None = None
    max_walk_m: int | None = Field(default=None, ge=0, le=800)
    hard_flags: list[str] = Field(default_factory=list)
    price_sensitive: float | None = Field(default=None, ge=0, le=1)
    weights: dict[str, float] | None = None

    @field_validator("mobility")
    @classmethod
    def known_mobility(cls, value: str | None) -> str | None:
        if value is not None and value not in MOBILITY_RANK:
            raise ValueError("unknown mobility")
        return value

    @field_validator("hard_flags")
    @classmethod
    def known_flags(cls, value: list[str]) -> list[str]:
        allowed = {"no_stairs", "no_minibus", "no_non_lowfloor_bus"}
        if set(value) - allowed:
            raise ValueError("unknown hard flag")
        return sorted(set(value))

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is not None and (set(value) != CRITERIA or
                                  any(not 0 <= weight <= 1 for weight in value.values()) or
                                  abs(sum(value.values()) - 1) > 1e-6):
            raise ValueError("weights must cover known criteria and sum to one")
        return value


class PreferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch: ProfilePatch
    explanation: str = Field(min_length=1, max_length=300)
    method: str


class PreferenceClient(Protocol):
    def generate_json(self, *, system_prompt: str, user_prompt: str,
                      json_schema: Mapping[str, Any], timeout_seconds: float) -> str | Mapping[str, Any]: ...


PERSONA_DATA = Path(__file__).resolve().parents[3] / "data" / "personas.json"
PRESET_DATA = PERSONA_DATA.with_name("presets.json")


class PersonaProfile(BaseModel):
    """Simulated defaults passed as a complete profile to route queries."""

    model_config = ConfigDict(extra="forbid")
    persona: str
    mobility: str
    max_walk_m: int = Field(ge=0, le=800)
    max_transfers: int = Field(ge=0)
    preset: str
    hard_flags: list[str]
    weights: dict[str, float]

    @field_validator("mobility")
    @classmethod
    def known_mobility(cls, value: str) -> str:
        if value not in MOBILITY_RANK:
            raise ValueError("unknown mobility")
        return value

    @field_validator("hard_flags")
    @classmethod
    def known_flags(cls, value: list[str]) -> list[str]:
        return ProfilePatch.known_flags(value)

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value: dict[str, float]) -> dict[str, float]:
        return ProfilePatch.valid_weights(value)


def load_personas() -> list[PersonaProfile]:
    document = json.loads(PERSONA_DATA.read_text(encoding="utf-8"))
    if document.get("meta", {}).get("provenance") != "simulated":
        raise ValueError("persona defaults must be marked simulated")
    profiles = [PersonaProfile.model_validate(item) for item in document["personas"]]
    if [item.persona for item in profiles] != ["commuter", "student", "tourist", "elderly", "wheelchair"]:
        raise ValueError("persona catalog does not match the agreed contract")
    wheelchair = profiles[-1]
    if (wheelchair.mobility != "wheelchair" or wheelchair.max_walk_m > 400 or
            not {"no_stairs", "no_minibus", "no_non_lowfloor_bus"}.issubset(wheelchair.hard_flags)):
        raise ValueError("wheelchair catalog must retain hard accessibility limits")
    return profiles


def load_presets() -> dict[str, dict[str, float]]:
    document = json.loads(PRESET_DATA.read_text(encoding="utf-8"))
    if document.get("meta", {}).get("provenance") != "simulated":
        raise ValueError("preset defaults must be marked simulated")
    presets = document["presets"]
    if set(presets) != {"fastest", "most_stable", "fewest_transfers"}:
        raise ValueError("preset catalog does not match the agreed contract")
    return {name: ProfilePatch.valid_weights(weights) for name, weights in presets.items()}


def _rule_patch(text: str) -> ProfilePatch:
    reduced = any(word in text for word in ("腿脚不便", "腿腳不便", "行动不便", "行動不便", "少走路"))
    wheelchair = any(word in text for word in ("轮椅", "輪椅", "wheelchair"))
    cheap = any(word in text for word in ("别太贵", "別太貴", "便宜", "省钱", "省錢", "cheap", "低价"))
    flags = ["no_stairs"] if reduced else []
    if wheelchair:
        flags = ["no_stairs", "no_minibus", "no_non_lowfloor_bus"]
    return ProfilePatch(
        mobility="wheelchair" if wheelchair else ("reduced" if reduced else None),
        max_walk_m=400 if reduced or wheelchair else None,
        hard_flags=flags,
        price_sensitive=0.8 if cheap else None,
        weights=PRICE_WEIGHTS if cheap else None,
    )


def parse_preference(text: str, *, client: PreferenceClient | None = None,
                     current_profile: Mapping[str, Any] | None = None) -> PreferenceResult:
    if not text or not text.strip() or len(text) > 500:
        raise ValueError("free_text must contain 1 to 500 characters")
    base = _rule_patch(text.lower())
    method = "rule_fallback"
    candidate = base
    if client is not None:
        # Remove common contact identifiers before sending preference text.
        redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
        redacted = re.sub(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)(?!\d)", "[phone]", redacted)
        try:
            raw = client.generate_json(
                system_prompt="Extract only stated travel preferences as ProfilePatch JSON. No routes, times, fares, personal identity or invented facts. Return JSON only.",
                user_prompt=redacted,
                json_schema=ProfilePatch.model_json_schema(),
                timeout_seconds=10.0,
            )
            candidate = ProfilePatch.model_validate_json(raw) if isinstance(raw, str) else ProfilePatch.model_validate(raw)
            method = "llm"
        except Exception:
            # A model or network failure must not block the preference form.
            candidate = base
    # A model may add restrictions but cannot undo explicit text or an existing
    # accessibility profile. Unknown text never clears existing hard limits.
    previous = current_profile or {}
    if previous.get("mobility") not in (None, *MOBILITY_RANK):
        raise ValueError("unknown current mobility")
    previous_flags = previous.get("hard_flags") or ()
    if not isinstance(previous_flags, (list, tuple, set)) or not all(isinstance(flag, str) for flag in previous_flags):
        raise ValueError("invalid current hard flags")
    if set(previous_flags) - {"no_stairs", "no_minibus", "no_non_lowfloor_bus"}:
        raise ValueError("unknown current hard flag")
    mobility = max((item for item in (candidate.mobility, base.mobility, previous.get("mobility")) if item),
                   key=lambda item: MOBILITY_RANK[item], default=None)
    flags = sorted(set(candidate.hard_flags) | set(base.hard_flags) | set(previous_flags))
    if mobility == "wheelchair":
        flags = sorted(set(flags) | {"no_stairs", "no_minibus", "no_non_lowfloor_bus"})
    previous_limit = previous.get("max_walk_m")
    if previous_limit is not None and (not isinstance(previous_limit, int) or not 0 <= previous_limit <= 800):
        raise ValueError("invalid current walking limit")
    limits = [value for value in (candidate.max_walk_m, base.max_walk_m, previous_limit) if value is not None]
    patch = ProfilePatch(mobility=mobility, hard_flags=flags,
                         max_walk_m=min(limits) if limits else None,
                         price_sensitive=max((value for value in (candidate.price_sensitive, base.price_sensitive)
                                              if value is not None), default=None),
                         weights=base.weights or candidate.weights)
    if mobility == "wheelchair" and (patch.max_walk_m is None or patch.max_walk_m > 400):
        patch.max_walk_m = 400
    explanation = "已保留无障碍限制；" if mobility in {"reduced", "wheelchair"} else ""
    explanation += "已提高价格偏好。" if patch.price_sensitive is not None else "仅使用明确提及的偏好；其他设置保持原样。"
    return PreferenceResult(patch=patch, explanation=explanation, method=method)
