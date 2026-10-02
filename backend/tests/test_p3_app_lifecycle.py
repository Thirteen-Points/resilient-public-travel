"""Verify main owns approved-window reconciliation and collector cleanup."""
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import create_app, runtime
from backend.app.services.review_state import EventReviewService
from backend.tests.test_runtime_replanning import engine, weather_event


def test_main_reconciles_future_approved_weather_and_stops_workers(tmp_path, monkeypatch):
    monkeypatch.setenv('OFFLINE_MODE', 'true')
    for name in ('ADMIN_USERNAME', 'ADMIN_PASSWORD_HASH', 'ADMIN_ENCRYPTION_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runtime, 'engine', engine())
    now = datetime.now(timezone.utc)
    starts = now + timedelta(seconds=1.2)
    query = {'origin': 'A', 'destination': 'B', 'depart_at': now + timedelta(minutes=10),
             'modes': ['BUS'], 'limit': 1}
    app = create_app(db_path=tmp_path/'events.sqlite3', review_token='lifecycle-simulated')
    with TestClient(app) as client:
        coordinator = app.state.replanning
        coordinator.register_simulation('exercise', query, 1000)
        event = weather_event()
        event.update(created_at=now.isoformat(), updated_at=now.isoformat())
        event['window']['start'] = starts.isoformat()
        app.state.event_store.create_event(event)
        EventReviewService(app.state.event_store).approve('wx', actor='simulated-reviewer')
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            body = client.get('/api/replanning/status').json()
            if body.get('latest', {}).get('trigger') == 'weather_changed':
                break
            time.sleep(.05)
        assert body['latest']['trigger'] == 'weather_changed'
        assert body['latest']['within_five_second_budget']
        assert coordinator.latest['result']['diversion']['exercise']['demand'] == 1000
        assert client.get('/api/sources/status').json()['offline'] is True
        assert 'routes' not in body['latest']
    assert app.state.source_scheduler._tasks == []
