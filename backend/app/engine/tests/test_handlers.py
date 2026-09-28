"""Handler contracts and real adapter/registry/CSim integration, all data simulated."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from backend.app.ai.tools import build_default_registry
from backend.app.engine.handlers import RouteHandlers
from backend.app.engine.sim_adapter import MappingDemandAdapter
from backend.app.graph.adapter import DataUnavailable, JsonDataAdapter, MappingDataAdapter, SeedDataAdapter

ROOT = Path(__file__).resolve().parents[4]
FIX = ROOT / 'backend/app/engine/fixtures'
AT = '2026-09-22T08:20:00+08:00'


def read(name):
    return json.loads((FIX / name).read_text(encoding='utf-8'))


def normalized(network=None, events=None):
    policy = read('routing.synthetic.json')
    return MappingDataAdapter(network or read('network.synthetic.json'), baseline_fare=policy['baseline_fare'],
                              profiles=policy['profiles'], events=events or read('events.synthetic.json')['events'])


def tools(adapter=None, rate=60):
    demand = MappingDemandAdapter({}, source='handler_demand_fixture', provenance='simulated',
                                  freshness_s=12, default_rate_per_hour=rate)
    return RouteHandlers(adapter or normalized(), demand_adapter=demand, observed_at=AT)


def search(handlers, profile_id=None):
    return handlers.search_transit_routes(**{'from': 'O', 'to': 'D', 'depart_at': AT, 'profile_id': profile_id})


class HandlerContracts(unittest.TestCase):
    def test_geocode_place_contract(self):
        handlers = tools()
        place = handlers.geocode_place('o')
        self.assertEqual(set(place), {'node_id', 'lat', 'lng', 'label', 'provenance', 'freshness_s'})
        self.assertEqual(place['node_id'], 'O')
        self.assertEqual(place['provenance'], 'simulated')
        self.assertEqual(place['freshness_s'], 1200)
        self.assertEqual(place, handlers.geocode_place('O'))
        with self.assertRaises(DataUnavailable):
            handlers.geocode_place('unmapped town')

    def test_find_access_points_contract(self):
        handlers = tools()
        place = handlers.geocode_place('O')
        points = handlers.find_access_points(place['lat'], place['lng'], radius_m=400)
        self.assertEqual(points[0]['node_id'], 'O')
        self.assertEqual(points[0]['distance_m'], 0)
        for point in points:
            self.assertEqual(set(point), {'node_id', 'label', 'kind', 'lat', 'lng', 'distance_m',
                                         'accessible', 'provenance', 'freshness_s'})
            self.assertTrue(0 <= point['distance_m'] <= 400)
            self.assertEqual(point['provenance'], 'simulated')
            self.assertIsInstance(point['accessible'], bool)
        self.assertEqual(points, handlers.find_access_points(place['lat'], place['lng'], radius_m=400))
        with self.assertRaises(ValueError):
            handlers.find_access_points(91, 0)

    def test_search_transit_routes_contract_and_stable_fields(self):
        handlers = tools()
        routes = search(handlers)
        self.assertEqual(len(routes), 9)
        self.assertEqual(routes, search(handlers))
        for route in routes:
            self.assertTrue({'route_id', 'total', 'legs', 'provenance', 'load_estimate'} <= set(route))
            self.assertTrue({'time_s', 'transfers', 'walk_m', 'fare_hkd', 'reliability', 'freshness_s'} <= set(route['total']))
            self.assertEqual(route['provenance'], 'simulated')
            self.assertIsInstance(route['total']['transfers'], int)
            self.assertTrue(0 <= route['total']['reliability'] <= 1)
            self.assertTrue(all(isinstance(leg['accessible'], bool) for leg in route['legs']))
            supply = handlers._context['details']['route_parameters'][route['route_id']]
            self.assertTrue({'route_id', 'headway_s', 'capacity_per_hour', 'service_capacity_per_hour',
                             'provenance', 'freshness_s'} <= set(supply))
            self.assertGreater(supply['headway_s'], 0)
            self.assertAlmostEqual(supply['capacity_per_hour'], supply['service_capacity_per_hour'] * .85)
            self.assertAlmostEqual(supply['capacity_per_hour'], route['load_estimate']['capacity_per_hour'], places=3)
            self.assertEqual(supply['freshness_s'], route['total']['freshness_s'])
            self.assertEqual(supply['provenance'], 'simulated')

    def test_score_routes_contract_uses_full_candidate_normalization(self):
        handlers = tools()
        routes = search(handlers)
        ids = [r['route_id'] for r in routes]
        scores = handlers.score_routes(ids)
        for row in scores:
            self.assertEqual(set(row), {'route_id', 'score', 'score_breakdown', 'provenance', 'freshness_s'})
            self.assertAlmostEqual(row['score'], sum(x['contribution'] for x in row['score_breakdown']))
        self.assertEqual(scores[0], handlers.score_routes(ids[:1])[0])
        self.assertEqual(scores, handlers.score_routes(ids))
        time_only = handlers.score_routes(ids, weights={'time': 1})
        self.assertTrue(all(next(x for x in s['score_breakdown'] if x['criterion'] == 'time')['weight'] == 1 for s in time_only))
        with self.assertRaises(DataUnavailable):
            handlers.score_routes(['invented_route'])

    def test_estimate_load_contract_and_horizon_units(self):
        handlers = tools(rate=60)
        route_id = search(handlers)[0]['route_id']
        ten = handlers.estimate_load([route_id], horizon_min=10)[0]
        thirty = handlers.estimate_load([route_id], horizon_min=30)[0]
        self.assertEqual(set(ten), {'route_id', 'users_on_route', 'capacity_per_hour', 'load_factor',
                                    'expected_wait_s', 'board_refusal_prob', 'overloaded', 'provenance', 'freshness_s'})
        self.assertEqual(ten['users_on_route'], 10)
        self.assertEqual(thirty['users_on_route'], 30)
        self.assertEqual(ten['load_factor'], thirty['load_factor'])
        self.assertEqual(ten['provenance'], 'simulated')
        self.assertGreater(ten['freshness_s'], 0)
        self.assertEqual(ten, handlers.estimate_load([route_id], 10)[0])
        with self.assertRaises(ValueError):
            handlers.estimate_load([route_id], 0)

    def test_get_diversion_plan_contract_and_conservation(self):
        handlers = tools()
        routes = search(handlers)
        plan = handlers.get_diversion_plan('evt_fixture_closed', 100000)
        self.assertEqual(set(plan), {'plan_id', 'event_id', 'demand', 'window_min', 'shares',
                                     'unstoppable_demand', 'advice', 'fairness', 'provenance'})
        self.assertEqual(plan['provenance'], 'simulated')
        self.assertEqual(plan['window_min'], 60)
        self.assertEqual(sum(x['users'] for x in plan['shares']) + plan['unstoppable_demand'], 100000)
        self.assertTrue({x['route_id'] for x in plan['shares']} <= {r['route_id'] for r in routes})
        self.assertEqual(plan, handlers.get_diversion_plan('evt_fixture_closed', 100000))
        with self.assertRaises(DataUnavailable):
            handlers.get_diversion_plan('unknown_event', 10)
        with self.assertRaises(ValueError):
            handlers.get_diversion_plan('evt_fixture_closed', -1)

    def test_all_six_handlers_in_existing_ai_registry(self):
        handlers = tools()
        registry = build_default_registry(handlers.handlers())
        async def check():
            arguments = {
                'geocode_place': {'query': 'O'},
                'find_access_points': {'lat': 22, 'lng': 114},
                'search_transit_routes': {'from': 'O', 'to': 'D', 'depart_at': AT},
            }
            result = {}
            for name, args in arguments.items():
                response = await registry.call(name, args)
                self.assertTrue(response['ok'], response)
                result[name] = response['data']
            ids = [r['route_id'] for r in result['search_transit_routes']['routes']]
            for name, args in {
                'score_routes': {'route_ids': ids},
                'estimate_load': {'route_ids': ids, 'horizon_min': 60},
                'get_diversion_plan': {'event_id': 'evt_fixture_closed', 'demand': 1000},
            }.items():
                response = await registry.call(name, args)
                self.assertTrue(response['ok'], response)
            self.assertEqual(len(registry.audit_log), 6)
        asyncio.run(check())

    def test_closed_segments_excluded_in_both_directions(self):
        handlers = tools()
        for origin, destination in [('O', 'D'), ('D', 'O')]:
            routes = handlers.search_transit_routes(**{'from': origin, 'to': destination, 'depart_at': AT})
            self.assertTrue(routes)
            self.assertFalse(any(leg.get('line') == 'SIM_00' for route in routes for leg in route['legs']))

    def test_wheelchair_excludes_inaccessible_routes(self):
        data = read('network.synthetic.json')
        data['lines'][1]['low_floor'] = False
        data['lines'][2]['mode'] = 'MINIBUS'
        data['lines'][3]['has_stairs'] = True
        data['lines'][4]['accessible'] = 'partial'
        data['nodes'][7]['accessible'] = False
        handlers = tools(normalized(data))
        routes = search(handlers, profile_id='wheelchair')
        self.assertTrue(routes)
        excluded = {'SIM_00', 'SIM_01', 'SIM_02', 'SIM_03', 'SIM_04', 'SIM_05'}
        for route in routes:
            self.assertLessEqual(route['total']['walk_m'], 400)
            self.assertTrue(all(leg['accessible'] and leg['mode'] != 'MINIBUS' for leg in route['legs']))
            self.assertFalse(any(leg.get('line') in excluded for leg in route['legs']))

    def test_stale_snapshot_route_ids_are_rejected(self):
        handlers = tools()
        ids = [r['route_id'] for r in search(handlers)]
        event = read('events.synthetic.json')['events'][0]
        event.update(version=event['version'] + 1, status='expired')
        handlers.engine.snapshots.update_event(event)
        for call in [lambda: handlers.score_routes(ids), lambda: handlers.estimate_load(ids, 60),
                     lambda: handlers.get_diversion_plan('evt_fixture_closed', 1000)]:
            with self.assertRaises(DataUnavailable):
                call()
        self.assertEqual(len(search(handlers)), 10)

    def test_normalized_file_adapter_replacement_needs_no_core_changes(self):
        original = tools(JsonDataAdapter(FIX / 'network.synthetic.json', FIX / 'routing.synthetic.json',
                                        FIX / 'events.synthetic.json'))
        self.assertEqual(len(search(original)), 9)
        core_path = ROOT / 'backend/app/engine/candidates.py'
        core_before = core_path.read_bytes()
        network = read('network.synthetic.json')
        network['lines'] = [deepcopy(network['lines'][0])]
        network['lines'][0].update(id='ADAPTER_ONLY_LINE', headway_s=333, capacity_per_vehicle=444, fare_hkd=23)
        network['nodes'][0].update(name_zh='Adapter Place', lat=21.5)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'network.json'
            path.write_text(json.dumps(network), encoding='utf-8')
            changed = tools(JsonDataAdapter(path, FIX / 'routing.synthetic.json'))
            route = search(changed)[0]
            self.assertEqual(route['legs'][0]['line'], 'ADAPTER_ONLY_LINE')
            self.assertEqual(route['legs'][0]['headway_s'], 333)
            self.assertEqual(route['total']['fare_hkd'], 23)
            self.assertAlmostEqual(route['load_estimate']['capacity_per_hour'], 3600 / 333 * 444 * .85, places=3)
            self.assertEqual(changed.geocode_place('Adapter Place')['lat'], 21.5)
            self.assertEqual(route['provenance'], 'simulated')
        self.assertEqual(core_before, core_path.read_bytes())

    def test_seed_handler_profiles_without_llm(self):
        handlers = RouteHandlers(SeedDataAdapter(events_path=ROOT / 'contracts/seed/event.seed.json'), observed_at=AT)
        result = handlers.search_transit_routes(**{'from': 'TAW', 'to': 'ADM', 'depart_at': AT, 'profile_id': 'wheelchair'})
        self.assertIsNot(handlers.engine.snapshots.network.nodes['TAW']['accessible'], True)
        self.assertTrue(result)  # M0 wheelchair policy defaults MTR/large bus to accessible
        self.assertTrue(all(leg['accessible'] for route in result for leg in route['legs']))
        self.assertTrue(all(route['provenance'] == 'simulated' for route in result))
        with self.assertRaises(DataUnavailable):
            handlers.search_transit_routes(**{'from': 'TAW', 'to': 'ADM', 'depart_at': AT, 'profile_id': 'unknown'})


if __name__ == '__main__':
    unittest.main()
