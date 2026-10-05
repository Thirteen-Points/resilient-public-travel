"""B-owned P3/P4 contracts and truthful fallback checks."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.ai.schemas import SchemaValidationError, validate_chat_response
from backend.app.admin.scheduler import public_source_status
from backend.app.main import build_preference_client, create_app
from backend.app.services.persona import load_personas, load_presets


class FakePreferenceClient:
    def __init__(self, result):
        self.result = result

    def generate_json(self, **_kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_catalog_matches_engine_weights_and_preserves_accessibility():
    from backend.app.engine.score import CRITERIA, PRESETS

    personas, presets = load_personas(), load_presets()
    assert [item.persona for item in personas] == ["commuter", "student", "tourist", "elderly", "wheelchair"]
    assert len({tuple(item.weights.values()) for item in personas}) == 5
    assert personas[-1].max_walk_m == 400
    assert set(personas[-1].hard_flags) == {"no_stairs", "no_minibus", "no_non_lowfloor_bus"}
    for name, weights in presets.items():
        assert abs(sum(weights.values()) - 1) < 1e-6
        for criterion, raw in zip(CRITERIA, PRESETS[name]):
            assert abs(weights[criterion] - raw / sum(PRESETS[name])) < 1e-6


def test_public_catalog_parser_and_fallback_are_wired_to_shared_app():
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(db_path=Path(directory) / "events.sqlite3",
                                   preference_client=FakePreferenceClient(TimeoutError()))) as client:
            catalog = client.get("/api/personas")
            presets = client.get("/api/personas/presets")
            parsed = client.post("/api/persona/parse", json={
                "free_text": "轮椅，别太贵", "current_profile": {
                    "mobility": "wheelchair", "max_walk_m": 250, "hard_flags": ["no_stairs"]}})
    assert catalog.status_code == 200 and len(catalog.json()) == 5
    assert presets.status_code == 200 and len(presets.json()) == 3
    assert parsed.status_code == 200 and parsed.json()["method"] == "rule_fallback"
    assert parsed.json()["patch"]["max_walk_m"] == 250
    assert set(parsed.json()["patch"]["hard_flags"]) == {"no_stairs", "no_minibus", "no_non_lowfloor_bus"}


def test_preference_model_is_off_by_default_and_offline_guarded():
    with patch.dict(os.environ, {"AI_ENABLED": "true", "PERSONA_PARSE_AI_ENABLED": "false",
                                "DEEPSEEK_API_KEY": "test-only", "OFFLINE_MODE": "false"}):
        assert build_preference_client() is None
    with patch.dict(os.environ, {"AI_ENABLED": "true", "PERSONA_PARSE_AI_ENABLED": "true",
                                "DEEPSEEK_API_KEY": "test-only", "OFFLINE_MODE": "true"}):
        assert build_preference_client() is None


def test_weather_policy_is_explicitly_simulated():
    weather = json.loads((Path(__file__).resolve().parents[2] / "data/weather_impact.json").read_text(encoding="utf-8"))
    assert all(value["provenance"] == "simulated" for value in weather["weather_conditions"].values())
    assert weather["reliability_cv"]["provenance"] == "simulated"
    assert weather["ferry_cancellation_threshold"]["provenance"] == "simulated"


def test_public_source_status_exposes_safe_history_without_secrets():
    class Store:
        ready = True

        def settings(self):
            return {"sources": {name: {"enabled": True, "poll_interval_seconds": 90}
                                for name in ("hko", "mtr")}}

        def source_state(self, name):
            return {"last_attempt": 1, "last_success": "2026-10-04T12:00:00Z",
                    "last_result": {"status": "failed", "at": "2026-10-04T12:01:00Z",
                                    "failures": 1, "details": {"private": "secret"}},
                    "api_key": "secret", "error": "private-provider-url"}

    class OnlineStore:
        def state(self, name):
            assert name == "mtr_mobile"
            return {"status": "partial_failure", "last_attempt": "2026-10-04T12:01:00+00:00",
                    "last_success": "2026-10-04T12:00:00+00:00", "token": "secret",
                    "error": "https://private-provider-url?key=secret"}

    with patch("backend.app.admin.scheduler.offline_mode", return_value=False):
        response = public_source_status(Store(), online_store=OnlineStore())
    assert response["sources"]["hko"]["classification"] == "official_public_warning"
    assert response["sources"]["mtr"]["classification"] == "official_public_eta"
    assert response["sources"]["hko"]["last_success"] == "2026-10-04T12:00:00Z"
    assert response["sources"]["hko"]["status"] == "failed"
    assert response["sources"]["hko"]["stale"]
    assert response["sources"]["mtr_mobile"]["status"] == "partial_failure"
    assert response["sources"]["mtr_mobile"]["classification"] == "official_public_notice"
    assert response["sources"]["mtr_mobile"]["stale"]
    assert "secret" not in json.dumps(response)
    assert "private-provider-url" not in json.dumps(response)


def test_wording_rejects_invented_route_line_and_measured_claim():
    tools = [{"ok": True, "data": {"route_id": "r_known", "line": "East Rail Line", "line_zh": "东铁线",
                                    "provenance": "simulated"}}]
    for message in ("Take r_invented", "Take Fantasy Line", "乘坐虚构线", "这是实测客流"):
        try:
            validate_chat_response({"message": message, "tool_calls": []}, tools)
        except SchemaValidationError:
            pass
        else:
            raise AssertionError(message)
    assert validate_chat_response({"message": "Take East Rail Line on r_known (simulated)",
                                   "tool_calls": []}, tools)["message"]
    assert validate_chat_response({"message": "请乘坐东铁线（模拟数据）", "tool_calls": []}, tools)["message"]
