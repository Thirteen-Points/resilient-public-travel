from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.app.services.ingest.mtr_eta import (
    CORRIDOR_STATIONS,
    MtrDetectionConfig,
    MtrEtaAnomalyPoller,
    MtrEtaClient,
    MtrEtaFetchError,
    parse_station_observation,
)
from backend.app.services.signal_models import Signal


POLL_TIME = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


def payload(
    station_code: str,
    *,
    ttnt: int = 2,
    isdelay: str = "N",
    valid: str = "Y",
) -> dict:
    return {
        "status": 1,
        "message": "successful",
        "isdelay": isdelay,
        "data": {
            f"EAL-{station_code}": {
                "UP": [{"ttnt": str(ttnt), "valid": valid}],
                "DOWN": [{"ttnt": str(ttnt + 1), "valid": valid}],
            }
        },
    }


def poll_round(
    abnormal: tuple[str, ...] = (),
    *,
    failures: tuple[str, ...] = (),
    use_official_delay: bool = False,
) -> dict[str, dict | Exception]:
    result: dict[str, dict | Exception] = {}
    for station_code, _ in CORRIDOR_STATIONS:
        if station_code in failures:
            result[station_code] = MtrEtaFetchError("timeout")
        else:
            result[station_code] = payload(
                station_code,
                ttnt=12 if station_code in abnormal else 2,
                isdelay="Y" if use_official_delay and station_code in abnormal else "N",
            )
    return result


class FakeMtrClient:
    def __init__(self, rounds: list[dict[str, dict | Exception]]) -> None:
        self.rounds = rounds
        self.round_index = 0
        self.calls_in_round = 0

    def fetch_station(self, station_code: str) -> dict:
        current = self.rounds[min(self.round_index, len(self.rounds) - 1)]
        value = current[station_code]
        self.calls_in_round += 1
        if self.calls_in_round == len(CORRIDOR_STATIONS):
            self.calls_in_round = 0
            self.round_index += 1
        if isinstance(value, Exception):
            raise value
        return value


class FakeHttpResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class MtrEtaAnomalyTestCase(unittest.TestCase):
    def test_client_converts_invalid_json_to_recoverable_error(self) -> None:
        client = MtrEtaClient(opener=lambda *_args, **_kwargs: FakeHttpResponse(b"{"))

        with self.assertRaisesRegex(MtrEtaFetchError, "not valid JSON"):
            client.fetch_station("HUH")

    def test_client_converts_timeout_to_recoverable_error(self) -> None:
        def timeout_opener(*_args: object, **_kwargs: object) -> object:
            raise TimeoutError("timed out")

        client = MtrEtaClient(opener=timeout_opener)

        with self.assertRaisesRegex(MtrEtaFetchError, "request failed"):
            client.fetch_station("HUH")

    def test_normal_six_station_data_does_not_emit(self) -> None:
        result = MtrEtaAnomalyPoller(FakeMtrClient([poll_round()])).poll_once()

        self.assertEqual(result.signals, ())
        self.assertEqual(len(result.observations), 6)
        self.assertFalse(result.degraded)
        self.assertFalse(result.insufficient_data)

    def test_single_station_anomaly_does_not_emit(self) -> None:
        result = MtrEtaAnomalyPoller(
            FakeMtrClient([poll_round(("HUH",))])
        ).poll_once()

        self.assertEqual(result.signals, ())
        self.assertEqual(result.anomalous_stations, ("HUH",))
        self.assertEqual(result.qualifying_stations, ())

    def test_non_adjacent_anomalies_do_not_qualify(self) -> None:
        result = MtrEtaAnomalyPoller(
            FakeMtrClient([poll_round(("TAW", "HUH"))])
        ).poll_once()

        self.assertEqual(result.signals, ())
        self.assertEqual(result.qualifying_stations, ())

    def test_adjacent_anomalies_need_two_polls(self) -> None:
        poller = MtrEtaAnomalyPoller(FakeMtrClient([poll_round(("HUH", "EXC"))]))

        result = poller.poll_once()

        self.assertEqual(result.signals, ())
        self.assertEqual(result.qualifying_stations, ("HUH", "EXC"))
        self.assertEqual(result.consecutive_polls, 1)

    def test_adjacent_anomalies_twice_emit_one_signal(self) -> None:
        abnormal = poll_round(("HUH", "EXC"))
        poller = MtrEtaAnomalyPoller(FakeMtrClient([abnormal, abnormal]))

        poller.poll_once(received_at=POLL_TIME)
        result = poller.poll_once(received_at=POLL_TIME)

        self.assertEqual(len(result.signals), 1)
        self.assertEqual(result.consecutive_polls, 2)

    def test_persistent_third_poll_does_not_repeat_signal(self) -> None:
        abnormal = poll_round(("HUH", "EXC"))
        poller = MtrEtaAnomalyPoller(FakeMtrClient([abnormal, abnormal, abnormal]))

        poller.poll_once(received_at=POLL_TIME)
        second = poller.poll_once(received_at=POLL_TIME)
        third = poller.poll_once(received_at=POLL_TIME)

        self.assertEqual(len(second.signals), 1)
        self.assertEqual(third.signals, ())
        self.assertEqual(third.consecutive_polls, 3)

    def test_recovery_resets_and_recurrence_can_emit(self) -> None:
        abnormal = poll_round(("HUH", "EXC"))
        normal = poll_round()
        poller = MtrEtaAnomalyPoller(
            FakeMtrClient([abnormal, abnormal, normal, abnormal, abnormal])
        )

        results = [poller.poll_once(received_at=POLL_TIME) for _ in range(5)]

        self.assertEqual(len(results[1].signals), 1)
        self.assertEqual(results[2].consecutive_polls, 0)
        self.assertEqual(len(results[4].signals), 1)

    def test_official_isdelay_is_an_anomaly_reason(self) -> None:
        observation = parse_station_observation(
            payload("HUH", isdelay="Y"), "HUH", "红磡", MtrDetectionConfig()
        )

        self.assertTrue(observation.official_delay)
        self.assertTrue(observation.anomalous)
        self.assertIn("isdelay=Y", observation.anomaly_reasons[0])

    def test_high_ttnt_is_an_anomaly_reason(self) -> None:
        observation = parse_station_observation(
            payload("HUH", ttnt=11), "HUH", "红磡", MtrDetectionConfig()
        )

        self.assertTrue(observation.anomalous)
        self.assertIn("ttnt=11", observation.anomaly_reasons[0])

    def test_station_timeout_is_not_treated_as_delay(self) -> None:
        result = MtrEtaAnomalyPoller(
            FakeMtrClient([poll_round(failures=("HUH",))])
        ).poll_once()

        self.assertTrue(result.degraded)
        self.assertEqual(result.anomalous_stations, ())
        self.assertEqual(result.signals, ())
        self.assertEqual(result.failures[0].station_code, "HUH")

    def test_partial_failure_can_still_detect_with_enough_data(self) -> None:
        abnormal = poll_round(("HUH", "EXC"), failures=("TAW",))
        poller = MtrEtaAnomalyPoller(FakeMtrClient([abnormal, abnormal]))

        poller.poll_once(received_at=POLL_TIME)
        result = poller.poll_once(received_at=POLL_TIME)

        self.assertTrue(result.degraded)
        self.assertFalse(result.insufficient_data)
        self.assertEqual(len(result.signals), 1)

    def test_all_failures_keep_last_successful_snapshot(self) -> None:
        all_failed = poll_round(failures=tuple(code for code, _ in CORRIDOR_STATIONS))
        poller = MtrEtaAnomalyPoller(FakeMtrClient([poll_round(), all_failed]))
        poller.poll_once()
        snapshot = dict(poller.last_successful_observations)

        result = poller.poll_once()

        self.assertTrue(result.degraded)
        self.assertTrue(result.insufficient_data)
        self.assertTrue(result.used_cached_snapshot)
        self.assertEqual(result.signals, ())
        self.assertEqual(poller.last_successful_observations, snapshot)

    def test_invalid_structure_is_recoverable(self) -> None:
        malformed = {code: {"status": 1, "data": {}} for code, _ in CORRIDOR_STATIONS}
        result = MtrEtaAnomalyPoller(FakeMtrClient([malformed])).poll_once()

        self.assertTrue(result.degraded)
        self.assertTrue(result.insufficient_data)
        self.assertEqual(len(result.failures), 6)
        self.assertEqual(result.signals, ())

    def test_generated_signal_uses_existing_contract_and_provenance(self) -> None:
        abnormal = poll_round(("HUH", "EXC"))
        poller = MtrEtaAnomalyPoller(FakeMtrClient([abnormal, abnormal]))
        poller.poll_once(received_at=POLL_TIME)

        signal = poller.poll_once(received_at=POLL_TIME).signals[0]

        self.assertIsInstance(signal, Signal)
        self.assertEqual(signal.provenance, "real-derived")
        self.assertEqual(signal.source_type, "official")
        self.assertEqual(signal.lang, "zh-HK")
        self.assertIn("东铁线", signal.raw_text)
        self.assertIn("HUH（红磡）", signal.raw_text)
        self.assertIn("连续 2 次", signal.raw_text)
        self.assertIn("疑似延误，尚未人工确认", signal.raw_text)


if __name__ == "__main__":
    unittest.main()
