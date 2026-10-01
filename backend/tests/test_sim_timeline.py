import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import unittest

from app.sim.timeline import journey_timeline_from_fixture, simulate_journey_timeline


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "journey_timeline.simulated.json"


def load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class JourneyTimelineSimulationTests(unittest.TestCase):
    def test_fixed_seed_is_reproducible(self):
        specification = journey_timeline_from_fixture(load_fixture())

        first = simulate_journey_timeline(specification)
        second = simulate_journey_timeline(specification)

        self.assertEqual(first, second)
        self.assertEqual(first["provenance"], "simulated")
        self.assertEqual(first["served_samples"] + first["unserved_samples"], 200)

    def test_representative_is_modal_and_scenario_order_is_consistent(self):
        result = simulate_journey_timeline(journey_timeline_from_fixture(load_fixture()))
        scenarios = result["scenarios"]
        modal_count = max(item["sample_count"] for item in result["outcome_distribution"])

        self.assertEqual(scenarios["representative"]["sample_count"], modal_count)
        self.assertLessEqual(
            scenarios["faster"]["outcome"]["total_s"],
            scenarios["representative"]["outcome"]["total_s"],
        )
        self.assertLessEqual(
            scenarios["representative"]["outcome"]["total_s"],
            scenarios["slower"]["outcome"]["total_s"],
        )

    def test_denial_advances_service_and_propagates_to_downstream_connection(self):
        payload = load_fixture()
        payload["sample_count"] = 1
        payload["legs"][0]["boarding"]["denial_probabilities"] = [1, 0, 0, 0, 0]
        for index in (2, 3):
            payload["legs"][index]["boarding"]["denial_probabilities"] = [
                0 for _ in payload["legs"][index]["departures"]
            ]

        outcome = simulate_journey_timeline(journey_timeline_from_fixture(payload))[
            "scenarios"
        ]["representative"]["outcome"]
        first_leg, walk_leg, bus_leg, final_leg = outcome["legs"]

        self.assertEqual(first_leg["denial_wait_s"], 180)
        self.assertEqual(first_leg["missed_services"], 1)
        self.assertEqual(first_leg["delay_reasons"][0]["code"], "SIMULATED_BOARDING_DENIAL_ASSUMPTION")
        self.assertEqual(walk_leg["start_at"], first_leg["arrive_at"])
        self.assertEqual(bus_leg["start_at"], walk_leg["arrive_at"])
        self.assertEqual(final_leg["start_at"], bus_leg["arrive_at"])
        self.assertTrue(
            any(
                reason["code"] == "UPSTREAM_DELAY_MISSED_CONNECTION"
                for leg in (bus_leg, final_leg)
                for reason in leg["delay_reasons"]
            )
        )

        accounted = sum(
            leg["transfer_s"] + leg["wait_s"] + leg["ride_s"]
            for leg in outcome["legs"]
        )
        self.assertEqual(outcome["total_s"], accounted)
        for earlier, later in zip(outcome["legs"], outcome["legs"][1:]):
            self.assertLessEqual(
                datetime.fromisoformat(earlier["arrive_at"]),
                datetime.fromisoformat(later["start_at"]),
            )

    def test_boarding_assumption_is_mandatory_and_not_inferred_from_next_train(self):
        payload = load_fixture()
        payload["legs"][0]["departure_source"]["kind"] = "mtr_next_train"
        del payload["legs"][0]["boarding"]

        with self.assertRaisesRegex(ValueError, "boarding"):
            journey_timeline_from_fixture(payload)

    def test_fixture_rejects_non_simulated_boarding_provenance(self):
        payload = load_fixture()
        payload["legs"][0]["boarding"]["provenance"] = "real-derived"

        with self.assertRaisesRegex(ValueError, "must remain simulated"):
            journey_timeline_from_fixture(payload)

    def test_fixture_rejects_missing_or_misaligned_boarding_parameters(self):
        missing = load_fixture()
        del missing["legs"][2]["boarding"]["denial_probabilities"]
        with self.assertRaisesRegex(ValueError, "must match departures exactly"):
            journey_timeline_from_fixture(missing)

        misaligned = load_fixture()
        misaligned["legs"][2]["boarding"]["denial_probabilities"] = [0]
        with self.assertRaisesRegex(ValueError, "must match departures exactly"):
            journey_timeline_from_fixture(misaligned)

    def test_output_marks_assumptions_and_does_not_claim_real_probability(self):
        result = simulate_journey_timeline(journey_timeline_from_fixture(load_fixture()))
        serialized = json.dumps(result, ensure_ascii=False).lower()

        self.assertIn("simulated assumptions", result["disclaimer"])
        self.assertIn("not observed facts", result["disclaimer"])
        self.assertNotIn("real probability", serialized.replace("real-world probabilities", ""))
        self.assertNotIn("preference", serialized)
        self.assertNotIn("score_weight", serialized)
        for scenario in result["scenarios"].values():
            self.assertEqual(scenario["outcome"]["provenance"], "simulated")
            for leg in scenario["outcome"]["legs"]:
                self.assertEqual(leg["provenance"], "simulated")

    def test_different_seed_can_change_sample_distribution_without_changing_input(self):
        specification = journey_timeline_from_fixture(load_fixture())
        first = simulate_journey_timeline(specification)
        second = simulate_journey_timeline(replace(specification, seed=20261001))

        self.assertNotEqual(first["outcome_distribution"], second["outcome_distribution"])


if __name__ == "__main__":
    unittest.main()
