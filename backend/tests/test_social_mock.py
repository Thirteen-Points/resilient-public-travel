from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

from backend.app.services.ingest.social_mock import (
    DEFAULT_SCENARIO,
    MAX_SCENARIO_SECONDS,
    SIMULATION_MARKER,
    MockSocialPost,
    SocialMockPlayer,
    main,
)
from backend.app.services.signal_models import Signal


BASE_TIME = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)


def post(sequence: int, offset: float) -> MockSocialPost:
    return MockSocialPost(
        sequence=sequence,
        offset_seconds=offset,
        author_hint=f"模拟账号_{sequence}",
        raw_text=f"{SIMULATION_MARKER}第 {sequence} 条测试观察，情况尚未确认。",
    )


def play_once(
    *,
    speed: float = 1.0,
    run_id: str = "test-run",
) -> tuple[list[float], list[Signal]]:
    waits: list[float] = []
    signals: list[Signal] = []
    player = SocialMockPlayer(
        clock=lambda: BASE_TIME,
        sleep=waits.append,
    )
    result = player.play(signals.append, speed=speed, run_id=run_id)
    if not result.completed:
        raise AssertionError("default playback unexpectedly failed")
    return waits, signals


class SocialMockPlayerTestCase(unittest.TestCase):
    def test_default_scenario_contains_exactly_three_posts(self) -> None:
        self.assertEqual(len(DEFAULT_SCENARIO), 3)

    def test_default_offsets_are_ordered_and_within_thirty_seconds(self) -> None:
        offsets = [item.offset_seconds for item in DEFAULT_SCENARIO]

        self.assertEqual(offsets, sorted(offsets))
        self.assertLessEqual(offsets[-1], MAX_SCENARIO_SECONDS)

    def test_callback_receives_each_post_at_its_time(self) -> None:
        waits, signals = play_once()

        self.assertEqual(waits, [10.0, 10.0])
        self.assertEqual(len(signals), 3)
        self.assertEqual(
            [(item.received_at - BASE_TIME).total_seconds() for item in signals],
            [0.0, 10.0, 20.0],
        )

    def test_playback_returns_three_delivered_signals(self) -> None:
        player = SocialMockPlayer(clock=lambda: BASE_TIME, sleep=lambda _value: None)

        result = player.play(lambda _signal: None, run_id="delivery-test")

        self.assertTrue(result.completed)
        self.assertEqual(result.attempted_count, 3)
        self.assertEqual(len(result.delivered_signals), 3)
        self.assertEqual(result.failures, ())

    def test_signal_ids_are_unique_and_use_social_mock_prefix(self) -> None:
        _, signals = play_once()
        signal_ids = [item.signal_id for item in signals]

        self.assertEqual(len(signal_ids), len(set(signal_ids)))
        self.assertTrue(all(item.startswith("social-mock-") for item in signal_ids))
        self.assertTrue(all(not item.startswith("hko-") for item in signal_ids))
        self.assertTrue(all(not item.startswith("mtr-") for item in signal_ids))

    def test_different_run_ids_do_not_collide(self) -> None:
        _, first = play_once(run_id="first-run")
        _, second = play_once(run_id="second-run")

        self.assertTrue(
            set(item.signal_id for item in first).isdisjoint(
                item.signal_id for item in second
            )
        )

    def test_every_item_is_a_valid_existing_signal(self) -> None:
        _, signals = play_once()

        self.assertTrue(all(isinstance(item, Signal) for item in signals))
        for item in signals:
            Signal.model_validate(item.model_dump())

    def test_signal_contract_values_identify_simulation(self) -> None:
        _, signals = play_once()

        for signal in signals:
            self.assertEqual(signal.source_type, "social")
            self.assertEqual(signal.provenance, "simulated")
            self.assertEqual(signal.lang, "zh-HK")
            self.assertIn("模拟", signal.source_name)
            self.assertIn(SIMULATION_MARKER, signal.raw_text)
            self.assertIsNone(signal.raw_url)
            self.assertIn("模拟", signal.author_hint or "")

    def test_negative_offset_is_rejected(self) -> None:
        scenario = (post(1, -1), post(2, 10), post(3, 20))

        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            SocialMockPlayer(scenario)

    def test_scenario_later_than_thirty_seconds_is_rejected(self) -> None:
        scenario = (post(1, 0), post(2, 10), post(3, 31))

        with self.assertRaisesRegex(ValueError, "within 30 seconds"):
            SocialMockPlayer(scenario)

    def test_duplicate_sequence_is_rejected(self) -> None:
        scenario = (post(1, 0), post(1, 10), post(3, 20))

        with self.assertRaisesRegex(ValueError, "must be unique"):
            SocialMockPlayer(scenario)

    def test_duplicate_offset_is_rejected(self) -> None:
        scenario = (post(1, 0), post(2, 10), post(3, 10))

        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            SocialMockPlayer(scenario)

    def test_invalid_run_id_is_rejected_before_delivery(self) -> None:
        delivered: list[Signal] = []
        player = SocialMockPlayer(clock=lambda: BASE_TIME, sleep=lambda _value: None)

        with self.assertRaisesRegex(ValueError, "run_id"):
            player.play(delivered.append, run_id="bad run id")
        self.assertEqual(delivered, [])

    def test_zero_or_negative_speed_is_rejected(self) -> None:
        player = SocialMockPlayer(clock=lambda: BASE_TIME, sleep=lambda _value: None)

        for speed in (0, -1):
            with self.subTest(speed=speed):
                with self.assertRaisesRegex(ValueError, "must be positive"):
                    player.play(lambda _signal: None, speed=speed)

    def test_callback_failure_is_not_counted_as_success(self) -> None:
        delivered: list[Signal] = []

        def fail_on_second(signal: Signal) -> None:
            if len(delivered) == 1:
                raise RuntimeError("test callback failure")
            delivered.append(signal)

        player = SocialMockPlayer(clock=lambda: BASE_TIME, sleep=lambda _value: None)
        result = player.play(fail_on_second, run_id="callback-test")

        self.assertFalse(result.completed)
        self.assertEqual(result.attempted_count, 2)
        self.assertEqual(len(result.delivered_signals), 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].phase, "delivery")

    def test_speed_changes_wait_only_not_order_or_script_timestamps(self) -> None:
        normal_waits, normal_signals = play_once(speed=1.0, run_id="normal")
        fast_waits, fast_signals = play_once(speed=10.0, run_id="fast")

        self.assertEqual(normal_waits, [10.0, 10.0])
        self.assertEqual(fast_waits, [1.0, 1.0])
        self.assertEqual(
            [item.received_at for item in normal_signals],
            [item.received_at for item in fast_signals],
        )
        self.assertEqual(
            [item.author_hint for item in normal_signals],
            [item.author_hint for item in fast_signals],
        )

    def test_main_plays_once_and_prints_three_signals_and_one_summary(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["--speed", "1000000000", "--run-id", "cli-test"])

        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(lines), 4)
        self.assertEqual(
            [line["type"] for line in lines],
            ["simulated_signal"] * 3 + ["playback_summary"],
        )
        self.assertTrue(all(line["simulation"] is True for line in lines))
        self.assertTrue(lines[-1]["completed"])


if __name__ == "__main__":
    unittest.main()
