"""Provider-neutral acceptance metrics for T2.6 event structuring.

This module deliberately knows nothing about API keys, HTTP endpoints, or model
vendors.  A real client is injected through the existing ``LlmJsonClient``
protocol, while recorded results contain only safe outcome categories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from ..signal_models import Signal
from .llm_structurer import LlmEventStructurer, LlmJsonClient, StructureMethod


@dataclass(frozen=True)
class AcceptanceSample:
    sample_id: str
    text: str
    lang: str
    source_note: str


@dataclass(frozen=True)
class AcceptanceCaseResult:
    sample_id: str
    first_pass: bool
    schema_valid: bool
    retried: bool
    degraded: bool
    method: StructureMethod
    attempts: int
    error_categories: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceSummary:
    total: int
    first_passes: int
    retries: int
    fallbacks: int
    cases: tuple[AcceptanceCaseResult, ...]

    @property
    def passes_t2_6(self) -> bool:
        return self.total == 10 and self.first_passes >= 8


def run_acceptance(
    client: LlmJsonClient,
    samples: Sequence[AcceptanceSample],
    *,
    timeout_seconds: float = 10.0,
) -> AcceptanceSummary:
    """Run real or test clients without retaining prompts or raw responses."""

    if len(samples) != 10:
        raise ValueError("T2.6 acceptance requires exactly 10 samples")
    ids = [sample.sample_id for sample in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("acceptance sample ids must be unique")

    structurer = LlmEventStructurer(client, timeout_seconds=timeout_seconds)
    received_at = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    cases: list[AcceptanceCaseResult] = []
    for sample in samples:
        if not sample.text.strip() or not sample.source_note.strip():
            raise ValueError("acceptance text and source note must not be empty")
        signal = Signal(
            signal_id=f"t2-6-acceptance-{sample.sample_id}",
            received_at=received_at,
            source_type="acceptance_sample",
            source_name="T2.6 anonymised acceptance corpus",
            author_hint=None,
            raw_text=sample.text,
            raw_url=None,
            lang=sample.lang,
            provenance="simulated",
        )
        result = structurer.structure(signal)
        cases.append(AcceptanceCaseResult(
            sample_id=sample.sample_id,
            first_pass=result.first_pass,
            schema_valid=True,
            retried=result.attempts == 2,
            degraded=result.degraded,
            method=result.method,
            attempts=result.attempts,
            error_categories=result.errors,
        ))

    frozen_cases = tuple(cases)
    return AcceptanceSummary(
        total=len(frozen_cases),
        first_passes=sum(case.first_pass for case in frozen_cases),
        retries=sum(case.retried for case in frozen_cases),
        fallbacks=sum(case.degraded for case in frozen_cases),
        cases=frozen_cases,
    )
