import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS_FILE = ROOT / "data" / "access" / "station_entrances.json"
sys.path.insert(0, str(ROOT))
from scripts.validate_data import ALLOWED_PROVENANCE, FILES, SEED_DIR, validate


def test_all_seed_files_are_valid_json_objects():
    for name in FILES:
        value = json.loads((SEED_DIR / name).read_text(encoding="utf-8"))
        assert isinstance(value, dict)


def test_seed_integrity_has_no_errors_and_only_documented_warnings():
    result = validate()
    assert not result.errors
    assert any("simulated" in warning for warning in result.warnings)


def test_unverified_481b_is_not_an_operational_network_line():
    network = json.loads((SEED_DIR / "network.seed.json").read_text(encoding="utf-8"))
    assert "GMB_481B" not in {line["id"] for line in network["lines"]}
    tai_wai_bus = next(node for node in network["nodes"] if node["id"] == "BS_TAW")
    assert "481B" not in tai_wai_bus["lines"]
    assert "BS_TW" in network["missing_nodes_note"]


def test_official_station_access_records_and_centres_are_complete_and_linked():
    access = json.loads(ACCESS_FILE.read_text(encoding="utf-8"))
    network = json.loads((SEED_DIR / "network.seed.json").read_text(encoding="utf-8"))
    expected = {"TAW": 8, "KOT": 11, "MKK": 4, "HUH": 14, "EXC": 6, "ADM": 7}
    node_by_id = {node["id"]: node for node in network["nodes"]}
    refs = {item["node_id"]: item for item in access["station_reference_points"]}
    assert set(refs) == set(expected)
    assert {station: sum(1 for row in access["entrances"] if row["station_id"] == station)
            for station in expected} == expected
    assert len({row["geonameid"] for row in access["entrances"]}) == 50
    for row in access["entrances"] + access["station_reference_points"]:
        assert isinstance(row["easting"], int) and isinstance(row["northing"], int)
        assert 22.0 <= row["lat"] <= 23.0 and 113.0 <= row["lng"] <= 115.0
        assert row["provenance"] == "real-derived"
    for station, reference in refs.items():
        assert reference["geonameid"] in node_by_id[station]["coordinate_source"]
        assert node_by_id[station]["lat"] == reference["lat"]
        assert node_by_id[station]["lng"] == reference["lng"]
        assert node_by_id[station]["accessible"] is None
        assert node_by_id[station]["accessibility_status"] == "unknown"
    assert access["walk_connectivity_status"].startswith("not asserted")


def test_provenance_values_are_contract_values():
    result = validate()
    assert ALLOWED_PROVENANCE == {"real", "real-derived", "simulated"}
    assert not any("unsupported value" in error for error in result.errors)


def test_m1_event_and_route_refresh_fields_are_linked():
    result = validate()
    assert not any("affected_segments" in error for error in result.errors)
    assert not any("freshness_s" in error for error in result.errors)


def test_every_seed_route_and_leg_has_traceable_evidence():
    routes = json.loads((SEED_DIR / "routes.seed.json").read_text(encoding="utf-8"))
    for route in routes["routes"]:
        assert route.get("evidence"), route["route_id"]
        for leg in route["legs"]:
            assert leg.get("evidence"), f"{route['route_id']}:{leg.get('line', leg['mode'])}"


def test_six_core_nodes_are_present_without_claiming_route_generation():
    network = json.loads((SEED_DIR / "network.seed.json").read_text(encoding="utf-8"))
    core = {"TAW", "KOT", "MKK", "HUH", "EXC", "ADM"}
    assert core <= {node["id"] for node in network["nodes"]}
    assert len(core) * (len(core) - 1) == 30
