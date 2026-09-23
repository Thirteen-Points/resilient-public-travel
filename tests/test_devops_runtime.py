"""M0 runtime composition checks; all inputs are repository-local simulated data."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_reports_offline_seed_and_optional_llm():
    response = TestClient(app).get("/api/health")
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["mode"] == "offline"
    assert body["seed"]["loaded"] is True
    assert body["llm"]["required_for_startup"] is False
    assert body["database"] == {"configured": True, "status": "available"}
    assert body["components"]["signals"] == "ready"


def test_deep_health_checks_route_simulation_and_ai_fallback():
    response = TestClient(app).get("/api/health/deep")
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["checks"]["route"]["routes"] >= 1
    assert body["checks"]["simulation"]["scenario_id"] == "scn_huh_exc_closed_am_peak"
    assert body["checks"]["ai_fallback"]["external_call"] is False
    assert body["checks"]["route"]["origin"] == "TAW"
    assert body["checks"]["route"]["destination"] == "ADM"


def test_ai_chat_without_route_context_is_deterministic_fallback():
    response = TestClient(app).post("/api/ai/chat", json={"message": "请帮我规划路线"})
    assert response.status_code == 200
    assert response.json()["fallback"] is True
