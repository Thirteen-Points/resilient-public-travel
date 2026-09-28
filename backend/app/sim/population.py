"""Fixed-seed generation for the 10,000-person simulated population."""

from __future__ import annotations

import random
from collections import Counter
from typing import Hashable, Mapping, TypeVar

from .models import Agent


DEFAULT_SEED = 20260922
PERSONA_SHARES: dict[str, float] = {
    "commuter": 0.55,
    "student": 0.20,
    "tourist": 0.10,
    "elderly": 0.10,
    "wheelchair": 0.05,
}
ORIGIN_WEIGHTS: dict[str, float] = {
    "TAW": 0.38,
    "KOT": 0.20,
    "MKK": 0.14,
    "HUH": 0.18,
    "EXC": 0.10,
}

Label = TypeVar("Label", bound=Hashable)


def _exact_labels(population: int, shares: Mapping[Label, float]) -> list[Label]:
    if population < 0:
        raise ValueError("population cannot be negative")
    if not shares or abs(sum(shares.values()) - 1.0) > 1e-9:
        raise ValueError("shares must be non-empty and sum to one")
    raw = {label: population * share for label, share in shares.items()}
    counts = {label: int(value) for label, value in raw.items()}
    remainder = population - sum(counts.values())
    order = sorted(shares, key=lambda label: (-(raw[label] - counts[label]), label))
    for label in order[:remainder]:
        counts[label] += 1
    return [label for label in shares for _ in range(counts[label])]


def generate_population(
    population: int = 10_000,
    *,
    seed: int = DEFAULT_SEED,
    persona_shares: Mapping[str, float] = PERSONA_SHARES,
    origin_weights: Mapping[str, float] = ORIGIN_WEIGHTS,
    od_weights: Mapping[tuple[str, str], float] | None = None,
) -> tuple[Agent, ...]:
    """Return an immutable, byte-for-byte reproducible simulated population."""

    rng = random.Random(seed)
    personas = _exact_labels(population, persona_shares)
    rng.shuffle(personas)
    if od_weights is None:
        od_pairs = [(origin, "ADM") for origin in _exact_labels(population, origin_weights)]
    else:
        for od in od_weights:
            if (
                not isinstance(od, tuple)
                or len(od) != 2
                or not all(isinstance(value, str) and value for value in od)
                or od[0] == od[1]
            ):
                raise ValueError("OD keys must be distinct non-empty (origin, destination) pairs")
        od_pairs = _exact_labels(population, od_weights)
    rng.shuffle(od_pairs)

    mobility = {
        "commuter": "standard",
        "student": "standard",
        "tourist": "standard",
        "elderly": "reduced",
        "wheelchair": "wheelchair",
    }
    max_walk = {"standard": 800, "reduced": 400, "wheelchair": 400}
    return tuple(
        Agent(
            agent_id=f"sim_{index:05d}",
            origin=od_pairs[index][0],
            destination=od_pairs[index][1],
            persona=personas[index],
            mobility=mobility[personas[index]],
            max_walk_m=max_walk[mobility[personas[index]]],
        )
        for index in range(population)
    )


def population_summary(agents: tuple[Agent, ...]) -> dict:
    return {
        "population": len(agents),
        "persona_counts": dict(sorted(Counter(agent.persona for agent in agents).items())),
        "origin_counts": dict(sorted(Counter(agent.origin for agent in agents).items())),
        "provenance": "simulated",
    }
