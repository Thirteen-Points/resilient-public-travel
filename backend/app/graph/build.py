"""Read the frozen network contract into an immutable directed multigraph."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

HK = timezone(timedelta(hours=8))
MODES = {"MTR", "BUS", "MINIBUS", "WALK", "FERRY"}


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value):
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if result.tzinfo is None:
        result = result.replace(tzinfo=HK)
    return result.astimezone(HK)


def next_departure(t: float, headway_s: float, offset_s: float = 0) -> float:
    """Seconds on the service-day clock; ceil(t / headway) at the terminus."""
    if not math.isfinite(headway_s) or headway_s <= 0:
        raise ValueError("headway_s must be finite and positive")
    return offset_s + math.ceil((t - offset_s) / headway_s) * headway_s


def service_key(at: datetime, holidays=frozenset()):
    at = at.astimezone(HK)
    if at.date().isoformat() in holidays or at.weekday() == 6:
        return "sunday_ph"
    if at.weekday() == 5:
        return "saturday"
    return "weekday_peak" if 7 <= at.hour < 9 or 17 <= at.hour < 19 else "weekday_offpeak"


def clock_seconds(value):
    hour, minute = map(int, value.split(":"))
    return hour * 3600 + minute * 60


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    mode: str
    line: str
    travel_s: float
    walk_m: float
    offset_s: float
    data: Mapping
    reverse: bool = False


@dataclass(frozen=True)
class Network:
    nodes: Mapping
    adjacency: Mapping
    edges: tuple[Edge, ...]
    source: Mapping
    diagnostics: tuple[str, ...]
    holidays: frozenset[str]

    def boarding(self, edge, at, factor=1.0, _transitions=0):
        """Return (departure, effective headway), or None when out of service.

        An onboard passenger continues without paying a new wait at each stop.
        Calendars are checked again at the computed boarding time.
        """
        at = timestamp(at)
        if _transitions > 8:
            return None
        if edge.mode == "WALK":
            return at, 0.0
        if edge.data.get('gtfs_services') is not None:
            from .bus_schedule import boarding
            if not edge.data.get('gtfs_pickup', {}).get(edge.source, True):
                return None
            return boarding(edge, at, factor)
        key = service_key(at, self.holidays)
        if edge.data.get("service_calendar") == "weekday_peak_only" and key != "weekday_peak":
            return None
        schedule = edge.data.get("headway_s", {})
        h = schedule.get(key) if isinstance(schedule, Mapping) else schedule
        if h is None or h <= 0 or factor <= 0:
            return None
        h = h / factor
        midnight = at.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds = (at - midnight).total_seconds()
        hours = edge.data.get("service_hours_reverse") if edge.reverse else None
        hours = hours or edge.data.get("service_hours")
        last = None
        first_departure = None
        if hours:
            start, end = map(clock_seconds, hours.split("-"))
            # The published/estimated window is at the first modelled stop in
            # this direction. Segment times shift it to the boarding station.
            if end < start:
                end += 86400
            for day in (-1, 0):
                first = midnight + timedelta(days=day, seconds=start + edge.offset_s)
                candidate_last = midnight + timedelta(days=day, seconds=end + edge.offset_s)
                if first <= at <= candidate_last:
                    first_departure = first
                    last = candidate_last
                    break
            if last is None:
                return None
        # Keep the established modelled headway phase; the published first and
        # last departures are additional exact boundary trains.
        departure_s = next_departure(seconds, h, edge.offset_s)
        departure = midnight + timedelta(seconds=departure_s)
        if first_departure == at:
            departure = at
        # Recompute at a headway boundary instead of discarding an all-day line
        # or using the old headway beyond its period. Null peak-only service
        # still terminates here, and passengers already onboard may continue.
        boundaries = [midnight + timedelta(hours=hour) for hour in (7, 9, 17, 19, 24)]
        boundary = next(b for b in boundaries if b > at)
        if departure >= boundary and service_key(boundary, self.holidays) != key:
            if last is not None and last < boundary:
                return last, h
            return self.boarding(edge, boundary, factor, _transitions + 1)
        # A published last departure need not coincide with the modelled
        # headway grid. It is still boardable at the stated time.
        if last is not None and departure > last:
            departure = last
        return departure, h


def build_graph(source, *, holidays=()) -> Network:
    if isinstance(source, (str, Path)):
        source = json.loads(Path(source).read_text(encoding="utf-8"))
    source = freeze(source)
    nodes = {node["id"]: node for node in source["nodes"]}
    if len(nodes) != len(source["nodes"]):
        raise ValueError("Duplicate node id")
    edges, diagnostics = [], []
    seen = set()
    for line in source.get("lines", ()):
        lid, mode = line["id"], line["mode"]
        if lid in seen or mode not in MODES - {"WALK"}:
            raise ValueError(f"Invalid or duplicate line: {lid}")
        seen.add(lid)
        # Preserve the source record, but never operate a partial/unverified line.
        missing = sorted(set(line["stops"]) - nodes.keys())
        reasons = []
        if missing:
            reasons.append("missing nodes: " + ", ".join(missing))
        if line.get("demo_only") or line.get("operational_status") == "unverified":
            reasons.append("demo_only/unverified")
        if reasons:
            diagnostics.append(f"Excluded line {lid}: {'; '.join(reasons)}")
            continue
        schedule = line.get("headway_s", {})
        headways = schedule.values() if isinstance(schedule, Mapping) else [schedule]
        if any(h is not None and (not isinstance(h, (int, float)) or not math.isfinite(h) or h <= 0) for h in headways):
            raise ValueError(f"Invalid headway: {lid}")
        stops, times = line["stops"], line["seg_time_s"]
        if len(times) != len(stops) - 1 or any(not math.isfinite(t) or t <= 0 for t in times):
            raise ValueError(f"Invalid segment times: {lid}")
        for reverse in range(2 if line.get("bidirectional", False) else 1):
            order = list(reversed(stops)) if reverse else stops
            durations = list(reversed(times)) if reverse else times
            offset = 0
            for a, b, duration in zip(order, order[1:], durations):
                edges.append(Edge(f"{lid}:{a}>{b}", a, b, mode, lid, duration, 0, offset, line, bool(reverse)))
                offset += duration
    for i, link in enumerate(source.get("walk_links", ())):
        a, b = link["from"], link["to"]
        distance = link.get("walk_m", 0)
        if not math.isfinite(distance) or distance < 0:
            raise ValueError("Invalid walking distance")
        if a not in nodes or b not in nodes:
            diagnostics.append(f"Skipped walk {a}>{b}: missing node")
            continue
        for src, dst in [(a, b)] + ([(b, a)] if link.get("bidirectional", True) else []):
            edges.append(Edge(f"WALK_{i}:{src}>{dst}", src, dst, "WALK", "", 0, distance, 0, link))
    adjacency = {node: tuple(e for e in edges if e.source == node) for node in nodes}
    return Network(freeze(nodes), freeze(adjacency), tuple(edges), source, tuple(diagnostics), frozenset(holidays))
