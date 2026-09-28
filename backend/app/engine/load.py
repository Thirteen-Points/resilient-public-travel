"""Capacity-bucket calculations used by diversion and simulation.

``capacity_per_hour`` is the contract-facing target capacity.  It includes the
0.85 target occupancy factor.  Queueing uses ``service_capacity_per_hour``
instead, which is the physical throughput after the scenario availability
factor but before the target occupancy factor.  Keeping both values avoids
applying the 0.85 factor twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Iterable


ETA_MAX_FACTOR = 0.85


@dataclass(frozen=True, slots=True)
class RouteSupply:
    """Capacity inputs for one stable C-Route ``route_id``.

    ``available_capacity_factor`` represents the fraction of the physical
    service that remains available to this diversion scenario.  It must be
    labelled by the caller as real-derived or simulated; this model never
    invents it.
    """

    route_id: str
    headway_s: float
    vehicle_capacity: float
    available_capacity_factor: float = 1.0
    eta_max_factor: float = ETA_MAX_FACTOR
    provenance: str = "simulated"
    note: str = ""
    capacity_per_hour_override: float | None = None
    service_capacity_per_hour_override: float | None = None

    def __post_init__(self) -> None:
        if not self.route_id:
            raise ValueError("route_id is required")
        if self.headway_s <= 0:
            raise ValueError("headway_s must be positive")
        if self.vehicle_capacity <= 0:
            raise ValueError("vehicle_capacity must be positive")
        if not 0 <= self.available_capacity_factor <= 1:
            raise ValueError("available_capacity_factor must be within [0, 1]")
        if not 0 < self.eta_max_factor <= 1:
            raise ValueError("eta_max_factor must be within (0, 1]")
        if self.capacity_per_hour_override is not None and self.capacity_per_hour_override < 0:
            raise ValueError("capacity_per_hour_override cannot be negative")
        if (
            self.service_capacity_per_hour_override is not None
            and self.service_capacity_per_hour_override < 0
        ):
            raise ValueError("service_capacity_per_hour_override cannot be negative")
        if self.provenance not in {"real", "real-derived", "simulated"}:
            raise ValueError("unsupported provenance")

    @property
    def departures_per_hour(self) -> float:
        return 3600.0 / self.headway_s

    @property
    def raw_capacity_per_hour(self) -> float:
        return self.departures_per_hour * self.vehicle_capacity

    @property
    def service_capacity_per_hour(self) -> float:
        if self.service_capacity_per_hour_override is not None:
            return self.service_capacity_per_hour_override
        if self.capacity_per_hour_override is not None:
            return self.capacity_per_hour_override / self.eta_max_factor
        return self.raw_capacity_per_hour * self.available_capacity_factor

    @property
    def capacity_per_hour(self) -> float:
        """Target bucket capacity exposed by the frozen public contract."""

        if self.capacity_per_hour_override is not None:
            return self.capacity_per_hour_override
        return self.service_capacity_per_hour * self.eta_max_factor

    def bucket_capacity(self, window_min: float) -> int:
        if window_min <= 0:
            raise ValueError("window_min must be positive")
        return floor(self.capacity_per_hour * window_min / 60.0)

    def service_capacity(self, window_min: float) -> int:
        if window_min <= 0:
            raise ValueError("window_min must be positive")
        return floor(self.service_capacity_per_hour * window_min / 60.0)

    def calculation(self) -> dict[str, float | str]:
        """Return enough inputs for reviewers to reproduce the capacity."""

        return {
            "route_id": self.route_id,
            "headway_s": self.headway_s,
            "departures_per_hour": self.departures_per_hour,
            "vehicle_capacity": self.vehicle_capacity,
            "available_capacity_factor": self.available_capacity_factor,
            "eta_max_factor": self.eta_max_factor,
            "raw_capacity_per_hour": self.raw_capacity_per_hour,
            "service_capacity_per_hour": self.service_capacity_per_hour,
            "capacity_per_hour": self.capacity_per_hour,
            "provenance": self.provenance,
        }

    @classmethod
    def from_route_output(cls, route: dict) -> "RouteSupply":
        """Consume C-Route's stable route/capacity/headway output.

        An explicit ``capacity_per_hour`` is treated as the already
        eta-limited bucket capacity required by the public contract.
        ``vehicle_capacity`` is still required so the calculation remains
        auditable; C-Route may also provide ``service_capacity_per_hour``.
        """

        capacity_override = (
            float(route["capacity_per_hour"])
            if route.get("capacity_per_hour") is not None
            else None
        )
        eta_max_factor = float(route.get("eta_max_factor", ETA_MAX_FACTOR))
        if route.get("vehicle_capacity") is not None:
            vehicle_capacity = float(route["vehicle_capacity"])
        elif capacity_override is not None:
            # C-Route's stable integration surface may expose only route_id,
            # capacity and headway. Derive the implied vehicle capacity so the
            # capacity calculation remains inspectable without demanding a new
            # public field.
            vehicle_capacity = capacity_override / eta_max_factor * float(route["headway_s"]) / 3600.0
        else:
            raise ValueError("vehicle_capacity is required when capacity_per_hour is absent")
        return cls(
            route_id=str(route["route_id"]),
            headway_s=float(route["headway_s"]),
            vehicle_capacity=vehicle_capacity,
            available_capacity_factor=float(route.get("available_capacity_factor", 1.0)),
            eta_max_factor=eta_max_factor,
            provenance=str(route.get("provenance", "simulated")),
            note=str(route.get("note", "")),
            capacity_per_hour_override=capacity_override,
            service_capacity_per_hour_override=(
                float(route["service_capacity_per_hour"])
                if route.get("service_capacity_per_hour") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class BucketShare:
    route_id: str
    users: int
    capacity_per_hour: float
    load_factor: float

    def to_contract(self, demand: int) -> dict[str, float | int | str]:
        return {
            "route_id": self.route_id,
            "share": round(self.users / demand, 6) if demand else 0.0,
            "users": self.users,
            "capacity_per_hour": round(self.capacity_per_hour, 3),
            "load_factor": round(self.load_factor, 6),
        }


@dataclass(frozen=True, slots=True)
class BucketAllocation:
    demand: int
    window_min: float
    shares: tuple[BucketShare, ...]
    unstoppable_demand: int

    @property
    def allocated(self) -> int:
        return sum(item.users for item in self.shares)


def allocate_capacity_buckets(
    demand: int,
    supplies: Iterable[RouteSupply],
    *,
    window_min: float = 60.0,
) -> BucketAllocation:
    """Fill independent route buckets from largest to smallest.

    This aggregate helper is used by ``POST /api/sim/load``.  The population
    simulator adds per-person accessibility and maximum-delay checks on top.
    """

    if demand < 0:
        raise ValueError("demand cannot be negative")
    if window_min <= 0:
        raise ValueError("window_min must be positive")
    ordered = sorted(supplies, key=lambda item: (-item.capacity_per_hour, item.route_id))
    remaining = demand
    shares: list[BucketShare] = []
    for supply in ordered:
        capacity = supply.bucket_capacity(window_min)
        users = min(remaining, capacity)
        if users:
            shares.append(
                BucketShare(
                    route_id=supply.route_id,
                    users=users,
                    capacity_per_hour=supply.capacity_per_hour,
                    load_factor=(users / capacity) if capacity else 0.0,
                )
            )
        remaining -= users
        if remaining == 0:
            break
    return BucketAllocation(
        demand=demand,
        window_min=window_min,
        shares=tuple(shares),
        unstoppable_demand=remaining,
    )
