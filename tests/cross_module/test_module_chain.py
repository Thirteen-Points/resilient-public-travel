"""Real code + simulated data: passing checks do not certify C-Data or B/DevOps."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from backend.app.ai.handlers import build_engine_handlers
from backend.app.ai.query import NoLLMQueryService
from backend.app.ai.tools import build_default_registry
from backend.app.engine.api import create_app
from backend.app.engine.load import RouteSupply
from backend.app.engine.handlers import RouteHandlers
from backend.app.engine.sim_adapter import MappingDemandAdapter
from backend.app.graph.adapter import MappingDataAdapter
from backend.app.sim.api import build_router
from backend.app.sim.cache import PrecomputedResultStore, write_precomputed
from backend.app.sim.models import Agent, RouteOption
from backend.app.sim.replanning import ReplanningMonitor, dispatch_replan
from backend.app.sim.service import build_diversion_plan
from backend.app.sim.run import _guided_assignments, _personal_rankings
from scripts.integration.contracts import validate_payload, validate_response
from scripts.integration.module_bridge import ModuleBridge

class ModuleChainTests(unittest.TestCase):
    def setUp(self):
        self.bridge = ModuleBridge()

    def test_json_adapter_to_http_route_candidate(self):
        original = deepcopy(self.bridge.network)
        client = TestClient(create_app(self.bridge.engine))
        response = client.post("/api/routes/query", json={
            "origin":self.bridge.config["origin"], "destination":self.bridge.config["destination"],
            "depart_at":self.bridge.config["depart_at"]})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 8)
        self.assertEqual(validate_response("POST", "/api/routes/query", 200, response.json()), [])
        self.assertEqual(original, self.bridge.network)
        self.assertTrue(all(r["provenance"] == "simulated" for r in response.json()))

    def test_route_capacity_to_real_sim_reproduces_and_caches(self):
        details = self.bridge.query()
        result = self.bridge.simulate(details)
        self.assertEqual(result, self.bridge.simulate(details))
        self.assertEqual(validate_payload("SimResult", result), [])
        self.assertEqual({r["route_id"] for r in details["routes"]},
                         {c["route_id"] for c in result["capacity_calculations"]})
        for supply in result["capacity_calculations"]:
            parameters = details["route_parameters"][supply["route_id"]]
            self.assertAlmostEqual(supply["capacity_per_hour"], parameters["capacity_per_hour"])
            self.assertAlmostEqual(supply["headway_s"], parameters["headway_s"])
        self.assertEqual(sum(r["users"] for r in result["guided"]["shares"]) +
                         result["guided"]["unstoppable_demand"], self.bridge.config["population"])
        with tempfile.TemporaryDirectory() as directory:
            write_precomputed(result, Path(directory))
            self.assertEqual(PrecomputedResultStore(Path(directory)).read(result["scenario_id"]), result)

    def test_route_and_sim_routers_share_contract_and_error_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self.bridge.engine)
            app.include_router(build_router(Path(directory)))
            client = TestClient(app)
            details = self.bridge.query()
            payload = {"event_id":"integration_closure", "demand":self.bridge.config["population"],
                       "window_min":self.bridge.config["window_min"], "routes":self.bridge.supplies(details)}
            response = client.post("/api/sim/load", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(validate_payload("DiversionPlan", response.json()), [])
            result = self.bridge.simulate(details)
            write_precomputed(result, Path(directory))
            self.assertEqual(client.get("/api/sim/result", params={"scenario_id":result["scenario_id"]}).json(), result)
            missing = client.get("/api/sim/result", params={"scenario_id":"missing"})
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(validate_response("GET", "/api/sim/result", 404, missing.json()), [])

    def test_event_fixture_refreshes_graph_routes_and_sim(self):
        monitor = ReplanningMonitor()
        before = self.bridge.query()
        decision = monitor.observe_event(self.bridge.closure("pending_review"))
        self.assertFalse(decision.should_replan)
        self.assertEqual(before, self.bridge.query())
        event = self.bridge.closure("published", 2)
        def refresh(_):
            self.bridge.engine.snapshots.update_event(event)
            details = self.bridge.query()
            return details, self.bridge.simulate(details)
        execution = dispatch_replan(monitor.observe_event(event), refresh)
        self.assertTrue(execution.recomputed)
        details, result = execution.result
        self.assertNotEqual(before["graph_snapshot"], details["graph_snapshot"])
        self.assertLess(len(details["routes"]), len(before["routes"]))
        self.assertTrue(all(leg.get("line") != event["line"] for r in details["routes"] for leg in r["legs"]))
        self.assertEqual({c["route_id"] for c in result["capacity_calculations"]},
                         {r["route_id"] for r in details["routes"]})
        event = self.bridge.closure("expired", 3)
        restored = dispatch_replan(monitor.observe_event(event), refresh)
        self.assertEqual(len(restored.result[0]["routes"]), len(before["routes"]))

    def test_real_ai_handlers_receive_engine_and_sim_results(self):
        registry = build_default_registry(build_engine_handlers(self.bridge.engine, build_diversion_plan))
        service = NoLLMQueryService(registry)
        result = asyncio.run(service.query(user_input="Show synthetic alternatives", origin=self.bridge.config["origin"],
                                            destination=self.bridge.config["destination"],
                                            depart_at=self.bridge.config["depart_at"], event_id="integration_closure",
                                            demand=self.bridge.config["population"]))
        self.assertTrue(result["fallback"])
        self.assertTrue(all(call["ok"] for call in result["tool_calls"]))
        self.assertEqual(result["routes"], self.bridge.query()["routes"])
        self.assertEqual(validate_payload("DiversionPlan", result["diversion"]), [])
        self.assertEqual(len(registry.audit_log), 3)

class StrictAcceptanceTests(unittest.TestCase):
    """Failures are open owner issues, deliberately not marked expectedFailure/skip."""
    def test_ai_chat_message_is_public_contract_string(self):
        bridge = ModuleBridge()
        registry = build_default_registry(build_engine_handlers(bridge.engine, build_diversion_plan))
        result = asyncio.run(NoLLMQueryService(registry).query(
            user_input="Show synthetic alternatives", origin=bridge.config["origin"],
            destination=bridge.config["destination"], depart_at=bridge.config["depart_at"]))
        self.assertIsInstance(result["message"], str, "03 section 4 chat message must not be a nested response envelope")

    def test_simulated_tool_trace_keeps_provenance(self):
        bridge = ModuleBridge()
        registry = build_default_registry(build_engine_handlers(bridge.engine, build_diversion_plan))
        result = asyncio.run(registry.call("search_transit_routes", {
            "from":bridge.config["origin"], "to":bridge.config["destination"],
            "depart_at":bridge.config["depart_at"]}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["trace"]["provenance"], result["data"]["provenance"],
                         "deterministic describes computation, not data truthfulness")

    def test_protected_personal_best_is_preserved(self):
        agent = Agent("sim_protected", "O", "D", "wheelchair", "wheelchair", 400)
        best = RouteOption("best", 10, 0, 0, 0, .9, ("MTR",), True)
        slower = RouteOption("slower", 11, 0, 0, 0, .9, ("MTR",), True)
        # Invented one-person fixture; both routes have spare simulated capacity.
        supplies = {r.route_id: RouteSupply(r.route_id, 3600, capacity,
                    provenance="simulated", note="Synthetic fairness acceptance fixture")
                    for r, capacity in ((best, 10), (slower, 20))}
        rankings = _personal_rankings((agent,), (best, slower))
        self.assertEqual(rankings[agent.agent_id][0].route_id, "best")
        assignments, _ = _guided_assignments((agent,), (best, slower), supplies, rankings, 60)
        self.assertEqual(assignments[agent.agent_id], "best",
                         "03 fairness note promises personal-best protection even when another route has more capacity")

    def test_route_owned_handlers_plug_into_ai_orchestrator(self):
        bridge = ModuleBridge()
        handlers = RouteHandlers(
            MappingDataAdapter(bridge.network, baseline_fare=bridge.config["baseline_fare_hkd"]),
            demand_adapter=MappingDemandAdapter({}, source="integration_zero_demand_fixture",
                                               provenance="simulated", freshness_s=0,
                                               default_rate_per_hour=0),
            observed_at=bridge.config["depart_at"])
        service = NoLLMQueryService(build_default_registry(handlers.handlers()))
        result = asyncio.run(service.query(
            user_input="Show simulated alternatives", origin=bridge.config["origin"],
            destination=bridge.config["destination"], depart_at=bridge.config["depart_at"]))
        self.assertGreater(len(result["routes"]), 0)
