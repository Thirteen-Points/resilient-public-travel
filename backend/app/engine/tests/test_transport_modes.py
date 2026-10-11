"""Transport selection must find real candidates before diversity/ranking."""
import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.engine.load_provider import FixtureLoadProvider
from backend.app.graph.adapter import MappingDataAdapter

AT = '2026-10-12T08:20:00+08:00'


class TransportModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RouteEngine.from_seed()
        cls.client = TestClient(create_app(cls.engine))

    def query(self, **extra):
        return self.client.post('/api/routes/query', json={
            'origin': 'TAW', 'destination': 'ADM', 'depart_at': AT, **extra})

    def test_bus_and_ferry_filters_return_only_routes_using_requested_mode(self):
        for mode in ('MTR', 'BUS', 'FERRY'):
            with self.subTest(mode=mode):
                response = self.query(required_modes=[mode])
                self.assertEqual(response.status_code, 200)
                routes = response.json()
                self.assertTrue(routes)
                self.assertTrue(all(any(leg['mode'] == mode for leg in route['legs']) for route in routes))
        # A ferry journey from the original corridor needs feeder transport.
        ferry = self.query(required_modes=['FERRY']).json()
        self.assertTrue(any(any(leg['mode'] == 'MTR' for leg in route['legs']) for route in ferry))

    def test_piers_can_be_queried_for_a_direct_ferry_journey(self):
        response = self.query(origin='PIER_TST', destination='PIER_CEN', modes=['FERRY'], required_modes=['FERRY'])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())
        self.assertEqual({leg['mode'] for route in response.json() for leg in route['legs']}, {'FERRY'})

    def test_unverified_minibus_does_not_substitute_rail_or_bus(self):
        response = self.query(required_modes=['MINIBUS'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_mode_selection_is_part_of_cache_identity(self):
        for mode in ('BUS', 'FERRY', 'BUS'):
            routes = self.query(required_modes=[mode]).json()
            self.assertTrue(routes)
            self.assertTrue(all(mode in {leg['mode'] for leg in route['legs']} for route in routes))

    def test_filters_preserve_wheelchair_hard_constraints(self):
        fixtures = Path(__file__).resolve().parent.parent / 'fixtures'
        network = json.loads((fixtures / 'network.synthetic.json').read_text(encoding='utf-8'))
        network['lines'][1]['low_floor'] = False
        load = json.loads((fixtures / 'seed_policy.json').read_text(encoding='utf-8'))['load']
        engine = RouteEngine.from_adapter(MappingDataAdapter(network, baseline_fare=5), load_provider=FixtureLoadProvider(load))
        response = TestClient(create_app(engine)).post('/api/routes/query', json={
            'origin': 'O', 'destination': 'D', 'depart_at': AT, 'required_modes': ['BUS'], 'profile': {
            'mobility': 'wheelchair', 'preset': 'fastest', 'max_walk_m': 400, 'max_transfers': 2,
            'hard_flags': ['no_stairs', 'no_minibus', 'no_non_lowfloor_bus']}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())
        for route in response.json():
            self.assertLessEqual(route['total']['walk_m'], 400)
            self.assertLessEqual(route['total']['transfers'], 2)
            self.assertTrue(all(leg['accessible'] is True and leg['mode'] != 'MINIBUS' for leg in route['legs']))
            self.assertFalse(any(leg.get('line') == 'SIM_01' for leg in route['legs']))

    def test_invalid_mode_filters_are_rejected(self):
        for key in ('modes', 'required_modes'):
            for value in ([], 'BUS', [None], ['PLANE']):
                with self.subTest(key=key, value=value):
                    response = self.query(**{key: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()['error']['code'], 'INVALID_ROUTE_QUERY')
