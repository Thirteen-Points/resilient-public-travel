"""30 directed OD contracts and adapter-only access replacement; all simulated."""
from copy import deepcopy
from itertools import permutations
import json
import unittest

from backend.app.engine import RouteEngine
from backend.app.engine.coverage import CORRIDOR_NODES, coverage_matrix
from backend.app.engine.constraints import normalize_profile
from backend.app.engine.candidates import search_paths, select_diverse, intermediate_nodes, jaccard
from backend.app.engine.tests.test_c_route import AT, ROOT
from backend.app.engine.tests.test_contracts import provider
from backend.app.graph.adapter import SeedDataAdapter, MappingDataAdapter
from backend.app.graph.build import thaw


def adapted_access(*, accessible=None, one_way=False):
    data = SeedDataAdapter().load()
    network = deepcopy(data.network)
    links = json.loads((ROOT / 'backend/app/engine/fixtures/corridor_access.simulated.json').read_text(encoding='utf-8'))['walk_links']
    for link in links:
        if accessible is not None:
            link.update(accessible=accessible, walk_m=150)
        if one_way:
            link['bidirectional'] = False
    network['walk_links'].extend(links)
    # Close all ERL segments to prove independent access, not a hidden rail path.
    stops = next(line['stops'] for line in network['lines'] if line['id'] == 'ERL')
    event = {'event_id': 'fixture_erl_closed', 'version': 1, 'status': 'published',
             'line': 'ERL', 'direction': 'both', 'provenance': 'simulated',
             'window': {'start': '2026-09-22T08:00:00+08:00', 'end': None},
             'affected_segments': [{'from_node': a, 'to_node': b, 'impact': 'closed', 'capacity_factor': 0}
                                   for a, b in zip(stops, stops[1:])]}
    adapter = MappingDataAdapter(network, baseline_fare=data.baseline_fare,
                                 fares=thaw(data.fares), events=[event])
    return RouteEngine.from_adapter(adapter, load_provider=provider())


class CorridorCoverageTests(unittest.TestCase):
    def test_all_30_dynamic_queries_are_continuous_unique_and_report_shortfall(self):
        engine = RouteEngine.from_seed()
        for origin, destination in permutations(CORRIDOR_NODES, 2):
            with self.subTest(od=(origin, destination)):
                result = engine.query_details(origin, destination, AT)
                routes = result['routes']
                self.assertTrue(routes)
                self.assertLessEqual(len(routes), 10)
                self.assertEqual(len({r['route_id'] for r in routes}), len(routes))
                self.assertEqual(result['search_statistics']['target'], 10)
                self.assertEqual(result['search_statistics']['shortfall'], 10-len(routes))
                if len(routes) < 10:
                    self.assertTrue(any('target 10' in text for text in result['diagnostics']))
                for route in routes:
                    self.assertEqual(route['legs'][0]['from'], origin)
                    self.assertEqual(route['legs'][-1]['to'], destination)
                    self.assertTrue(all(a['to'] == b['from'] for a, b in zip(route['legs'], route['legs'][1:])))
                    self.assertEqual(route['provenance'], 'simulated')
                    self.assertFalse(route['route_id'].startswith('r_seed_'))
                    self.assertTrue(all(l.get('line') != 'GMB_481B' for l in route['legs']))

    def test_30_od_path_diversity_does_not_pad_or_repeat_nodes(self):
        engine = RouteEngine.from_seed()
        for origin, destination in permutations(CORRIDOR_NODES, 2):
            paths = select_diverse(search_paths(engine.snapshots.current, origin, destination, AT, normalize_profile()).paths)
            signatures = [tuple(t.edge.id for t in path) for path in paths]
            self.assertEqual(len(set(signatures)), len(paths))
            for i, path in enumerate(paths):
                visited = [origin] + [step.edge.target for step in path]
                self.assertEqual(len(visited), len(set(visited)))
                for other in paths[i+1:]:
                    self.assertLess(jaccard(intermediate_nodes(path), intermediate_nodes(other)), .7)

    def test_matrix_records_30_pairs_and_endpoint_data_gaps(self):
        result = coverage_matrix(RouteEngine.from_seed(), AT)
        self.assertEqual(result['od_count'], 30)
        self.assertEqual(result['covered'], 30)
        self.assertEqual({(r['origin'], r['destination']) for r in result['rows']}, set(permutations(CORRIDOR_NODES, 2)))
        for node in ('MKK', 'EXC'):
            self.assertTrue(result['endpoint_topology'][node]['single_line_dependency'])
            self.assertEqual(result['endpoint_topology'][node]['walking_access'], {'in': False, 'out': False})
        self.assertTrue(all(row['reasons'] for row in result['rows'] if row['shortfall']))
        # C-Data may exclude the unresolved line from the source altogether.
        raw = SeedDataAdapter().load().network
        if any(line['id'] == 'GMB_481B' for line in raw['lines']):
            self.assertTrue(any(row['line'] == 'GMB_481B' for row in result['unavailable_services']))
        self.assertFalse(any(edge.line == 'GMB_481B' for edge in RouteEngine.from_seed().snapshots.network.edges))

    def test_adapter_access_fixture_closes_mkk_exc_gap_without_core_rewrite(self):
        seed_path = ROOT / 'contracts/seed/network.seed.json'
        before = seed_path.read_bytes()
        engine = adapted_access()
        for origin, destination in [('MKK', 'EXC'), ('EXC', 'MKK')]:
            routes = engine.query(origin, destination, AT)
            self.assertTrue(routes)
            for route in routes:
                self.assertTrue(all(leg.get('line') != 'ERL' for leg in route['legs']))
                self.assertGreaterEqual(route['total']['walk_m'], 1000)
                self.assertTrue(any('Long walk' in w for w in route['warnings']))
        self.assertEqual(seed_path.read_bytes(), before)

    def test_access_unknown_partial_and_direction_are_not_upgraded(self):
        for value in ('unknown', 'partial', False):
            engine = adapted_access(accessible=value)
            self.assertEqual(engine.query('MKK', 'EXC', AT, {'mobility': 'wheelchair'}), [])
        engine = adapted_access(accessible=True)
        routes = engine.query('MKK', 'EXC', AT, {'mobility': 'wheelchair'})
        self.assertIsNot(engine.snapshots.network.nodes['MKK']['accessible'], True)
        self.assertEqual(routes, [])  # accessible link alone cannot certify an unknown station
        self.assertTrue(all(l['accessible'] is True and l['mode'] != 'MINIBUS' for r in routes for l in r['legs']))
        engine = adapted_access(one_way=True)
        self.assertEqual(engine.query('MKK', 'EXC', AT), [])
        self.assertEqual(engine.query('EXC', 'MKK', AT), [])

    def test_wheelchair_and_published_closure_across_all_30_od(self):
        engine = RouteEngine.from_seed(events_path=ROOT / 'contracts/seed/event.seed.json')
        result = coverage_matrix(engine, AT, profile={'mobility': 'wheelchair'})
        self.assertEqual(result['od_count'], 30)
        for origin, destination in permutations(CORRIDOR_NODES, 2):
            for route in engine.query(origin, destination, AT, {'mobility': 'wheelchair'}):
                self.assertTrue(all(l['accessible'] is True and l['mode'] != 'MINIBUS' for l in route['legs']))
            paths = search_paths(engine.snapshots.current, origin, destination, AT, normalize_profile({'mobility': 'wheelchair'})).paths
            self.assertTrue(all(engine.snapshots.current.impact(t.edge, t.depart, t.arrive)[0] > 0 for p in paths for t in p))


if __name__ == '__main__':
    unittest.main()
