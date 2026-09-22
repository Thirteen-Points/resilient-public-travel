"""
Data integrity tests for C-Data work package.
Run with: python -m pytest tests/test_data_integrity.py -v
Or: python tests/test_data_integrity.py
"""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def stations_data():
    return load_json(ROOT / "data" / "network" / "stations.json")


@pytest.fixture
def lines_data():
    return load_json(ROOT / "data" / "network" / "lines.json")


@pytest.fixture
def walk_links_data():
    return load_json(ROOT / "data" / "network" / "walk_links.json")


@pytest.fixture
def bus_routes_data():
    return load_json(ROOT / "data" / "network" / "bus_routes.json")


@pytest.fixture
def calendar_data():
    return load_json(ROOT / "data" / "calendar.json")


@pytest.fixture
def all_node_ids(stations_data):
    ids = set()
    for section in ["stations", "bus_stops", "piers"]:
        for node in stations_data.get(section, []):
            ids.add(node["id"])
    return ids


class TestJSONValidity:
    """Test that all data files are valid JSON."""

    DATA_FILES = [
        "data/network/stations.json",
        "data/network/lines.json",
        "data/network/walk_links.json",
        "data/network/bus_routes.json",
        "data/access/access_points.json",
        "data/calendar.json",
        "data/weather_impact.json",
        "contracts/seed/network.seed.json",
        "contracts/seed/event.seed.json",
        "contracts/seed/routes.seed.json",
        "contracts/seed/sim.seed.json",
    ]

    @pytest.mark.parametrize("filepath", DATA_FILES)
    def test_file_is_valid_json(self, filepath):
        path = ROOT / filepath
        if not path.exists():
            pytest.skip(f"{filepath} not found")
        data = load_json(path)
        assert isinstance(data, dict), f"{filepath} root should be a dict"


class TestCoordinates:
    """Test coordinate validity."""

    HK_LAT_RANGE = (22.0, 23.0)
    HK_LNG_RANGE = (113.5, 114.5)

    def test_all_coordinates_in_hk_range(self, stations_data):
        for section in ["stations", "bus_stops", "piers"]:
            for node in stations_data.get(section, []):
                lat = node.get("lat")
                lng = node.get("lng")
                assert lat is not None, f"{node['id']}: missing lat"
                assert lng is not None, f"{node['id']}: missing lng"
                assert self.HK_LAT_RANGE[0] <= lat <= self.HK_LAT_RANGE[1], \
                    f"{node['id']}: lat {lat} out of range"
                assert self.HK_LNG_RANGE[0] <= lng <= self.HK_LNG_RANGE[1], \
                    f"{node['id']}: lng {lng} out of range"

    def test_lat_before_lng(self, stations_data):
        """Lat should be ~22.x, lng should be ~114.x (not swapped)."""
        for section in ["stations", "bus_stops", "piers"]:
            for node in stations_data.get(section, []):
                lat = node["lat"]
                lng = node["lng"]
                assert lat < 100, f"{node['id']}: lat {lat} > 100, possibly swapped"
                assert lng > 100, f"{node['id']}: lng {lng} < 100, possibly swapped"


class TestNodeIntegrity:
    """Test node ID integrity."""

    def test_no_duplicate_node_ids(self, stations_data):
        seen = set()
        for section in ["stations", "bus_stops", "piers"]:
            for node in stations_data.get(section, []):
                nid = node["id"]
                assert nid not in seen, f"Duplicate node ID: {nid}"
                seen.add(nid)

    def test_corridor_six_stations_exist(self, stations_data):
        """The six corridor stations must exist."""
        corridor_ids = {"TAW", "KOT", "MKK", "HUH", "EXC", "ADM"}
        actual_ids = {n["id"] for n in stations_data["stations"]}
        missing = corridor_ids - actual_ids
        assert not missing, f"Missing corridor stations: {missing}"

    def test_exc_is_erl_only(self, stations_data):
        """Exhibition Centre should only have ERL line."""
        exc = next(n for n in stations_data["stations"] if n["id"] == "EXC")
        assert exc["lines"] == ["ERL"], f"EXC should only have ERL, got {exc['lines']}"


class TestLineIntegrity:
    """Test transit line integrity."""

    def test_all_line_stops_exist(self, lines_data, all_node_ids):
        for line in lines_data["lines"]:
            for stop in line.get("stops", []):
                assert stop in all_node_ids, \
                    f"Line {line['id']}: stop '{stop}' not found in nodes"

    def test_erl_corridor_stops(self, lines_data):
        """ERL should have the six corridor stations in order."""
        erl = next(l for l in lines_data["lines"] if l["id"] == "ERL")
        assert erl["stops"] == ["TAW", "KOT", "MKK", "HUH", "EXC", "ADM"], \
            f"ERL stops mismatch: {erl['stops']}"

    def test_all_lines_have_headway(self, lines_data):
        for line in lines_data["lines"]:
            assert "headway_s" in line, f"Line {line['id']}: missing headway_s"
            hw = line["headway_s"]
            assert "weekday_peak" in hw, f"Line {line['id']}: missing weekday_peak headway"

    def test_all_lines_have_capacity(self, lines_data):
        for line in lines_data["lines"]:
            assert "capacity_per_vehicle" in line, \
                f"Line {line['id']}: missing capacity_per_vehicle"
            assert isinstance(line["capacity_per_vehicle"], (int, float)), \
                f"Line {line['id']}: capacity_per_vehicle not numeric"

    def test_bus_982x_no_weekend_service(self, lines_data):
        """982X should not have weekend service."""
        bus = next(l for l in lines_data["lines"] if l["id"] == "BUS_982X")
        assert bus["headway_s"]["saturday"] is None, "982X should not run on Saturday"
        assert bus["headway_s"]["sunday_ph"] is None, "982X should not run on Sunday/PH"

    def test_minibus_not_accessible(self, lines_data):
        """GMB 481B should not be accessible (no low-floor)."""
        gmb = next(l for l in lines_data["lines"] if l["id"] == "GMB_481B")
        assert gmb["accessible"] is False, "481B minibus should not be accessible (no low-floor)"


class TestWalkLinks:
    """Test walk link integrity."""

    def test_all_walk_link_endpoints_exist(self, walk_links_data, all_node_ids):
        for link in walk_links_data["walk_links"]:
            assert link["from"] in all_node_ids, \
                f"Walk link from '{link['from']}' not found in nodes"
            assert link["to"] in all_node_ids, \
                f"Walk link to '{link['to']}' not found in nodes"

    def test_walk_link_has_provenance(self, walk_links_data):
        for link in walk_links_data["walk_links"]:
            assert "provenance" in link, \
                f"Walk link {link['from']}->{link['to']}: missing provenance"


class TestProvenance:
    """Test provenance compliance."""

    def test_all_stations_have_provenance(self, stations_data):
        for section in ["stations", "bus_stops", "piers"]:
            for node in stations_data.get(section, []):
                assert "provenance" in node, f"Node {node['id']}: missing provenance"
                assert node["provenance"] in ("real", "real-derived", "simulated"), \
                    f"Node {node['id']}: invalid provenance '{node['provenance']}'"

    def test_all_lines_have_provenance(self, lines_data):
        for line in lines_data["lines"]:
            assert "provenance" in line, f"Line {line['id']}: missing provenance"
            assert line["provenance"] in ("real", "real-derived", "simulated"), \
                f"Line {line['id']}: invalid provenance"

    def test_minibus_capacity_is_real(self, lines_data):
        """Minibus capacity 19 is a statutory fact (Cap 374D)."""
        gmb = next(l for l in lines_data["lines"] if l["id"] == "GMB_481B")
        assert gmb["capacity_per_vehicle"] == 19
        assert gmb["provenance"] == "real", "481B capacity (19) is a legal fact, should be 'real'"


class TestCalendar:
    """Test service calendar integrity."""

    def test_three_schedule_types(self, calendar_data):
        types = calendar_data["schedule_types"]
        assert "weekday" in types
        assert "saturday" in types
        assert "sunday_ph" in types

    def test_holiday_dates(self, calendar_data):
        """2026 holidays within project window should be present."""
        dates = {h["date"] for h in calendar_data["public_holidays_2026"]}
        assert "2026-09-26" in dates, "Mid-Autumn Festival should be in calendar"
        assert "2026-10-01" in dates, "National Day should be in calendar"

    def test_peak_only_exceptions(self, calendar_data):
        """982X and 985B should have weekday_peak_only exception."""
        peak_only_lines = {
            e["line_id"] for e in calendar_data["service_exceptions"]
            if e["exception"] == "weekday_peak_only"
        }
        assert "BUS_982X" in peak_only_lines, "982X should be weekday_peak_only"
        assert "BUS_985B" in peak_only_lines, "985B should be weekday_peak_only"


class TestBusRoutes:
    """Test bus route verification."""

    def test_excluded_routes_present(self, bus_routes_data):
        """Excluded routes should be documented."""
        excluded_ids = {r["route_id"] for r in bus_routes_data["excluded_routes"]}
        # These must be excluded per 08-data-appendix.md
        must_exclude = {"680", "681", "682", "307", "673", "978", "968", "948X"}
        assert must_exclude.issubset(excluded_ids), \
            f"Missing excluded routes: {must_exclude - excluded_ids}"

    def test_88k_excluded(self, bus_routes_data):
        """88K should be excluded (possibly cancelled)."""
        excluded = {r["route_id"] for r in bus_routes_data["excluded_routes"]}
        assert "88K" in excluded, "88K should be excluded (possibly cancelled)"

    def test_all_serving_routes_verified(self, bus_routes_data):
        """All serving routes should have verified=true."""
        for route in bus_routes_data["serving_tai_wai"]:
            assert route.get("verified") is True, \
                f"Route {route['route_id']} should be verified"

    def test_182_is_daily_service(self, bus_routes_data):
        """182 should be the only full-day cross-harbour bus from Sha Tin."""
        r182 = next(r for r in bus_routes_data["serving_tai_wai"] if r["route_id"] == "182")
        assert r182["calendar_type"] == "daily"
        assert r182["tunnel"] == "CHT"


if __name__ == "__main__":
    # Allow running without pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
