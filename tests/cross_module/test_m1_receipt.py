"""M1 delta coverage: current combined app after C receives a simulated event.

B publication/delivery and A rendering are dependencies, not mocked successes.
Existing test_module_chain owns in-memory Route->Sim recomputation coverage.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from backend.app.ai.llm_client import LLMClient
from scripts.integration.checks import closed_crossings
from scripts.integration.contracts import validate_response
from scripts.integration.m1_acceptance import integrated_client, published_event
from scripts.integration.module_bridge import ModuleBridge


class M1ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.bridge = ModuleBridge()
        self.request = {key: self.bridge.config[key] for key in ('origin', 'destination', 'depart_at')}
        self.event = published_event(self.bridge.engine, self.bridge.query(), self.request['depart_at'])

    @staticmethod
    def ids(routes):
        return {route['route_id'] for route in routes}

    def query(self, client, **overrides):
        response = client.post('/api/routes/query', json={**self.request, **overrides})
        self.assertEqual(response.status_code, 200, response.text)
        routes = response.json()
        self.assertTrue(routes, 'A closure test must retain a usable alternative')
        self.assertEqual(validate_response('POST', '/api/routes/query', 200, routes), [])
        self.assertTrue(all(route['provenance'] == 'simulated' for route in routes))
        return routes

    def test_cached_public_routes_follow_snapshot_close_expire_and_stale_delivery(self):
        with integrated_client(self.bridge) as client:
            before = self.query(client)
            self.assertTrue(any(closed_crossings(r, self.bridge.network, [self.event]) for r in before),
                            'Closure must affect a route actually present before publication')
            self.query(client)
            self.assertGreater(self.bridge.engine.cache.hits, 0)
            old = client.get('/api/graph/snapshot').json()
            self.bridge.engine.snapshots.update_event(self.event)
            new = client.get('/api/graph/snapshot').json()
            self.assertNotEqual(old['snapshot_id'], new['snapshot_id'])
            self.assertEqual(client.get('/api/meta').json()['graph_snapshot'], new['snapshot_id'])
            segment = self.event['affected_segments'][0]
            self.assertTrue(any(edge['from_node'] == segment['from_node'] and
                                edge['to_node'] == segment['to_node'] and edge['capacity_factor'] == 0 and
                                self.event['event_id'] in edge['event_ids'] for edge in new['affected_edges']))
            after = self.query(client, event_ids=[])
            self.assertNotEqual(self.ids(before), self.ids(after))
            self.assertTrue(all(not closed_crossings(r, self.bridge.network, [self.event]) for r in after))
            expired = {**deepcopy(self.event), 'status': 'expired', 'version': 3}
            restored = self.bridge.engine.snapshots.update_event(expired)
            self.assertEqual(self.ids(before), self.ids(self.query(client)))
            self.bridge.engine.snapshots.update_event(self.event)  # older published delivery
            self.assertEqual(restored.snapshot_id, client.get('/api/graph/snapshot').json()['snapshot_id'])
            self.assertEqual(self.ids(before), self.ids(self.query(client)))

    def test_pending_and_rejected_receipts_do_not_close_http_routes(self):
        with integrated_client(self.bridge) as client:
            before = self.query(client)
            for version, status in enumerate(('pending_review', 'rejected'), start=1):
                self.bridge.engine.snapshots.update_event({**deepcopy(self.event), 'status': status, 'version': version})
                self.assertEqual(client.get('/api/graph/snapshot').json()['affected_edges'], [])
                self.assertEqual(self.ids(before), self.ids(self.query(client)))

    def test_invalid_receipt_preserves_published_snapshot_and_http_response(self):
        with integrated_client(self.bridge) as client:
            self.bridge.engine.snapshots.update_event(self.event)
            expected = self.query(client)
            snapshot = client.get('/api/graph/snapshot').json()
            invalid = deepcopy(self.event)
            invalid['version'] += 1
            invalid['affected_segments'][0]['capacity_factor'] = -1
            with self.assertRaises(ValueError):
                self.bridge.engine.snapshots.update_event(invalid)
            self.assertEqual(snapshot, client.get('/api/graph/snapshot').json())
            self.assertEqual(expected, self.query(client))

    def test_llm_disabled_chat_uses_the_same_refreshed_routes_as_http(self):
        with patch.object(LLMClient, '_post', side_effect=AssertionError('LLM transport forbidden')) as transport:
            with integrated_client(self.bridge) as client:
                self.bridge.engine.snapshots.update_event(self.event)
                expected = self.query(client)
                health = client.get('/api/health').json()
                self.assertFalse(health['llm']['enabled'])
                response = client.post('/api/ai/chat', json={**self.request, 'message': 'Find simulated alternatives'})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertTrue(body['fallback'])
                self.assertIsInstance(body['message'], str)
                self.assertEqual(body['routes'], expected)
                self.assertTrue(body['tool_calls'])
                self.assertTrue(all(call['ok'] for call in body['tool_calls']))
                self.assertTrue(all(not closed_crossings(r, self.bridge.network, [self.event]) for r in body['routes']))
            transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
