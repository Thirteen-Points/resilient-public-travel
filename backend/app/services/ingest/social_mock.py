"""Scripted, clearly labelled social-media signals for the project demo.

This module never contacts a real social network.  It emits three simulated
``Signal`` objects on a short, deterministic timeline and then exits.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence
from uuid import uuid4

from ..signal_models import Signal


SIMULATION_MARKER = "【模拟社媒帖】"
SOURCE_NAME = "ResilientRoute 模拟社媒流"
MAX_SCENARIO_SECONDS = 30.0
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class MockSocialPost:
    """Internal script item; this is not a replacement Signal contract."""

    sequence: int
    offset_seconds: float
    author_hint: str
    raw_text: str


DEFAULT_SCENARIO: tuple[MockSocialPost, ...] = (
    MockSocialPost(
        sequence=1,
        offset_seconds=0.0,
        author_hint="模拟乘客_红磡",
        raw_text="【模拟社媒帖】红磡站的列车停留得比平时久，现场广播请乘客稍候；情况尚未确认。",
    ),
    MockSocialPost(
        sequence=2,
        offset_seconds=10.0,
        author_hint="模拟乘客_会展",
        raw_text="【模拟社媒帖】在会展站候车时感觉东铁线行程似乎受阻，暂时只是一名乘客的观察。",
    ),
    MockSocialPost(
        sequence=3,
        offset_seconds=20.0,
        author_hint="模拟通勤者_金钟",
        raw_text="【模拟社媒帖】金钟站有乘客等候，广播提示大家耐心稍候；没有官方确认异常。",
    ),
)


@dataclass(frozen=True)
class PlaybackFailure:
    sequence: int
    phase: str
    reason: str


@dataclass(frozen=True)
class PlaybackResult:
    run_id: str
    delivered_signals: tuple[Signal, ...]
    failures: tuple[PlaybackFailure, ...]
    attempted_count: int

    @property
    def completed(self) -> bool:
        return not self.failures and self.attempted_count == 3


class SocialMockPlayer:
    """Play one validated three-post scenario and then return."""

    def __init__(
        self,
        scenario: Sequence[MockSocialPost] = DEFAULT_SCENARIO,
        *,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.scenario = self._validate_scenario(scenario)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep

    @staticmethod
    def _validate_scenario(
        scenario: Sequence[MockSocialPost],
    ) -> tuple[MockSocialPost, ...]:
        posts = tuple(scenario)
        if len(posts) != 3:
            raise ValueError("a social mock scenario must contain exactly 3 posts")

        sequences = [post.sequence for post in posts]
        if any(sequence < 1 for sequence in sequences):
            raise ValueError("post sequence numbers must be positive")
        if len(set(sequences)) != len(sequences):
            raise ValueError("post sequence numbers must be unique")

        if any(post.offset_seconds < 0 for post in posts):
            raise ValueError("post offsets cannot be negative")
        ordered = tuple(sorted(posts, key=lambda post: post.offset_seconds))
        offsets = [post.offset_seconds for post in ordered]
        if len(set(offsets)) != len(offsets):
            raise ValueError("post offsets must be strictly increasing")
        if offsets[-1] > MAX_SCENARIO_SECONDS:
            raise ValueError("all social mock posts must arrive within 30 seconds")

        for post in ordered:
            if not post.author_hint.strip():
                raise ValueError("each social mock post needs a simulated author")
            if SIMULATION_MARKER not in post.raw_text:
                raise ValueError(
                    f"each social mock post must contain {SIMULATION_MARKER}"
                )
        return ordered

    def play(
        self,
        on_signal: Callable[[Signal], None],
        *,
        speed: float = 1.0,
        run_id: str | None = None,
    ) -> PlaybackResult:
        """Play once; speed changes waiting, not the scripted timestamps."""

        if speed <= 0:
            raise ValueError("playback speed must be positive")
        resolved_run_id = run_id or self._new_run_id()
        if not RUN_ID_PATTERN.fullmatch(resolved_run_id):
            raise ValueError(
                "run_id must contain only letters, digits, underscores or hyphens"
            )

        base_time = self._clock()
        if base_time.tzinfo is None or base_time.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")

        delivered: list[Signal] = []
        failures: list[PlaybackFailure] = []
        previous_offset = 0.0
        attempted_count = 0

        for post in self.scenario:
            wait_seconds = (post.offset_seconds - previous_offset) / speed
            if wait_seconds:
                self._sleep(wait_seconds)
            previous_offset = post.offset_seconds
            attempted_count += 1

            try:
                signal = self._to_signal(post, resolved_run_id, base_time)
            except Exception:
                failures.append(
                    PlaybackFailure(
                        sequence=post.sequence,
                        phase="signal_conversion",
                        reason="Signal validation failed",
                    )
                )
                break

            try:
                on_signal(signal)
            except Exception:
                failures.append(
                    PlaybackFailure(
                        sequence=post.sequence,
                        phase="delivery",
                        reason="Signal callback rejected the simulated post",
                    )
                )
                break
            delivered.append(signal)

        return PlaybackResult(
            run_id=resolved_run_id,
            delivered_signals=tuple(delivered),
            failures=tuple(failures),
            attempted_count=attempted_count,
        )

    @staticmethod
    def _new_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{uuid4().hex[:8]}"

    @staticmethod
    def _to_signal(
        post: MockSocialPost,
        run_id: str,
        base_time: datetime,
    ) -> Signal:
        return Signal(
            signal_id=f"social-mock-{run_id}-{post.sequence:03d}",
            received_at=base_time + timedelta(seconds=post.offset_seconds),
            source_type="social",
            source_name=SOURCE_NAME,
            author_hint=post.author_hint,
            raw_text=post.raw_text,
            raw_url=None,
            lang="zh-HK",
            provenance="simulated",
        )


def _json_line(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main(argv: Sequence[str] | None = None) -> int:
    """Play the default scenario exactly once and emit JSON Lines."""

    parser = argparse.ArgumentParser(description="播放一次 ResilientRoute 模拟社媒流")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="播放倍速，必须大于 0；只改变等待时间",
    )
    parser.add_argument(
        "--run-id",
        help="可选的本次播放标识；省略时自动生成",
    )
    args = parser.parse_args(argv)

    def print_signal(signal: Signal) -> None:
        _json_line(
            {
                "type": "simulated_signal",
                "simulation": True,
                "signal": signal.model_dump(mode="json"),
            }
        )

    try:
        result = SocialMockPlayer().play(
            print_signal,
            speed=args.speed,
            run_id=args.run_id,
        )
    except ValueError as exc:
        _json_line({"type": "error", "simulation": True, "error": str(exc)})
        return 2

    _json_line(
        {
            "type": "playback_summary",
            "simulation": True,
            "run_id": result.run_id,
            "delivered": len(result.delivered_signals),
            "attempted": result.attempted_count,
            "completed": result.completed,
            "failures": [
                {
                    "sequence": failure.sequence,
                    "phase": failure.phase,
                    "reason": failure.reason,
                }
                for failure in result.failures
            ],
        }
    )
    return 0 if result.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
