from __future__ import annotations

import unittest
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
        self.assertEqual(score_confidence([first, second]).score, 0.35)
        self.assertEqual(score_confidence([first, second, third]).score, 0.55)
        self.assertEqual(score_confidence([first, second, third, official]).score, 0.85)
        confirmed = score_confidence([first, second, third, official], admin_confirmed=True)
        self.assertEqual(confirmed.score, 0.90)
        self.assertFalse(confirmed.review_required)
        self.assertEqual(confirmed.independent_agreeing_sources, 4)
        self.assertEqual(sum(f.factor == "source_authority" and f.score == 1.0 for f in confirmed.factors), 1)

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
        self.assertEqual(result.factors[-1].factor, "source_conflict")

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
