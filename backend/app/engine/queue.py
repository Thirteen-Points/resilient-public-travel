"""Numerically stable queue and denied-boarding approximations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueEstimate:
    load_factor: float
    expected_wait_s: float
    board_refusal_prob: float
    overloaded: bool

    def to_contract(self, route_id: str, users: int, capacity_per_hour: float) -> dict:
        return {
            "route_id": route_id,
            "users_on_route": users,
            "capacity_per_hour": round(capacity_per_hour, 3),
            "load_factor": round(self.load_factor, 6),
            "expected_wait_s": round(self.expected_wait_s, 3),
            "board_refusal_prob": round(self.board_refusal_prob, 6),
            "overloaded": self.overloaded,
        }


def estimate_queue(
    *,
    demand_per_hour: float,
    service_capacity_per_hour: float,
    headway_s: float,
    base_refusal_rate: float = 1.0,
) -> QueueEstimate:
    """Apply the architecture's capped M/M/1-style waiting approximation.

    The uncapped wait grows as ``rho`` approaches one.  The product contract
    deliberately caps it at two headways for a stable, conservative display.
    Unserved demand is reported separately and is never hidden by this cap.
    """

    if demand_per_hour < 0:
        raise ValueError("demand_per_hour cannot be negative")
    if service_capacity_per_hour < 0:
        raise ValueError("service_capacity_per_hour cannot be negative")
    if headway_s <= 0:
        raise ValueError("headway_s must be positive")
    if not 0 <= base_refusal_rate <= 1:
        raise ValueError("base_refusal_rate must be within [0, 1]")

    if service_capacity_per_hour == 0:
        rho = float("inf") if demand_per_hour else 0.0
    else:
        rho = demand_per_hour / service_capacity_per_hour

    cap_s = 2.0 * headway_s
    if rho >= 1.0:
        wait_s = cap_s
    else:
        denominator = max(1.0 - rho, 1e-12)
        wait_s = min((headway_s / 2.0) / denominator, cap_s)

    refusal_pressure = max(0.0, (rho - 0.9) / 0.1)
    refusal_prob = min(1.0, refusal_pressure * base_refusal_rate)
    return QueueEstimate(
        load_factor=rho,
        expected_wait_s=wait_s,
        board_refusal_prob=refusal_prob,
        overloaded=rho > 1.0,
    )
