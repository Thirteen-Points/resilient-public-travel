"""Read-only structural validator for the data/ layer.

This is deliberately separate from scripts/validate_data.py, which checks the
frozen contracts/seed/ files. This script checks only the documentation /
evidence layer under data/:

- every JSON file parses;
- node / line / bus-route / access-point references resolve (no dangling ids);
- line stop sequences match seg_time_s lengths and headway dicts are sane;
- the 982X schedule_evidence panels are internally consistent: departure
  times strictly increasing, gaps_min equals the adjacent time differences,
  window equals first-last, and the user-provided/unverified source marking
  is still present (canary against silent provenance upgrades).

It deliberately does NOT verify any value against an external source, does
not extrapolate the 982X panels to other days/windows/directions, and never
promotes unverified items to verified. Passing means "internally consistent
with the recorded evidence level", nothing more.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ALLOWED_PROVENANCE = {"real", "real-derived", "simulated"}
LINE_ALIASES = {"TST_CEN": "FERRY_TST_CEN"}
REQUIRED_FILES = (
    "network/stations.json",
    "network/lines.json",
    "network/bus_routes.json",
    "network/walk_links.json",
    "access/access_points.json",
    "access/station_entrances.json",
    "calendar.json",
    "weather_impact.json",
)
# GMB_481B was removed from runnable lines but keeps a documentation-only
# operating-hours row; 481B likewise stays in the bus_routes verification log.
DOCUMENTATION_ONLY_IDS = {"GMB_481B"}


def load_documents(data_dir: Path) -> dict:
    """Parse every *.json under data_dir; return {relative_posix_path: value}."""
    docs = {}
    for path in sorted(data_dir.rglob("*.json")):
        rel = path.relative_to(data_dir).as_posix()
        docs[rel] = json.loads(path.read_text(encoding="utf-8"))
    return docs


def _walk_provenance(value, path, errors):
    if isinstance(value, dict):
        provenance = value.get("provenance")
        if isinstance(provenance, str) and provenance not in ALLOWED_PROVENANCE:
            errors.append(f"{path}.provenance: unsupported value {provenance!r}")
        for key, child in value.items():
            _walk_provenance(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_provenance(child, f"{path}[{index}]", errors)


def _check_times(departures, errors, where):
    def minutes(text):
        parts = text.split(":")
        if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
            errors.append(f"{where}: departure {text!r} is not a HH:MM time")
            return None
        return int(parts[0]) * 60 + int(parts[1])

    previous = None
    for text in departures:
        value = minutes(text)
        if value is None:
            return
        if previous is not None and value <= previous:
            errors.append(f"{where}: departures not strictly increasing at {text!r}")
        previous = value


def _check_schedule_evidence(route, errors):
    evidence = route.get("schedule_evidence")
    if not isinstance(evidence, dict):
        errors.append("bus_routes: 982X is missing schedule_evidence")
        return
    source = str(evidence.get("source", ""))
    note = str(evidence.get("provenance_note", ""))
    days = str(evidence.get("days", ""))
    if "user-provided" not in source.lower():
        errors.append("bus_routes: 982X schedule_evidence.source must keep the "
                      "user-provided marking (canary against provenance upgrade)")
    if "not" not in note.lower() and "no provenance upgrade" not in note.lower() \
            and "user-provided" not in note.lower():
        errors.append("bus_routes: 982X schedule_evidence.provenance_note must keep "
                      "the no-provenance-upgrade statement")
    if "monday to friday" not in days.lower():
        errors.append("bus_routes: 982X schedule_evidence.days must stay scoped to "
                      "the screenshot panels (Monday to Friday)")
    for index, direction in enumerate(evidence.get("directions", [])):
        where = f"bus_routes: 982X schedule_evidence.directions[{index}]"
        departures = direction.get("departures")
        gaps = direction.get("gaps_min")
        window = direction.get("window", "")
        if not isinstance(departures, list) or not departures:
            errors.append(f"{where}: departures missing")
            continue
        _check_times(departures, errors, where)
        if not isinstance(gaps, list) or len(gaps) != len(departures) - 1:
            errors.append(f"{where}: gaps_min length must be len(departures)-1")
            continue
        for first, second, gap in zip(departures, departures[1:], gaps):
            try:
                h1, m1 = (int(p) for p in first.split(":"))
                h2, m2 = (int(p) for p in second.split(":"))
            except ValueError:
                continue  # already reported by _check_times
            if (h2 * 60 + m2) - (h1 * 60 + m1) != gap:
                errors.append(f"{where}: gap {gap} does not match {first}->{second}")
        expected_window = f"{departures[0]}-{departures[-1]}"
        if window != expected_window:
            errors.append(f"{where}: window {window!r} != {expected_window!r}")


def validate(docs: dict):
    """Pure structural check over parsed documents; returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    for name in REQUIRED_FILES:
        if name not in docs:
            errors.append(f"missing required file data/{name}")
    if errors:
        return errors, warnings

    for rel, document in docs.items():
        _walk_provenance(document, rel, errors)

    stations_doc = docs["network/stations.json"]
    lines_doc = docs["network/lines.json"]
    routes_doc = docs["network/bus_routes.json"]
    walks_doc = docs["network/walk_links.json"]
    access_doc = docs["access/access_points.json"]
    calendar_doc = docs["calendar.json"]
    weather_doc = docs["weather_impact.json"]

    node_ids, station_ids, bus_stop_ids = set(), set(), set()
    for group, kind in (("stations", "station"), ("bus_stops", "bus_stop"), ("piers", "pier")):
        for node in stations_doc.get(group, []):
            node_id = node.get("id")
            if not node_id:
                errors.append(f"stations.{group}: entry without id")
                continue
            if node_id in node_ids:
                errors.append(f"stations.{group}: duplicate id {node_id}")
            node_ids.add(node_id)
            if kind == "station":
                station_ids.add(node_id)
            elif kind == "bus_stop":
                bus_stop_ids.add(node_id)
            for coordinate in ("lat", "lng"):
                value = node.get(coordinate)
                if not isinstance(value, (int, float)):
                    errors.append(f"stations.{group}:{node_id}: {coordinate} must be numeric")
            if not (21.0 <= node.get("lat", 0) <= 23.0 and 113.0 <= node.get("lng", 0) <= 115.0):
                errors.append(f"stations.{group}:{node_id}: coordinates outside Hong Kong bounds")

    line_ids = set()
    for line in lines_doc.get("lines", []):
        line_id = line.get("id")
        if not line_id:
            errors.append("lines: entry without id")
            continue
        if line_id in line_ids:
            errors.append(f"lines: duplicate id {line_id}")
        line_ids.add(line_id)
        stops = line.get("stops", [])
        dangling = [stop for stop in stops if stop not in node_ids]
        if dangling:
            errors.append(f"lines:{line_id}: unresolved stop ids {dangling}")
        if len(stops) != len(line.get("seg_time_s", [])) + 1:
            errors.append(f"lines:{line_id}: stops/seg_time_s length mismatch")
        headways = line.get("headway_s")
        if not isinstance(headways, dict) or not headways:
            errors.append(f"lines:{line_id}: headway_s must be a non-empty object")
        else:
            for key, value in headways.items():
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
                    errors.append(f"lines:{line_id}: headway_s.{key} must be null or a positive number")
        capacity = line.get("capacity_per_vehicle")
        if isinstance(capacity, bool) or not isinstance(capacity, (int, float)) or capacity <= 0:
            errors.append(f"lines:{line_id}: capacity_per_vehicle must be a positive number")

    routes = routes_doc.get("serving_tai_wai", []) + routes_doc.get("excluded_routes", [])
    route_ids = set()
    for route in routes:
        route_id = route.get("route_id")
        if not route_id:
            errors.append("bus_routes: entry without route_id")
            continue
        if route_id in route_ids:
            errors.append(f"bus_routes: duplicate route_id {route_id}")
        route_ids.add(route_id)
    for route in routes_doc.get("serving_tai_wai", []):
        if route.get("route_id") == "982X":
            _check_schedule_evidence(route, errors)

    # Bus-stop "lines" name bus routes; "481B" must not be back on any
    # network-side node (documented network exclusion), although the route
    # itself may remain in the verification log above.
    network_route_refs = set()
    for node in stations_doc.get("bus_stops", []):
        network_route_refs.update(node.get("lines", []))
    for station in access_doc.get("stations", []):
        for point in station.get("access_points", []):
            network_route_refs.update(point.get("lines", []))
    if "481B" in network_route_refs:
        errors.append("bus-stop line references: 481B must not appear on network nodes "
                      "(removed from the runnable network)")
    unknown_routes = sorted(network_route_refs - route_ids)
    if unknown_routes:
        errors.append(f"bus-stop line references: unresolved route ids {unknown_routes}")

    for station in stations_doc.get("stations", []):
        unknown = sorted(set(station.get("lines", [])) - line_ids)
        if unknown:
            errors.append(f"stations:{station.get('id')}: unresolved line ids {unknown}")
    for pier in stations_doc.get("piers", []):
        unknown = sorted({LINE_ALIASES.get(ref, ref) for ref in pier.get("lines", [])} - line_ids)
        if unknown:
            errors.append(f"stations:{pier.get('id')}: unresolved line ids {unknown}")

    for link in walks_doc.get("walk_links", []):
        dangling = [end for end in (link.get("from"), link.get("to")) if end not in node_ids]
        if dangling:
            errors.append(f"walk_links:{link.get('from')}->{link.get('to')}: unresolved node ids {dangling}")
    # unmodelled_walk_links are documented gaps and are intentionally NOT
    # referentially checked.

    for station in access_doc.get("stations", []):
        if station.get("station_id") not in station_ids:
            errors.append(f"access_points: unknown station_id {station.get('station_id')!r}")
        seen = set()
        for point in station.get("access_points", []):
            point_id = point.get("id")
            if point_id in seen:
                errors.append(f"access_points:{station.get('station_id')}: duplicate id {point_id}")
            seen.add(point_id)
            # Only ids claiming to BE a network bus-stop node (BS_*) must
            # resolve; ap_* entries are catchment approximations by design.
            if point_id and point_id.startswith("BS_") and point_id not in bus_stop_ids:
                errors.append(f"access_points:{point_id}: BS_ id not present in stations.json bus_stops")

    holidays = calendar_doc.get("public_holidays_2026", [])
    dates = set()
    for row in holidays:
        date = row.get("date", "")
        try:
            year, month, day = (int(part) for part in date.split("-"))
        except ValueError:
            errors.append(f"calendar: holiday date {date!r} is not yyyy-mm-dd")
            continue
        if not (1 <= month <= 12 and 1 <= day <= 31):
            errors.append(f"calendar: holiday date {date!r} out of range")
        if date in dates:
            errors.append(f"calendar: duplicate holiday date {date}")
        dates.add(date)
        if row.get("schedule_type") not in calendar_doc.get("schedule_types", {}):
            errors.append(f"calendar: holiday {date} has unknown schedule_type")
    if not isinstance(calendar_doc.get("operating_hours"), dict):
        errors.append("calendar: operating_hours must be an object")

    for name, condition in weather_doc.get("weather_conditions", {}).items():
        for mode, penalty in condition.get("mode_penalties", {}).items():
            if isinstance(penalty, bool) or not isinstance(penalty, (int, float)) or penalty < 0:
                errors.append(f"weather:{name}: penalty for {mode} must be a non-negative number")

    warnings.append("structural pass only: source authenticity (TD/MTR rows, user "
                    "screenshots, operator pages) still requires the human checks "
                    "recorded in data/PROVENANCE.md")
    return errors, warnings


def main() -> int:
    try:
        docs = load_documents(DATA_DIR)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR data layer JSON parse failure: {exc}")
        return 1
    errors, warnings = validate(docs)
    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: data/ layer structurally consistent ({len(docs)} JSON files); "
          f"{len(warnings)} documented warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
