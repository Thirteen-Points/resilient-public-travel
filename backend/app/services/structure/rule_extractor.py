"""Conservative, offline extraction of an unverified event draft.

The rules only copy categorical facts stated in the Signal text.  They never
create a disruption merely because a station or a line is mentioned.
"""

from __future__ import annotations

import re

from ..signal_models import Signal
from .llm_structurer import ExtractedSegment, StructuredEventDraft


# This small dictionary is deliberately limited to the six-station corridor
# in contracts/seed/network.seed.json and the T2.6 draft schema.
STATIONS: dict[str, tuple[str, ...]] = {
    "TAW": ("大圍", "大围", "Tai Wai", "TAW"),
    "KOT": ("九龍塘", "九龙塘", "Kowloon Tong", "KOT"),
    "MKK": ("旺角東", "旺角东", "Mong Kok East", "MKK"),
    "HUH": ("紅磡", "红磡", "Hung Hom", "HUH"),
    "EXC": ("會展", "会展", "Exhibition Centre", "EXC"),
    "ADM": ("金鐘", "金钟", "Admiralty", "ADM"),
}
ERL_ALIASES = ("東鐵綫", "东铁线", "東鐵線", "东铁", "東鐵", "East Rail Line", "ERL", "EAL")
MTR_ALIASES = ("港鐵", "港铁", "地鐵", "地铁", "MTR")
SPAN_CONNECTOR = re.compile(r"^\s*(?:站)?\s*(?:至|到|往|—|–|－|→|->|~|－)\s*$", re.IGNORECASE)
NEGATED_DISRUPTION = re.compile(r"(?:沒有|没有|未有|無|无|並無|并无|未發生|未发生)(?:\S{0,2})(?:故障|延誤|延误|停運|停运|停駛|停驶|異常|异常)")


def _mentions(text: str, aliases: tuple[str, ...]) -> bool:
    """Match Chinese substrings and whole English/code tokens."""

    for alias in aliases:
        if alias.isascii():
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE):
                return True
        elif alias in text:
            return True
    return False


def _station_mentions(text: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for code, aliases in STATIONS.items():
        for alias in aliases:
            if alias.isascii():
                pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
            else:
                pattern = re.escape(alias)
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append((match.start(), match.end(), code))
    # Prefer the longest alias where an English name and code could overlap.
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    nonoverlapping: list[tuple[int, int, str]] = []
    for item in found:
        if nonoverlapping and item[0] < nonoverlapping[-1][1]:
            continue
        nonoverlapping.append(item)
    return nonoverlapping


def _impact(text: str) -> str | None:
    if _mentions(text, ("暫停服務", "暂停服务", "停運", "停运", "停駛", "停驶", "停開", "停开", "封閉", "封闭", "closed", "suspended")):
        return "closed"
    if _mentions(text, ("減班", "减班", "班次減少", "班次减少", "reduced service")):
        return "reduced_capacity"
    if _mentions(text, ("延誤", "延误", "受阻", "緩慢", "缓慢", "停留較久", "停留较久", "delay", "delayed")):
        return "slow"
    if _mentions(text, ("擁擠", "拥挤", "人多", "crowded")):
        return "crowded"
    return None


def _event_type(text: str) -> str:
    if _mentions(text, ("信號故障", "信号故障", "signal failure")):
        return "signal_failure"
    if _mentions(text, ("車門故障", "车门故障", "door fault")):
        return "door_fault"
    if _mentions(text, ("供電故障", "供电故障", "電力故障", "电力故障", "power failure")):
        return "power_failure"
    if _mentions(text, ("列車故障", "列车故障", "train failure")):
        return "train_failure"
    if _mentions(text, ("颱風", "台风", "暴雨", "雷暴", "typhoon", "rainstorm")):
        return "weather"
    if _mentions(text, ("擁擠", "拥挤", "人潮", "crowd")):
        return "crowd"
    if _mentions(text, ("道路事故", "交通意外", "road accident")):
        return "road_incident"
    return "other"


class RuleEventExtractor:
    """Extract only explicit, contract-safe fields without network access."""

    def extract(self, signal: Signal) -> StructuredEventDraft:
        text = signal.raw_text.strip()
        # A denial of an incident is not positive evidence of one.  Retain the
        # original report for the reviewer, but make no categorical claims.
        denied = bool(NEGATED_DISRUPTION.search(text))
        mentions = _station_mentions(text)
        line = "ERL" if not denied and _mentions(text, ERL_ALIASES) else None
        mode = "MTR" if line or (not denied and _mentions(text, MTR_ALIASES)) else None
        impact = None if denied else _impact(text)
        segments: list[ExtractedSegment] = []
        if line and impact:
            for first, second in zip(mentions, mentions[1:]):
                if first[2] == second[2]:
                    continue
                between = text[first[1] : second[0]]
                if SPAN_CONNECTOR.fullmatch(between):
                    segments.append(
                        ExtractedSegment(
                            from_node=first[2], to_node=second[2], impact=impact
                        )
                    )

        direction = None
        if not denied and _mentions(text, ("雙向", "双向", "兩個方向", "两个方向", "both directions")):
            direction = "both"
        elif line and not denied:
            if _mentions(text, ("往金鐘", "往金钟", "金鐘方向", "金钟方向", "towards Admiralty")):
                direction = "southbound"
            elif _mentions(text, ("往大圍", "往大围", "大圍方向", "大围方向", "towards Tai Wai")):
                direction = "northbound"

        return StructuredEventDraft(
            event_type="other" if denied else _event_type(text),
            title="待核实：" + text[:115],
            summary=text[:1000],
            mode=mode,
            line=line,
            direction=direction,
            affected_segments=segments,
        )
