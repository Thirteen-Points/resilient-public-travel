"""P4 interface acceptance: snapshot header, chat metadata, source last_success_at.

Every test uses an isolated database or a synthetic engine plus controlled mock
responses; no live source, no paid model, no deployment.
"""

import asyncio
import json
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.admin import collect
from backend.app.admin.scheduler import public_source_status, router as sources_router
from backend.app.admin.store import AdminStore, password_hash
from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app as engine_create_app
from backend.app.engine.load_provider import FixtureLoadProvider
from backend.app.graph.adapter import MappingDataAdapter
from backend.app.main import create_app, runtime
from backend.app.services.event_store import EventStore
from backend.app.services.ingest.hko import HkoWarningPoller
from backend.app.services.ingest.mtr_eta import MtrEtaFetchError, MtrEtaAnomalyPoller, MtrDetectionConfig
from backend.app.services.signal_store import SignalStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "app" / "engine" / "fixtures"
AT = "2026-09-22T08:20:00+08:00"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def synthetic_engine(events=()):
    adapter = MappingDataAdapter(read("network.synthetic.json"),
                                 baseline_fare=read("seed_policy.json")["baseline_fare_hkd"],
                                 events=events)
    return RouteEngine.from_adapter(adapter,
                                    load_provider=FixtureLoadProvider(read("seed_policy.json")["load"]))


def later_event(base):
    """A second valid published event so replace_events produces a new snapshot id."""
    event = deepcopy(base)
    event["event_id"] = "evt_fixture_published_mid_query"
    event["window"]["start"] = "2026-09-22T08:05:00+08:00"
    return event


def chat_payload(**overrides):
    payload = {"message": "请给我路线", "origin": "TAW", "destination": "ADM", "depart_at": AT}
    payload.update(overrides)
    return payload


class TestRouteSnapshotHeader:
    def test_main_app_query_returns_array_with_computation_snapshot_header(self):
        assert runtime.engine is not None, runtime.error
        with tempfile.TemporaryDirectory(prefix=".p4-api-", dir=ROOT) as directory:
            client = TestClient(create_app(db_path=Path(directory) / "p4.sqlite3"))
            response = client.post("/api/routes/query", json=chat_payload_for_route())
            assert response.status_code == 200, response.text
            body = response.json()
            assert isinstance(body, list) and body  # bare RouteCandidate[], no wrapper
            header = response.headers["x-route-snapshot"]
            assert header.startswith("g_")
            # The header is the snapshot used for THIS computation, taken from the
            # single query_details call, never a post-computation global read.
            assert header == runtime.engine.snapshots.current.snapshot_id

    def test_cached_query_returns_snapshot_matching_cached_result(self):
        engine = synthetic_engine()
        client = TestClient(engine_create_app(engine))
        payload = {"origin": "O", "destination": "D", "depart_at": AT}
        first = client.post("/api/routes/query", json=payload)
        assert first.status_code == 200
        hits = engine.cache.hits
        second = client.post("/api/routes/query", json=payload)
        assert second.status_code == 200
        assert engine.cache.hits == hits + 1  # second call served from cache
        assert second.headers["x-route-snapshot"] == first.headers["x-route-snapshot"]
        assert second.headers["x-route-snapshot"] == engine.snapshots.current.snapshot_id
        assert second.json() == first.json()

    def test_header_reports_pinned_snapshot_when_events_change_mid_computation(self, monkeypatch):
        import backend.app.engine.service as service_module

        base_events = read("events.synthetic.json")["events"]
        engine = synthetic_engine(events=base_events)
        pinned_id = engine.snapshots.current.snapshot_id
        real_search = service_module.search_paths

        def swapping_search(snapshot, *args, **kwargs):
            # A reviewer-approved event lands while the first query computes.
            engine.snapshots.replace_events([*base_events, later_event(base_events[0])])
            assert engine.snapshots.current.snapshot_id != pinned_id
            return real_search(snapshot, *args, **kwargs)

        monkeypatch.setattr(service_module, "search_paths", swapping_search)
        client = TestClient(engine_create_app(engine))
        response = client.post("/api/routes/query", json={"origin": "O", "destination": "D", "depart_at": AT})
        assert response.status_code == 200, response.text
        assert response.headers["x-route-snapshot"] == pinned_id
        # The global snapshot moved on, but the answer was computed on the pinned one.
        assert engine.snapshots.current.snapshot_id != pinned_id

    def test_publishing_new_event_changes_header_and_body_recomputation(self):
        engine = synthetic_engine()
        client = TestClient(engine_create_app(engine))
        payload = {"origin": "O", "destination": "D", "depart_at": AT}
        before = client.post("/api/routes/query", json=payload)
        assert before.status_code == 200
        base_events = read("events.synthetic.json")["events"]
        engine.snapshots.replace_events(base_events)
        after = client.post("/api/routes/query", json=payload)
        assert after.status_code == 200
        assert after.headers["x-route-snapshot"] != before.headers["x-route-snapshot"]
        assert after.headers["x-route-snapshot"] == engine.snapshots.current.snapshot_id

    def test_error_responses_keep_contract_without_snapshot_header(self):
        engine = synthetic_engine()
        client = TestClient(engine_create_app(engine), raise_server_exceptions=False)
        response = client.post("/api/routes/query", json={"origin": "O", "destination": "D", "depart_at": "nonsense"})
        assert response.status_code == 400
        assert "x-route-snapshot" not in response.headers
        assert set(response.json()["error"]) == {"code", "message", "fallback"}

    def test_cors_exposes_route_snapshot_header(self):
        with tempfile.TemporaryDirectory(prefix=".p4-cors-", dir=ROOT) as directory:
            client = TestClient(create_app(db_path=Path(directory) / "p4.sqlite3"))
            origin = "http://localhost:5173"
            preflight = client.options("/api/routes/query", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"})
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == origin
            response = client.post("/api/routes/query", json=chat_payload_for_route(),
                                   headers={"Origin": origin})
            assert response.status_code == 200
            assert "x-route-snapshot" in response.headers["access-control-expose-headers"].lower()
            assert response.headers["access-control-allow-origin"] == origin


def chat_payload_for_route():
    return {"origin": "TAW", "destination": "ADM", "depart_at": AT}


class TestChatProfileMetadata:
    @pytest.fixture
    def client(self):
        with tempfile.TemporaryDirectory(prefix=".p4-chat-", dir=ROOT) as directory:
            with TestClient(create_app(db_path=Path(directory) / "p4.sqlite3")) as app_client:
                yield app_client

    @pytest.mark.parametrize(("mobility", "speed"), [("standard", 1.4), ("reduced", 0.7), ("wheelchair", 0.7)])
    def test_explicit_profile_reaches_deterministic_engine(self, client, mobility, speed):
        response = client.post("/api/ai/chat", json=chat_payload(profile={"mobility": mobility}))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fallback"] is True  # no model in tests: explicit deterministic fallback
        effective = body["effective_profile"]
        assert effective["mobility"] == mobility
        assert effective["walking_speed_mps"] == speed
        if mobility != "standard":
            assert effective["max_walk_m"] <= 400
            assert all(leg["mode"] != "MINIBUS" for route in body["routes"] for leg in route["legs"])
        # Chat metadata must mirror the route tool result, not a re-read snapshot.
        assert body["graph_snapshot"] == body["tool_calls"][0]["data"]["graph_snapshot"]
        assert effective == body["tool_calls"][0]["data"]["effective_profile"]
        assert body["graph_snapshot"] == runtime.engine.snapshots.current.snapshot_id
        # The exact same profile produces the identical deterministic candidates.
        expected = runtime.engine.query_details("TAW", "ADM", AT, {"mobility": mobility})["routes"]
        assert [r["route_id"] for r in body["routes"]] == [r["route_id"] for r in expected]
        assert [r["score"] for r in body["routes"]] == [r["score"] for r in expected]

    def test_explicit_weights_and_hard_limits_actually_apply(self, client):
        profile = {"mobility": "standard", "weights": {"time": 0.05, "price": 0.95},
                   "hard_flags": ["no_minibus"], "max_transfers": 1, "max_walk_m": 250}
        response = client.post("/api/ai/chat", json=chat_payload(profile=profile))
        assert response.status_code == 200, response.text
        body = response.json()
        effective = body["effective_profile"]
        assert effective["weights"] == profile["weights"]
        assert effective["hard_flags"] == ["no_minibus"]
        assert effective["max_transfers"] == 1
        assert effective["max_walk_m"] == 250
        assert body["routes"]
        for route in body["routes"]:
            assert all(leg["mode"] != "MINIBUS" for leg in route["legs"])
            assert sum(1 for leg in route["legs"] if leg["mode"] != "WALK") <= 2  # max 1 transfer
            assert route["total"]["walk_m"] <= 250
        # Different weights change the deterministic score breakdown, proving
        # the weights were used by the scoring pass and not just echoed back.
        fast = client.post("/api/ai/chat", json=chat_payload(
            profile={**profile, "weights": {"time": 0.95, "price": 0.05}})).json()
        assert {r["route_id"] for r in body["routes"]} == {r["route_id"] for r in fast["routes"]}

        def time_contribution(route):
            return next(row for row in route["score_breakdown"] if row["criterion"] == "time")["contribution"]

        cheap_top, fast_top = body["routes"][0], fast["routes"][0]
        assert cheap_top["route_id"] == fast_top["route_id"]
        assert abs(time_contribution(fast_top) - time_contribution(cheap_top)) > 1e-9
        assert abs(fast_top["score"] - cheap_top["score"]) > 1e-9

    def test_merging_explicit_parameters_never_relaxes_wheelchair_profile(self, client):
        response = client.post("/api/ai/chat", json=chat_payload(
            profile_id="wheelchair",
            profile={"mobility": "standard", "max_walk_m": 100000, "hard_flags": []}))
        assert response.status_code == 200, response.text
        effective = response.json()["effective_profile"]
        assert effective["mobility"] == "wheelchair"
        assert effective["max_walk_m"] == 400  # explicit 100000 m cannot relax the limit
        assert effective["walking_speed_mps"] == 0.7
        for flag in ("no_stairs", "no_minibus", "no_non_lowfloor_bus"):
            assert flag in effective["hard_flags"]
        assert all(leg["mode"] != "MINIBUS" for route in response.json()["routes"] for leg in route["legs"])

    @pytest.mark.parametrize("overrides", [
        {"profile": {"mobility": "teleport"}},
        {"profile": "wheelchair"},
        {"profile": {"mobility": "wheelchair", "max_transfers": -1}},
        {"profile": {"weights": {"unknown_criterion": 1.0}}},
        {"profile_id": "does-not-exist"},
    ])
    def test_invalid_parameters_are_reported_not_ignored_and_never_500(self, client, overrides):
        response = client.post("/api/ai/chat", json=chat_payload(**overrides))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fallback"] is True
        assert body["graph_snapshot"] is None      # tool failed: no invented metadata
        assert body["effective_profile"] is None
        assert body["tool_calls"][0]["ok"] is False
        assert isinstance(body["message"], str) and body["message"]
        assert "routes" not in body

    def test_missing_travel_fields_return_null_metadata(self, client):
        response = client.post("/api/ai/chat", json={"message": "你好"})
        assert response.status_code == 200
        body = response.json()
        assert body["fallback"] is True
        assert body["graph_snapshot"] is None
        assert body["effective_profile"] is None
        assert body["tool_calls"] == []

    def test_concurrent_chats_keep_per_request_context(self):
        from backend.app.ai.handlers import build_engine_handlers
        from backend.app.ai.query import NoLLMQueryService
        from backend.app.ai.tools import build_default_registry
        from backend.app.sim.service import build_diversion_plan

        assert runtime.engine is not None, runtime.error

        async def one_chat(mobility):
            # Exactly how /api/ai/chat constructs the service: fresh handlers
            # per request over the shared engine.
            service = NoLLMQueryService(build_default_registry(
                build_engine_handlers(runtime.engine, build_diversion_plan)))
            return await service.query(user_input="并行请求", origin="TAW", destination="ADM",
                                       depart_at=AT, profile={"mobility": mobility})

        async def scenario():
            return await asyncio.gather(one_chat("wheelchair"), one_chat("standard"))

        wheelchair, standard = asyncio.run(scenario())
        assert wheelchair["effective_profile"]["mobility"] == "wheelchair"
        assert standard["effective_profile"]["mobility"] == "standard"
        assert wheelchair["graph_snapshot"] == standard["graph_snapshot"]
        assert wheelchair["graph_snapshot"] == runtime.engine.snapshots.current.snapshot_id

    def test_model_wording_cannot_override_metadata_or_route_numbers(self, tmp_path, monkeypatch):
        from backend.app.ai.handlers import build_engine_handlers
        from backend.app.ai.query import NoLLMQueryService
        from backend.app.ai.tools import build_default_registry
        from backend.app.services.structure.llm_api_client import OpenAiCompatJsonClient
        from backend.app.sim.service import build_diversion_plan

        monkeypatch.setenv("OFFLINE_MODE", "false")
        monkeypatch.delenv("AI_DISABLE_EXTERNAL", raising=False)
        monkeypatch.setenv("AI_ENABLED", "true")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "never-a-real-key")
        for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "ADMIN_ENCRYPTION_KEY"):
            monkeypatch.delenv(name, raising=False)

        def fake_generate(self, **kwargs):
            self.usage = {"prompt_tokens": 10, "completion_tokens": 10}
            return '{"message":"模型改写后的说明。","tool_calls":[]}'

        monkeypatch.setattr(OpenAiCompatJsonClient, "generate_json", fake_generate)
        with TestClient(create_app(db_path=tmp_path / "p4-wording.sqlite3")) as client:
            body = client.post("/api/ai/chat",
                               json=chat_payload(profile={"mobility": "wheelchair"})).json()
        assert body["fallback"] is False
        assert body["message"] == "模型改写后的说明。"
        # Computed routes and metadata survive the wording pass untouched.
        assert body["routes"] == body["tool_calls"][0]["data"]["routes"]
        assert body["graph_snapshot"] == body["tool_calls"][0]["data"]["graph_snapshot"]
        assert body["effective_profile"] == body["tool_calls"][0]["data"]["effective_profile"]
        assert body["effective_profile"]["mobility"] == "wheelchair"
        # A wording failure degrades to fallback without touching metadata.
        monkeypatch.setattr(OpenAiCompatJsonClient, "generate_json",
                            lambda self, **kwargs: (_ for _ in ()).throw(ValueError("invalid")))
        service = NoLLMQueryService(build_default_registry(
            build_engine_handlers(runtime.engine, build_diversion_plan)))
        degraded = asyncio.run(service.query(user_input="再算一次", origin="TAW", destination="ADM",
                                             depart_at=AT, profile={"mobility": "wheelchair"}))
        assert degraded["fallback"] is True
        assert degraded["graph_snapshot"] == body["graph_snapshot"]
        assert degraded["effective_profile"] == body["effective_profile"]


HASH = password_hash("p4-source-fixture")


@pytest.fixture
def source_store(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setenv("ADMIN_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv("ADMIN_ENCRYPTION_KEY", "p4-source-fixture-key-" * 2)
    events = EventStore(tmp_path / "events.sqlite3")
    events.initialize()
    signals = SignalStore(events.db_path)
    signals.initialize()
    store = AdminStore(tmp_path / "admin.sqlite3", events.db_path)
    store.initialize()
    clock = [2_000_000_000.0]
    monkeypatch.setattr(collect.time, "time", lambda: clock[0])
    return store, events, signals, clock, monkeypatch


def configure(store, source, **changes):
    value = store.settings()
    revision = value["revision"]
    value["sources"][source].update(changes)
    value["revision"] += 1
    store.save_settings(value, revision, "operator")


def hko_poller():
    client = SimpleNamespace(
        fetch_warnsum=lambda: {"WFIRE": {"code": "WFIRE", "name": "Fire Danger Warning",
                                         "type": "Red", "issueTime": "2026-10-01T08:00:00+08:00"}},
        fetch_warning_info=lambda: {"details": []},
        endpoint_url=lambda _: "https://data.weather.gov.hk/weatherAPI/opendata/weather.php")
    return HkoWarningPoller(client)


def mtr_poller(failing=()):
    from backend.app.services.ingest.mtr_eta import CORRIDOR_STATIONS as stations

    class Client:
        def fetch_station(self, code):
            if code in failing:
                raise MtrEtaFetchError(f"station {code} unavailable")
            return {"status": 1, "isdelay": "Y",
                    "data": {f"EAL-{code}": {"UP": [{"valid": "Y", "ttnt": "12"}]}}}

    assert stations  # corridor fixture is loaded, not silently empty
    return MtrEtaAnomalyPoller(Client(), MtrDetectionConfig())


def status_client(store):
    app = FastAPI()
    app.state.admin_store = store
    app.state.source_scheduler = None
    app.include_router(sources_router)
    return TestClient(app)


def source_status(store, name="hko"):
    response = status_client(store).get("/api/sources/status")
    assert response.status_code == 200
    return response.json()["sources"][name]


class TestSourceLastSuccessAt:
    def test_success_persists_then_survives_failure_disable_offline_and_restart(self, source_store):
        store, events, signals, clock, monkeypatch = source_store
        configure(store, "hko", enabled=True)
        monkeypatch.setattr(collect, "make_poller", lambda source, cfg: hko_poller())

        first = collect.source_operation(store, "hko", "operator")
        assert first["status"] == "success"
        state = store.source_state("hko")
        assert state["last_success_at"] == first["at"]
        when = datetime.fromisoformat(state["last_success_at"].replace("Z", "+00:00"))
        assert when.tzinfo is not None  # ISO 8601 with timezone
        body = source_status(store)
        assert body["last_success_at"] == first["at"]
        assert body["last_result"]["status"] == "success"
        assert body["enabled"] is True and body["stale"] is False
        assert events.list_events() == []  # collection stays Signal-only

        clock[0] += 90
        def broken():
            raise RuntimeError("private-provider-error")
        monkeypatch.setattr(collect, "make_poller",
                            lambda *args: SimpleNamespace(poll_once=broken,
                                                          restore_state=lambda state: None,
                                                          export_state=dict))
        with pytest.raises(RuntimeError):
            collect.source_operation(store, "hko", "scheduled-collector")
        body = source_status(store)
        assert body["status"] == "failed"
        assert body["last_success_at"] == first["at"]

        configure(store, "hko", enabled=False)
        body = source_status(store)
        assert body["status"] == "disabled"
        assert body["last_success_at"] == first["at"]

        monkeypatch.setenv("OFFLINE_MODE", "true")
        body = source_status(store)
        assert body["status"] == "offline"
        assert body["last_success_at"] == first["at"]
        monkeypatch.setenv("OFFLINE_MODE", "false")

        reopened = AdminStore(store.path, store.event_db)
        reopened.initialize()
        assert reopened.source_state("hko")["last_success_at"] == first["at"]
        assert source_status(reopened)["last_success_at"] == first["at"]

    def test_partial_failure_keeps_previous_success_without_updating_it(self, source_store):
        store, _, _, clock, monkeypatch = source_store
        configure(store, "mtr", enabled=True)
        monkeypatch.setattr(collect, "make_poller", lambda source, cfg: mtr_poller())
        first = collect.source_operation(store, "mtr", "operator")
        assert first["status"] == "success"
        first_attempt = store.source_state("mtr")["last_attempt"]
        assert source_status(store, "mtr")["last_success_at"] == first["at"]

        clock[0] += 60
        monkeypatch.setattr(collect, "make_poller", lambda source, cfg: mtr_poller(failing={"ADM"}))
        second = collect.source_operation(store, "mtr", "scheduled-collector")
        assert second["status"] == "partial_failure"
        assert store.source_state("mtr")["last_attempt"] > first_attempt  # a later attempt really ran
        body = source_status(store, "mtr")
        assert body["status"] == "partial_failure"
        assert body["last_success_at"] == first["at"]  # partial is not a success

    def test_connection_test_is_never_a_successful_collection(self, source_store):
        store, _, _, clock, monkeypatch = source_store
        configure(store, "hko", enabled=True)
        monkeypatch.setattr(collect, "make_poller", lambda source, cfg: hko_poller())
        result = collect.source_operation(store, "hko", "operator", test=True)
        assert result["status"] == "success"
        assert store.source_state("hko") == {}  # nothing persisted for a connection test
        body = source_status(store)
        assert body["last_success_at"] is None
        assert body["status"] == "waiting"

    def test_backfill_only_from_a_reliable_stored_success(self, source_store):
        store, _, _, _, _ = source_store
        def seed_state(value):
            with store.connect() as db:
                db.execute("INSERT OR REPLACE INTO source_state VALUES(?,?)",
                           ("hko", json.dumps(value)))
        seed_state({"last_result": {"status": "success", "at": "2026-09-01T00:00:00Z"}})
        assert source_status(store)["last_success_at"] == "2026-09-01T00:00:00Z"
        seed_state({"last_result": {"status": "failed", "at": "2026-09-02T00:00:00Z"}})
        assert source_status(store)["last_success_at"] is None
        seed_state({"last_result": {"status": "success"}})  # success without a time is not reliable
        assert source_status(store)["last_success_at"] is None
        seed_state({"last_success_at": "2026-09-03T00:00:00Z",
                    "last_result": {"status": "failed", "at": "2026-09-04T00:00:00Z"}})
        assert source_status(store)["last_success_at"] == "2026-09-03T00:00:00Z"
        seed_state({})  # no history at all
        assert source_status(store)["last_success_at"] is None

    def test_unconfigured_status_reports_null_last_success_at_without_secrets(self):
        body = public_source_status(None)
        assert body["configured"] is False
        for source in body["sources"].values():
            assert source["last_success_at"] is None
        assert "api_key" not in json.dumps(body)
