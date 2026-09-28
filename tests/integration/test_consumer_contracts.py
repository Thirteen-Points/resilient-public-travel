"""Contract and adapter tests use invented data, never operational transport claims."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from integration.contracts import CONTRACTS, RESPONSES, validate_payload, validate_response
from integration.fixture_source import FixtureSource, validate_fixture


class ConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.source = FixtureSource()

    def test_all_public_fixture_objects(self):
        for kind in CONTRACTS:
            with self.subTest(kind=kind):
                self.assertEqual(validate_payload(kind, self.source.get(kind)), [])
        self.assertEqual(validate_fixture(self.source), [])

    def test_every_required_root_field(self):
        for kind, rule in CONTRACTS.items():
            for key in rule["required"]:
                with self.subTest(kind=kind, missing=key):
                    payload = self.source.get(kind)
                    del payload[key]
                    self.assertTrue(validate_payload(kind, payload))

    def test_all_registered_success_responses(self):
        for (method, path), (kind, many) in RESPONSES.items():
            with self.subTest(path=path):
                value = self.source.get(kind)
                self.assertEqual(validate_response(method, path + "?scenario_id=fixture", 200,
                                                   [value] if many else value), [])
        self.assertEqual(validate_response("POST", "/api/events/fixture/review", 200, self.source.get("Event")), [])

    def test_all_error_statuses_require_envelope(self):
        for status in range(400, 600):
            self.assertEqual(validate_response("POST", "/api/routes/query", status, self.source.get("Error")), [])
            self.assertTrue(validate_response("POST", "/api/routes/query", status, {"detail": "not the contract"}))

    def test_route_response_is_array_not_private_envelope(self):
        route = self.source.get("RouteCandidate")
        self.assertTrue(validate_response("POST", "/api/routes/query", 200, {"routes": [route]}))
        self.assertEqual(validate_response("POST", "/api/routes/query", 200, []), [])

    def test_missing_and_renamed_nested_fields(self):
        route = self.source.get("RouteCandidate")
        leg = route["legs"][0]
        leg["travel_s"] = leg.pop("in_vehicle_s")
        del route["total"]["freshness_s"]
        self.assertTrue(validate_payload("RouteCandidate", route))

    def test_nonfinite_bool_numeric_and_wrong_types(self):
        for value in (True, float("nan"), float("inf"), -1, "100"):
            with self.subTest(value=value):
                route = self.source.get("RouteCandidate")
                route["total"]["time_s"] = value
                self.assertTrue(validate_payload("RouteCandidate", route))

    def test_bad_enum_and_missing_timezone(self):
        event = self.source.get("Event")
        event["status"] = "auto_approved"
        event["created_at"] = "2026-09-22T08:00:00"
        self.assertEqual({f.code for f in validate_payload("Event", event)}, {"ENUM", "DATETIME"})

    def test_nullable_event_times(self):
        event = self.source.get("Event")
        event.update(status="draft", published_at=None, expires_at=None, reviewed_by=None)
        self.assertEqual(validate_payload("Event", event), [])

    def test_unknown_extensions_are_preserved(self):
        route = self.source.get("RouteCandidate")
        route["future_extension"] = {"unchanged": True}
        before = deepcopy(route)
        self.assertEqual(validate_payload("RouteCandidate", route), [])
        self.assertEqual(route, before)

    def test_empty_evidence_not_accepted(self):
        route = self.source.get("RouteCandidate")
        route["evidence"] = [{}]
        self.assertTrue(validate_payload("RouteCandidate", route))

    def test_transit_line_required_but_walk_line_optional(self):
        route = self.source.get("RouteCandidate")
        self.assertEqual(validate_payload("RouteCandidate", route), [])
        route["legs"][0]["mode"] = "MTR"
        self.assertTrue(validate_payload("RouteCandidate", route))

    def test_unsupported_endpoint_never_passes(self):
        self.assertTrue(validate_response("GET", "/api/not-yet-contracted", 200, {}))
        self.assertTrue(validate_response("GET", "/api/health", 302, {}))
        self.assertTrue(validate_response("GET", "/api/health", True, {}))


class DataAdapterTests(unittest.TestCase):
    def test_returns_independent_copies(self):
        source = FixtureSource()
        changed = source.get("RouteCandidate")
        changed["legs"][0]["walk_m"] = 99999
        self.assertEqual(source.get("RouteCandidate")["legs"][0]["walk_m"], 80)

    def test_loader_injection_replaces_values_not_validation_logic(self):
        source = FixtureSource()
        changed = deepcopy(source._data)
        changed["network"]["lines"][0]["headway_s"]["weekday_peak"] = 900
        changed["network"]["lines"][0]["capacity_per_vehicle"] = 7
        injected = FixtureSource(loader=lambda path: changed)
        self.assertEqual(injected.network()["lines"][0]["capacity_per_vehicle"], 7)
        self.assertEqual(validate_fixture(injected), [])

    def test_simulated_fixture_cannot_claim_verified_provenance(self):
        source = FixtureSource()
        for label in ("real", "real-derived", None):
            with self.subTest(label=label):
                changed = deepcopy(source._data)
                changed["network"]["lines"][0]["provenance"] = label
                with self.assertRaises(ValueError):
                    FixtureSource(loader=lambda path: changed)

    def test_missing_object_does_not_become_default_data(self):
        source = FixtureSource()
        changed = deepcopy(source._data)
        del changed["objects"]["Meta"]
        findings = validate_fixture(FixtureSource(loader=lambda path: changed))
        self.assertTrue(any(f.path == "Meta" for f in findings))


if __name__ == "__main__":
    unittest.main()
