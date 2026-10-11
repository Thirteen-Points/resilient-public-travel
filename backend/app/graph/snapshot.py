"""Atomic event revision publication and optional JSON persistence."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .build import HK, build_graph, freeze, thaw, timestamp


def active(event, at):
    if event.get("status") != "published":
        return False
    window = event.get("window", {})
    starts = [window.get("start"), event.get("published_at")]
    ends = [window.get("end"), event.get("expires_at")]
    return all(not s or timestamp(s) <= at for s in starts) and all(not e or at < timestamp(e) for e in ends)


def matches(event, segment, edge):
    line = event.get("line")
    aliases = {edge.line, edge.line.removeprefix("BUS_").removeprefix("GMB_").removeprefix("FERRY_")}
    if edge.data.get('route_number'):
        aliases.update({edge.data['route_number'], 'BUS_' + edge.data['route_number']})
    if line and line not in aliases:
        return False
    if event.get("mode") and event["mode"] != edge.mode:
        return False
    pair = (segment["from_node"], segment["to_node"])
    return (edge.source, edge.target) == pair or (event.get("direction") == "both" and (edge.target, edge.source) == pair)


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    network: object
    events: tuple
    weather_policy: object = None

    def weather_effect(self, mode, at):
        from ..engine.environment import weather_effect
        return weather_effect(self.events, self.weather_policy, mode, at, active)

    def impact(self, edge, at, until=None):
        factor, slow, ids = 1.0, 1.0, []
        for event in self.events:
            # A traversal must not cross a closure starting during the ride.
            applies = active(event, at)
            for start in (event.get("window", {}).get("start"), event.get("published_at")):
                if until and start and at < timestamp(start) < until:
                    applies = applies or active(event, timestamp(start))
            if not applies:
                continue
            for segment in event.get("affected_segments", ()):
                if matches(event, segment, edge):
                    value = segment["capacity_factor"]
                    factor = min(factor, 0.0 if segment["impact"] == "closed" else value)
                    if segment["impact"] == "slow" and value > 0:
                        slow = max(slow, 1 / value)
                    ids.append(event["event_id"])
        return factor, slow, tuple(sorted(set(ids)))

    def describe(self, at=None):
        at = timestamp(at or datetime.now(HK))
        affected = []
        for edge in self.network.edges:
            factor, slow, ids = self.impact(edge, at)
            if ids:
                affected.append({"from_node": edge.source, "to_node": edge.target, "line": edge.line,
                                 "capacity_factor": factor, "event_ids": list(ids)})
        return {"snapshot_id": self.snapshot_id, "affected_edges": affected}


class SnapshotStore:
    """B calls update_event for deltas or replace_events for a full repository list.

    Build/persist first, then swap a single immutable pointer under a lock.
    Readers pin that pointer for the entire query.
    """
    def __init__(self, network, *, path=None, weather_policy=None):
        self.network = network
        self.path = Path(path) if path else None
        self.weather_policy = freeze(thaw(weather_policy)) if weather_policy else None
        self._lock = threading.RLock()
        self._events = {}
        self._snapshot = self._make({})

    @property
    def current(self):
        with self._lock:
            return self._snapshot

    def _make(self, events):
        payload = {"network": thaw(self.network.source), "holidays": sorted(self.network.holidays),
                   "events": [thaw(events[k]) for k in sorted(events)], "weather_policy": thaw(self.weather_policy)}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        sid = "g_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
        return Snapshot(sid, self.network, tuple(freeze(e) for e in payload["events"]), self.weather_policy)

    def _publish(self, events):
        for event in events.values():
            for segment in event.get("affected_segments", ()):
                if not segment.get("from_node") or not segment.get("to_node"):
                    raise ValueError("Affected segments require from_node and to_node")
                if segment.get("impact") not in {"closed", "reduced_capacity", "slow", "crowded"}:
                    raise ValueError("Unknown segment impact")
                value = segment.get("capacity_factor")
                if not isinstance(value, (float, int)) or not 0 <= value <= 1:
                    raise ValueError("capacity_factor must be in [0, 1]")
            for value in [event.get("published_at"), event.get("expires_at"),
                          event.get("window", {}).get("start"), event.get("window", {}).get("end")]:
                if value:
                    timestamp(value)
        candidate = self._make(events)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps({"network": thaw(self.network.source), "holidays": sorted(self.network.holidays),
                                       "events": [thaw(e) for e in candidate.events],
                                       "weather_policy": thaw(self.weather_policy)}, ensure_ascii=False), encoding="utf-8")
            temp.replace(self.path)
        self._events = {k: freeze(thaw(v)) for k, v in events.items()}
        self._snapshot = candidate
        return candidate

    def update_event(self, event):
        with self._lock:
            old = self._events.get(event["event_id"])
            if old and event.get("version", 0) < old.get("version", 0):
                return self._snapshot
            return self._publish({**self._events, event["event_id"]: event})

    def replace_events(self, events):
        with self._lock:
            return self._publish({e["event_id"]: e for e in events})

    @classmethod
    def restore(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls(build_graph(payload["network"], holidays=payload.get("holidays", ())), path=path,
                    weather_policy=payload.get("weather_policy"))
        store.replace_events(payload["events"])
        return store
