from __future__ import annotations

import math
import unittest

from backend.app.engine.load import RouteSupply, allocate_capacity_buckets
from backend.app.engine.queue import estimate_queue


class CapacityAndQueueTests(unittest.TestCase):
    def test_capacity_is_recomputable_and_units_are_hourly(self) -> None:
        supply = RouteSupply("bus", headway_s=900, vehicle_capacity=137)
        self.assertAlmostEqual(supply.departures_per_hour, 4.0)
        self.assertAlmostEqual(supply.service_capacity_per_hour, 548.0)
        self.assertAlmostEqual(supply.capacity_per_hour, 465.8)
        self.assertEqual(supply.bucket_capacity(60), 465)

    def test_bucket_reports_unmet_demand_without_overfilling(self) -> None:
        supplies = (
            RouteSupply("large", 600, 100),
            RouteSupply("small", 1200, 20),
        )
        result = allocate_capacity_buckets(1000, supplies)
        self.assertEqual(result.allocated + result.unstoppable_demand, 1000)
        for share in result.shares:
            supply = next(item for item in supplies if item.route_id == share.route_id)
            self.assertLessEqual(share.users, supply.bucket_capacity(60))

    def test_route_adapter_accepts_frozen_capacity_without_vehicle_field(self) -> None:
        supply = RouteSupply.from_route_output(
            {"route_id": "r", "headway_s": 600, "capacity_per_hour": 510, "provenance": "simulated"}
        )
        self.assertAlmostEqual(supply.capacity_per_hour, 510)
        self.assertAlmostEqual(supply.service_capacity_per_hour, 600)

    def test_queue_diverges_then_caps_and_stays_finite(self) -> None:
        low = estimate_queue(demand_per_hour=10, service_capacity_per_hour=100, headway_s=300)
        near = estimate_queue(demand_per_hour=99.999, service_capacity_per_hour=100, headway_s=300)
        over = estimate_queue(demand_per_hour=120, service_capacity_per_hour=100, headway_s=300)
        self.assertLess(low.expected_wait_s, near.expected_wait_s)
        self.assertEqual(near.expected_wait_s, 600)
        self.assertEqual(over.expected_wait_s, 600)
        self.assertTrue(math.isfinite(over.expected_wait_s))
        self.assertEqual(over.board_refusal_prob, 1.0)


if __name__ == "__main__":
    unittest.main()
