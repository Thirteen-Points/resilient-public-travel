from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.app.services.ingest.hko import (
    HkoFetchError,
    HkoWarningPoller,
)


POLL_TIME = datetime(2026, 9, 22, 6, 40, tzinfo=timezone.utc)


def warning(code: str, name: str) -> dict:
    return {
        "name": name,
        "code": code,
        "actionCode": "ISSUE",
        "issueTime": "2026-09-22T14:00:00+08:00",
        "updateTime": "2026-09-22T14:00:00+08:00",
    }


class StubHkoClient:
    def __init__(self, summaries: list[dict | Exception], details: dict | Exception):
        self.summaries = list(summaries)
        self.details = details
        self.warning_info_calls = 0

    def fetch_warnsum(self) -> dict:
        result = self.summaries.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def fetch_warning_info(self) -> dict:
        self.warning_info_calls += 1
        if isinstance(self.details, Exception):
            raise self.details
        return self.details

    @staticmethod
    def endpoint_url(data_type: str) -> str:
        return f"https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType={data_type}&lang=tc"


class HkoWarningPollerTestCase(unittest.TestCase):
    def test_first_poll_emits_current_active_warning(self) -> None:
        client = StubHkoClient(
            [{"WTS": warning("WTS", "雷暴警告")}],
            {
                "details": [
                    {
                        "warningStatementCode": "WTS",
                        "contents": ["预料香港部分地区有雷暴。"],
                        "updateTime": "2026-09-22T14:40:00+08:00",
                    }
                ]
            },
        )

        result = HkoWarningPoller(client).poll_once(received_at=POLL_TIME)

        self.assertTrue(result.changed)
        self.assertFalse(result.degraded)
        self.assertEqual(result.active_codes, frozenset({"WTS"}))
        self.assertEqual(len(result.signals), 1)
        signal = result.signals[0]
        self.assertEqual(signal.source_type, "official")
        self.assertEqual(signal.provenance, "real")
        self.assertIn("雷暴警告", signal.raw_text)
        self.assertIn("预料香港部分地区有雷暴", signal.raw_text)

    def test_same_code_set_does_not_emit_duplicate_signal(self) -> None:
        client = StubHkoClient(
            [
                {"WTS": warning("WTS", "雷暴警告")},
                {"WTS": {**warning("WTS", "雷暴警告"), "actionCode": "EXTEND"}},
            ],
            {"details": []},
        )
        poller = HkoWarningPoller(client)

        poller.poll_once(received_at=POLL_TIME)
        second = poller.poll_once(received_at=POLL_TIME)

        self.assertFalse(second.changed)
        self.assertEqual(second.signals, ())
        self.assertEqual(client.warning_info_calls, 1)

    def test_added_code_emits_only_new_warning(self) -> None:
        client = StubHkoClient(
            [
                {"WTS": warning("WTS", "雷暴警告")},
                {
                    "WTS": warning("WTS", "雷暴警告"),
                    "WHOT": warning("WHOT", "酷热天气警告"),
                },
            ],
            {"details": []},
        )
        poller = HkoWarningPoller(client)

        poller.poll_once(received_at=POLL_TIME)
        result = poller.poll_once(received_at=POLL_TIME)

        self.assertEqual(len(result.signals), 1)
        self.assertIn("WHOT", result.signals[0].raw_text)
        self.assertIn("activated", result.signals[0].signal_id)

    def test_removed_code_emits_clear_signal(self) -> None:
        client = StubHkoClient(
            [
                {
                    "WTS": warning("WTS", "雷暴警告"),
                    "WHOT": warning("WHOT", "酷热天气警告"),
                },
                {"WTS": warning("WTS", "雷暴警告")},
            ],
            {"details": []},
        )
        poller = HkoWarningPoller(client)

        poller.poll_once(received_at=POLL_TIME)
        result = poller.poll_once(received_at=POLL_TIME)

        self.assertTrue(result.changed)
        self.assertEqual(len(result.signals), 1)
        self.assertIn("取消或不再生效", result.signals[0].raw_text)
        self.assertIn("WHOT", result.signals[0].raw_text)

    def test_warning_info_failure_still_emits_degraded_signal(self) -> None:
        client = StubHkoClient(
            [{"WTS": warning("WTS", "雷暴警告")}],
            HkoFetchError("warningInfo request timed out"),
        )

        result = HkoWarningPoller(client).poll_once(received_at=POLL_TIME)

        self.assertTrue(result.changed)
        self.assertTrue(result.degraded)
        self.assertIn("warningInfo", result.error or "")
        self.assertEqual(len(result.signals), 1)
        self.assertIn("仅根据 warnsum 生成", result.signals[0].raw_text)

    def test_malformed_warning_info_also_uses_degraded_signal(self) -> None:
        client = StubHkoClient(
            [{"WTS": warning("WTS", "雷暴警告")}],
            {"details": "unexpected text instead of a list"},
        )

        result = HkoWarningPoller(client).poll_once(received_at=POLL_TIME)

        self.assertTrue(result.degraded)
        self.assertIn("not a list", result.error or "")
        self.assertEqual(len(result.signals), 1)
        self.assertIn("仅根据 warnsum 生成", result.signals[0].raw_text)

    def test_warnsum_failure_returns_error_without_raising(self) -> None:
        client = StubHkoClient(
            [HkoFetchError("warnsum request timed out")],
            {"details": []},
        )

        result = HkoWarningPoller(client).poll_once(received_at=POLL_TIME)

        self.assertFalse(result.changed)
        self.assertTrue(result.degraded)
        self.assertFalse(result.stale)
        self.assertEqual(result.signals, ())
        self.assertIn("timed out", result.error or "")

    def test_failure_after_success_keeps_last_good_snapshot(self) -> None:
        summary = {"WTS": warning("WTS", "雷暴警告")}
        client = StubHkoClient(
            [summary, HkoFetchError("temporary network failure")],
            {"details": []},
        )
        poller = HkoWarningPoller(client)
        poller.poll_once(received_at=POLL_TIME)

        result = poller.poll_once(received_at=POLL_TIME)

        self.assertTrue(result.stale)
        self.assertEqual(result.active_codes, frozenset({"WTS"}))
        self.assertEqual(poller.last_successful_warnsum, summary)

    def test_poll_interval_must_stay_within_contract_range(self) -> None:
        client = StubHkoClient([{}], {"details": []})

        with self.assertRaises(ValueError):
            HkoWarningPoller(client, poll_interval_s=30)
        with self.assertRaises(ValueError):
            HkoWarningPoller(client, poll_interval_s=180)


if __name__ == "__main__":
    unittest.main()
