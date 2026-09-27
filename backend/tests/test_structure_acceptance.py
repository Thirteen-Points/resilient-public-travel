from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, Mapping

from backend.app.services.structure.acceptance import AcceptanceSample, run_acceptance


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "backend/tests/fixtures/t2_6_acceptance_samples.json"


class ScriptedClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)

    def generate_json(
        self, *, system_prompt: str, user_prompt: str,
        json_schema: Mapping[str, Any], timeout_seconds: float,
    ) -> str | Mapping[str, Any]:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response  # type: ignore[return-value]


def valid_draft() -> dict[str, object]:
    return {
        "event_type": "other",
        "title": "待核實事件",
        "summary": "匿名化驗收文字，等待人工核實。",
        "mode": None,
        "line": None,
        "direction": None,
        "affected_segments": [],
    }


def samples() -> list[AcceptanceSample]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [AcceptanceSample(**item) for item in payload["samples"]]


class StructureAcceptanceTests(unittest.TestCase):
    def test_fixture_has_exactly_ten_anonymised_samples(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["samples"]), 10)
        self.assertIn("anonymised", payload["meta"]["privacy"])
        self.assertEqual(payload["meta"]["provenance"], "simulated")
        self.assertEqual(len({item["sample_id"] for item in payload["samples"]}), 10)
        self.assertTrue(all(item["source_note"] for item in payload["samples"]))

    def test_summary_counts_first_pass_retry_and_fallback_without_raw_output(self) -> None:
        responses: list[object] = [valid_draft() for _ in range(8)]
        responses.extend(["not-json", valid_draft(), RuntimeError("secret provider detail"),
                          RuntimeError("secret provider detail")])
        summary = run_acceptance(ScriptedClient(responses), samples())

        self.assertTrue(summary.passes_t2_6)
        self.assertEqual(summary.first_passes, 8)
        self.assertEqual(summary.retries, 2)
        self.assertEqual(summary.fallbacks, 1)
        self.assertEqual(summary.cases[-1].error_categories,
                         ("attempt 1: LLM client error", "attempt 2: LLM client error"))
        self.assertNotIn("secret provider detail", repr(summary))

    def test_requires_exactly_ten_unique_samples(self) -> None:
        client = ScriptedClient([])
        with self.assertRaisesRegex(ValueError, "exactly 10"):
            run_acceptance(client, samples()[:-1])
        duplicate = samples()
        duplicate[-1] = duplicate[0]
        with self.assertRaisesRegex(ValueError, "unique"):
            run_acceptance(client, duplicate)


if __name__ == "__main__":
    unittest.main()
