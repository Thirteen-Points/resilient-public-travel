"""Tests for the data/-layer validator (scripts/validate_data_layer.py).

These complement tests/test_data_integrity.py, which checks the frozen
contracts/seed/ files. Here we check that the validator accepts the current
data/ layer and rejects mutated copies: dangling references, a corrupted
982X schedule panel, and a stripped user-provided source marking.

The validator and these tests are structural only: they never verify values
against external sources and never promote unverified items to verified.
"""
import copy
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_data_layer import DATA_DIR, load_documents, validate


def _docs():
    return load_documents(DATA_DIR)


def test_current_data_layer_passes():
    docs = _docs()
    errors, warnings = validate(docs)
    assert errors == []
    assert any("structural pass only" in warning for warning in warnings)
    # every required file actually parsed
    assert "network/stations.json" in docs and "calendar.json" in docs


def test_dangling_line_stop_fails():
    docs = _docs()
    docs["network/lines.json"]["lines"][0]["stops"].append("NOPE")
    errors, _ = validate(docs)
    assert any("unresolved stop ids" in error and "NOPE" in error for error in errors)


def test_dangling_bus_stop_route_reference_fails():
    docs = _docs()
    stops = docs["network/stations.json"]["bus_stops"]
    tai_wai = next(stop for stop in stops if stop["id"] == "BS_TAW")
    tai_wai["lines"].append("999X")
    errors, _ = validate(docs)
    assert any("unresolved route ids" in error and "999X" in error for error in errors)


def test_excluded_481b_on_network_node_fails():
    docs = _docs()
    stops = docs["network/stations.json"]["bus_stops"]
    tai_wai = next(stop for stop in stops if stop["id"] == "BS_TAW")
    tai_wai["lines"].append("481B")
    errors, _ = validate(docs)
    assert any("481B must not appear on network nodes" in error for error in errors)


def test_schedule_gap_mismatch_fails():
    docs = _docs()
    route = next(route for route in docs["network/bus_routes.json"]["serving_tai_wai"]
                 if route["route_id"] == "982X")
    evidence = copy.deepcopy(route["schedule_evidence"])
    evidence["directions"][0]["gaps_min"][0] += 1
    route["schedule_evidence"] = evidence
    errors, _ = validate(docs)
    assert any("does not match" in error and "gaps_min length" not in error for error in errors)


def test_schedule_window_mismatch_fails():
    docs = _docs()
    route = next(route for route in docs["network/bus_routes.json"]["serving_tai_wai"]
                 if route["route_id"] == "982X")
    evidence = copy.deepcopy(route["schedule_evidence"])
    evidence["directions"][1]["window"] = "17:00-18:27"
    route["schedule_evidence"] = evidence
    errors, _ = validate(docs)
    assert any("window" in error for error in errors)


def test_schedule_provenance_upgrade_canary_fails():
    docs = _docs()
    route = next(route for route in docs["network/bus_routes.json"]["serving_tai_wai"]
                 if route["route_id"] == "982X")
    evidence = copy.deepcopy(route["schedule_evidence"])
    evidence["source"] = "Officially verified operator timetable"
    evidence["days"] = "Every day"
    route["schedule_evidence"] = evidence
    errors, _ = validate(docs)
    assert any("user-provided marking" in error for error in errors)
    assert any("scoped to the screenshot panels" in error for error in errors)


def test_dangling_bs_prefix_access_point_fails():
    docs = _docs()
    stations = docs["access/access_points.json"]["stations"]
    adm = next(station for station in stations if station["station_id"] == "ADM")
    adm["access_points"].append({"id": "BS_NOPE", "type": "bus_stop", "lat": 22.27, "lng": 114.16})
    errors, _ = validate(docs)
    assert any("BS_NOPE" in error and "not present in stations.json bus_stops" in error
               for error in errors)


def test_catchment_access_point_id_does_not_need_to_be_a_network_node():
    docs = _docs()
    stations = docs["access/access_points.json"]["stations"]
    kot = next(station for station in stations if station["station_id"] == "KOT")
    kot["access_points"].append({"id": "ap_kot_bus_stop_extra", "type": "bus_stop",
                                 "lat": 22.3367, "lng": 114.1768})
    errors, _ = validate(docs)
    assert not any("ap_kot_bus_stop_extra" in error for error in errors)


def test_string_fare_rejected():
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "BUS_182")
    line["fare_hkd"] = "16.0"
    errors, _ = validate(docs)
    assert any("fare_hkd" in error and "finite non-negative number" in error for error in errors)


def test_nan_fare_rejected():
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "BUS_182")
    line["fare_hkd"] = [float("nan"), 20.8]
    errors, _ = validate(docs)
    assert any("fare must be a finite non-negative number" in error for error in errors)


def test_infinite_fare_rejected():
    docs = _docs()
    route = docs["network/bus_routes.json"]["serving_tai_wai"][0]
    route["fare_hkd"] = [16.0, float("inf")]
    errors, _ = validate(docs)
    assert any("fare must be a finite non-negative number" in error for error in errors)


def test_negative_fare_rejected():
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "BUS_982X")
    line["fare_hkd"] = [-6.0, 20.8]
    errors, _ = validate(docs)
    assert any("fare must be a finite non-negative number" in error for error in errors)


def test_boolean_fare_rejected():
    docs = _docs()
    route = docs["network/bus_routes.json"]["serving_tai_wai"][0]
    route["fare_hkd"] = [True, 20.8]
    errors, _ = validate(docs)
    assert any("fare must be a finite non-negative number" in error for error in errors)


def test_inverted_fare_pair_rejected():
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "BUS_182")
    line["fare_hkd"] = [20.8, 16.0]
    errors, _ = validate(docs)
    assert any("ascending" in error for error in errors)


def test_missing_optional_fare_is_accepted():
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "ERL")
    assert "fare_hkd" not in line  # precondition: MTR lines carry no fare field
    errors, _ = validate(docs)
    assert not any("fare_hkd" in error for error in errors)


def _with_982x_line_mutated(**changes):
    docs = _docs()
    line = next(line for line in docs["network/lines.json"]["lines"] if line["id"] == "BUS_982X")
    for key, value in changes.items():
        if value is ...:  # sentinel: delete the key
            line.pop(key, None)
        else:
            line[key] = value
    return docs


def test_982x_provenance_upgrade_to_real_fails():
    docs = _with_982x_line_mutated(provenance="real")
    errors, _ = validate(docs)
    assert any("must not be upgraded to 'real'" in error for error in errors)


def test_982x_data_status_upgrade_to_verified_fails():
    docs = _with_982x_line_mutated(data_status="verified")
    errors, _ = validate(docs)
    assert any("must not be upgraded to 'verified'" in error for error in errors)


def test_982x_backfilled_headway_fails():
    docs = _with_982x_line_mutated(headway_s={"weekday_peak": 600, "weekday_offpeak": None,
                                              "saturday": None, "sunday_ph": None})
    errors, _ = validate(docs)
    assert any("must stay all-null" in error and "weekday_peak" in error for error in errors)


def test_982x_headway_status_upgrade_fails():
    docs = _with_982x_line_mutated(headway_status="verified_single_headway")
    errors, _ = validate(docs)
    assert any("'unverified' marker" in error for error in errors)


def test_982x_line_missing_fails():
    docs = _docs()
    lines = docs["network/lines.json"]["lines"]
    docs["network/lines.json"]["lines"] = [l for l in lines if l["id"] != "BUS_982X"]
    errors, _ = validate(docs)
    assert any("BUS_982X is missing" in error for error in errors)


def test_route_level_verified_flag_is_not_conflated_with_schedule_tier():
    # The TD-verified route existence flag in bus_routes.json is legitimate
    # and must NOT itself trigger the schedule-tier canaries.
    docs = _docs()
    route = next(route for route in docs["network/bus_routes.json"]["serving_tai_wai"]
                 if route["route_id"] == "982X")
    assert route["verified"] is True  # precondition, unchanged by this suite
    errors, _ = validate(docs)
    assert not any("BUS_982X" in error or "982X schedule" in error for error in errors)


def test_dangling_walk_link_fails():
    docs = _docs()
    docs["network/walk_links.json"]["walk_links"].append(
        {"from": "NOPE", "to": "TAW", "walk_s": 60, "walk_m": 50})
    errors, _ = validate(docs)
    assert any("unresolved node ids" in error and "NOPE" in error for error in errors)


def test_duplicate_node_id_fails():
    docs = _docs()
    stations = docs["network/stations.json"]["stations"]
    clone = dict(stations[0])
    stations.append(clone)
    errors, _ = validate(docs)
    assert any("duplicate id" in error for error in errors)
