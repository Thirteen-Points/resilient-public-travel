"""Stateful triggers for event, sustained-load and severe-weather changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Callable, TypeVar


LOAD_THRESHOLD = 0.95
LOAD_SUSTAINED_MIN = 5
PUBLISH_CONFIDENCE = 0.60
SEVERE_WEATHER_CODES = {"BLACK_RAIN", "T8", "T9", "T10"}


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    should_replan: bool
    trigger: str | None = None
    reason: str | None = None
    occurred_at: datetime | None = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplanExecution:
    decision: ReplanDecision
    recomputed: bool
    elapsed_ms: float
    within_five_second_budget: bool
    result: object | None = None


T = TypeVar("T")


def dispatch_replan(decision: ReplanDecision, replanner: Callable[[ReplanDecision], T]) -> ReplanExecution:
    """Invoke C-Route only for a positive trigger and preserve its result.

    The returned decision reason is the exact banner text the frontend can
    display.  The coordinator measures, but never conceals, a breach of the
    five-second product budget.
    """

    if not decision.should_replan:
        return ReplanExecution(decision, False, 0.0, True, None)
    started = perf_counter()
    result = replanner(decision)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return ReplanExecution(decision, True, elapsed_ms, elapsed_ms <= 5000.0, result)


class ReplanningMonitor:
    def __init__(self) -> None:
        self._events: dict[str, tuple[int, str, bool]] = {}
        self._load_started: dict[str, datetime] = {}
        self._load_triggered: set[str] = set()
        self._weather_signature: frozenset[str] | None = None

    def observe_event(self, event: dict, *, observed_at: datetime | None = None) -> ReplanDecision:
        now = observed_at or datetime.now(timezone.utc)
        event_id = str(event["event_id"])
        current = (
            int(event.get("version", 1)),
            str(event.get("status", "draft")),
            float(event.get("confidence", 0.0)) >= PUBLISH_CONFIDENCE,
        )
        previous = self._events.get(event_id)
        self._events[event_id] = current
        if previous is None:
            if current[1] in {"published", "updated"} and current[2]:
                return ReplanDecision(True, "event_new", f"路线已更新：新增已发布事件 {event_id}", now)
            return ReplanDecision(False)
        current_active = current[1] in {"published", "updated"} and current[2]
        previous_active = previous[1] in {"published", "updated"} and previous[2]
        if current != previous and (current_active or previous_active):
            if current[1] in {"expired", "rejected"}:
                reason = f"路线已更新：事件 {event_id} 已撤销或过期"
            elif current[2] != previous[2]:
                reason = f"路线已更新：事件 {event_id} 置信度跨过发布阈值"
            else:
                reason = f"路线已更新：事件 {event_id} 内容或状态有变化"
            return ReplanDecision(True, "event_changed", reason, now)
        return ReplanDecision(False)

    def observe_load(
        self,
        route_id: str,
        load_factor: float,
        *,
        observed_at: datetime | None = None,
    ) -> ReplanDecision:
        now = observed_at or datetime.now(timezone.utc)
        if load_factor <= LOAD_THRESHOLD:
            self._load_started.pop(route_id, None)
            self._load_triggered.discard(route_id)
            return ReplanDecision(False)
        started = self._load_started.setdefault(route_id, now)
        if route_id not in self._load_triggered and now - started >= timedelta(minutes=LOAD_SUSTAINED_MIN):
            self._load_triggered.add(route_id)
            return ReplanDecision(
                True,
                "sustained_load",
                f"路线已更新：{route_id} 载客率持续 5 分钟高于 95%",
                now,
                {"route_id": route_id, "load_factor": load_factor},
            )
        return ReplanDecision(False)

    def observe_weather(
        self,
        warning_codes: set[str],
        *,
        observed_at: datetime | None = None,
    ) -> ReplanDecision:
        now = observed_at or datetime.now(timezone.utc)
        signature = frozenset(code.upper() for code in warning_codes)
        previous = self._weather_signature
        self._weather_signature = signature
        if previous is None or signature == previous:
            return ReplanDecision(False)
        changed_severe = (signature ^ previous) & SEVERE_WEATHER_CODES
        if changed_severe:
            labels = "、".join(sorted(changed_severe))
            return ReplanDecision(
                True,
                "weather_changed",
                f"路线已更新：严重天气警告变化（{labels}）",
                now,
                {"warning_codes": sorted(signature)},
            )
        return ReplanDecision(False)
