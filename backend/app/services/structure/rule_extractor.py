"""Conservative, offline extraction of an unverified event draft.

The rules only copy categorical facts stated in the Signal text.  They never
create a disruption merely because a station or a line is mentioned.
"""

from __future__ import annotations

import re

from ..signal_models import Signal
from .llm_structurer import (
    ConservativeTemplateFallback,
    ExtractedSegment,
    StructuredEventDraft,
)


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
ERL_ALIASES = ("東鐵綫", "东铁线", "東鐵線", "东铁", "東鐵", "East Rail Line", "East Rail", "ERL", "EAL")
MTR_ALIASES = ("港鐵", "港铁", "地鐵", "地铁", "MTR")
STATION_ORDER = tuple(STATIONS)
CLAUSE_BREAK = re.compile(r"[，,。.;；！!?？\n]|但是|然而|(?<![A-Za-z])but(?![A-Za-z])|但")
SPAN_CONNECTOR = re.compile(
    r"^\s*(?:站|station)?\s*(?:至|到|往|—|–|－|→|->|~|-|to|and)\s*$", re.IGNORECASE
)
NEGATED_DISRUPTION = re.compile(
    r"(?:沒有|没有|未有|無|无|並無|并无|未發生|未发生|未|no|not)"
    r"\s*(?:任何|發生|发生|出現|出现|any)?\s*"
    r"(?:信號故障|信号故障|故障|延誤|延误|停運|停运|停駛|停驶|"
    r"服務暫停|服务暂停|暫停|暂停|異常|异常|颱風|台风|暴雨|"
    r"delay|disruption|failure|suspension)",
    re.IGNORECASE,
)
UNCERTAIN_CLAIM = re.compile(
    r"疑似|似乎|可能|未確認|未确认|尚未確認|尚未确认|未经確認|未经确认|"
    r"未經證實|未经证实|unconfirmed|possibly|suspected|might|maybe|perhaps|seems|apparently|could be",
    re.IGNORECASE,
)


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
    if re.search(r"\b(?:not running(?!\s+(?:late|slow))|no service|no trains(?!\s+(?:delayed|running late))|service (?:is |has been )?(?:stopped|halted)|trains? (?:are |is )?(?:stopped|halted))\b", text, re.I):
        return "closed"
    if _mentions(text, ("暫停服務", "暂停服务", "服務暫停", "服务暂停", "停運", "停运", "停駛", "停驶", "停開", "停开", "封閉", "封闭", "closed", "suspended")):
        return "closed"
    if _mentions(text, ("減班", "减班", "班次減少", "班次减少", "reduced service", "fewer trains", "less frequent")):
        return "reduced_capacity"
    if _mentions(text, ("延誤", "延误", "受阻", "緩慢", "缓慢", "停留較久", "停留较久", "delay", "delays", "delayed", "running late", "running slow", "moving slowly", "crawling", "held up", "stuck")) or re.search(r"\b\d+(?:\s*(?:to|-|–)\s*\d+)?\s*(?:minutes?|mins?)\s+late\b", text, re.I):
        return "slow"
    if _mentions(text, ("擁擠", "拥挤", "人多", "crowded", "packed", "overcrowded")):
        return "crowded"
    return None


def _event_type(text: str) -> str:
    if _mentions(text, ("信號故障", "信号故障", "signal failure", "signal fault", "signal problem", "signal problems", "signalling fault", "signaling fault", "signalling problem", "signaling problem")):
        return "signal_failure"
    if _mentions(text, ("車門故障", "车门故障", "door fault", "door problem", "doors won't close", "doors will not close")):
        return "door_fault"
    if _mentions(text, ("供電故障", "供电故障", "電力故障", "电力故障", "power failure", "power outage", "power cut")):
        return "power_failure"
    if _mentions(text, ("列車故障", "列车故障", "train failure", "train broke down", "train breakdown", "broken down train")):
        return "train_failure"
    if _mentions(text, ("颱風", "台风", "暴雨", "雷暴", "typhoon", "rainstorm")):
        return "weather"
    if _mentions(text, ("擁擠", "拥挤", "人潮", "crowd", "crowds", "crowded", "packed", "overcrowded")):
        return "crowd"
    if _mentions(text, ("道路事故", "交通意外", "road accident")):
        return "road_incident"
    return "other"


def _positive_clauses(text: str) -> list[str]:
    """Discard only denied claims, not a separate positive claim after 'but'."""

    clauses = (part.strip() for part in CLAUSE_BREAK.split(text))
    return [
        clause
        for clause in clauses
        if clause
        and not NEGATED_DISRUPTION.search(clause)
        and not re.search(r"\b(?:no|not|never|without|isn't|aren't|wasn't|weren't)\b(?!\s+(?:running(?!\s+(?:late|slow))|trains(?!\s+(?:delayed|running late))|service)\b)|\b(?:normal service|running normally|back to normal|no longer|resumed|resolved)\b", clause, re.I)
        and not UNCERTAIN_CLAIM.search(clause)
        and (_impact(clause) is not None or _event_type(clause) != "other")
    ]


def _adjacent(first: str, second: str) -> bool:
    """Event segments must correspond to one graph edge in the six-stop corridor."""

    return abs(STATION_ORDER.index(first) - STATION_ORDER.index(second)) == 1


class RuleEventExtractor:
    """Extract only explicit, contract-safe fields without network access."""

    def extract(self, signal: Signal) -> StructuredEventDraft:
        text = signal.raw_text.strip()
        positive = _positive_clauses(text)
        if not positive:
            return ConservativeTemplateFallback().extract(signal)

        line = "ERL" if any(_mentions(clause, ERL_ALIASES) for clause in positive) else None
        mode = "MTR" if line or any(_mentions(clause, MTR_ALIASES) for clause in positive) else None
        segments: list[ExtractedSegment] = []
        for index, clause in enumerate(positive):
            if not _mentions(clause, ERL_ALIASES):
                continue
            impact = _impact(clause)
            # A following clause with no station can describe the same span,
            # e.g. "HUH to EXC signal failure, cross-harbour service suspended".
            if impact is None and index + 1 < len(positive):
                following = positive[index + 1]
                if not _station_mentions(following):
                    impact = _impact(following)
            if impact is None:
                continue
            mentions = _station_mentions(clause)
            for first, second in zip(mentions, mentions[1:]):
                if not _adjacent(first[2], second[2]):
                    continue
                between = clause[first[1] : second[0]]
                connector = SPAN_CONNECTOR.fullmatch(between)
                # 'and' denotes a span only in the explicit 'between A and B' form.
                if connector and (not re.search(r"\band\s*$", between, re.I) or re.search(r"\bbetween\s*$", clause[:first[0]], re.I)):
                    segment = ExtractedSegment(
                        from_node=first[2], to_node=second[2], impact=impact
                    )
                    if segment not in segments:
                        segments.append(segment)

        direction = None
        supported_text = " ".join(positive)
        if _mentions(supported_text, ("雙向", "双向", "兩個方向", "两个方向", "both directions")):
            direction = "both"
        elif line:
            if _mentions(supported_text, ("往金鐘", "往金钟", "金鐘方向", "金钟方向", "towards Admiralty", "southbound")):
                direction = "southbound"
            elif _mentions(supported_text, ("往大圍", "往大围", "大圍方向", "大围方向", "towards Tai Wai", "northbound")):
                direction = "northbound"

        causes = {_event_type(clause) for clause in positive} - {"other"}
        # Crowding is often a consequence of an explicitly reported fault.
        # It does not replace that cause; two distinct faults remain ambiguous.
        if causes - {"crowd"}:
            causes.discard("crowd")
        return StructuredEventDraft(
            event_type=next(iter(causes)) if len(causes) == 1 else "other",
            title=("Unverified: " if signal.lang == "en" else "待核实：") + text[:108],
            summary=text[:1000],
            mode=mode,
            line=line,
            direction=direction,
            affected_segments=segments,
        )
