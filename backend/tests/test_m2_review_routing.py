"""Real combined-app regression: approved facts, edits, times and routes."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app.main import create_app, runtime
from backend.tests import test_event_api_flow as flow


class M2ReviewRoutingTests(unittest.TestCase):
    report = flow.EventApiFlowTests.report
    initial_card = flow.EventApiFlowTests.initial_card

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.app = create_app(db_path=Path(directory.name) / 'm2.sqlite3', review_token='test-only')
        context = TestClient(self.app)
        self.client = context.__enter__()
        self.addCleanup(lambda: context.__exit__(None, None, None))
        self.headers = {'X-Review-Token': 'test-only'}
        first = self.report('scripted-source-1')
        self.client.post('/api/events', json=self.initial_card(first), headers=self.headers).raise_for_status()
        for author in ['scripted-source-2', 'scripted-source-3']:
            signal = self.report(author)
            self.client.post('/api/events/ingest', json={'signal_id': signal}, headers=self.headers).raise_for_status()
        self.path = '/api/events/evt-api-flow-001/review'
        self.at = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()

    def act(self, action, edits=None):
        body = {'action': action, 'actor': 'test-reviewer'}
        if edits is not None:
            body['edits'] = edits
        response = self.client.post(self.path, json=body, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def impacts(self):
        return self.client.get('/api/graph/snapshot', params={'at': self.at}).json()['affected_edges']

    def published(self):
        return self.client.get('/api/events/published', params={'at': self.at}).json()

    def test_pending_then_approved_then_edited_then_reapproved_and_withdrawn(self):
        self.assertEqual(self.published(), [])
        self.assertEqual(self.impacts(), [])
        approved = self.act('approve')
        self.assertEqual(approved['confidence'], .60)
        self.assertTrue(self.impacts())
        before = self.published()[0]
        old_impacts = self.impacts()
        self.act('edit', {'title': 'Unapproved title', 'affected_segments': [
            {'from_node': 'TAW', 'to_node': 'KOT', 'impact': 'closed', 'capacity_factor': 0}
        ]})
        self.assertEqual(self.published()[0], before)
        self.assertEqual(self.impacts(), old_impacts)
        # Durable storage survives a new store instance, including a pending edit.
        from backend.app.services.event_store import EventStore
        restored = EventStore(self.app.state.event_store.db_path)
        restored.initialize()
        self.assertEqual(restored.approved_events()[0].title, before['title'])
        self.act('approve')
        self.assertEqual(self.published()[0]['title'], 'Unapproved title')
        self.assertNotEqual(self.impacts(), old_impacts)
        self.act('expire')
        self.assertEqual(self.published(), [])
        self.assertEqual(self.impacts(), [])

    def test_reject_updated_withdraws_last_approved_revision(self):
        self.act('approve')
        self.act('edit', {'title': 'Needs review'})
        self.act('reject')
        self.assertEqual(self.published(), [])
        self.assertEqual(self.impacts(), [])

    def test_edit_preserves_and_can_clear_nullable_window_end(self):
        approved = self.act('approve')
        start = approved['window']['start']
        end = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        self.act('edit', {'window': {'start': start, 'end': end, 'end_confidence': 'test'}})
        edited = self.act('edit', {'window': {'start': start, 'end': None, 'end_confidence': 'unknown'}})
        self.assertIsNone(edited['window']['end'])
        invalid = self.client.post(self.path, json={
            'action': 'edit', 'actor': 'test-reviewer', 'edits': {
                'window': {'start': start, 'end': '2000-01-01T00:00:00+08:00', 'end_confidence': 'test'}
            }
        }, headers=self.headers)
        self.assertEqual(invalid.status_code, 422)

    def test_public_window_and_route_snapshot_agree_without_reviewer_auth(self):
        approved = self.act('approve')
        instant = datetime.now(timezone.utc)
        # Keep this publication-window test inside the frozen rail service
        # hours, including when the suite runs after midnight in Hong Kong.
        operating_time = (instant + timedelta(days=1)).replace(hour=0, minute=20)
        future = operating_time.isoformat()
        later = (operating_time + timedelta(hours=1)).isoformat()
        self.act('edit', {'window': {'start': future, 'end': later, 'end_confidence': 'test'}})
        self.act('approve')
        for at, expected in [(self.at, False), (future, True), (later, False)]:
            public = self.client.get('/api/events/published', params={'at': at})
            graph = self.client.get('/api/graph/snapshot', params={'at': at})
            self.assertEqual(public.status_code, 200)
            self.assertEqual(bool(public.json()), expected)
            self.assertEqual(bool(graph.json()['affected_edges']), expected)
        self.assertEqual(self.client.get('/api/events').status_code, 401)
        self.assertEqual(self.client.get('/api/stream/events?token=test-only').status_code, 401)
        self.assertEqual(self.client.get('/api/events/published?at=2026-09-30T08:00:00').status_code, 422)
        routes = self.client.post('/api/routes/query', json={
            'origin': 'TAW', 'destination': 'ADM', 'depart_at': future, 'profile': {'preset': 'fastest'},
        })
        self.assertEqual(routes.status_code, 200)
        self.assertTrue(routes.json())
        for route in routes.json():
            self.assertFalse(any(leg.get('line') == 'ERL' and leg['from'] == 'HUH' and leg['to'] == 'EXC' for leg in route['legs']))


if __name__ == '__main__':
    unittest.main()
