"""Real stores/pollers with mocked official responses; no external requests."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.admin import collect
from backend.app.admin.scheduler import SourceScheduler, public_source_status, router
from backend.app.admin.store import AdminStore, password_hash
from backend.app.services.event_store import EventStore
from backend.app.services.ingest.hko import HkoWarningPoller
from backend.app.services.ingest.mtr_eta import MtrDetectionConfig, MtrEtaAnomalyPoller
from backend.app.services.signal_store import SignalStore

HASH = password_hash("source-scheduler-fixture")


@pytest.fixture
def source_store(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setenv("ADMIN_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv("ADMIN_ENCRYPTION_KEY", "scheduler-fixture-key-" * 3)
    events = EventStore(tmp_path / "events.sqlite3")
    events.initialize()
    signals = SignalStore(events.db_path)
    signals.initialize()
    store = AdminStore(tmp_path / "admin.sqlite3", events.db_path)
    store.initialize()
    return store, events, signals


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


async def until(predicate):
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(.01)
    assert predicate(), "Scheduler fixture did not reach expected state"


def test_scheduled_hko_persists_dedup_state_across_restart_without_publication(source_store, monkeypatch):
    store, events, signals = source_store
    clock = [2_000_000_000.0]
    monkeypatch.setattr(collect.time, "time", lambda: clock[0])
    monkeypatch.setattr(collect, "make_poller", lambda source, cfg: hko_poller())
    configure(store, "hko", enabled=True)

    async def scenario():
        first = SourceScheduler(store, clock=lambda: clock[0], poll_seconds=.01, initial_delay=False)
        await first.start()
        try:
            await until(lambda: len(signals.list_signals()) == 1)
        finally:
            await first.stop()
        clock[0] += 90
        second = SourceScheduler(store, clock=lambda: clock[0], poll_seconds=.01, initial_delay=False)
        await second.start()
        try:
            await until(lambda: store.source_state("hko").get("last_attempt") == clock[0])
        finally:
            await second.stop()
        assert len(signals.list_signals()) == 1
        assert events.list_events() == []
        assert store.source_state("hko")["last_result"]["added"] == 0
    asyncio.run(scenario())


def test_scheduled_mtr_retains_consecutive_observations(source_store, monkeypatch):
    store, events, signals = source_store
    clock = [2_000_000_000.0]
    monkeypatch.setattr(collect.time, "time", lambda: clock[0])
    client = SimpleNamespace(fetch_station=lambda code: {
        "status": 1, "isdelay": "Y", "data": {f"EAL-{code}": {"UP": [{"valid": "Y", "ttnt": "12"}]}}})
    monkeypatch.setattr(collect, "make_poller", lambda source, cfg: MtrEtaAnomalyPoller(client, MtrDetectionConfig()))
    configure(store, "mtr", enabled=True)

    async def scenario():
        scheduler = SourceScheduler(store, clock=lambda: clock[0], poll_seconds=.01, initial_delay=False)
        await scheduler.start()
        try:
            await until(lambda: store.source_state("mtr").get("last_result", {}).get("details", {}).get("consecutive_polls") == 1)
            assert len(signals.list_signals()) == 0
            clock[0] += 60
            scheduler.notify()
            await until(lambda: len(signals.list_signals()) == 1)
        finally:
            await scheduler.stop()
        assert events.list_events() == []
    asyncio.run(scenario())


def test_committed_observation_cannot_shift_cadence_before_worker_returns(source_store, monkeypatch):
    """Force a clock advance between SQLite commit and scheduler's finally."""
    store, _, signals = source_store
    clock = [2_000_000_000.0]
    monkeypatch.setattr(collect.time, "time", lambda: clock[0])
    client = SimpleNamespace(fetch_station=lambda code: {
        "status": 1, "isdelay": "Y", "data": {f"EAL-{code}": {"UP": [{"valid": "Y", "ttnt": "12"}]}}})
    monkeypatch.setattr(collect, "make_poller", lambda source, cfg: MtrEtaAnomalyPoller(client, MtrDetectionConfig()))
    configure(store, "mtr", enabled=True)
    committed, return_to_scheduler = threading.Event(), threading.Event()
    calls = []

    def operation(*args, **kwargs):
        result = collect.source_operation(*args, **kwargs)
        calls.append(result)
        if len(calls) == 1:
            committed.set()
            assert return_to_scheduler.wait(3), "Fixture did not release committed worker"
        return result

    async def scenario():
        scheduler = SourceScheduler(store, operation=operation, clock=lambda: clock[0],
                                    poll_seconds=.01, initial_delay=False)
        await scheduler.start()
        try:
            await until(committed.is_set)
            assert scheduler._running["mtr"]
            assert store.source_state("mtr")["next_attempt"] == clock[0] + 60
            clock[0] += 60
            return_to_scheduler.set()
            scheduler.notify()
            await until(lambda: len(calls) == 2)
            assert len(signals.list_signals()) == 1
            assert len(calls) == 2
        finally:
            return_to_scheduler.set()
            await scheduler.stop()
    asyncio.run(scenario())


def test_configuration_notifications_preserve_first_interval_and_cadence(source_store, monkeypatch):
    store, _, signals = source_store
    clock = [2_000_000_000.0]
    monkeypatch.setattr(collect.time, "time", lambda: clock[0])
    monkeypatch.setattr(collect, "make_poller", lambda source, cfg: hko_poller())
    configure(store, "hko", enabled=True)

    async def scenario():
        scheduler = SourceScheduler(store, clock=lambda: clock[0], poll_seconds=.01)
        await scheduler.start()
        try:
            await until(lambda: "hko" in scheduler._active_since)
            scheduler.notify()
            await asyncio.sleep(.03)
            assert signals.list_signals() == []
            clock[0] += 90
            scheduler.notify()
            await until(lambda: len(signals.list_signals()) == 1)
            recorded = store.source_state("hko")["last_attempt"]
            configure(store, "hko", poll_interval_seconds=60)
            clock[0] += 10
            scheduler.notify()
            await asyncio.sleep(.03)
            assert store.source_state("hko")["last_attempt"] == recorded
        finally:
            await scheduler.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("test", [False, True])
def test_offline_blocks_manual_source_collection_and_connection_tests(source_store, monkeypatch, test):
    store, _, _ = source_store
    configure(store, "hko", enabled=True)
    monkeypatch.setenv("OFFLINE_MODE", "true")
    monkeypatch.setattr(collect, "make_poller", lambda *args: pytest.fail("Offline touched an official client"))
    with pytest.raises(HTTPException) as blocked:
        collect.source_operation(store, "hko", "operator", test=test)
    assert blocked.value.status_code == 409


@pytest.mark.parametrize("stop_reason", ["disable", "offline", "shutdown"])
def test_inflight_thread_drains_and_stop_conditions_discard_signals(source_store, monkeypatch, stop_reason):
    store, events, signals = source_store
    configure(store, "hko", enabled=True)
    entered, release = threading.Event(), threading.Event()
    original = hko_poller()
    poll_once = original.poll_once
    def blocking_poll():
        entered.set()
        assert release.wait(3), "Test did not release in-flight mock response"
        return poll_once()
    original.poll_once = blocking_poll
    monkeypatch.setattr(collect, "make_poller", lambda *args: original)

    async def scenario():
        scheduler = SourceScheduler(store, poll_seconds=.01, initial_delay=False)
        await scheduler.start()
        stop = None
        try:
            await until(entered.is_set)
            if stop_reason == "disable":
                configure(store, "hko", enabled=False)
                scheduler.notify()
            elif stop_reason == "offline":
                monkeypatch.setenv("OFFLINE_MODE", "true")
            stop = asyncio.create_task(scheduler.stop())
            await asyncio.sleep(.03)
            assert not stop.done(), "Shutdown cancelled a still-running collection thread"
        finally:
            release.set()
            if stop is not None:
                await stop
            else:
                await scheduler.stop()
        assert signals.list_signals() == []
        assert events.list_events() == []
    asyncio.run(scenario())


def test_failed_attempt_backoff_and_public_status_never_expose_exception_or_key(source_store, monkeypatch):
    store, _, _ = source_store
    configure(store, "hko", enabled=True)
    def broken():
        raise RuntimeError("private-provider-key-and-raw-request")
    monkeypatch.setattr(collect, "make_poller", lambda *args: SimpleNamespace(poll_once=broken))
    with pytest.raises(RuntimeError):
        collect.source_operation(store, "hko", "scheduled-collector")
    state = store.source_state("hko")
    assert state["consecutive_failures"] == 1
    assert state["next_attempt"] - state["last_attempt"] >= 180
    with pytest.raises(HTTPException) as limited:
        collect.source_operation(store, "hko", "operator")
    assert limited.value.status_code == 429
    app = FastAPI()
    app.state.admin_store = store
    app.include_router(router)
    response = TestClient(app).get("/api/sources/status")
    assert response.status_code == 200
    assert response.json()["sources"]["hko"]["stale"]
    assert "private-provider" not in response.text
    assert "api_key" not in response.text
    assert response.json()["publishes_events"] is False


def test_persistent_lease_prevents_overlapping_manual_and_scheduled_operations(source_store, monkeypatch):
    store, _, signals = source_store
    configure(store, "hko", enabled=True)
    owner = store.acquire("hko")
    try:
        with pytest.raises(HTTPException) as overlap:
            collect.source_operation(store, "hko", "scheduled-collector")
        assert overlap.value.status_code == 409
        assert signals.list_signals() == []
    finally:
        store.release("hko", owner)


def test_unconfigured_public_source_status_is_available_without_admin_credentials():
    value = public_source_status(None)
    assert value["configured"] is False
    assert all(not source["scheduled"] for source in value["sources"].values())


def test_official_response_stream_has_total_deadline_size_and_stop_bounds(monkeypatch):
    import io
    clock = [1.0]
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setattr(collect.time, "monotonic", lambda: clock[0])
    response = collect.BoundedOfficialResponse(io.BytesIO(b"safe-json"), 10, lambda: True)
    assert response.read() == b"safe-json"
    with pytest.raises(OSError, match="size limit"):
        collect.BoundedOfficialResponse(io.BytesIO(b"x" * (2 * 1024 * 1024 + 1)), 10, None).read()
    with pytest.raises(OSError, match="stopped"):
        collect.BoundedOfficialResponse(io.BytesIO(b"safe"), 10, lambda: False).read()
    clock[0] = 11
    with pytest.raises(TimeoutError, match="deadline"):
        collect.BoundedOfficialResponse(io.BytesIO(b"safe"), 10, None).read()
