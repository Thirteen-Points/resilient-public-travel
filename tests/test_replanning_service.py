from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.app.sim.replanning import ReplanDecision, ReplanningMonitor, dispatch_replan
from backend.app.sim.service import build_diversion_plan


class ReplanningAndServiceTests(unittest.TestCase):
    def test_event_changes_trigger(self) -> None:
        monitor = ReplanningMonitor()
        now = datetime(2026, 9, 22, tzinfo=timezone.utc)
        first = monitor.observe_event({"event_id": "evt", "version": 1, "status": "published", "confidence": 0.9}, observed_at=now)
        same = monitor.observe_event({"event_id": "evt", "version": 1, "status": "published", "confidence": 0.9}, observed_at=now)
        changed = monitor.observe_event({"event_id": "evt", "version": 2, "status": "updated", "confidence": 0.9}, observed_at=now)
        self.assertTrue(first.should_replan)
        self.assertFalse(same.should_replan)
        self.assertTrue(changed.should_replan)

    def test_unpublished_event_edits_do_not_trigger_routes(self) -> None:
        monitor = ReplanningMonitor()
        now = datetime(2026, 9, 22, tzinfo=timezone.utc)
        monitor.observe_event({"event_id": "draft", "version": 1, "status": "draft", "confidence": 0.2}, observed_at=now)
        changed = monitor.observe_event({"event_id": "draft", "version": 2, "status": "pending_review", "confidence": 0.55}, observed_at=now)
        self.assertFalse(changed.should_replan)

    def test_load_requires_five_sustained_minutes_and_rearms(self) -> None:
        monitor = ReplanningMonitor()
        now = datetime(2026, 9, 22, tzinfo=timezone.utc)
        self.assertFalse(monitor.observe_load("r", 0.96, observed_at=now).should_replan)
        self.assertFalse(monitor.observe_load("r", 0.97, observed_at=now + timedelta(minutes=4, seconds=59)).should_replan)
        self.assertTrue(monitor.observe_load("r", 0.97, observed_at=now + timedelta(minutes=5)).should_replan)
        self.assertFalse(monitor.observe_load("r", 0.98, observed_at=now + timedelta(minutes=6)).should_replan)
        monitor.observe_load("r", 0.90, observed_at=now + timedelta(minutes=7))
        self.assertFalse(monitor.observe_load("r", 0.99, observed_at=now + timedelta(minutes=8)).should_replan)

    def test_weather_change_only_triggers_for_severe_codes(self) -> None:
        monitor = ReplanningMonitor()
        self.assertFalse(monitor.observe_weather({"AMBER_RAIN"}).should_replan)
        self.assertFalse(monitor.observe_weather({"RED_RAIN"}).should_replan)
        self.assertTrue(monitor.observe_weather({"BLACK_RAIN"}).should_replan)

    def test_dispatch_calls_route_replanner_only_for_positive_trigger(self) -> None:
        calls = []

        def replanner(decision):
            calls.append(decision.trigger)
            return {"snapshot_id": "g2"}

        skipped = dispatch_replan(ReplanDecision(False), replanner)
        executed = dispatch_replan(
            ReplanDecision(True, "event_changed", "路线已更新：事件变化"), replanner
        )
        self.assertFalse(skipped.recomputed)
        self.assertTrue(executed.recomputed)
        self.assertEqual(executed.result, {"snapshot_id": "g2"})
        self.assertTrue(executed.within_five_second_budget)
        self.assertEqual(calls, ["event_changed"])

    def test_load_service_keeps_contract_fields_and_reports_gap(self) -> None:
        result = build_diversion_plan(
            {
                "event_id": "evt",
                "demand": 1000,
                "window_min": 60,
                "routes": [
                    {"route_id": "r1", "headway_s": 600, "vehicle_capacity": 100, "capacity_per_hour": 500, "provenance": "simulated"}
                ],
            }
        )
        self.assertEqual(result["event_id"], "evt")
        self.assertEqual(result["shares"][0]["route_id"], "r1")
        self.assertEqual(result["unstoppable_demand"], 500)
        self.assertEqual(result["provenance"], "simulated")


if __name__ == "__main__":
    unittest.main()
