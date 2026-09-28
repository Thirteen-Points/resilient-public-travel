"""Internal simulation models that adapt frozen public route fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Agent:
    agent_id: str
    origin: str
    destination: str
    persona: str
    mobility: str
    max_walk_m: int

    @property
    def fairness_priority(self) -> bool:
        return self.persona in {"elderly", "wheelchair"}


@dataclass(frozen=True, slots=True)
class RouteOption:
    route_id: str
    eta_min: float
    transfers: int
    walk_m: int
    fare_hkd: float
    reliability: float
    modes: tuple[str, ...]
    accessible: bool
    freshness_s: float = 0.0

    @classmethod
    def from_route_candidate(cls, route: dict) -> "RouteOption":
        """Read only existing RouteCandidate fields; do not extend the contract."""

        legs = route.get("legs", [])
        access_values = [leg.get("accessible", False) for leg in legs]
        return cls(
            route_id=str(route["route_id"]),
            eta_min=float(route["total"]["time_s"]) / 60.0,
            transfers=int(route["total"]["transfers"]),
            walk_m=int(route["total"]["walk_m"]),
            fare_hkd=float(route["total"]["fare_hkd"]),
            reliability=float(route["total"]["reliability"]),
            freshness_s=float(route["total"]["freshness_s"]),
            modes=tuple(str(leg["mode"]) for leg in legs),
            accessible=bool(access_values) and all(value is True for value in access_values),
        )
