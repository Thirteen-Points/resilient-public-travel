"""Sequential, schedule-aware journey simulation for internal C-Sim use.

This module deliberately separates departure-time inputs from boarding
assumptions. A timetable or MTR Next Train response can say when a service is
expected; it cannot establish capacity or whether a passenger can board.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import random
from typing import Mapping


TRANSIT_MODES = {"MTR", "BUS", "MINIBUS", "FERRY"}
PROVENANCE_VALUES = {"real", "real-derived", "simulated"}


def _mapping(value: object, path: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _number(value: object, path: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{path} must be finite and >= {minimum}")
    return result


def _datetime(value: object, path: str) -> datetime:
    text = _string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{path} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{path} must include a timezone")
    return parsed


def _iso(value: datetime) -> str:
    return value.isoformat()


@dataclass(frozen=True, slots=True)
class DepartureSource:
    kind: str
    provenance: str
    note: str


@dataclass(frozen=True, slots=True)
class BoardingAssumption:
    denial_probabilities: tuple[float, ...]
    provenance: str
    note: str


@dataclass(frozen=True, slots=True)
class TimelineLeg:
    leg_id: str
    mode: str
    from_node: str
    to_node: str
    travel_s: float
    minimum_transfer_s: float
    departures: tuple[datetime, ...] = ()
    departure_source: DepartureSource | None = None
    boarding: BoardingAssumption | None = None

    @property
    def is_transit(self) -> bool:
        return self.mode in TRANSIT_MODES


@dataclass(frozen=True, slots=True)
class JourneyTimelineInput:
    route_id: str
    start_at: datetime
    legs: tuple[TimelineLeg, ...]
    seed: int
    sample_count: int
    assumptions: tuple[str, ...]
    provenance: str


def journey_timeline_from_fixture(payload: dict) -> JourneyTimelineInput:
    """Validate an offline fixture without inventing any boarding parameter."""

    root = _mapping(payload, "journey timeline fixture")
    if root.get("fixture") is not True:
        raise ValueError("journey timeline fixture.fixture must be true")
    provenance = _string(root.get("provenance"), "journey timeline fixture.provenance")
    if provenance != "simulated":
        raise ValueError("journey timeline fixture.provenance must remain simulated")
    route_id = _string(root.get("route_id"), "journey timeline fixture.route_id")
    start_at = _datetime(root.get("start_at"), "journey timeline fixture.start_at")
    seed = root.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("journey timeline fixture.seed must be an integer")
    sample_count = root.get("sample_count")
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
        raise ValueError("journey timeline fixture.sample_count must be a positive integer")
    assumptions = root.get("assumptions")
    if (
        not isinstance(assumptions, list)
        or not assumptions
        or any(not isinstance(item, str) or not item.strip() for item in assumptions)
    ):
        raise ValueError("journey timeline fixture.assumptions must contain text")
    raw_legs = root.get("legs")
    if not isinstance(raw_legs, list) or not raw_legs:
        raise ValueError("journey timeline fixture.legs must be a non-empty array")

    legs: list[TimelineLeg] = []
    for index, value in enumerate(raw_legs):
        path = f"journey timeline fixture.legs[{index}]"
        item = _mapping(value, path)
        leg_provenance = _string(item.get("provenance"), f"{path}.provenance")
        if leg_provenance != "simulated":
            raise ValueError(f"{path}.provenance must remain simulated")
        mode = _string(item.get("mode"), f"{path}.mode").upper()
        if mode not in TRANSIT_MODES | {"WALK"}:
            raise ValueError(f"{path}.mode is unsupported")
        travel_s = _number(item.get("travel_s"), f"{path}.travel_s", minimum=1e-12)
        transfer_s = _number(
            item.get("minimum_transfer_s", 0), f"{path}.minimum_transfer_s"
        )
        common = {
            "leg_id": _string(item.get("leg_id"), f"{path}.leg_id"),
            "mode": mode,
            "from_node": _string(item.get("from"), f"{path}.from"),
            "to_node": _string(item.get("to"), f"{path}.to"),
            "travel_s": travel_s,
            "minimum_transfer_s": transfer_s,
        }
        if mode == "WALK":
            if item.get("departures") not in (None, []):
                raise ValueError(f"{path}.departures are not valid for WALK")
            if item.get("boarding") is not None:
                raise ValueError(f"{path}.boarding is not valid for WALK")
            legs.append(TimelineLeg(**common))
            continue

        raw_departures = item.get("departures")
        if not isinstance(raw_departures, list) or not raw_departures:
            raise ValueError(f"{path}.departures must be a non-empty array")
        departures = tuple(
            _datetime(departure, f"{path}.departures[{departure_index}]")
            for departure_index, departure in enumerate(raw_departures)
        )
        if any(later <= earlier for earlier, later in zip(departures, departures[1:])):
            raise ValueError(f"{path}.departures must be strictly increasing")

        source = _mapping(item.get("departure_source"), f"{path}.departure_source")
        source_kind = _string(source.get("kind"), f"{path}.departure_source.kind")
        if source_kind not in {"fixture", "mtr_next_train"}:
            raise ValueError(f"{path}.departure_source.kind is unsupported")
        source_provenance = _string(
            source.get("provenance"), f"{path}.departure_source.provenance"
        )
        if source_provenance != "simulated":
            raise ValueError(f"{path}.departure_source.provenance must remain simulated")
        departure_source = DepartureSource(
            kind=source_kind,
            provenance=source_provenance,
            note=_string(source.get("note"), f"{path}.departure_source.note"),
        )

        boarding = _mapping(item.get("boarding"), f"{path}.boarding")
        if boarding.get("kind") != "assumption":
            raise ValueError(f"{path}.boarding.kind must be assumption")
        boarding_provenance = _string(
            boarding.get("provenance"), f"{path}.boarding.provenance"
        )
        if boarding_provenance != "simulated":
            raise ValueError(f"{path}.boarding.provenance must remain simulated")
        raw_probabilities = boarding.get("denial_probabilities")
        if not isinstance(raw_probabilities, list) or len(raw_probabilities) != len(departures):
            raise ValueError(
                f"{path}.boarding.denial_probabilities must match departures exactly"
            )
        probabilities = tuple(
            _number(probability, f"{path}.boarding.denial_probabilities[{probability_index}]")
            for probability_index, probability in enumerate(raw_probabilities)
        )
        if any(probability > 1 for probability in probabilities):
            raise ValueError(f"{path}.boarding.denial_probabilities must be <= 1")
        boarding_assumption = BoardingAssumption(
            denial_probabilities=probabilities,
            provenance=boarding_provenance,
            note=_string(boarding.get("note"), f"{path}.boarding.note"),
        )
        legs.append(
            TimelineLeg(
                **common,
                departures=departures,
                departure_source=departure_source,
                boarding=boarding_assumption,
            )
        )

    if len({leg.leg_id for leg in legs}) != len(legs):
        raise ValueError("journey timeline fixture leg_id values must be unique")
    return JourneyTimelineInput(
        route_id=route_id,
        start_at=start_at,
        legs=tuple(legs),
        seed=seed,
        sample_count=sample_count,
        assumptions=tuple(assumptions),
        provenance=provenance,
    )


def _raw_timeline(
    specification: JourneyTimelineInput,
    rng: random.Random | None,
    *,
    force_board: bool,
) -> dict:
    current = specification.start_at
    raw_legs: list[dict] = []
    signature: list[str] = []
    for leg_index, leg in enumerate(specification.legs):
        if not leg.is_transit:
            arrival = current + timedelta(seconds=leg.travel_s)
            raw_legs.append(
                {
                    "leg_index": leg_index,
                    "start_at": current,
                    "ready_at": current,
                    "arrive_at": arrival,
                    "eligible_index": None,
                    "boarded_index": None,
                }
            )
            signature.append("walk")
            current = arrival
            continue

        ready_at = current + timedelta(seconds=leg.minimum_transfer_s)
        eligible_index = bisect_left(leg.departures, ready_at)
        if eligible_index >= len(leg.departures):
            return {
                "served": False,
                "failed_leg_index": leg_index,
                "failure_reason": "NO_DEPARTURE_AFTER_READY_TIME",
            }
        boarded_index = eligible_index
        if not force_board:
            assert rng is not None and leg.boarding is not None
            while boarded_index < len(leg.departures):
                probability = leg.boarding.denial_probabilities[boarded_index]
                denied = probability >= 1 or (
                    probability > 0 and rng.random() < probability
                )
                if not denied:
                    break
                boarded_index += 1
            if boarded_index >= len(leg.departures):
                return {
                    "served": False,
                    "failed_leg_index": leg_index,
                    "failure_reason": "NO_DEPARTURE_AFTER_SIMULATED_BOARDING_DENIALS",
                }
        depart_at = leg.departures[boarded_index]
        arrival = depart_at + timedelta(seconds=leg.travel_s)
        raw_legs.append(
            {
                "leg_index": leg_index,
                "start_at": current,
                "ready_at": ready_at,
                "depart_at": depart_at,
                "arrive_at": arrival,
                "eligible_index": eligible_index,
                "boarded_index": boarded_index,
            }
        )
        signature.append(str(boarded_index))
        current = arrival
    return {
        "served": True,
        "arrive_at": current,
        "total_s": (current - specification.start_at).total_seconds(),
        "signature": tuple(signature),
        "legs": raw_legs,
    }


def _explain_timeline(
    specification: JourneyTimelineInput, raw: dict, fastest: dict
) -> dict:
    explained_legs: list[dict] = []
    total_missed = 0
    for leg, actual, baseline in zip(specification.legs, raw["legs"], fastest["legs"]):
        if not leg.is_transit:
            explained_legs.append(
                {
                    "leg_id": leg.leg_id,
                    "mode": leg.mode,
                    "from": leg.from_node,
                    "to": leg.to_node,
                    "start_at": _iso(actual["start_at"]),
                    "ready_at": _iso(actual["ready_at"]),
                    "depart_at": _iso(actual["start_at"]),
                    "arrive_at": _iso(actual["arrive_at"]),
                    "transfer_s": round(leg.travel_s, 3),
                    "scheduled_wait_s": 0.0,
                    "denial_wait_s": 0.0,
                    "wait_s": 0.0,
                    "ride_s": 0.0,
                    "missed_services": 0,
                    "delay_reasons": [],
                    "provenance": "simulated",
                }
            )
            continue

        assert leg.boarding is not None and leg.departure_source is not None
        eligible_index = actual["eligible_index"]
        boarded_index = actual["boarded_index"]
        baseline_eligible = baseline["eligible_index"]
        propagation_misses = max(0, eligible_index - baseline_eligible)
        denial_misses = boarded_index - eligible_index
        scheduled_wait_s = (
            leg.departures[eligible_index] - actual["ready_at"]
        ).total_seconds()
        denial_wait_s = (
            leg.departures[boarded_index] - leg.departures[eligible_index]
        ).total_seconds()
        reasons: list[dict] = []
        if propagation_misses:
            reasons.append(
                {
                    "code": "UPSTREAM_DELAY_MISSED_CONNECTION",
                    "missed_services": propagation_misses,
                    "delay_s": round(
                        (
                            leg.departures[eligible_index]
                            - leg.departures[baseline_eligible]
                        ).total_seconds(),
                        3,
                    ),
                    "provenance": "simulated",
                }
            )
        if denial_misses:
            reasons.append(
                {
                    "code": "SIMULATED_BOARDING_DENIAL_ASSUMPTION",
                    "missed_services": denial_misses,
                    "delay_s": round(denial_wait_s, 3),
                    "note": leg.boarding.note,
                    "provenance": leg.boarding.provenance,
                }
            )
        missed_services = propagation_misses + denial_misses
        total_missed += missed_services
        explained_legs.append(
            {
                "leg_id": leg.leg_id,
                "mode": leg.mode,
                "from": leg.from_node,
                "to": leg.to_node,
                "start_at": _iso(actual["start_at"]),
                "ready_at": _iso(actual["ready_at"]),
                "depart_at": _iso(actual["depart_at"]),
                "arrive_at": _iso(actual["arrive_at"]),
                "transfer_s": round(leg.minimum_transfer_s, 3),
                "scheduled_wait_s": round(scheduled_wait_s, 3),
                "denial_wait_s": round(denial_wait_s, 3),
                "wait_s": round(scheduled_wait_s + denial_wait_s, 3),
                "ride_s": round(leg.travel_s, 3),
                "missed_services": missed_services,
                "delay_reasons": reasons,
                "departure_source": {
                    "kind": leg.departure_source.kind,
                    "provenance": leg.departure_source.provenance,
                    "note": leg.departure_source.note,
                },
                "boarding_model": {
                    "kind": "assumption",
                    "provenance": leg.boarding.provenance,
                    "note": leg.boarding.note,
                },
                "provenance": "simulated",
            }
        )
    return {
        "depart_at": _iso(specification.start_at),
        "arrive_at": _iso(raw["arrive_at"]),
        "total_s": round(raw["total_s"], 3),
        "delay_vs_fastest_s": round(raw["total_s"] - fastest["total_s"], 3),
        "missed_services": total_missed,
        "legs": explained_legs,
        "provenance": "simulated",
    }


def simulate_journey_timeline(specification: JourneyTimelineInput) -> dict:
    """Sample schedule propagation and expose representative/faster/slower outcomes."""

    fastest_raw = _raw_timeline(specification, None, force_board=True)
    if not fastest_raw["served"]:
        raise ValueError("fixture has no complete journey even without boarding denials")
    rng = random.Random(specification.seed)
    served_by_signature: dict[tuple[str, ...], dict] = {}
    counts: Counter[tuple[str, ...]] = Counter()
    failures: Counter[str] = Counter()
    for _ in range(specification.sample_count):
        raw = _raw_timeline(specification, rng, force_board=False)
        if not raw["served"]:
            failures[raw["failure_reason"]] += 1
            continue
        signature = raw["signature"]
        counts[signature] += 1
        served_by_signature.setdefault(signature, raw)
    if not counts:
        raise ValueError("all sampled journeys are unserved under the configured assumptions")

    def total(signature: tuple[str, ...]) -> float:
        return served_by_signature[signature]["total_s"]

    representative_signature = min(
        counts,
        key=lambda signature: (-counts[signature], total(signature), signature),
    )
    faster_signature = min(counts, key=lambda signature: (total(signature), signature))
    slower_signature = max(counts, key=lambda signature: (total(signature), signature))

    def scenario(role: str, signature: tuple[str, ...]) -> dict:
        return {
            "role": role,
            "sample_count": counts[signature],
            "simulation_share": round(counts[signature] / specification.sample_count, 6),
            "outcome": _explain_timeline(
                specification, served_by_signature[signature], fastest_raw
            ),
        }

    distribution = [
        {
            "signature": list(signature),
            "sample_count": counts[signature],
            "simulation_share": round(counts[signature] / specification.sample_count, 6),
            "total_s": round(total(signature), 3),
        }
        for signature in sorted(counts, key=lambda item: (total(item), item))
    ]
    return {
        "route_id": specification.route_id,
        "seed": specification.seed,
        "sample_count": specification.sample_count,
        "served_samples": sum(counts.values()),
        "unserved_samples": sum(failures.values()),
        "unserved_reasons": dict(sorted(failures.items())),
        "scenarios": {
            "representative": scenario("representative", representative_signature),
            "faster": scenario("faster", faster_signature),
            "slower": scenario("slower", slower_signature),
        },
        "outcome_distribution": distribution,
        "assumptions": list(specification.assumptions),
        "disclaimer": (
            "Boarding denials and congestion are simulated assumptions, not observed facts "
            "or calibrated real-world probabilities. Departure inputs alone do not imply "
            "capacity or an inability to board."
        ),
        "provenance": specification.provenance,
    }
