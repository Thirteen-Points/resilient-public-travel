"""Validated, synthetic UserProfile presets for the six-station demo."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


PERSONAS = frozenset({"commuter", "student", "tourist", "elderly", "wheelchair"})
CRITERIA = frozenset({"time", "transfers", "walk", "price", "comfort", "reliability", "carbon", "freshness"})
HARD_FLAGS = frozenset({"no_stairs", "no_minibus", "no_non_lowfloor_bus"})
DEFAULT_PERSONAS_PATH = Path(__file__).resolve().parents[3] / "data" / "personas.json"


class UserProfile(BaseModel):
    """Strict local representation of docs/plan/03-contracts.md §3.3."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    user_id: str = Field(min_length=1)
    persona: Literal["commuter", "student", "tourist", "elderly", "wheelchair"]
    mobility: Literal["standard", "reduced", "wheelchair"]
    walking_speed_mps: float = Field(gt=0)
    max_walk_m: int = Field(ge=0)
    max_transfers: int = Field(ge=0)
    price_sensitive: float = Field(ge=0, le=1)
    has_discount_card: StrictBool
    urgency: str = Field(min_length=1)
    preset: Literal["fastest", "most_stable", "fewest_transfers"]
    weights: dict[str, float]
    hard_flags: list[str]
    note: str = Field(min_length=1)

    @field_validator("walking_speed_mps", "price_sensitive")
    @classmethod
    def numeric_value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("numeric profile values must be finite")
        return value

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, values: dict[str, float]) -> dict[str, float]:
        if set(values) != CRITERIA:
            raise ValueError("weights must contain exactly the eight route criteria")
        if any(not math.isfinite(value) or value < 0 for value in values.values()):
            raise ValueError("weights must be finite and nonnegative")
        if not math.isclose(sum(values.values()), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("weights must sum to 1")
        return values

    @field_validator("hard_flags")
    @classmethod
    def validate_hard_flags(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or set(values) - HARD_FLAGS:
            raise ValueError("hard_flags must be unique and known to the route engine")
        return values

    @model_validator(mode="after")
    def protect_accessibility(self) -> "UserProfile":
        if self.persona == "wheelchair" and (
            self.mobility != "wheelchair" or self.max_walk_m > 400
            or not HARD_FLAGS.issubset(self.hard_flags)
        ):
            raise ValueError("wheelchair profile must retain conservative accessibility limits")
        return self


def load_personas(path: str | Path = DEFAULT_PERSONAS_PATH) -> tuple[UserProfile, ...]:
    """Validate one versioned data file; return fresh models on every call."""

    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("personas data must be a list")
    profiles = tuple(UserProfile.model_validate(item) for item in payload)
    if len(profiles) != len(PERSONAS) or {item.persona for item in profiles} != PERSONAS:
        raise ValueError("personas data must contain each of the five personas once")
    if len({item.user_id for item in profiles}) != len(profiles):
        raise ValueError("persona user_id values must be unique")
    return profiles
