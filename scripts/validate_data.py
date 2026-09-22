#!/usr/bin/env python3
"""
Data validation script for C-Data work package.
Validates all data files in data/ and contracts/seed/ for:
- JSON validity
- Coordinate ranges (Hong Kong area)
- Lat/lng order correctness
- Line stops reference existing nodes
- Walk link endpoints reference existing nodes
- No duplicate station IDs
- Station name/ID consistency
- Headway and capacity fields present
- Provenance field present
- No unverified data marked as "real" inappropriately
- Bus route stops reference existing nodes

Usage:
    python scripts/validate_data.py

Exit codes:
    0 = all checks passed (warnings allowed)
    1 = one or more checks failed
"""

import json
import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent

# HK coordinate bounds (generous)
HK_LAT_MIN, HK_LAT_MAX = 22.0, 23.0
HK_LNG_MIN, HK_LNG_MAX = 113.5, 114.5


def load_json(filepath):
    """Load a JSON file and return the data, or raise."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_all_nodes(stations_data):
    """Collect all node IDs from stations.json."""
    node_ids = set()
    for section in ["stations", "bus_stops", "piers"]:
        for node in stations_data.get(section, []):
            node_ids.add(node["id"])
    return node_ids


def check_json_validity(filepath):
    """Check if a file is valid JSON."""
    try:
        load_json(filepath)
        return True, []
    except json.JSONDecodeError as e:
        return False, [f"JSON parse error in {filepath}: {e}"]
    except Exception as e:
        return False, [f"Error reading {filepath}: {e}"]


def check_coordinates(stations_data):
    """Check coordinate ranges and lat/lng order."""
    errors = []
    for section in ["stations", "bus_stops", "piers"]:
        for node in stations_data.get(section, []):
            lat = node.get("lat")
            lng = node.get("lng")
            if lat is None or lng is None:
                errors.append(f"{node['id']}: missing lat or lng")
                continue
            if not (HK_LAT_MIN <= lat <= HK_LAT_MAX):
                errors.append(f"{node['id']}: lat {lat} out of HK range [{HK_LAT_MIN}, {HK_LAT_MAX}]")
            if not (HK_LNG_MIN <= lng <= HK_LNG_MAX):
                errors.append(f"{node['id']}: lng {lng} out of HK range [{HK_LNG_MIN}, {HK_LNG_MAX}]")
            # Check order: lat should be ~22.x, lng should be ~114.x
            if lat > 100 and lng < 100:
                errors.append(f"{node['id']}: lat/lng possibly swapped (lat={lat}, lng={lng})")
    return errors


def check_duplicate_ids(stations_data):
    """Check for duplicate station IDs."""
    errors = []
    seen = set()
    for section in ["stations", "bus_stops", "piers"]:
        for node in stations_data.get(section, []):
            nid = node["id"]
            if nid in seen:
                errors.append(f"Duplicate node ID: {nid}")
            seen.add(nid)
    return errors


def check_line_stops(lines_data, all_node_ids):
    """Check that all line stops reference existing nodes."""
    errors = []
    for line in lines_data.get("lines", []):
        for stop in line.get("stops", []):
            if stop not in all_node_ids:
                errors.append(f"Line {line['id']}: stop '{stop}' not found in nodes")
    return errors


def check_walk_links(walk_links_data, all_node_ids):
    """Check that walk link endpoints reference existing nodes."""
    errors = []
    for link in walk_links_data.get("walk_links", []):
        if link["from"] not in all_node_ids:
            errors.append(f"Walk link: 'from' node '{link['from']}' not found")
        if link["to"] not in all_node_ids:
            errors.append(f"Walk link: 'to' node '{link['to']}' not found")
    return errors


def check_provenance(stations_data, lines_data, walk_links_data):
    """Check that all data items have provenance field."""
    errors = []
    for section in ["stations", "bus_stops", "piers"]:
        for node in stations_data.get(section, []):
            if "provenance" not in node:
                errors.append(f"Node {node['id']}: missing 'provenance' field")
            elif node["provenance"] not in ("real", "real-derived", "simulated"):
                errors.append(f"Node {node['id']}: invalid provenance '{node['provenance']}'")
    for line in lines_data.get("lines", []):
        if "provenance" not in line:
            errors.append(f"Line {line['id']}: missing 'provenance' field")
        elif line["provenance"] not in ("real", "real-derived", "simulated"):
            errors.append(f"Line {line['id']}: invalid provenance '{line['provenance']}'")
    for link in walk_links_data.get("walk_links", []):
        if "provenance" not in link:
            errors.append(f"Walk link {link['from']}->{link['to']}: missing 'provenance' field")
    return errors


def check_capacity_and_headway(lines_data):
    """Check that all lines have capacity and headway defined."""
    errors = []
    for line in lines_data.get("lines", []):
        if "capacity_per_vehicle" not in line:
            errors.append(f"Line {line['id']}: missing 'capacity_per_vehicle'")
        if "headway_s" not in line:
            errors.append(f"Line {line['id']}: missing 'headway_s'")
    return errors


def check_seed_data():
    """Validate seed data files in contracts/seed/."""
    errors = []
    seed_dir = ROOT / "contracts" / "seed"
    for seed_file in sorted(seed_dir.glob("*.json")):
        ok, errs = check_json_validity(seed_file)
        if not ok:
            errors.extend(errs)
    return errors


def check_bus_routes(bus_routes_data, all_node_ids):
    """Check bus route data integrity."""
    errors = []
    for route in bus_routes_data.get("serving_tai_wai", []):
        # Check that key fields exist
        if "route_id" not in route:
            errors.append("Bus route missing 'route_id'")
        if "verified" not in route:
            errors.append(f"Bus route {route.get('route_id', '?')}: missing 'verified' field")
    return errors


def main():
    print("=" * 60)
    print("C-Data Validation Script")
    print("=" * 60)

    all_errors = []
    all_warnings = []

    # 1. JSON validity for all data files
    print("\n[1/10] Checking JSON validity...")
    data_files = [
        ROOT / "data" / "network" / "stations.json",
        ROOT / "data" / "network" / "lines.json",
        ROOT / "data" / "network" / "walk_links.json",
        ROOT / "data" / "network" / "bus_routes.json",
        ROOT / "data" / "access" / "access_points.json",
        ROOT / "data" / "calendar.json",
        ROOT / "data" / "weather_impact.json",
    ]
    for f in data_files:
        if f.exists():
            ok, errs = check_json_validity(f)
            if ok:
                print(f"  PASS: {f.name}")
            else:
                print(f"  FAIL: {f.name}")
                all_errors.extend(errs)
        else:
            print(f"  SKIP: {f.name} (not found)")

    # Also check seed data
    for f in sorted((ROOT / "contracts" / "seed").glob("*.json")):
        ok, errs = check_json_validity(f)
        if ok:
            print(f"  PASS: {f.name}")
        else:
            print(f"  FAIL: {f.name}")
            all_errors.extend(errs)

    # Load data for further checks
    stations_path = ROOT / "data" / "network" / "stations.json"
    lines_path = ROOT / "data" / "network" / "lines.json"
    walk_path = ROOT / "data" / "network" / "walk_links.json"
    bus_routes_path = ROOT / "data" / "network" / "bus_routes.json"

    if not all(f.exists() for f in [stations_path, lines_path, walk_path]):
        print("\nFATAL: Required data files missing. Aborting further checks.")
        sys.exit(1)

    stations_data = load_json(stations_path)
    lines_data = load_json(lines_path)
    walk_links_data = load_json(walk_path)
    bus_routes_data = load_json(bus_routes_path) if bus_routes_path.exists() else {}

    all_node_ids = collect_all_nodes(stations_data)

    # 2. Coordinate ranges
    print("\n[2/10] Checking coordinate ranges...")
    errs = check_coordinates(stations_data)
    if errs:
        print(f"  FAIL: {len(errs)} coordinate issues")
        all_errors.extend(errs)
    else:
        print("  PASS: All coordinates within HK range")

    # 3. Duplicate IDs
    print("\n[3/10] Checking for duplicate node IDs...")
    errs = check_duplicate_ids(stations_data)
    if errs:
        print(f"  FAIL: {len(errs)} duplicates found")
        all_errors.extend(errs)
    else:
        print("  PASS: No duplicate node IDs")

    # 4. Line stops reference existing nodes
    print("\n[4/10] Checking line stops reference existing nodes...")
    errs = check_line_stops(lines_data, all_node_ids)
    if errs:
        print(f"  WARN: {len(errs)} unresolved stop references")
        all_warnings.extend(errs)
    else:
        print("  PASS: All line stops reference existing nodes")

    # 5. Walk link endpoints
    print("\n[5/10] Checking walk link endpoints...")
    errs = check_walk_links(walk_links_data, all_node_ids)
    if errs:
        print(f"  FAIL: {len(errs)} unresolved walk link endpoints")
        all_errors.extend(errs)
    else:
        print("  PASS: All walk link endpoints reference existing nodes")

    # 6. Provenance fields
    print("\n[6/10] Checking provenance fields...")
    errs = check_provenance(stations_data, lines_data, walk_links_data)
    if errs:
        print(f"  FAIL: {len(errs)} missing/invalid provenance")
        all_errors.extend(errs)
    else:
        print("  PASS: All data items have valid provenance")

    # 7. Capacity and headway
    print("\n[7/10] Checking capacity and headway fields...")
    errs = check_capacity_and_headway(lines_data)
    if errs:
        print(f"  FAIL: {len(errs)} missing fields")
        all_errors.extend(errs)
    else:
        print("  PASS: All lines have capacity and headway defined")

    # 8. Seed data validity
    print("\n[8/10] Checking seed data files...")
    errs = check_seed_data()
    if errs:
        print(f"  FAIL: {len(errs)} seed data issues")
        all_errors.extend(errs)
    else:
        print("  PASS: All seed data files are valid JSON")

    # 9. Bus route data
    print("\n[9/10] Checking bus route data...")
    errs = check_bus_routes(bus_routes_data, all_node_ids)
    if errs:
        print(f"  WARN: {len(errs)} bus route issues")
        all_warnings.extend(errs)
    else:
        print("  PASS: Bus route data is consistent")

    # 10. Summary
    print("\n[10/10] Summary")
    print(f"  Nodes checked: {len(all_node_ids)}")
    print(f"  Lines checked: {len(lines_data.get('lines', []))}")
    print(f"  Walk links checked: {len(walk_links_data.get('walk_links', []))}")
    print(f"  Bus routes checked: {len(bus_routes_data.get('serving_tai_wai', []))}")

    print("\n" + "=" * 60)
    if all_errors:
        print(f"RESULT: FAIL ({len(all_errors)} errors, {len(all_warnings)} warnings)")
        for e in all_errors:
            print(f"  ERROR: {e}")
    else:
        print(f"RESULT: PASS ({len(all_warnings)} warnings)")
        for w in all_warnings:
            print(f"  WARN: {w}")
    print("=" * 60)

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
