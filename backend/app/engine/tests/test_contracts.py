"""Consumer contract tests sourced from docs/plan/03-contracts.md, no schema edits.

The repository has no authoritative JSON Schema yet. These independently assert
the documented shape, numeric semantics, HTTP errors and injected data boundary.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import unittest

from fastapi.testclient import TestClient

from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.engine.load_provider import FixtureLoadProvider
from backend.app.graph.adapter import DataUnavailable, MappingDataAdapter, SeedDataAdapter

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / 'backend/app/engine/fixtures'
AT = '2026-09-22T08:20:00+08:00'


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def provider():
    return FixtureLoadProvider(read('seed_policy.json')['load'])


def synthetic_adapter(network=None, events=()):
    return MappingDataAdapter(network or read('network.synthetic.json'),
                              baseline_fare=read('seed_policy.json')['baseline_fare_hkd'], events=events)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = (ROOT / 'docs/plan/03-contracts.md').read_text(encoding='utf-8')
        examples = [json.loads(s) for s in re.findall(r'```json\s*\n(.*?)\n```', spec, re.S)]
        cls.template = next(x for x in examples if 'route_id' in x and 'legs' in x)

    def client(self, adapter=None, load=None):
        engine = RouteEngine.from_adapter(adapter or synthetic_adapter(), load_provider=load or provider())
        return TestClient(create_app(engine), raise_server_exceptions=False), engine

    def assert_route(self, route):
        self.assertEqual(set(route), set(self.template))
        self.assertEqual(set(route['total']), set(self.template['total']))
        self.assertEqual(set(route['load_estimate']), set(self.template['load_estimate']))
        for name in ('route_id', 'label', 'explain', 'provenance'):
            self.assertIsInstance(route[name], str)
        self.assertEqual(route['provenance'], 'simulated')
        for leg in route['legs']:
            self.assertTrue({'mode', 'from', 'to', 'in_vehicle_s', 'walk_m', 'accessible', 'provenance'} <= set(leg))
            self.assertIn(leg['mode'], {'MTR', 'BUS', 'MINIBUS', 'WALK', 'FERRY'})
            self.assertEqual(leg['provenance'], 'simulated')
            self.assertIsInstance(leg['accessible'], bool)
        for name in ('warnings', 'notes'):
            self.assertTrue(all(isinstance(x, str) for x in route[name]))
        self.assertTrue(all(('event_id' in e and isinstance(e['used'], bool)) or
                            ('source' in e and e['freshness_s'] >= 0) for e in route['evidence']))
        for row in route['score_breakdown']:
            self.assertEqual(set(row), set(self.template['score_breakdown'][0]))
            self.assertTrue(0 <= row['normalized'] <= 1)
            self.assertAlmostEqual(row['contribution'], row['normalized'] * row['weight'])
        self.assertAlmostEqual(route['score'], sum(x['contribution'] for x in route['score_breakdown']))
        for value in route['total'].values():
            for number in value if isinstance(value, list) else [value]:
                self.assertIsInstance(number, (int, float))
                self.assertTrue(math.isfinite(number) and number >= 0)
        self.assertAlmostEqual(route['total']['fare_hkd'], sum(x['fare_hkd'] for x in route['legs']))
        self.assertLessEqual(route['total']['time_range_s'][0], route['total']['time_s'])
        self.assertLessEqual(route['total']['time_s'], route['total']['time_range_s'][1])
        self.assertGreaterEqual(route['load_estimate']['capacity_per_hour'], 0)
        json.dumps(route, allow_nan=False)

    def test_synthetic_query_matches_documented_contract(self):
        client, _ = self.client()
        response = client.post('/api/routes/query', json={'origin': 'O', 'destination': 'D', 'depart_at': AT})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 10)
        for route in response.json():
            self.assert_route(route)

    def test_seed_routes_graph_and_sources_are_simulated(self):
        client, engine = self.client(SeedDataAdapter(events_path=ROOT / 'contracts/seed/event.seed.json'))
        response = client.post('/api/routes/query', json={'origin': 'TAW', 'destination': 'ADM', 'depart_at': AT})
        self.assertGreaterEqual(len(response.json()), 8)
        for route in response.json():
            self.assert_route(route)
        graph = client.get('/api/graph/network').json()
        self.assertEqual(graph['meta']['provenance'], 'simulated')
        for row in [*graph['nodes'], *graph['lines'], *graph['walk_links']]:
            self.assertEqual(row['provenance'], 'simulated')
        self.assertTrue(all(e['provenance'] == 'simulated' for e in engine.snapshots.current.events))

    def test_snapshot_and_published_closure_contract(self):
        events = read('events.synthetic.json')['events']
        client, engine = self.client(synthetic_adapter(events=events))
        snapshot = engine.snapshots.current.describe(AT)
        self.assertEqual(set(snapshot), {'snapshot_id', 'affected_edges'})
        self.assertEqual(len(snapshot['affected_edges']), 2)
        result = client.post('/api/routes/query', json={'origin': 'O', 'destination': 'D', 'depart_at': AT}).json()
        self.assertEqual(len(result), 9)
        self.assertFalse(any(l.get('line') == 'SIM_00' for r in result for l in r['legs']))
        self.assertEqual(client.get('/api/graph/snapshot').status_code, 200)

    def test_errors_follow_contract(self):
        client, _ = self.client()
        for payload in [[], {}, {'origin': 'O', 'destination': 'D', 'depart_at': AT, 'extra': 1},
                        {'origin': 'O', 'destination': 'D', 'depart_at': 'invalid'},
                        {'origin': 'O', 'destination': 'D', 'depart_at': AT, 'profile': []},
                        {'origin': 'O', 'destination': 'D', 'depart_at': AT, 'event_ids': 'bad'}]:
            response = client.post('/api/routes/query', json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(set(response.json()['error']), {'code', 'message', 'fallback'})
        for method, path in [('get', '/api/routes/query'), ('get', '/missing')]:
            response = getattr(client, method)(path)
            self.assertTrue(400 <= response.status_code < 500)
            self.assertEqual(set(response.json()['error']), {'code', 'message', 'fallback'})
        self.assertEqual(client.post('/api/routes/query', content='{').status_code, 400)

    def test_no_implicit_live_load_or_transport_defaults(self):
        engine = RouteEngine.from_adapter(synthetic_adapter())
        client = TestClient(create_app(engine), raise_server_exceptions=False)
        response = client.post('/api/routes/query', json={'origin': 'O', 'destination': 'D', 'depart_at': AT})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'DATA_UNAVAILABLE')
        for field in ['capacity_per_vehicle', 'headway_s', 'fare_hkd', 'provenance']:
            data = read('network.synthetic.json')
            del data['lines'][0][field]
            with self.assertRaises(DataUnavailable):
                synthetic_adapter(data).load()

    def test_change_only_adapter_changes_ids_headway_capacity_and_fare(self):
        first = read('network.synthetic.json')
        first['lines'] = first['lines'][:1]
        second = deepcopy(first)
        second['lines'][0].update(id='UNRELATED_TEST_ID', headway_s=333, capacity_per_vehicle=444, fare_hkd=23)
        routes = []
        for network in [first, second]:
            _, engine = self.client(synthetic_adapter(network))
            routes.append(engine.query('O', 'D', AT)[0])
        self.assertEqual(routes[1]['legs'][0]['line'], 'UNRELATED_TEST_ID')
        self.assertEqual(routes[1]['legs'][0]['headway_s'], 333)
        self.assertEqual(routes[1]['total']['fare_hkd'], 23)
        self.assertAlmostEqual(routes[1]['load_estimate']['capacity_per_hour'], 3600 / 333 * 444 * .85)
        self.assertNotEqual(routes[0]['route_id'], routes[1]['route_id'])

    def test_fare_group_is_adapter_policy_not_hardcoded_mode(self):
        network = read('network.synthetic.json')
        network['lines'] = network['lines'][:2]
        network['lines'][0].update(stops=['O', 'V00'], seg_time_s=[90])
        network['lines'][1].update(stops=['V00', 'D'], seg_time_s=[90])
        fares = {line['id']: {'fare_hkd': 7, 'group': 'synthetic_intermodal_ticket',
                             'provenance': 'simulated'} for line in network['lines']}
        adapter = MappingDataAdapter(network, baseline_fare=7, fares=fares)
        _, engine = self.client(adapter)
        self.assertEqual(engine.query('O', 'D', AT)[0]['total']['fare_hkd'], 7)

    def test_load_provider_refreshes_even_on_route_cache_hit(self):
        class ChangingProvider:
            provenance, source, freshness_s = 'simulated', 'changing_fixture', 0
            users = 0
            def __call__(self, route, parameters):
                return {'users_on_route': self.users, 'capacity_per_hour': parameters['capacity_per_hour'],
                        'load_factor': self.users / parameters['service_capacity_per_hour'],
                        'expected_wait_s': 1, 'board_refusal_prob': 0}
        load = ChangingProvider()
        _, engine = self.client(load=load)
        first = engine.query('O', 'D', AT)
        load.users = 25
        second = engine.query('O', 'D', AT)
        self.assertEqual(first[0]['load_estimate']['users_on_route'], 0)
        self.assertEqual(second[0]['load_estimate']['users_on_route'], 25)
        self.assertEqual(engine.cache.hits, 1)

    def test_invalid_load_is_service_error_not_client_error(self):
        class InvalidProvider:
            provenance, source, freshness_s = 'simulated', 'invalid_fixture', 0
            def __call__(self, route, parameters):
                return {'users_on_route': 0}
        client, _ = self.client(load=InvalidProvider())
        response = client.post('/api/routes/query', json={'origin': 'O', 'destination': 'D', 'depart_at': AT})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'DATA_UNAVAILABLE')

    def test_input_documents_are_not_mutated(self):
        path = ROOT / 'contracts/seed/network.seed.json'
        before = path.read_bytes()
        SeedDataAdapter().load()
        self.assertEqual(before, path.read_bytes())
        data = read('network.synthetic.json')
        before = deepcopy(data)
        adapter = synthetic_adapter(data)
        adapter.load().network['lines'].clear()
        self.assertEqual(data, before)
        self.assertEqual(len(adapter.load().network['lines']), 10)


if __name__ == '__main__':
    unittest.main()
