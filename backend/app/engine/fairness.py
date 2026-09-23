"""Accessibility and maximum-extra-delay constraints for diversion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


FAIRNESS_MAX_EXTRA_MIN = 15.0


class AgentLike(Protocol):
    persona: str
    mobility: str
    max_walk_m: int


class RouteLike(Protocol):
    route_id: str
    eta_min: float
    transfers: int
    walk_m: int
    fare_hkd: float
    reliability: float
    modes: tuple[str, ...]
    accessible: bool


@dataclass(frozen=True, slots=True)
class FairnessDecision:
    allowed: bool
    reason: str | None = None


PERSONA_WEIGHTS: dict[str, dict[str, float]] = {
    "commuter": {"time": 0.50, "transfers": 0.10, "walk": 0.10, "price": 0.10, "reliability": 0.20},
    "student": {"time": 0.25, "transfers": 0.10, "walk": 0.10, "price": 0.45, "reliability": 0.10},
    "tourist": {"time": 0.20, "transfers": 0.35, "walk": 0.15, "price": 0.10, "reliability": 0.20},
    "elderly": {"time": 0.25, "transfers": 0.15, "walk": 0.25, "price": 0.05, "reliability": 0.30},
    "wheelchair": {"time": 0.20, "transfers": 0.10, "walk": 0.30, "price": 0.05, "reliability": 0.35},
}


def is_accessible(agent: AgentLike, route: RouteLike) -> FairnessDecision:
    if route.walk_m > agent.max_walk_m:
        return FairnessDecision(False, "max_walk_exceeded")
    if agent.mobility in {"reduced", "wheelchair"}:
        if "MINIBUS" in route.modes:
            return FairnessDecision(False, "minibus_not_accessible")
        if not route.accessible:
            return FairnessDecision(False, "route_not_fully_accessible")
    return FairnessDecision(True)


def rank_routes(agent: AgentLike, routes: Iterable[RouteLike]) -> list[RouteLike]:
    candidates = [route for route in routes if is_accessible(agent, route).allowed]
    if not candidates:
        return []

    min_eta = min(route.eta_min for route in candidates)
    max_eta = max(route.eta_min for route in candidates)
    max_fare = max((route.fare_hkd for route in candidates), default=0.0)
    weights = PERSONA_WEIGHTS[agent.persona]

    def utility(route: RouteLike) -> tuple[float, str]:
        time_span = max_eta - min_eta
        time_score = 1.0 if time_span == 0 else 1.0 - (route.eta_min - min_eta) / time_span
        transfer_score = 1.0 / (1.0 + route.transfers)
        walk_score = max(0.0, 1.0 - route.walk_m / max(agent.max_walk_m, 1))
        price_score = 1.0 if max_fare == 0 else max(0.0, 1.0 - route.fare_hkd / max_fare)
        score = (
            weights["time"] * time_score
            + weights["transfers"] * transfer_score
            + weights["walk"] * walk_score
            + weights["price"] * price_score
            + weights["reliability"] * route.reliability
        )
        return score, route.route_id

    return sorted(candidates, key=lambda route: (-utility(route)[0], utility(route)[1]))


def check_extra_delay(
    agent: AgentLike,
    proposed: RouteLike,
    personal_best: RouteLike,
    *,
    max_extra_delay_min: float = FAIRNESS_MAX_EXTRA_MIN,
) -> FairnessDecision:
    accessibility = is_accessible(agent, proposed)
    if not accessibility.allowed:
        return accessibility
    if proposed.eta_min - personal_best.eta_min > max_extra_delay_min + 1e-9:
        return FairnessDecision(False, "max_extra_delay_exceeded")
    return FairnessDecision(True)
