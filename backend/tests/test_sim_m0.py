from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_sim_m0 import REPORT_PATH, verify, write_report


ROOT = Path(__file__).resolve().parents[2]


class SimM0AcceptanceTests(unittest.TestCase):
    def test_m0_verification_passes_and_is_reproducible(self) -> None:
        first = verify(ROOT)
        second = verify(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PASS")
        self.assertTrue(all(first["checks"].values()))
        self.assertEqual(first["provenance"], "simulated")

    def test_checked_in_report_matches_verifier(self) -> None:
        expected = verify(ROOT)
        actual = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_report_writer_uses_machine_readable_json(self) -> None:
        report = verify(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            write_report(report, target)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), report)


if __name__ == "__main__":
    unittest.main()
