"""Deterministic confidence ladder for unverified event evidence.

The score is a review aid, not a probability that a report is true.  Text or
LLM output cannot set it directly.  A caller explicitly marks agreement,
contradiction, and whether an official notice has been verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .event_models import ConfidenceFactor
from .signal_models import Signal


EvidenceRole = Literal["agree", "conflict"]


@dataclass(frozen=True)
class ConfidenceObservation:
    signal: Signal
    role: EvidenceRole = "agree"
    verified_official_notice: bool = False


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    factors: tuple[ConfidenceFactor, ...]
    review_required: bool
    independent_agreeing_sources: int


def _source_key(signal: Signal) -> tuple[str, str, str]:
    """Anonymous reports from the same channel count as one source."""

    return (
        signal.source_type.casefold(),
        signal.source_name.casefold(),
        (signal.author_hint or "").casefold(),
    )


def score_confidence(
    observations: Sequence[ConfidenceObservation],
    *,
    admin_confirmed: bool = False,
) -> ConfidenceResult:
    """Return the documented 0.20 → 0.35 → 0.55 → 0.85 → 0.90 ladder.

    The base, second independent source, and third independent source have
    weights 0.20, 0.15, and 0.20.  A verified official notice has authority
    weight 0.35 and lifts the official stage directly to 0.85; it stays there until a
    reviewer confirms it.  Contradictory evidence deducts 0.15 and forces
    review.  Duplicate signal ids or repeated reports by the same source do
    not raise the score.
    """

    if not observations:
        raise ValueError("at least one observation is required")
    ids = [item.signal.signal_id for item in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("signal ids must be unique")
    for item in observations:
        if item.role not in ("agree", "conflict"):
            raise ValueError("evidence role must be agree or conflict")
        if item.verified_official_notice and (
            item.signal.source_type != "official" or item.signal.provenance != "real"
        ):
            raise ValueError("only a real official notice may be marked verified")

    agreeing = [item for item in observations if item.role == "agree"]
    if not agreeing:
        raise ValueError("at least one agreeing signal is required")
    count = len({_source_key(item.signal) for item in agreeing})
    official = any(item.verified_official_notice for item in agreeing)
    conflict = any(item.role == "conflict" for item in observations)

    score = 0.20
    if count >= 2:
        score += 0.15
    if count >= 3:
        score += 0.20
    if official:
        score = 0.85
    if admin_confirmed:
        score += 0.05
    if conflict:
        score -= 0.15
    score = round(min(1.0, max(0.0, score)), 2)

    factors = (
        ConfidenceFactor(factor="base_signal", weight=0.20, score=1.0,
                         note="有一条未经核实的事件信号；不是事实确认"),
        ConfidenceFactor(factor="independent_source", weight=0.15,
                         score=float(count >= 2), note=f"独立同意来源 {count} 个"),
        ConfidenceFactor(factor="multi_source_agreement", weight=0.20,
                         score=float(count >= 3), note="至少三个独立来源一致" if count >= 3 else "独立来源不足三个"),
        ConfidenceFactor(factor="source_authority", weight=0.35,
                         score=float(official), note="已核实真实官方公告" if official else "没有已核实官方公告"),
        ConfidenceFactor(factor="admin_confirmation", weight=0.05,
                         score=float(admin_confirmed), note="审核员确认" if admin_confirmed else "尚未审核"),
        ConfidenceFactor(factor="source_conflict", weight=0.15,
                         score=float(conflict), note="扣减 0.15，待核实" if conflict else "未记录矛盾；此项为扣分因子"),
    )
    return ConfidenceResult(
        score=score,
        factors=factors,
        review_required=conflict or not admin_confirmed,
        independent_agreeing_sources=count,
    )
