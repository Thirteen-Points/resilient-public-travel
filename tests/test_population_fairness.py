from __future__ import annotations

import unittest
from collections import Counter

from backend.app.engine.fairness import check_extra_delay, is_accessible
from backend.app.sim.models import Agent, RouteOption
from backend.app.sim.population import generate_population


class PopulationAndFairnessTests(unittest.TestCase):
    def test_population_is_reproducible_and_exact(self) -> None:
        first = generate_population()
        second = generate_population()
        different = generate_population(seed=7)
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertEqual(len(first), 10_000)
        self.assertEqual(
            Counter(agent.persona for agent in first),
            {"commuter": 5500, "student": 2000, "tourist": 1000, "elderly": 1000, "wheelchair": 500},
        )

    def test_wheelchair_rejects_minibus_and_excess_walk(self) -> None:
        agent = Agent("a", "TAW", "ADM", "wheelchair", "wheelchair", 400)
        minibus = RouteOption("m", 20, 0, 10, 5, 0.8, ("MINIBUS",), False)
        long_walk = RouteOption("w", 20, 0, 401, 5, 0.8, ("MTR",), True)
        self.assertFalse(is_accessible(agent, minibus).allowed)
        self.assertFalse(is_accessible(agent, long_walk).allowed)

    def test_extra_delay_is_a_hard_limit(self) -> None:
        agent = Agent("a", "TAW", "ADM", "elderly", "reduced", 400)
        best = RouteOption("best", 30, 1, 100, 10, 0.9, ("MTR",), True)
        at_limit = RouteOption("ok", 45, 1, 100, 10, 0.9, ("MTR",), True)
        over = RouteOption("bad", 45.01, 1, 100, 10, 0.9, ("MTR",), True)
        self.assertTrue(check_extra_delay(agent, at_limit, best).allowed)
        self.assertFalse(check_extra_delay(agent, over, best).allowed)


if __name__ == "__main__":
    unittest.main()
