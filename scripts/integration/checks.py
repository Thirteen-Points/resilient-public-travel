"""Small, dependency-free boundary checks, not a replacement for B's JSON Schemas."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import subprocess

MODES = {"MTR", "BUS", "MINIBUS", "WALK", "FERRY"}
PROVENANCE = {"real", "real-derived", "simulated"}
STATUSES = {"draft", "pending_review", "published", "updated", "expired", "rejected"}


@dataclass
class Finding:
    code: str
    path: str
    message: str


def require(condition, code, path, message, findings):
    if not condition:
        findings.append(Finding(code, path, message))


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def number(obj, key, path, findings, low=0, high=None):
    value = obj.get(key)
    require(finite(value) and value >= low and (high is None or value <= high),
            "NUMBER", f"{path}.{key}", f"Expected finite number in [{low}, {high}]", findings)


def fields(obj, keys, path, findings):
    require(isinstance(obj, dict), "TYPE", path, "Expected object", findings)
    if not isinstance(obj, dict):
        return False
    for key in keys.split():
        require(key in obj, "REQUIRED", f"{path}.{key}", "Missing contract field", findings)
    return True


def provenance(obj, path, findings):
    require(obj.get("provenance") in PROVENANCE, "PROVENANCE", path, "Missing/invalid provenance", findings)
    notes = " ".join(str(v) for k, v in obj.items() if "note" in k)
    require(not (obj.get("provenance") == "real" and "待核实" in notes),
            "UNVERIFIED_REAL", path, "Unverified values are labelled real", findings)


def unique(rows, key, path, findings):
    values = [r.get(key) for r in rows]
    require(None not in values and len(set(values)) == len(values), "UNIQUE", path,
            f"Missing or duplicate {key}", findings)


def check_network(network):
    f = []
    fields(network, "nodes lines walk_links meta", "network", f)
    nodes, lines = network.get("nodes", []), network.get("lines", [])
    require(bool(nodes) and bool(lines), "EMPTY", "network", "Network must contain nodes and lines", f)
    unique(nodes, "id", "network.nodes", f)
    unique(lines, "id", "network.lines", f)
    ids = {n["id"] for n in nodes}
    for n in nodes:
        p = f"network.nodes[{n['id']}]"
        fields(n, "id kind lat lng provenance", p, f)
        number(n, "lat", p, f, -90, 90)
        number(n, "lng", p, f, -180, 180)
        provenance(n, p, f)
    for line in lines:
        p = f"network.lines[{line['id']}]"
        fields(line, "mode stops seg_time_s headway_s capacity_per_vehicle provenance", p, f)
        require(line.get("mode") in MODES, "MODE", p, "Invalid transit mode", f)
        stops = line.get("stops", [])
        require(len(stops) >= 2 and len(line.get("seg_time_s", [])) == len(stops) - 1,
                "SEGMENTS", p, "Segment times must match adjacent stop pairs", f)
        for stop in stops:
            require(stop in ids, "NODE_REF", p, f"Unknown stop {stop}", f)
        for value in line.get("seg_time_s", []):
            require(finite(value) and value > 0, "TRAVEL_TIME", p, "Nonpositive segment time", f)
        for day, value in line.get("headway_s", {}).items():
            require(value is None or (finite(value) and value > 0), "HEADWAY", p,
                    f"{day}: headway must be positive or null (no service)", f)
        number(line, "capacity_per_vehicle", p, f, 1)
        provenance(line, p, f)
    for link in network.get("walk_links", []):
        p = f"network.walk_links[{link.get('from')}->{link.get('to')}]"
        require(link.get("from") in ids and link.get("to") in ids, "NODE_REF", p, "Unknown walking endpoint", f)
        number(link, "walk_m", p, f)
        number(link, "walk_s", p, f)
        provenance(link, p, f)
    counts = network.get("meta", {}).get("counts", {})
    for key in ("nodes", "lines", "walk_links"):
        if key in counts:
            require(counts[key] == len(network.get(key, [])), "COUNT", f"network.meta.counts.{key}", "Declared count differs", f)
    require(network.get("meta", {}).get("catchment_m") == 800, "CATCHMENT", "network.meta", "Expected 800m catchment", f)
    return f


def check_events(bundle, network):
    f = []
    events, signals = bundle.get("events", []), bundle.get("signals", [])
    require(bool(events), "EMPTY", "events", "No events", f)
    unique(events, "event_id", "events", f)
    unique(signals, "signal_id", "signals", f)
    signal_ids = {s["signal_id"] for s in signals}
    nodes = {n["id"] for n in network.get("nodes", [])}
    for event in events:
        p = f"events[{event['event_id']}]"
        fields(event, "version status affected_segments confidence audit_log provenance", p, f)
        require(event.get("status") in STATUSES, "STATUS", p, "Unknown event status", f)
        number(event, "confidence", p, f, 0, 1)
        provenance(event, p, f)
        for sid in event.get("signals", []):
            require(sid in signal_ids, "SIGNAL_REF", p, f"Unknown signal {sid}", f)
        for seg in event.get("affected_segments", []):
            require(seg.get("from_node") in nodes and seg.get("to_node") in nodes,
                    "NODE_REF", p, "Unknown affected endpoint", f)
            require(seg.get("impact") in {"closed", "reduced_capacity", "slow", "crowded"}, "IMPACT", p, "Invalid impact", f)
            number(seg, "capacity_factor", p, f, 0, 1)
            if seg.get("impact") == "closed":
                require(seg.get("capacity_factor") == 0, "CLOSURE", p, "Closed segment must have zero capacity", f)
        if event.get("status") in {"published", "updated"}:
            require(bool(event.get("published_at")) and bool(event.get("reviewed_by")),
                    "REVIEW", p, "Published event needs timestamp and reviewer", f)
            require(any(a.get("action") in {"published", "approved", "updated"} for a in event.get("audit_log", [])),
                    "AUDIT", p, "Published event lacks audit evidence", f)
    return f


def check_route(route, network, origin=None, destination=None, wheelchair=False):
    f = []
    p = f"routes[{route.get('route_id', '?')}]"
    fields(route, "route_id label legs total score score_breakdown warnings notes explain evidence provenance", p, f)
    provenance(route, p, f)
    number(route, "score", p, f, 0, 1)
    total = route.get("total", {})
    for key in ("time_s", "transfers", "walk_m", "fare_hkd", "freshness_s"):
        number(total, key, p + ".total", f)
    number(total, "reliability", p + ".total", f, 0, 1)
    interval = total.get("time_range_s", [])
    require(isinstance(interval, list) and len(interval) == 2 and all(finite(v) for v in interval)
            and 0 <= interval[0] <= total.get("time_s", -1) <= interval[1],
            "TIME_RANGE", p, "ETA must lie within its time range", f)
    require(bool(route.get("evidence")), "EVIDENCE", p, "Route requires source/event evidence", f)
    require(isinstance(route.get("explain"), str) and bool(route["explain"].strip()),
            "EXPLAIN", p, "Missing explanation", f)
    breakdown = route.get("score_breakdown", [])
    require(len({b.get("criterion") for b in breakdown}) >= 3, "SCORE_DIMENSIONS", p, "At least three scoring dimensions required", f)
    for b in breakdown:
        for key in ("normalized", "weight", "contribution"):
            number(b, key, p + ".score_breakdown", f, 0, 1)
        if all(finite(b.get(k)) for k in ("contribution", "normalized", "weight")):
            require(math.isclose(b["contribution"], b["normalized"] * b["weight"], abs_tol=0.001),
                    "SCORE_TERM", p, "Contribution differs from normalized × weight", f)
    if breakdown and all(finite(b.get("contribution")) for b in breakdown) and finite(route.get("score")):
        require(math.isclose(sum(b["contribution"] for b in breakdown), route["score"], abs_tol=0.002),
                "SCORE_SUM", p, "Score differs from sum of disclosed contributions", f)
    legs = route.get("legs", [])
    require(bool(legs), "EMPTY", p, "Route has no legs", f)
    nodes = {n["id"] for n in network.get("nodes", [])}
    node_by_id = {n["id"]: n for n in network.get("nodes", [])}
    line_by_id = {line["id"]: line for line in network.get("lines", [])}
    for i, leg in enumerate(legs):
        lp = f"{p}.legs[{i}]"
        fields(leg, "mode from to in_vehicle_s walk_m accessible provenance", lp, f)
        if "in_vehicle_s" in leg:
            number(leg, "in_vehicle_s", lp, f)
        number(leg, "walk_m", lp, f)
        require(leg.get("mode") in MODES, "MODE", lp, "Unknown mode", f)
        require(leg.get("from") in nodes and leg.get("to") in nodes, "NODE_REF", lp, "Unknown route endpoint", f)
        provenance(leg, lp, f)
        if i:
            require(legs[i-1].get("to") == leg.get("from"), "CONTINUITY", lp, "Missing connecting leg", f)
        if wheelchair:
            mode = leg.get("mode")
            transit_default = mode in {"MTR", "BUS"}
            line = line_by_id.get(leg.get("line"), {})
            endpoints = (node_by_id.get(leg.get("from"), {}), node_by_id.get(leg.get("to"), {}))
            explicit_negative = any(value is False or value == "partial" for value in
                                    (line.get("accessible"), *(node.get("accessible") for node in endpoints)))
            if mode == "BUS":
                low_floor = line.get("low_floor", line.get("lowfloor"))
                explicit_negative |= low_floor is False or low_floor == "partial"
            require(mode != "MINIBUS" and leg.get("accessible") is True and
                    not leg.get("stairs", False) and not explicit_negative and
                    (transit_default or leg.get("accessible") is True),
                    "WHEELCHAIR_LEG", lp,
                    "Minibus, stairs, explicit negative accessibility or inaccessible leg", f)
    if legs:
        if origin is not None:
            require(legs[0].get("from") == origin, "ORIGIN", p, "Route misses query origin", f)
        if destination is not None:
            require(legs[-1].get("to") == destination, "DESTINATION", p, "Route misses query destination", f)
    if wheelchair:
        require(finite(total.get("walk_m")) and total["walk_m"] <= 400,
                "WHEELCHAIR_WALK", p, "Wheelchair walk exceeds 400m", f)
    return f


def closed_crossings(route, network, events):
    """Expand compressed rail legs so a TAW→ADM leg cannot hide HUH→EXC."""
    f = []
    lines = {l["id"]: l for l in network["lines"]}
    for leg in route.get("legs", []):
        line = lines.get(leg.get("line"))
        if not line:
            continue  # Noncanonical aliases require owner adapter/contract decision.
        stops = line["stops"]
        if leg.get("from") not in stops or leg.get("to") not in stops:
            continue
        a, b = stops.index(leg["from"]), stops.index(leg["to"])
        step = 1 if b > a else -1
        pairs = {(stops[i], stops[i + step]) for i in range(a, b, step)}
        for event in events:
            if event.get("status") not in {"published", "updated"} or event.get("line") != leg.get("line"):
                continue
            for seg in event.get("affected_segments", []):
                edge = (seg["from_node"], seg["to_node"])
                blocked = edge in pairs or (event.get("direction") == "both" and edge[::-1] in pairs)
                require(not (seg.get("impact") == "closed" and blocked), "CLOSED_EDGE",
                        route.get("route_id", "route"), f"Route crosses published closure {edge}", f)
    return f


def check_sim(result, route_ids=None):
    f = []
    fields(result, "scenario_id population baseline guided delta assumptions provenance", "sim", f)
    require(result.get("provenance") == "simulated", "SIM_PROVENANCE", "sim", "Simulation must be labelled simulated", f)
    require(not result.get("meta", {}).get("placeholder", False), "PLACEHOLDER", "sim", "Placeholder cannot be acceptance evidence", f)
    require(result.get("population") == 10000, "POPULATION", "sim", "Required demo is 10,000 people; 2,000 is a disclosed fallback only", f)
    require(bool(result.get("assumptions")), "ASSUMPTIONS", "sim", "Missing model assumptions", f)
    for policy in ("baseline", "guided"):
        data = result.get(policy, {})
        for key in ("total_delay_person_min", "p95_wait_min", "overloaded_routes"):
            number(data, key, "sim." + policy, f)
        number(data, "served_rate", "sim." + policy, f, 0, 1)
        loads = data.get("route_load", [])
        if loads:
            require(sum(r.get("load_factor", 0) > 1 for r in loads) == data.get("overloaded_routes"),
                    "OVERLOAD_COUNT", "sim." + policy, "Aggregate differs from route loads", f)
        for row in loads + data.get("shares", []):
            if route_ids is not None:
                require(row.get("route_id") in route_ids, "ROUTE_REF", "sim." + policy, "Unknown route reference", f)
    number(result.get("guided", {}), "unstoppable_demand", "sim.guided", f, 0, result.get("population", 0))
    for metric, key in (("total_delay_person_min", "delay_reduction_pct"), ("p95_wait_min", "p95_wait_reduction_pct")):
        base, guided = result.get("baseline", {}).get(metric), result.get("guided", {}).get(metric)
        reported = result.get("delta", {}).get(key)
        if finite(base) and base > 0 and finite(guided):
            require(finite(reported) and math.isclose(reported, 100 * (base - guided) / base, abs_tol=0.11),
                    "DELTA", "sim.delta." + key, "Delta does not match measured values", f)
    return f


def load_json(path):
    def invalid(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=invalid)


class Report:
    def __init__(self, suite):
        self.suite, self.checks = suite, []

    def add(self, name, status, detail, **extra):
        self.checks.append(dict(name=name, status=status, detail=detail, **extra))

    def run(self, name, operation):
        try:
            findings = operation()
            self.add(name, "FAIL" if findings else "PASS", [asdict(f) for f in findings])
        except Exception as exc:
            self.add(name, "FAIL", f"{type(exc).__name__}: {exc}")

    def finish(self, output=None):
        statuses = {c["status"] for c in self.checks}
        code = 1 if "FAIL" in statuses else 2 if "PENDING" in statuses or not statuses else 0
        repository = Path(__file__).resolve().parents[2]
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True, stderr=subprocess.DEVNULL).strip()
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repository, text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            revision, dirty = "unknown", None
        harness = {str(p.relative_to(repository)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path(__file__).parent.glob("*.py")}
        result = dict(suite=self.suite, generated_at=datetime.now(timezone.utc).isoformat(),
                      revision=revision, working_tree_dirty=dirty, harness_sha256=harness,
                      exit_code=code, checks=self.checks)
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for c in self.checks:
            detail = f"{len(c['detail'])} finding(s)" if isinstance(c["detail"], list) else c["detail"]
            print(f"{c['status']:7} {c['name']}: {detail}")
        return code
