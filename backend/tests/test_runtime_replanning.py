"""Exercise approved weather, route snapshots, calendars and runtime trust together."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.engine.service import RouteEngine
from backend.app.engine.load_provider import FixtureLoadProvider
from backend.app.graph.adapter import MappingDataAdapter, SeedDataAdapter
from backend.app.graph.build import service_key
from backend.app.graph.snapshot import SnapshotStore
from backend.app.sim.runtime_replanning import RuntimeReplanningCoordinator, build_router
from backend.app.services.event_store import EventStore
from backend.app.services.review_state import EventReviewService

AT = datetime(2026, 10, 2, 2, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def engine():
    network = {"meta": {"provenance": "simulated"}, "nodes": [
        {"id": "A", "lat": 22.3, "lng": 114.1, "provenance": "simulated"},
        {"id": "B", "lat": 22.4, "lng": 114.2, "provenance": "simulated"}],
        "lines": [{"id": mode, "mode": mode, "stops": ["A", "B"], "seg_time_s": [600],
                   "capacity_per_vehicle": 100, "headway_s": 300, "fare_hkd": 3,
                   "provenance": "simulated"} for mode in ("BUS", "FERRY", "MTR")],
        "walk_links": [{"from": "A", "to": "B", "walk_m": 1500, "provenance": "simulated"}]}
    weather = json.loads((ROOT / "data/weather_impact.json").read_text(encoding="utf-8"))
    return RouteEngine.from_adapter(MappingDataAdapter(network, baseline_fare=3, weather_policy=weather),
                                   load_provider=FixtureLoadProvider({"users_on_route": 0, "load_factor": 0, "board_refusal_prob": 0}))


def weather_event(code="WRAINR"):
    return {"event_id": "wx", "version": 1, "status": "pending_review",
            "created_at": AT.isoformat(), "updated_at": AT.isoformat(), "published_at": None,
            "expires_at": None, "event_type": "weather", "title": f"天气警告生效 ({code})",
            "summary": f"天文台警告 {code}", "mode": "BUS", "line": "BUS", "direction": "both",
            "affected_segments": [], "window": {"start": AT.isoformat(), "end": None, "end_confidence": "unknown"},
            "severity": 3, "confidence": .55, "confidence_factors": [], "signals": ["sig_wx"],
            "reviewed_by": None, "audit_log": [], "provenance": "simulated"}


def query(mode="BUS"):
    return {"origin": "A", "destination": "B", "depart_at": AT + timedelta(minutes=10),
            "modes": [mode], "limit": 1}


def test_default_seed_consumes_verified_holidays_and_weekday_peak_exception():
    data = SeedDataAdapter().load()
    assert "2026-10-01" in data.holidays
    assert service_key(datetime.fromisoformat("2026-10-01T08:00:00+08:00"), frozenset(data.holidays)) == "sunday_ph"
    runtime = RouteEngine.from_seed()
    edge = next(edge for edge in runtime.snapshots.network.edges if edge.line == "BUS_982X")
    assert runtime.snapshots.network.boarding(edge, datetime.fromisoformat("2026-10-01T08:00:00+08:00")) is None
    assert runtime.snapshots.network.boarding(edge, datetime.fromisoformat("2026-10-02T10:00:00+08:00")) is None
    rail = next(edge for edge in runtime.snapshots.network.edges if edge.line == "ERL")
    holiday = runtime.snapshots.network.boarding(rail, datetime.fromisoformat("2026-10-01T08:00:00+08:00"))
    weekday = runtime.snapshots.network.boarding(rail, datetime.fromisoformat("2026-10-02T08:00:00+08:00"))
    assert holiday[1] != weekday[1]


def test_weather_requires_review_keeps_last_approval_and_recomputes_after_withdrawal():
    route_engine = engine()
    with tempfile.TemporaryDirectory() as directory:
        store = EventStore(Path(directory) / "events.sqlite3")
        store.initialize()
        review = EventReviewService(store)
        coordinator = RuntimeReplanningCoordinator(route_engine, store.approved_events)
        coordinator.register_simulation("watched", query(), 1000)
        baseline = route_engine.query(**query())[0]["total"]["time_s"]
        store.create_event(weather_event())
        assert not coordinator.sync_approved_events(observed_at=AT)["should_replan"]
        assert route_engine.query(**query())[0]["total"]["time_s"] == baseline
        review.approve("wx", actor="reviewer", at=AT + timedelta(minutes=1))
        result = coordinator.sync_approved_events(observed_at=AT + timedelta(minutes=2))
        assert result["trigger"] == "weather_changed"
        assert result["result"]["routes"]["watched"]["routes"][0]["total"]["time_s"] > baseline
        assert result["elapsed_ms"] >= 0
        assert result["within_five_second_budget"]
        assert result["result"]["diversion"]["watched"]["demand"] == 1000
        assert result["result"]["diversion"]["watched"]["graph_snapshot"] == result["result"]["graph_snapshot"]
        reviewed_snapshot = route_engine.snapshots.current.snapshot_id
        review.edit("wx", {"title": "天气警告取消", "summary": "WRAINR 取消"}, actor="reviewer", at=AT + timedelta(minutes=3))
        assert not coordinator.sync_approved_events(observed_at=AT + timedelta(minutes=4))["should_replan"]
        assert route_engine.snapshots.current.snapshot_id == reviewed_snapshot
        review.expire("wx", actor="reviewer", at=AT + timedelta(minutes=5))
        removed = coordinator.sync_approved_events(observed_at=AT + timedelta(minutes=6))
        assert removed["should_replan"]
        assert route_engine.query(**query())[0]["total"]["time_s"] == baseline


def test_walk_speed_and_ferry_suspension_are_explicit_simulated_policy():
    route_engine = engine()
    event = weather_event("WRAINR")
    event.update(status="published", confidence=.9, reviewed_by="reviewer", published_at=AT.isoformat())
    baseline_walk = route_engine.query(**query("WALK"))[0]["total"]["time_s"]
    route_engine.snapshots.replace_events([event])
    walk = route_engine.query(**query("WALK"))[0]
    assert walk["total"]["time_s"] == pytest.approx(baseline_walk * 1.5 / .75)
    assert any("模拟系数" in warning for warning in walk["warnings"])
    event.update(title="天气警告生效 T8", summary="T8", version=2)
    route_engine.snapshots.replace_events([event])
    assert route_engine.query(**query("FERRY")) == []
    mtr = route_engine.query(**query("MTR"))[0]
    assert mtr["legs"][0]["in_vehicle_s"] == 720


def test_snapshot_restore_keeps_weather_policy_and_expired_event_does_not_apply():
    route_engine = engine()
    event = weather_event("WRAINB")
    event.update(status="published", confidence=.9, reviewed_by="reviewer", published_at=AT.isoformat(),
                 expires_at=(AT + timedelta(minutes=1)).isoformat())
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "snapshot.json"
        store = SnapshotStore(route_engine.snapshots.network, path=path,
                              weather_policy=route_engine.snapshots.weather_policy)
        store.replace_events([event])
        restored = SnapshotStore.restore(path)
        assert restored.current.snapshot_id == store.current.snapshot_id
        assert restored.current.weather_effect("BUS", AT)[0] == 1.5
        assert restored.current.weather_effect("BUS", AT + timedelta(minutes=2))[0] == 1


def test_unchanged_reconciliation_reuses_snapshot_but_replans_at_expiry(monkeypatch):
    route_engine = engine()
    event = weather_event("WRAINR")
    event.update(status="published", confidence=.9, reviewed_by="reviewer",
                 published_at=AT.isoformat(), expires_at=(AT + timedelta(minutes=2)).isoformat())
    coordinator = RuntimeReplanningCoordinator(route_engine, lambda: [event])
    coordinator.register_query("watched", query())
    coordinator.sync_approved_events(observed_at=AT)
    pinned = route_engine.snapshots.current
    rainy_time = route_engine.query("A", "B", AT + timedelta(seconds=30), modes=["BUS"])[0]["total"]["time_s"]

    def unexpected_rebuild(_):
        raise AssertionError("Unchanged events must not rebuild the network snapshot")

    monkeypatch.setattr(route_engine.snapshots, "_make", unexpected_rebuild)
    for second in range(1, 5):
        assert not coordinator.sync_approved_events(observed_at=AT + timedelta(seconds=second))["should_replan"]
        assert route_engine.snapshots.current is pinned
    expired = coordinator.sync_approved_events(observed_at=AT + timedelta(minutes=3))
    assert expired["should_replan"]
    assert route_engine.snapshots.current is pinned
    assert route_engine.query("A", "B", AT + timedelta(minutes=3), modes=["BUS"])[0]["total"]["time_s"] < rainy_time


def test_empty_snapshot_initial_persistence_and_unchanged_updates(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.json"
    store = SnapshotStore(engine().snapshots.network, path=path)
    store.replace_events([])
    assert path.is_file()
    assert SnapshotStore.restore(path).current.snapshot_id == store.current.snapshot_id
    pinned = store.current

    def unexpected_write(*args, **kwargs):
        raise AssertionError("Unchanged events must not rewrite persisted snapshots")

    monkeypatch.setattr(Path, "write_text", unexpected_write)
    assert store.replace_events([]) is pinned


def test_load_trigger_requires_trusted_continuous_observations_and_recomputes_diversion():
    calls = []
    coordinator = RuntimeReplanningCoordinator(engine(), lambda: [],
        diversion_replanner=lambda decision, routes: calls.append(decision.trigger) or {"scenario": "simulated"})
    with pytest.raises(ValueError):
        coordinator.observe_load("BUS", .96, observed_at=AT, source="manual_simulation", provenance="real")
    for minute in range(6):
        result = coordinator.observe_load("BUS", .96, observed_at=AT + timedelta(minutes=minute),
                                          source="manual_simulation", provenance="simulated", context=query())
        assert result["should_replan"] == (minute == 5)
    assert calls == ["sustained_load"]
    assert result["result"]["routes"]["requested"]["routes"]
    assert result["result"]["diversion"] == {"scenario": "simulated"}
    assert result["observation"]["provenance"] == "simulated"
    assert not coordinator.status()["live_load_provider_installed"]
    with pytest.raises(ValueError):
        coordinator.observe_load("BUS", .96, observed_at=AT, source="manual_simulation", provenance="simulated")


def test_load_gap_does_not_prove_sustained_load_and_api_requires_auth():
    coordinator = RuntimeReplanningCoordinator(engine(), lambda: [])
    app = FastAPI()
    app.state.review_token = "review-secret"
    app.include_router(build_router(coordinator))
    payload = {"route_id": "BUS", "load_factor": .97, "observed_at": AT.isoformat(),
               "source": "manual_simulation", "provenance": "simulated"}
    with TestClient(app) as client:
        assert client.post("/api/replanning/load-observations", json=payload).status_code == 401
        assert client.get("/api/replanning/status").json()["latest"] is None
        assert client.post("/api/replanning/load-observations", json=payload,
                           headers={"x-review-token": "review-secret"}).status_code == 200
        payload["observed_at"] = (AT + timedelta(minutes=5)).isoformat()
        result = client.post("/api/replanning/load-observations", json=payload,
                             headers={"x-review-token": "review-secret"})
        assert result.status_code == 200
        assert not result.json()["should_replan"]


def test_weather_changes_registered_diversion_to_explicit_unmet_demand():
    route_engine = engine()
    rows = []
    coordinator = RuntimeReplanningCoordinator(route_engine, lambda: rows)
    coordinator.register_simulation("bus", query(), 1000)
    coordinator.sync_approved_events(observed_at=AT)
    event = weather_event("WRAINR")
    event.update(status="published", confidence=.9, reviewed_by="reviewer", published_at=AT.isoformat())
    rows.append(event)
    rainy = coordinator.sync_approved_events(observed_at=AT)
    assert rainy["result"]["diversion"]["bus"]["unstoppable_demand"] == 0
    event.update(title="天气警告 T8", summary="T8", version=2)
    storm = coordinator.sync_approved_events(observed_at=AT + timedelta(minutes=1))
    assert storm["result"]["routes"]["bus"]["routes"] == []
    assert storm["result"]["diversion"]["bus"]["unstoppable_demand"] == 1000
    status = coordinator.status()
    assert "routes" not in str(status)
    assert "route_parameters" not in str(status)


def test_manual_load_replans_with_explicit_demand_without_claiming_live_load():
    coordinator = RuntimeReplanningCoordinator(engine(), lambda: [])
    for minute in range(6):
        result = coordinator.observe_load("BUS", .97, observed_at=AT + timedelta(minutes=minute),
                                          source="manual_simulation", provenance="simulated", context=query(), demand=1200)
    plan = result["result"]["diversion"]["requested"]
    assert plan["demand"] == 1200
    assert plan["unstoppable_demand"] == 180
    assert "do not alter route weights" in plan["note"]
    assert not coordinator.status()["live_load_provider_installed"]
