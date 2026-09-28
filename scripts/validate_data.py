"""Validate the four offline seed files without requiring third-party packages.

This is deliberately a structural/data-quality check, not a claim that a value is
operationally current.  Values marked ``real-derived`` or ``simulated`` remain
usable for the offline demo, while the ledger records what still needs human
verification.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "contracts" / "seed"
ALLOWED_PROVENANCE = {"real", "real-derived", "simulated"}
FILES = ("network.seed.json", "event.seed.json", "routes.seed.json", "sim.seed.json")
LINE_ALIASES = {
    "182": "BUS_182",
    "982X": "BUS_982X",
    "81C": "BUS_81C",
    "TST_CEN": "FERRY_TST_CEN",
}


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def load(name: str, result: Validation):
    path = SEED_DIR / name
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        result.error(f"{name}: file not found")
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        result.error(f"{name}: invalid JSON ({exc})")
        return {}
    if not isinstance(value, dict):
        result.error(f"{name}: root must be an object")
    return value


def check_provenance(value, path: str, result: Validation) -> None:
    if isinstance(value, dict):
        if "provenance" in value and value["provenance"] not in ALLOWED_PROVENANCE:
            result.error(f"{path}.provenance: unsupported value {value['provenance']!r}")
        for key, child in value.items():
            check_provenance(child, f"{path}.{key}", result)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_provenance(child, f"{path}[{index}]", result)


def validate() -> Validation:
    result = Validation()
    network = load("network.seed.json", result)
    event = load("event.seed.json", result)
    routes = load("routes.seed.json", result)
    sim = load("sim.seed.json", result)
    for name, value in (("network", network), ("event", event), ("routes", routes), ("sim", sim)):
        check_provenance(value, name, result)

    nodes = {item.get("id") for item in network.get("nodes", []) if isinstance(item, dict)}
    lines = {item.get("id") for item in network.get("lines", []) if isinstance(item, dict)}
    if len(nodes) != len(network.get("nodes", [])):
        result.error("network.nodes: ids must be unique")
    if len(lines) != len(network.get("lines", [])):
        result.error("network.lines: ids must be unique")
    for node in network.get("nodes", []):
        if not isinstance(node, dict) or not node.get("id") or not node.get("name_en"):
            result.error("network.nodes: every node needs id and name_en")
        if isinstance(node, dict) and node.get("kind") != "unknown":
            for coordinate in ("lat", "lng"):
                if not isinstance(node.get(coordinate), (int, float)):
                    result.error(f"network.nodes[{node.get('id')}]: {coordinate} must be numeric")
    for line in network.get("lines", []):
        if not isinstance(line, dict) or not line.get("id") or not line.get("stops"):
            result.error("network.lines: every line needs id and stops")
        if isinstance(line, dict):
            missing = [stop for stop in line.get("stops", []) if stop not in nodes]
            if missing:
                result.warning(f"network.lines[{line.get('id')}]: unresolved stop ids {missing}")
            if len(line.get("stops", [])) != len(line.get("seg_time_s", [])) + 1:
                result.error(f"network.lines[{line.get('id')}]: stops/seg_time_s length mismatch")

    event_ids = {item.get("event_id") for item in event.get("events", []) if isinstance(item, dict)}
    if len(event_ids) != len(event.get("events", [])):
        result.error("event.events: ids must be unique")
    for item in event.get("events", []):
        for segment in item.get("affected_segments", []):
            for key in ("from_node", "to_node"):
                if segment.get(key) not in nodes:
                    result.error(f"event[{item.get('event_id')}].affected_segments: unresolved {key}={segment.get(key)!r}")
            factor = segment.get("capacity_factor")
            if not isinstance(factor, (int, float)) or not 0 <= factor <= 1:
                result.error(f"event[{item.get('event_id')}].affected_segments: capacity_factor must be between 0 and 1")
        if item.get("event_id") and item.get("provenance") == "simulated" and item.get("status") == "published":
            result.warning(f"event {item['event_id']}: published demo event is simulated, not operational evidence")
    route_ids = {item.get("route_id") for item in routes.get("routes", []) if isinstance(item, dict)}
    if len(route_ids) != len(routes.get("routes", [])):
        result.error("routes.routes: ids must be unique")
    for route in routes.get("routes", []):
        freshness = route.get("total", {}).get("freshness_s")
        if not isinstance(freshness, (int, float)) or freshness < 0:
            result.error(f"routes[{route.get('route_id')}].total.freshness_s: must be a non-negative number")
        for leg in route.get("legs", []):
            for key in ("from", "to"):
                if leg.get(key) not in nodes:
                    result.warning(f"routes[{route.get('route_id')}].legs: unresolved {key}={leg.get(key)!r}")
            line_id = LINE_ALIASES.get(leg.get("line"), leg.get("line"))
            if leg.get("mode") in {"MTR", "BUS", "MINIBUS", "FERRY"} and line_id not in lines:
                if route.get("demo_only") is True and route.get("provenance") == "simulated":
                    result.warning(f"routes[{route.get('route_id')}].legs: excluded demo-only unknown line {leg.get('line')!r}")
                else:
                    result.error(f"routes[{route.get('route_id')}].legs: unknown line {leg.get('line')!r}")
    for name, item in (("sim.event_ref", sim.get("meta", {}).get("event_ref")),):
        if item not in event_ids:
            result.error(f"{name}: unknown event {item!r}")
    for item in sim.get("baseline", {}).get("route_load", []) + sim.get("guided", {}).get("shares", []):
        if item.get("route_id") not in route_ids:
            result.error(f"sim: unknown route {item.get('route_id')!r}")
    return result


def main() -> int:
    result = validate()
    for warning in result.warnings:
        print(f"WARN {warning}")
    for error in result.errors:
        print(f"ERROR {error}")
    if result.errors:
        print(f"FAIL: {len(result.errors)} error(s), {len(result.warnings)} warning(s)")
        return 1
    print(f"PASS: four seed files readable; {len(result.warnings)} documented warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
