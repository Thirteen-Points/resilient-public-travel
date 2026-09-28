import unittest
from scripts.integration.audit_all import classify_process
from scripts.integration.provenance_audit import fixture_issues

class AuditGateTests(unittest.TestCase):
    def test_empty_discovery_is_not_pass(self):
        self.assertEqual(classify_process(0, "Ran 0 tests", 1)[0], "FAIL")
        self.assertEqual(classify_process(0, "Ran 30 tests", 30)[0], "PASS")

    def test_skipped_and_missing_are_not_unconditional_pass(self):
        self.assertEqual(classify_process(0, "Ran 7 tests\nOK (skipped=1)", 7)[0], "CONDITIONAL")
        self.assertEqual(classify_process(2, "No such file", missing=True)[0], "BLOCKED")

    def test_provenance_scan_descends_into_arrays(self):
        self.assertTrue(fixture_issues({"provenance":"simulated","rows":[{"provenance":"real"}]}))
        self.assertEqual(fixture_issues({"meta":{"provenance":"simulated"},"rows":[{"provenance":"simulated"}]}), [])
        self.assertTrue(fixture_issues({"rows":[]}))

if __name__ == "__main__":
    unittest.main()
