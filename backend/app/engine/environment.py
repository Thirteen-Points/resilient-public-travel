"""Calendar and weather inputs; weather coefficients remain explicit simulations.

Only reviewer-approved published weather Events are interpreted. Signals,
pending reports and arbitrary request parameters cannot activate penalties.
"""
from datetime import date
import math
import re

from ..graph.adapter import DataUnavailable


ALIASES = {
    "AMBER_RAIN": "amber_rainstorm", "WRAINA": "amber_rainstorm",
    "RED_RAIN": "red_rainstorm", "WRAINR": "red_rainstorm",
    "BLACK_RAIN": "black_rainstorm", "WRAINB": "black_rainstorm",
    "T1": "t1", "TC1": "t1", "T3": "t3", "TC3": "t3",
    "T8": "t8", "TC8NE": "t8", "TC8SE": "t8", "TC8NW": "t8", "TC8SW": "t8",
    "T9": "t8", "TC9": "t8", "T10": "t8", "TC10": "t8",
}
LABELS = {"黃色暴雨": "amber_rainstorm", "黄色暴雨": "amber_rainstorm",
          "紅色暴雨": "red_rainstorm", "红色暴雨": "red_rainstorm",
          "黑色暴雨": "black_rainstorm", "八號": "t8", "八号": "t8",
          "九號": "t8", "九号": "t8", "十號": "t8", "十号": "t8",
          "三號": "t3", "三号": "t3", "一號": "t1", "一号": "t1"}


def calendar_holidays(payload):
    """Consume verified PH rows; fail on malformed verified dates."""
    holidays = []
    for row in payload.get("public_holidays_2026", ()):
        if row.get("verified") is True and row.get("schedule_type") == "sunday_ph":
            holidays.append(date.fromisoformat(row["date"]).isoformat())
    return tuple(sorted(set(holidays)))


def validate_weather_policy(payload):
    for condition, row in payload.get("weather_conditions", {}).items():
        for value in [row.get("walk_speed_factor"), *row.get("mode_penalties", {}).values()]:
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise DataUnavailable(f"Invalid weather coefficient: {condition}")
    for mode, value in payload.get("reliability_cv", {}).get("values", {}).items():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise DataUnavailable(f"Invalid weather reliability coefficient: {mode}")
    return payload


def approved_weather_conditions(event):
    if (event.get("event_type") != "weather" or event.get("status") != "published"
            or not event.get("reviewed_by") or float(event.get("confidence", 0)) < .6):
        return set()
    # Read the approved Event itself, never unapproved or subsequently edited Signals.
    text = " ".join(str(event.get(key, "")) for key in ("title", "summary"))
    if re.search(r"取消|不再生效|解除|cancel(?:led)?|cleared", text, re.I):
        return set()
    tokens = re.findall(r"[A-Z][A-Z0-9_]*", text.upper())
    conditions = {ALIASES[token] for token in tokens if token in ALIASES}
    conditions.update(condition for label, condition in LABELS.items() if label in text)
    return conditions


def weather_effect(events, policy, mode, at, is_active):
    duration, speed, conditions, event_ids = 1.0, 1.0, set(), []
    rows = policy.get("weather_conditions", {}) if policy else {}
    for event in events:
        if not is_active(event, at):
            continue
        selected = approved_weather_conditions(event)
        for condition in selected:
            row = rows.get(condition)
            if not row:
                continue
            conditions.add(condition)
            event_ids.append(event["event_id"])
            penalty = row["mode_penalties"].get(mode, 1.0)
            if penalty == 0:
                return 0.0, 0.0, tuple(sorted(conditions)), tuple(sorted(set(event_ids)))
            duration = max(duration, penalty)
            speed = min(speed, row["walk_speed_factor"])
    # WALK's mode penalty models weather delay; speed is an independent mobility
    # adjustment. Both are stated coefficients, not measurements or live closures.
    return duration, speed, tuple(sorted(conditions)), tuple(sorted(set(event_ids)))
