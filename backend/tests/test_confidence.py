from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from backend.app.services.confidence import ConfidenceObservation, score_confidence
from backend.app.services.signal_models import Signal


def signal(number: int, *, author: str | None = None, source_type: str = "social",
           source_name: str = "模拟社媒流", provenance: str = "simulated") -> Signal:
    return Signal(
        signal_id=f"sig-confidence-{number}",
        received_at=datetime(2026, 9, 22, 10, number, tzinfo=timezone.utc),
        source_type=source_type,
        source_name=source_name,
        author_hint=author,
        raw_text="东铁线红磡至会展服务受阻，待核实。",
        raw_url=None,
        lang="zh-HK",
        provenance=provenance,
    )


class ConfidenceTests(unittest.TestCase):
    def test_three_contract_stages_are_020_055_090(self) -> None:
        first = ConfidenceObservation(signal(1, author="乘客一"))
        second = ConfidenceObservation(signal(2, author="乘客二"))
        third = ConfidenceObservation(signal(3, author="乘客三"))
        official = ConfidenceObservation(
            signal(4, source_type="official", source_name="港铁公告", provenance="real"),
            verified_official_notice=True,
        )

        self.assertEqual(score_confidence([first]).score, 0.20)
        self.assertEqual(score_confidence([first, second]).score, 0.55)
        self.assertEqual(score_confidence([first, second, third]).score, 0.55)
        self.assertEqual(score_confidence([first, second, third, official]).score, 0.85)
        confirmed = score_confidence([first, second, third, official], admin_confirmed=True)
        self.assertEqual(confirmed.score, 0.90)
        self.assertFalse(confirmed.review_required)
        self.assertEqual(confirmed.independent_agreeing_sources, 4)
        self.assertEqual(sum(f.factor == "source_authority" and f.score == 1.0 for f in confirmed.factors), 1)
        for result in (
            score_confidence([first]), score_confidence([first, second]),
            score_confidence([first, second, third, official]), confirmed,
        ):
            positive = sum(f.weight * f.score for f in result.factors
                           if f.factor not in {"stage_cap", "source_conflict"})
            negative = sum(f.weight * f.score for f in result.factors
                           if f.factor in {"stage_cap", "source_conflict"})
            self.assertAlmostEqual(result.score, positive - negative)

    def test_official_direct_floor_and_pre_review_cap(self) -> None:
        official = ConfidenceObservation(
            signal(1, source_type="official", source_name="港铁公告", provenance="real"),
            verified_official_notice=True,
        )
        result = score_confidence([official])
        self.assertEqual(result.score, 0.85)
        self.assertTrue(result.review_required)
        self.assertEqual(score_confidence([official], admin_confirmed=True).score, 0.90)
        self.assertEqual(next(f.weight for f in result.factors if f.factor == "official_floor"), 0.30)

    def test_repeated_same_source_does_not_inflate_confidence(self) -> None:
        reports = [ConfidenceObservation(signal(i, author="same-account")) for i in range(1, 5)]
        result = score_confidence(reports)
        self.assertEqual(result.score, 0.20)
        self.assertEqual(result.independent_agreeing_sources, 1)

    def test_conflict_deducts_and_forces_review(self) -> None:
        reports = [ConfidenceObservation(signal(i, author=f"person-{i}")) for i in range(1, 4)]
        reports.append(ConfidenceObservation(signal(4, author="dissent"), role="conflict"))
        result = score_confidence(reports)
        self.assertEqual(result.score, 0.40)
        self.assertTrue(result.review_required)
        self.assertTrue(result.has_conflict)
        self.assertEqual(result.factors[-1].factor, "source_conflict")

    def test_order_independence_and_explicit_source_identity(self) -> None:
        first = ConfidenceObservation(signal(1, author="same"), independent_source_id="person-1")
        repeated = ConfidenceObservation(signal(2, author="different"), independent_source_id="person-1")
        second = ConfidenceObservation(signal(3, author="another"), independent_source_id="person-2")
        self.assertEqual(score_confidence([first, repeated]).score, 0.20)
        forward = score_confidence([first, repeated, second])
        reverse = score_confidence([second, repeated, first])
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.score, 0.55)

    def test_unrelated_official_warning_and_derived_eta_do_not_boost(self) -> None:
        report = ConfidenceObservation(signal(1, source_type="user", provenance="real"))
        hko = ConfidenceObservation(
            signal(2, source_type="official", source_name="香港天文台", provenance="real"),
            related_to_event=False,
        )
        eta = ConfidenceObservation(
            signal(3, source_type="official", source_name="港铁 ETA 推断", provenance="real-derived")
        )
        self.assertEqual(score_confidence([report, hko]).score, 0.20)
        result = score_confidence([report, eta])
        self.assertEqual(result.score, 0.55)
        self.assertEqual(next(f.score for f in result.factors if f.factor == "source_authority"), 0)
        with self.assertRaisesRegex(ValueError, "related, agreeing real official"):
            score_confidence([report, replace(hko, verified_official_notice=True)])

    def test_unreviewed_high_score_does_not_publish_or_mutate_signals(self) -> None:
        first = signal(1, author="one")
        second = signal(2, author="two")
        snapshot = (first.model_dump(), second.model_dump())
        result = score_confidence([ConfidenceObservation(first), ConfidenceObservation(second)])
        self.assertEqual(result.score, 0.55)
        self.assertTrue(result.review_required)
        self.assertEqual(snapshot, (first.model_dump(), second.model_dump()))
        self.assertFalse(hasattr(result, "status"))

    def test_invalid_inputs_and_boundaries(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            score_confidence([])
        with self.assertRaisesRegex(ValueError, "boolean"):
            score_confidence([ConfidenceObservation(signal(1))], admin_confirmed=1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "blank"):
            score_confidence([ConfidenceObservation(signal(1), independent_source_id="  ")])
        reports = [ConfidenceObservation(signal(i, author=f"person-{i}")) for i in range(1, 8)]
        maximum = score_confidence(reports, admin_confirmed=True)
        self.assertEqual(maximum.score, 0.60)
        self.assertGreaterEqual(maximum.score, 0)
        self.assertLessEqual(maximum.score, 1)

    def test_simulated_official_and_real_derived_heuristic_cannot_be_verified(self) -> None:
        for provenance in ("simulated", "real-derived"):
            with self.subTest(provenance=provenance):
                with self.assertRaisesRegex(ValueError, "real official notice"):
                    score_confidence([
                        ConfidenceObservation(
                            signal(1, source_type="official", provenance=provenance),
                            verified_official_notice=True,
                        )
                    ])

    def test_duplicate_ids_and_all_conflicts_are_rejected(self) -> None:
        item = ConfidenceObservation(signal(1))
        with self.assertRaisesRegex(ValueError, "unique"):
            score_confidence([item, item])
        with self.assertRaisesRegex(ValueError, "agreeing"):
            score_confidence([ConfidenceObservation(signal(2), role="conflict")])


if __name__ == "__main__":
    unittest.main()
