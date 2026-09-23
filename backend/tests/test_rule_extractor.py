from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.app.services.signal_models import Signal
from backend.app.services.structure.llm_structurer import LlmEventStructurer
from backend.app.services.structure.rule_extractor import RuleEventExtractor


def signal(text: str) -> Signal:
    return Signal(
        signal_id="sig-rule-001",
        received_at=datetime(2026, 9, 22, 10, 30, tzinfo=timezone.utc),
        source_type="user",
        source_name="用户上报（未经核实）",
        author_hint=None,
        raw_text=text,
        raw_url=None,
        lang="zh-HK",
        provenance="real",
    )


class RuleEventExtractorTests(unittest.TestCase):
    def test_explicit_line_segment_impact_and_cause(self) -> None:
        draft = RuleEventExtractor().extract(
            signal("东铁线红磡站至会展站信号故障，过海段暂停服务，金钟方向停开。")
        )

        self.assertEqual(draft.event_type, "signal_failure")
        self.assertEqual(draft.mode, "MTR")
        self.assertEqual(draft.line, "ERL")
        self.assertEqual(draft.direction, "southbound")
        self.assertEqual(
            [segment.model_dump() for segment in draft.affected_segments],
            [{"from_node": "HUH", "to_node": "EXC", "impact": "closed"}],
        )

    def test_station_mentions_alone_do_not_invent_an_affected_segment(self) -> None:
        text = "【模拟社媒帖】红磡站的列车停留得比平时久，情况尚未确认。"
        draft = RuleEventExtractor().extract(signal(text))

        self.assertEqual(draft.event_type, "other")
        self.assertIsNone(draft.line)
        self.assertIsNone(draft.mode)
        self.assertEqual(draft.affected_segments, [])
        self.assertEqual(draft.summary, text)

    def test_unknown_or_unstated_values_remain_unset(self) -> None:
        draft = RuleEventExtractor().extract(signal("现场不正常，原因尚未确认。"))

        self.assertEqual(draft.event_type, "other")
        self.assertIsNone(draft.mode)
        self.assertIsNone(draft.line)
        self.assertIsNone(draft.direction)
        self.assertEqual(draft.affected_segments, [])
        self.assertNotIn("severity", draft.model_dump())
        self.assertNotIn("confidence", draft.model_dump())

    def test_negated_disruption_is_not_reported_as_an_incident(self) -> None:
        draft = RuleEventExtractor().extract(
            signal("东铁线红磡至会展没有发生故障，也没有延误。")
        )

        self.assertEqual(draft.event_type, "other")
        self.assertIsNone(draft.line)
        self.assertEqual(draft.affected_segments, [])

    def test_english_aliases_require_token_boundaries(self) -> None:
        draft = RuleEventExtractor().extract(
            signal("East Rail Line Hung Hom to Exhibition Centre delayed.")
        )
        self.assertEqual(draft.line, "ERL")
        self.assertEqual(draft.mode, "MTR")
        self.assertEqual(draft.affected_segments, [])  # English span is not yet parsed.

        unrelated = RuleEventExtractor().extract(signal("The YEARLY report is delayed."))
        self.assertIsNone(unrelated.line)

    def test_disabled_llm_returns_immediately_with_rule_result(self) -> None:
        result = LlmEventStructurer(client=None).structure(
            signal("东铁线红磡至会展服务受阻。")
        )

        self.assertEqual(result.method, "rule_fallback")
        self.assertEqual(result.attempts, 0)
        self.assertEqual(result.errors, ())
        self.assertTrue(result.degraded)
        self.assertEqual(result.draft.line, "ERL")
        self.assertEqual(result.draft.affected_segments[0].impact, "slow")


if __name__ == "__main__":
    unittest.main()
