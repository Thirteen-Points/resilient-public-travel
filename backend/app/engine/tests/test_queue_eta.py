"""Demand/capacity queue estimates must reach public ETAs and their ranking."""
import json
import math
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.engine.candidates import route_from_path, search_paths
from backend.app.engine.constraints import normalize_profile
from backend.app.engine.sim_adapter import CSimAdapter, MappingDemandAdapter, SimLoadProvider
from backend.app.engine.tests.test_c_route import AT, event, line, network
from backend.app.engine.tests.test_contracts import synthetic_adapter
from backend.app.graph import SnapshotStore, build_graph
from backend.app.graph.build import timestamp


class QueueEtaTests(unittest.TestCase):
    def test_offline_seed_exposes_the_same_included_delay(self):
        root = Path(__file__).resolve().parents[4]
        bundle = json.loads((root / 'contracts/seed/routes.seed.json').read_text(encoding='utf-8'))
        at = timestamp(bundle['meta']['od']['depart_at'])
        for route in bundle['routes']:
            headway = max(leg.get('headway_s', 0) for leg in route['legs'])
            delay = max(0, route['load_estimate']['expected_wait_s'] - headway / 2)
            self.assertAlmostEqual(route['total']['queue_delay_s'], delay)
            base_time = (timestamp(route['legs'][-1]['arrive']) - at).total_seconds()
            self.assertAlmostEqual(route['total']['time_s'], base_time + delay, places=4)

    def engine(self, adapter=None, rate=0):
        demand = MappingDemandAdapter({}, source='queue_eta_test', provenance='simulated',
                                      freshness_s=0, default_rate_per_hour=rate)
        engine = RouteEngine.from_adapter(adapter or synthetic_adapter(),
                                          load_provider=SimLoadProvider(CSimAdapter(), demand))
        return engine, demand

    def test_zero_demand_preserves_existing_scheduled_wait(self):
        engine, _ = self.engine()
        profile = normalize_profile()
        paths = search_paths(engine.snapshots.current, 'O', 'D', AT, profile).paths
        baseline = {r['route_id']: r for r in
                    [route_from_path(p, engine.snapshots.current, AT, fares=engine.fares) for p in paths]}
        for route in engine.query('O', 'D', AT):
            self.assertEqual(route['total']['queue_delay_s'], 0)
            self.assertEqual(route['total']['time_s'], baseline[route['route_id']]['total']['time_s'])
            self.assertEqual(route['total']['time_range_s'], baseline[route['route_id']]['total']['time_range_s'])

    def test_demand_moves_mean_and_both_bounds_and_rescores_on_cache_hit(self):
        engine, demand = self.engine()
        profile = {'weights': {'time': 1}}
        baseline = engine.query('O', 'D', AT, profile)
        baseline_by_id = {r['route_id']: r for r in baseline}
        first = baseline[0]['route_id']
        demand.rates[first] = 1_000_000
        loaded = engine.query('O', 'D', AT, profile)
        self.assertNotEqual(loaded[0]['route_id'], first)
        self.assertEqual([r['total']['time_s'] for r in loaded], sorted(r['total']['time_s'] for r in loaded))
        for route in loaded:
            total, old = route['total'], baseline_by_id[route['route_id']]['total']
            expected = route['load_estimate']['expected_wait_s']
            headway = max(leg.get('headway_s', 0) for leg in route['legs'])
            delay = max(0, expected - headway / 2)
            self.assertAlmostEqual(total['queue_delay_s'], delay)
            self.assertAlmostEqual(total['time_s'], old['time_s'] + delay)
            for bound, before in zip(total['time_range_s'], old['time_range_s']):
                self.assertAlmostEqual(bound, before + delay)
            time_score = next(row for row in route['score_breakdown'] if row['criterion'] == 'time')
            self.assertEqual(time_score['raw'], total['time_s'])
            self.assertIn(f"{total['time_range_s'][0] / 60:.0f}–{total['time_range_s'][1] / 60:.0f}", route['explain'])
        self.assertEqual(engine.cache.hits, 1)
        self.assertEqual(loaded, engine.query('O', 'D', AT, profile))
        demand.rates.clear()
        self.assertEqual(baseline, engine.query('O', 'D', AT, profile))

    def test_public_http_response_contains_updated_range(self):
        engine, demand = self.engine()
        client = TestClient(create_app(engine))
        payload = {'origin': 'O', 'destination': 'D', 'depart_at': AT}
        baseline = {r['route_id']: r for r in client.post('/api/routes/query', json=payload).json()}
        demand.default = 1_000_000
        response = client.post('/api/routes/query', json=payload)
        self.assertEqual(response.status_code, 200)
        for route in response.json():
            old = baseline[route['route_id']]['total']
            total = route['total']
            self.assertGreater(total['queue_delay_s'], 0)
            self.assertGreater(total['time_range_s'][0], old['time_range_s'][0])
            self.assertGreater(total['time_range_s'][1], old['time_range_s'][1])
            self.assertTrue(all(math.isfinite(value) for value in total['time_range_s']))
            self.assertTrue(any('two-headway cap' in warning for warning in route['warnings']))
            self.assertTrue(any('Boarding may be refused' in warning for warning in route['warnings']))

    def test_same_line_intermediate_stops_do_not_multiply_queue_delay(self):
        demand = MappingDemandAdapter({}, source='queue_eta_test', provenance='simulated',
                                      freshness_s=0, default_rate_per_hour=1_000_000)
        def query(data):
            engine = RouteEngine(SnapshotStore(build_graph(data)),
                                 load_provider=SimLoadProvider(CSimAdapter(), demand))
            return engine.query('A', 'C', AT)[0]
        split = query(network())
        direct = query(network([line(stops=['A', 'C'], seg_time_s=[120])]))
        for field in ('time_s', 'time_range_s', 'queue_delay_s'):
            self.assertEqual(split['total'][field], direct['total'][field])
        self.assertEqual(split['total']['queue_delay_s'], 270)

    def test_reduced_capacity_increases_the_included_queue_delay(self):
        demand = MappingDemandAdapter({}, source='queue_eta_test', provenance='simulated',
                                      freshness_s=0, default_rate_per_hour=500)
        store = SnapshotStore(build_graph(network()))
        engine = RouteEngine(store, load_provider=SimLoadProvider(CSimAdapter(), demand))
        before = engine.query('A', 'C', AT)[0]
        store.update_event(event(affected_segments=[{
            'from_node': 'A', 'to_node': 'B', 'impact': 'reduced_capacity', 'capacity_factor': .5}]))
        after = engine.query('A', 'C', AT)[0]
        self.assertGreater(after['total']['queue_delay_s'], before['total']['queue_delay_s'])
        self.assertGreater(after['total']['time_s'], before['total']['time_s'])

    def test_transfers_add_the_route_bottleneck_delay_once(self):
        data = network([line(stops=['A', 'B']), line(id='L2', stops=['B', 'C'], headway_s=600)])
        demand = MappingDemandAdapter({}, source='queue_eta_test', provenance='simulated',
                                      freshness_s=0, default_rate_per_hour=1_000_000)
        engine = RouteEngine(SnapshotStore(build_graph(data)),
                             load_provider=SimLoadProvider(CSimAdapter(), demand))
        route = engine.query('A', 'C', AT)[0]
        self.assertEqual(route['total']['transfers'], 1)
        self.assertEqual(route['total']['queue_delay_s'], 900)

    def test_walking_only_has_no_boarding_delay(self):
        data = network(walk_links=[{'from': 'A', 'to': 'D', 'walk_m': 140, 'walk_s': 100, 'accessible': True}])
        demand = MappingDemandAdapter({}, source='queue_eta_test', provenance='simulated',
                                      freshness_s=0, default_rate_per_hour=1_000_000)
        engine = RouteEngine(SnapshotStore(build_graph(data)),
                             load_provider=SimLoadProvider(CSimAdapter(), demand))
        route = engine.query('A', 'D', AT, modes=['WALK'])[0]
        self.assertEqual(route['total']['queue_delay_s'], 0)
        self.assertEqual(route['load_estimate']['expected_wait_s'], 0)
        self.assertAlmostEqual(route['total']['time_s'], 100)

    def test_returned_data_cannot_corrupt_cached_base_time(self):
        engine, _ = self.engine(rate=1_000_000)
        expected = engine.query('O', 'D', AT)
        changed = engine.query('O', 'D', AT)
        changed[0]['total']['time_range_s'][0] = -1
        changed[0]['total']['time_s'] = -1
        self.assertEqual(expected, engine.query('O', 'D', AT))


if __name__ == '__main__':
    unittest.main()
