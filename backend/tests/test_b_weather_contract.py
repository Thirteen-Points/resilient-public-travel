"""B's weather coefficient contract for C; no claim of routing integration."""

import json
import unittest
from pathlib import Path


WEATHER = Path(__file__).resolve().parents[2] / "data" / "weather_impact.json"
MODES = {"MTR", "BUS", "MINIBUS", "WALK", "FERRY"}


class WeatherContractTests(unittest.TestCase):
    def test_every_condition_is_labelled_and_has_complete_mode_coefficients(self):
        document = json.loads(WEATHER.read_text(encoding="utf-8"))
        self.assertIn("simulated", document["meta"]["provenance_note"])
        for name, condition in document["weather_conditions"].items():
            with self.subTest(condition=name):
                self.assertEqual(condition["provenance"], "simulated")
                self.assertEqual(set(condition["mode_penalties"]), MODES)
                self.assertTrue(all(isinstance(value, (int, float)) and value >= 0
                                    for value in condition["mode_penalties"].values()))
                self.assertGreaterEqual(condition["walk_speed_factor"], 0)
                self.assertLessEqual(condition["walk_speed_factor"], 1)

    def test_zero_factor_is_suspension_not_zero_duration(self):
        document = json.loads(WEATHER.read_text(encoding="utf-8"))
        t8 = document["weather_conditions"]["t8"]
        self.assertEqual(t8["mode_penalties"]["FERRY"], 0)
        self.assertEqual(t8["mode_penalties"]["BUS"], 0)
        self.assertEqual(t8["walk_speed_factor"], 0)


if __name__ == "__main__":
    unittest.main()
