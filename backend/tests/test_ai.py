import asyncio
import json
import unittest
from pathlib import Path

from app.ai.llm_client import LLMClient, LLMConfig, Provider
from app.ai.handlers import build_engine_handlers
from app.ai.query import NoLLMQueryService
from app.ai.schemas import SchemaValidationError, validate_chat_response
from app.ai.tools import ToolSpec, ToolRegistry, build_default_registry


class SchemaTests(unittest.TestCase):
    @staticmethod
    def fixture_results():
        fixture = Path(__file__).parents[1] / "app" / "ai" / "fixtures" / "chat_tool_results.simulated.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        assert payload["provenance"] == "simulated"
        return payload["tool_results"]

    def test_rejects_an_invented_number(self):
        with self.assertRaises(SchemaValidationError):
            validate_chat_response({"message": "预计 12 分钟", "tool_calls": []}, [])

    def test_allows_number_from_tool_result(self):
        result = validate_chat_response({"message": "工具结果为 12", "tool_calls": []}, self.fixture_results())
        self.assertEqual(result["message"], "工具结果为 12")

    def test_rejects_wrong_schema_type(self):
        with self.assertRaises(SchemaValidationError):
            validate_chat_response({"message": "", "tool_calls": "not-an-array"})


class ToolTests(unittest.TestCase):
    def test_tool_results_are_traced(self):
        registry = ToolRegistry()
        registry.register(ToolSpec("x", "test", {"type": "object", "required": ["value"]}), lambda value: {"value": value})
        result = asyncio.run(registry.call("x", {"value": 3}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["trace"]["provenance"], "deterministic")
        self.assertEqual(registry.audit_log[0]["tool"], "x")

    def test_trace_preserves_handler_data_provenance(self):
        registry = ToolRegistry()
        registry.register(ToolSpec("simulated", "test", {"type": "object", "required": []}),
                          lambda: {"provenance": "simulated", "freshness_s": 0})
        result = asyncio.run(registry.call("simulated"))
        self.assertEqual(result["trace"]["provenance"], "simulated")
        self.assertEqual(result["trace"]["freshness_s"], 0)

    def test_default_registry_contains_contract_tools(self):
        names = {item["function"]["name"] for item in build_default_registry().schemas()}
        self.assertEqual(names, {"geocode_place", "find_access_points", "search_transit_routes", "score_routes", "estimate_load", "get_diversion_plan"})

    def test_contract_search_tool_schema(self):
        schema = next(item["function"]["parameters"] for item in build_default_registry().schemas()
                      if item["function"]["name"] == "search_transit_routes")
        self.assertEqual(schema["required"], ["from", "to", "depart_at"])
        self.assertEqual(schema["properties"]["depart_at"]["format"], "date-time")

    def test_handler_failure_is_a_safe_tool_result(self):
        registry = ToolRegistry()
        registry.register(ToolSpec("broken", "test", {"type": "object", "required": []}), lambda: (_ for _ in ()).throw(RuntimeError("offline")))
        result = asyncio.run(registry.call("broken"))
        self.assertEqual(result["error"], "tool_unavailable")
        self.assertEqual(result["trace"]["provenance"], "deterministic")

    def test_handler_timeout_is_a_safe_tool_result(self):
        async def delayed():
            await asyncio.sleep(0.03)
            return {"provenance": "simulated", "freshness_s": 0}
        registry = ToolRegistry(timeout_s=0.001)
        registry.register(ToolSpec("slow", "test", {"type": "object", "required": []}), delayed)
        result = asyncio.run(registry.call("slow"))
        self.assertEqual(result["error"], "tool_timeout")


class ClientTests(unittest.TestCase):
    def test_disabled_client_has_no_ai_fallback(self):
        client = LLMClient(LLMConfig(enabled=False))
        result = asyncio.run(client.chat("请解释路线"))
        self.assertTrue(result.fallback)
        self.assertIsNone(result.provider)

    def test_schema_failure_retries_then_uses_next_provider(self):
        config = LLMConfig(enabled=True, max_retries=0, providers=(
            Provider("deepseek", "https://one.invalid", "x", "m"), Provider("qwen", "https://two.invalid", "x", "m"),
        ))
        client = LLMClient(config)
        calls = []

        async def fake_request(provider, messages):
            calls.append(provider.name)
            if provider.name == "deepseek":
                return {"message": "I made 7 up", "tool_calls": []}, {}
            return {"message": "数据暂不可用", "tool_calls": []}, {}

        client._request = fake_request  # type: ignore[method-assign]
        result = asyncio.run(client.chat("hello"))
        self.assertFalse(result.fallback)
        self.assertEqual(result.provider, "qwen")
        self.assertEqual(calls, ["deepseek", "qwen"])

    def test_timeout_and_failure_fall_through_to_glm_with_audit_log(self):
        config = LLMConfig(enabled=True, max_retries=0, providers=(
            Provider("deepseek", "https://one.invalid", "x", "m"),
            Provider("qwen", "https://two.invalid", "x", "m"),
            Provider("glm", "https://three.invalid", "x", "m"),
        ))
        client = LLMClient(config)
        calls = []

        async def fake_request(provider, messages):
            calls.append(provider.name)
            if provider.name == "deepseek":
                raise asyncio.TimeoutError()
            if provider.name == "qwen":
                raise OSError("mock provider failure")
            return {"message": "数据暂不可用", "tool_calls": []}, {"prompt_tokens": 2, "completion_tokens": 3}

        client._request = fake_request  # type: ignore[method-assign]
        result = asyncio.run(client.chat("hello"))
        self.assertEqual(result.provider, "glm")
        self.assertFalse(result.fallback)
        self.assertEqual(calls, ["deepseek", "qwen", "glm"])
        self.assertEqual([row["status"] for row in client.call_log], ["failed", "failed", "ok"])


class NoLLMFlowTests(unittest.TestCase):
    @staticmethod
    def registry():
        from app.engine.service import RouteEngine
        from app.sim.service import build_diversion_plan
        engine = RouteEngine.from_seed()
        return build_default_registry(build_engine_handlers(engine, build_diversion_plan))

    def test_all_six_bound_handlers_preserve_metadata(self):
        async def call_all():
            registry = self.registry()
            geo = await registry.call("geocode_place", {"query": "TAW"})
            access = await registry.call("find_access_points", {"lat": geo["data"]["lat"], "lng": geo["data"]["lng"]})
            routes = await registry.call("search_transit_routes", {"from": "TAW", "to": "ADM", "depart_at": "2026-09-22T08:20:00+08:00"})
            ids = [route["route_id"] for route in routes["data"]["routes"]]
            score = await registry.call("score_routes", {"route_ids": ids})
            loads = await registry.call("estimate_load", {"route_ids": ids, "horizon_min": 60})
            diversion = await registry.call("get_diversion_plan", {"event_id": "evt_simulated", "demand": 25})
            return geo, access, routes, score, loads, diversion

        for result in asyncio.run(call_all()):
            self.assertTrue(result["ok"])
            self.assertIn(result["data"]["provenance"], {"real", "real-derived", "simulated"})
            self.assertIn("freshness_s", result["data"])

    def test_disabled_llm_full_deterministic_query(self):
        from app.engine.service import RouteEngine
        from app.sim.service import build_diversion_plan

        engine = RouteEngine.from_seed()
        registry = build_default_registry(build_engine_handlers(engine, build_diversion_plan))
        response = asyncio.run(NoLLMQueryService(registry).query(
            user_input="请给我替代方案", origin="TAW", destination="ADM",
            depart_at="2026-09-22T08:20:00+08:00", event_id="evt_simulated", demand=25,
        ))
        self.assertTrue(response["fallback"])
        self.assertTrue(response["routes"])
        self.assertTrue(response["loads"]["loads"])
        self.assertEqual(response["diversion"]["provenance"], "simulated")
        self.assertIsInstance(response["message"], str)
        self.assertIn("确定性", response["message"])
        self.assertTrue(all(call["trace"]["tool"] for call in response["tool_calls"]))

    def test_corridor_od_search_is_not_pinned_to_taw_adm(self):
        async def searches():
            registry = self.registry()
            results = {}
            for origin, destination in (("HUH", "KOT"), ("EXC", "MKK"), ("MKK", "ADM"), ("ADM", "TAW")):
                result = await registry.call("search_transit_routes", {
                    "from": origin, "to": destination, "depart_at": "2026-09-22T08:20:00+08:00"})
                results[(origin, destination)] = result
            return results

        for od, result in asyncio.run(searches()).items():
            self.assertTrue(result["ok"], od)
            data = result["data"]
            self.assertTrue(data["graph_snapshot"])
            self.assertEqual(data["provenance"], "simulated")
            route_ids = [route["route_id"] for route in data["routes"]]
            self.assertTrue(route_ids, od)
            self.assertEqual(len(route_ids), len(set(route_ids)), od)

    def test_fewer_than_target_candidates_are_explained_without_padding(self):
        response = asyncio.run(NoLLMQueryService(self.registry()).query(
            user_input="给我替代方案", origin="EXC", destination="MKK", depart_at="2026-09-22T08:20:00+08:00"))
        self.assertLess(len(response["routes"]), 10)
        self.assertIn("少于目标数量", response["message"])
        self.assertIn("不补造路线", response["message"])


if __name__ == "__main__":
    unittest.main()
