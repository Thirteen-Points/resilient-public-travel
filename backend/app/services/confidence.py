"""Pure confidence ladder for evidence already matched to one event.

The result helps review; it neither publishes an Event nor estimates truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .event_models import ConfidenceFactor
from .signal_models import Signal

EvidenceRole = Literal["agree", "conflict"]


@dataclass(frozen=True)
class ConfidencePolicy:
    base: float = 0.20
    second_independent: float = 0.15
    multi_source_agreement: float = 0.20
    official_authority: float = 0.35
    official_direct_floor: float = 0.85
    admin_confirmation: float = 0.05
    contradiction: float = 0.15
    single_source_cap: float = 0.35
    multi_source_cap: float = 0.55
    official_cap: float = 0.85
    publish_min: float = 0.60


POLICY = ConfidencePolicy()


@dataclass(frozen=True)
class ConfidenceObservation:
    signal: Signal
    role: EvidenceRole = "agree"
    # The caller, not source_type or text, must verify relevance and authority.
    verified_official_notice: bool = False
    related_to_event: bool = True
    independent_source_id: str | None = None


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    factors: tuple[ConfidenceFactor, ...]
    review_required: bool
    independent_agreeing_sources: int
    has_conflict: bool = False


def _source_key(item: ConfidenceObservation) -> tuple[str, ...]:
    """Prefer an upstream identity; otherwise group anonymous channel reports."""

    if item.independent_source_id is not None:
        source_id = item.independent_source_id.strip().casefold()
        if not source_id:
            raise ValueError("independent_source_id must not be blank")
        return ("explicit", source_id)
    signal = item.signal
    return (
        "channel", signal.source_type.casefold(), signal.source_name.casefold(),
        (signal.author_hint or "").casefold(),
    )


def score_confidence(
    observations: Sequence[ConfidenceObservation], *, admin_confirmed: bool = False,
) -> ConfidenceResult:
    """Score explicit evidence; factor names identify positive and negative entries.

    Two independent agreeing sources activate both +0.15 and +0.20, giving
    0.55. Official evidence gets a direct 0.85 floor and a pre-review 0.85 cap.
    Floor/cap adjustments are shown as factors, never hidden in the total.
    """

    if not observations:
        raise ValueError("at least one observation is required")
    if not isinstance(admin_confirmed, bool):
        raise ValueError("admin_confirmed must be a boolean")
    if any(not isinstance(item, ConfidenceObservation) for item in observations):
        raise ValueError("all observations must be ConfidenceObservation values")
    ids = [item.signal.signal_id for item in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("signal ids must be unique")
    for item in observations:
        if item.role not in ("agree", "conflict"):
            raise ValueError("evidence role must be agree or conflict")
        if not isinstance(item.related_to_event, bool):
            raise ValueError("related_to_event must be a boolean")
        if item.verified_official_notice and (
            not item.related_to_event or item.role != "agree"
            or item.signal.source_type != "official" or item.signal.provenance != "real"
        ):
            raise ValueError("only a related, agreeing real official notice may be marked verified")
        _source_key(item)

    relevant = [item for item in observations if item.related_to_event]
    agreeing = [item for item in relevant if item.role == "agree"]
    if not agreeing:
        raise ValueError("at least one related agreeing signal is required")
    count = len({_source_key(item) for item in agreeing})
    official = any(item.verified_official_notice for item in agreeing)
    conflict = any(item.role == "conflict" for item in relevant)

    factors: list[ConfidenceFactor] = []

    def add(name: str, weight: float, active: bool, note: str) -> None:
        factors.append(ConfidenceFactor(
            factor=name, weight=round(weight, 2), score=float(active), note=note,
        ))

    add("base_signal", POLICY.base, True, "At least one related report; the incident remains unverified.")
    add("independent_source", POLICY.second_independent, count >= 2,
        f"{count} independent agreeing sources")
    add("multi_source_agreement", POLICY.multi_source_agreement, count >= 2,
        "At least two independent sources agree." if count >= 2 else "Multiple-source agreement has not been established.")
    add("source_authority", POLICY.official_authority, official,
        "A verified official notice relates to this incident." if official else "No related verified official notice.")

    pre_cap = POLICY.base + (
        POLICY.second_independent + POLICY.multi_source_agreement if count >= 2 else 0
    ) + (POLICY.official_authority if official else 0)
    if official:
        floor_adjustment = max(0.0, POLICY.official_direct_floor - pre_cap)
        cap_adjustment = max(0.0, pre_cap + floor_adjustment - POLICY.official_cap)
        stage = min(POLICY.official_cap, pre_cap + floor_adjustment)
    else:
        floor_adjustment = 0.0
        cap = POLICY.multi_source_cap if count >= 2 else POLICY.single_source_cap
        cap_adjustment = max(0.0, pre_cap - cap)
        stage = min(cap, pre_cap)
    add("official_floor", floor_adjustment, floor_adjustment > 0,
        "Adjustment to the 0.85 confidence floor for official notices.")
    add("stage_cap", cap_adjustment, cap_adjustment > 0,
        "Deduction above the current confidence stage cap.")
    add("admin_confirmation", POLICY.admin_confirmation, admin_confirmed,
        "Confirmed by human review." if admin_confirmed else "Human review is still required.")
    add("source_conflict", POLICY.contradiction, conflict,
        "Deduct 0.15 for conflicting evidence; verification is required." if conflict else "No related conflicting evidence.")

    score = round(min(1.0, max(0.0, stage + (
        POLICY.admin_confirmation if admin_confirmed else 0
    ) - (POLICY.contradiction if conflict else 0))), 2)
    return ConfidenceResult(
        score=score, factors=tuple(factors),
        review_required=conflict or not admin_confirmed or score < POLICY.publish_min,
        independent_agreeing_sources=count, has_conflict=conflict,
    )
