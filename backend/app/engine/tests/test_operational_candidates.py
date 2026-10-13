"""M0 operational exclusions; synthetic inputs are explicitly simulated."""
from copy import deepcopy
import json
import unittest

from fastapi.testclient import TestClient
from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.engine.tests.test_c_route import AT, ROOT, line, make_engine, network
from backend.app.graph import SnapshotStore, build_graph
from backend.app.graph.build import thaw
from backend.app.engine.tests.test_handlers import tools
from backend.app.graph.adapter import MappingDataAdapter


class OperationalCandidateTests(unittest.TestCase):
    def query(self, client, origin='A', destination='C', **extra):
        return client.post('/api/routes/query', json={
            'origin': origin, 'destination': destination, 'depart_at': AT, **extra})

    def test_seed_api_has_no_tai_wai_to_admiralty_service_at_0300(self):
        client = TestClient(create_app(RouteEngine.from_seed()))
        night = self.query(client, 'TAW', 'ADM', depart_at='2026-10-11T03:00:00+08:00')
        day = self.query(client, 'TAW', 'ADM', depart_at='2026-10-11T12:00:00+08:00')
        self.assertEqual(night.status_code, 200)
        self.assertEqual(night.json(), [])
        self.assertEqual(day.status_code, 200)
        self.assertTrue(day.json())

    def test_unresolved_line_is_excluded_in_full_without_deleting_source(self):
        data = network([line(stops=['A', 'B', 'MISSING'])])
        original = deepcopy(data)
        graph = build_graph(data)
        client = TestClient(create_app(make_engine(SnapshotStore(graph))))
        # Even the resolved prefix must not become an operational recommendation.
        response = self.query(client, destination='B')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertFalse(graph.edges)
        self.assertTrue(any('MISSING' in warning for warning in graph.diagnostics))
        self.assertEqual(thaw(graph.source), original)
        self.assertEqual(data, original)
        self.assertNotIn('MISSING', graph.nodes)

    def test_demo_or_unverified_line_stays_excluded_with_resolved_nodes(self):
        for flag in ({'demo_only': True}, {'operational_status': 'unverified'}):
            with self.subTest(flag=flag):
                data = network([line(**flag), line(id='VALID')])
                client = TestClient(create_app(make_engine(SnapshotStore(build_graph(data)))))
                response = self.query(client)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json())
                self.assertEqual({leg['line'] for route in response.json()
                                  for leg in route['legs']}, {'VALID'})
                self.assertEqual(client.get('/api/graph/network').json(), data)

    def test_900m_total_is_allowed_with_resolved_access_and_warning(self):
        data = network([line(stops=['B', 'C'])], [
            {'from': 'A', 'to': 'B', 'walk_m': 450, 'accessible': True},
            {'from': 'C', 'to': 'D', 'walk_m': 450, 'accessible': True}])
        client = TestClient(create_app(make_engine(SnapshotStore(build_graph(data)))))
        for profile in ({}, {'max_walk_m': 1000}):
            response = self.query(client, destination='D', profile=profile)
            self.assertEqual(response.status_code, 200)
            route = response.json()[0]
            self.assertEqual(route['total']['walk_m'], 900)
            self.assertTrue(any('Long walk' in w for w in route['warnings']))
            self.assertEqual([(leg['from'], leg['to']) for leg in route['legs']],
                             [('A', 'B'), ('B', 'C'), ('C', 'D')])
        # An explicitly requested personal limit still applies.
        self.assertEqual(self.query(client, destination='D', profile={'max_walk_m': 800}).json(), [])
        self.assertEqual(client.get('/api/graph/network').json(), data)

    def test_missing_walk_endpoint_cannot_be_bridged(self):
        data = network([line(stops=['B', 'C'])], [
            {'from': 'A', 'to': 'MISSING', 'walk_m': 450, 'accessible': True},
            {'from': 'C', 'to': 'D', 'walk_m': 450, 'accessible': True}])
        client = TestClient(create_app(make_engine(SnapshotStore(build_graph(data)))))
        self.assertEqual(self.query(client, destination='D').json(), [])
        self.assertEqual(client.get('/api/graph/network').json(), data)

    def test_access_radius_is_capped_independently_of_route_total(self):
        data = network()
        for node, latitude in zip(data['nodes'], (0, .006, .009, .02)):
            node.update(lat=latitude, lng=0, kind='station')
        handlers = tools(MappingDataAdapter(data, baseline_fare=5))
        for radius in (800, 1000, 2000):
            points = handlers.find_access_points(0, 0, radius_m=radius)
            self.assertEqual([point['node_id'] for point in points], ['A', 'B'])
            self.assertTrue(all(point['distance_m'] <= 800 for point in points))
        self.assertEqual([p['node_id'] for p in handlers.find_access_points(0, 0, 400)], ['A'])

    def test_wheelchair_defaults_rail_and_full_size_bus_but_never_minibus(self):
        for mode, extra, allowed in [('MTR', {}, True), ('MTR', {'accessible': 'partial'}, False),
                                      ('BUS', {'low_floor': True}, True), ('BUS', {}, True),
                                      ('BUS', {'low_floor': False}, False),
                                      ('MINIBUS', {'low_floor': True}, False)]:
            with self.subTest(mode=mode, extra=extra):
                data = network([line(mode=mode, **extra)])
                client = TestClient(create_app(make_engine(SnapshotStore(build_graph(data)))))
                result = self.query(client, profile={'mobility': 'wheelchair'})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(bool(result.json()), allowed)

    def test_seed_candidates_are_not_promoted_and_facts_are_preserved(self):
        paths = [ROOT / 'contracts/seed' / name
                 for name in ('network.seed.json', 'routes.seed.json')]
        before = {path: path.read_bytes() for path in paths}
        raw_network, references = [json.loads(before[path]) for path in paths]
        archived = json.loads((ROOT / 'backend/app/engine/reports/route-seed-repair-review.json').read_text(encoding='utf-8'))
        by_id = {r['route_id']: r for r in archived['old_cards']}
        self.assertGreater(by_id['r_seed_007']['total']['walk_m'], 800)
        endpoint = by_id['r_seed_008']['legs'][-1]['to']
        self.assertNotIn(endpoint, {n['id'] for n in raw_network['nodes']})
        source_line = next((row for row in raw_network['lines'] if endpoint in row['stops']), None)
        engine = RouteEngine.from_seed()
        client = TestClient(create_app(engine))
        response = self.query(client, 'TAW', 'ADM', profile={'max_walk_m': 1000})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())
        for route in response.json():
            self.assertNotIn(route['route_id'], ('r_seed_007', 'r_seed_008'))
            self.assertEqual(route['provenance'], 'simulated')
            self.assertTrue(all(leg.get('line') != 'GMB_481B' and
                                endpoint not in (leg['from'], leg['to']) for leg in route['legs']))
        error = self.query(client, 'BS_TAW', endpoint)
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.json()['error']['code'], 'INVALID_ROUTE_QUERY')
        exposed = client.get('/api/graph/network').json()
        if source_line is not None:
            retained = next(row for row in exposed['lines'] if row['id'] == source_line['id'])
            self.assertEqual(retained, {**source_line, 'provenance': 'simulated'})
        else:
            self.assertFalse(any(row['id'] == 'GMB_481B' for row in exposed['lines']))
        self.assertNotIn(endpoint, {n['id'] for n in exposed['nodes']})
        for path in paths:
            self.assertEqual(path.read_bytes(), before[path])


if __name__ == '__main__':
    unittest.main()
