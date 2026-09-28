"""Regression checks for acceptance reporting, not product mocks."""
import unittest

from scripts.integration.audit_all import classify_process
from scripts.integration.m0_probe import assess
from scripts.integration.contracts import validate_payload
from scripts.integration.fixture_source import FixtureSource


class M0AuditTests(unittest.TestCase):
    def test_pytest_count_and_skips_are_not_silently_accepted(self):
        self.assertEqual(classify_process(0, "3 passed in 0.02s", 3), ("PASS", 3))
        self.assertEqual(classify_process(0, "2 passed, 1 skipped in 0.02s", 3)[0], "CONDITIONAL")
        self.assertEqual(classify_process(5, "no tests ran in 0.02s", 1)[0], "FAIL")

    def test_health_200_does_not_certify_real_data(self):
        rows = assess({"configuration": "explicit_simulated_fixture",
                       "health": {"status": 200, "body": {"ok": True}},
                       "route": {"status": 200, "body": [{"provenance": "simulated"}],
                                 "contract_errors": []}})
        self.assertEqual({r["status"] for r in rows}, {"CONDITIONAL"})

    def test_failed_health_does_not_become_pass(self):
        rows = assess({"configuration": "defaults",
                       "health": {"status": 503, "body": {"ok": False}},
                       "route": {"status": 404, "body": {}}})
        self.assertEqual({r["status"] for r in rows}, {"FAIL"})

    def test_walk_zero_headway_does_not_relax_transit_validation(self):
        route = FixtureSource().get("RouteCandidate")
        leg = route["legs"][0]
        leg.update(mode="WALK", headway_s=0)
        self.assertEqual(validate_payload("RouteCandidate", route), [])
        leg.update(mode="MTR", line="SIM_TEST")
        self.assertTrue(validate_payload("RouteCandidate", route))
        leg.update(mode="WALK", headway_s=-1)
        self.assertTrue(validate_payload("RouteCandidate", route))
