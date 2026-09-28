"""C-Route M0 consumers; no authoritative/shared schemas are defined here."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from backend.app.ai.query import NoLLMQueryService
from backend.app.ai.tools import build_default_registry
from backend.app.engine.api import create_app
from backend.app.engine.handlers import RouteHandlers
from backend.app.engine.m0 import SEEDS, collect, inspect_seeds, load_seeds
from backend.app.engine.sim_adapter import MappingDemandAdapter
from backend.app.engine.tests.test_handlers import AT, FIX, normalized, read, search, tools
from backend.app.graph.adapter import DataUnavailable, MappingDataAdapter, SeedDataAdapter

ROOT = Path(__file__).resolve().parents[4]
SEED_DIR = ROOT / 'contracts/seed'


class FourSeedConsumers(unittest.TestCase):
    def test_reads_all_four_complete_json_documents_without_mutation(self):
        before = {name: (SEED_DIR / name).read_bytes() for name in SEEDS}
        docs = load_seeds(SEED_DIR)
        audit = inspect_seeds(SEED_DIR)
        self.assertEqual(set(docs), set(SEEDS))
        self.assertTrue(audit['consumer_read_pass'])
        self.assertFalse(audit['full_m0_accepted'])
        self.assertEqual(len(audit['files']), 4)
        for evidence in audit['files']:
            self.assertEqual(evidence['sha256'], hashlib.sha256(before[evidence['name']]).hexdigest())
            self.assertEqual(before[evidence['name']], (SEED_DIR / evidence['name']).read_bytes())

    def test_reports_legacy_fixture_gaps_instead_of_certifying_them(self):
        audit = inspect_seeds(SEED_DIR)
        codes = {row['code'] for row in audit['findings']}
        self.assertNotIn('LEGACY_TRAVEL_FIELD', codes)
        self.assertNotIn('REFERENCE_WHEELCHAIR_CONFLICT', codes)
        # Preserve the negative consumer check using an isolated legacy fixture,
        # rather than requiring the shared seed to remain deliberately broken.
        with tempfile.TemporaryDirectory() as folder:
            for name in SEEDS:
                shutil.copyfile(SEED_DIR / name, Path(folder) / name)
            path = Path(folder) / 'routes.seed.json'
            document = json.loads(path.read_text(encoding='utf-8'))
            bad = document['routes'][0]
            bad['legs'][0]['travel_s'] = bad['legs'][0].pop('in_vehicle_s')
            bad['total']['walk_m'] = 401
            next(p for p in document['persona_top_picks'] if p['persona'] == 'wheelchair')['top'] = [bad['route_id']]
            path.write_text(json.dumps(document), encoding='utf-8')
            negative_codes = {row['code'] for row in inspect_seeds(folder)['findings']}
            self.assertTrue({'LEGACY_TRAVEL_FIELD', 'REFERENCE_WHEELCHAIR_CONFLICT'} <= negative_codes)
        self.assertEqual('SEED_REAL_LABEL' in codes, any('real' in row['raw_provenance_labels'] for row in audit['files']))
        self.assertNotEqual(audit['schema_validation'], 'passed')

    def test_all_reference_ids_resolve_at_consumer_boundary(self):
        docs = load_seeds(SEED_DIR)
        route_ids = {r['route_id'] for r in docs['routes.seed.json']['routes']}
        event_ids = {e['event_id'] for e in docs['event.seed.json']['events']}
        self.assertIn(docs['sim.seed.json']['meta']['event_ref'], event_ids)
        for picks in docs['routes.seed.json']['persona_top_picks']:
            self.assertTrue(set(picks['top']) <= route_ids)
        for policy in ('baseline', 'guided'):
            self.assertTrue({r['route_id'] for r in docs['sim.seed.json'][policy].get('route_load', docs['sim.seed.json'][policy].get('shares', []))} <= route_ids)

    def test_malformed_seed_and_nonfinite_json_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in SEEDS:
                shutil.copyfile(SEED_DIR / name, Path(folder) / name)
            target = Path(folder) / 'routes.seed.json'
            for raw in ['{"routes":NaN}', '{"routes":[],"routes":[]}', '{broken']:
                target.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_seeds(folder)
            target.write_text('{"meta":{},"routes":{},"persona_top_picks":[]}', encoding='utf-8')
            audit = inspect_seeds(folder)
            self.assertFalse(audit['consumer_read_pass'])
            self.assertTrue(audit['consumer_errors'])

    def test_reproducible_m0_demo_is_computed_not_reference_seed_output(self):
        first, second = collect(), collect()
        self.assertEqual(first, second)
        self.assertTrue(first['route_m0_prework_pass'])
        self.assertTrue(first['demo']['checks']['wheelchair_accessible'])
        self.assertGreaterEqual(first['demo']['counts']['wheelchair'], 3)
        self.assertTrue(all(v for k,v in first['demo']['checks'].items() if k != 'wheelchair_accessible'))
        self.assertFalse(first['demo']['reference_routes_used_for_search'])
        self.assertFalse(first['demo']['placeholder_sim_used_as_result'])
        self.assertEqual(len(first['demo']['public_response_sample']), 3)
        self.assertFalse(any(r['route_id'].startswith('r_seed_') for r in first['demo']['public_response_sample']))

    def test_public_query_consumes_seed_and_preserves_stable_ids(self):
        handlers = RouteHandlers(SeedDataAdapter(events_path=SEED_DIR / 'event.seed.json'), observed_at=AT)
        client = TestClient(create_app(handlers.engine))
        request = {'origin': 'TAW', 'destination': 'ADM', 'depart_at': AT}
        a = client.post('/api/routes/query', json=request)
        b = client.post('/api/routes/query', json=request)
        self.assertEqual(a.status_code, 200)
        self.assertIsInstance(a.json(), list)
        self.assertEqual([r['route_id'] for r in a.json()], [r['route_id'] for r in b.json()])
        other = RouteHandlers(SeedDataAdapter(events_path=SEED_DIR / 'event.seed.json'), observed_at=AT)
        self.assertEqual([r['route_id'] for r in a.json()], [r['route_id'] for r in other.engine.query(**request)])


class HandlerBoundaryContracts(unittest.TestCase):
    def test_all_six_tool_envelopes_have_simulated_source_and_freshness(self):
        h = tools()
        registry = build_default_registry(h.handlers())
        async def run():
            requests = [
                ('geocode_place', {'query': 'O'}),
                ('find_access_points', {'lat': 22, 'lng': 114}),
                ('search_transit_routes', {'from': 'O', 'to': 'D', 'depart_at': AT}),
            ]
            outputs = {}
            for name, args in requests:
                response = await registry.call(name, args)
                self.assertTrue(response['ok'], response)
                outputs[name] = response['data']
                self.assertEqual(response['trace']['provenance'], response['data']['provenance'])
                self.assertEqual(response['trace']['freshness_s'], response['data']['freshness_s'])
            ids = [r['route_id'] for r in outputs['search_transit_routes']['routes']]
            for name, args in [
                ('score_routes', {'route_ids': ids}),
                ('estimate_load', {'route_ids': ids, 'horizon_min': 30}),
                ('get_diversion_plan', {'event_id': 'evt_fixture_closed', 'demand': 500}),
            ]:
                response = await registry.call(name, args)
                self.assertTrue(response['ok'], response)
                outputs[name] = response['data']
                self.assertEqual(response['trace']['provenance'], response['data']['provenance'])
                self.assertEqual(response['trace']['freshness_s'], response['data']['freshness_s'])
            for name, value in outputs.items():
                with self.subTest(handler=name):
                    self.assertEqual(value['provenance'], 'simulated')
                    self.assertGreaterEqual(value['freshness_s'], 0)
                    json.dumps(value, allow_nan=False)
            self.assertEqual(outputs['search_transit_routes']['freshness_s'],
                             max(r['total']['freshness_s'] for r in outputs['search_transit_routes']['routes']))
            self.assertEqual(outputs['get_diversion_plan']['freshness_s'], outputs['search_transit_routes']['freshness_s'])
        asyncio.run(run())

    def test_every_handler_returns_registry_error_on_invalid_input(self):
        h = tools()
        ids = [r['route_id'] for r in search(h)]
        registry = build_default_registry(h.handlers())
        cases = [
            ('geocode_place', {'query': ''}),
            ('find_access_points', {'lat': None, 'lng': 114}),
            ('search_transit_routes', {'from': 'O', 'to': 'D', 'depart_at': 'not-a-date'}),
            ('score_routes', {'route_ids': ids, 'weights': {'time': -1}}),
            ('estimate_load', {'route_ids': ids, 'horizon_min': 0}),
            ('get_diversion_plan', {'event_id': 'evt_fixture_closed', 'demand': -1}),
        ]
        async def run():
            for name, args in cases:
                with self.subTest(handler=name):
                    response = await registry.call(name, args)
                    self.assertFalse(response['ok'])
                    self.assertEqual(response['error'], 'tool_unavailable')
        asyncio.run(run())

    def test_simulated_dataset_cannot_leak_mislabelled_real_children(self):
        network = read('network.synthetic.json')
        network['nodes'][0]['provenance'] = 'real'  # deliberate negative fixture
        network['lines'][0]['provenance'] = 'real'
        original = deepcopy(network)
        fares = {'SIM_00': {'fare_hkd': 4, 'provenance': 'real'}}
        h = tools(MappingDataAdapter(network, baseline_fare=12.5, fares=fares))
        self.assertEqual(h.geocode_place('O')['provenance'], 'simulated')
        self.assertTrue(all(row['provenance'] == 'simulated' for row in h.find_access_points(22, 114)))
        self.assertTrue(all(r['provenance'] == 'simulated' and all(l['provenance'] == 'simulated' for l in r['legs'])
                            for r in search(h)))
        self.assertEqual(h.engine.fares['SIM_00']['provenance'], 'simulated')
        self.assertEqual(network, original)

    def test_load_freshness_does_not_hide_stale_demand(self):
        demand = MappingDemandAdapter({}, source='stale_simulated_demand', provenance='simulated',
                                      freshness_s=99999, default_rate_per_hour=60)
        h = RouteHandlers(normalized(), demand_adapter=demand, observed_at=AT)
        ids = [r['route_id'] for r in search(h)]
        search_result = h.handlers()['search_transit_routes'](**{'from': 'O', 'to': 'D', 'depart_at': AT})
        self.assertEqual(search_result['freshness_s'], 99999)
        response = h.handlers()['estimate_load'](route_ids=ids, horizon_min=10)
        self.assertEqual(response['freshness_s'], 99999)
        self.assertTrue(all(row['freshness_s'] == 99999 for row in response['loads']))

    def test_unknown_and_stale_context_cannot_produce_load_or_score(self):
        h = tools()
        with self.assertRaises(DataUnavailable):
            h.score_routes([])
        routes = search(h)
        with self.assertRaises(DataUnavailable):
            h.estimate_load(['unknown_id'], 60)
        with self.assertRaises(ValueError):
            h.score_routes([routes[0]['route_id']] * 2)
        with self.assertRaises(DataUnavailable):
            h.get_diversion_plan('unpublished_event', 100)

    def test_actual_no_llm_orchestrator_consumes_route_owned_envelope(self):
        h = tools()
        service = NoLLMQueryService(build_default_registry(h.handlers()))
        result = asyncio.run(service.query(user_input='simulated fixture', origin='O', destination='D',
                                            depart_at=AT, profile_id='wheelchair',
                                            event_id='evt_fixture_closed', demand=1000))
        self.assertGreater(len(result['routes']), 0)
        self.assertTrue(all(call['ok'] for call in result['tool_calls']))
        self.assertTrue(all(leg['accessible'] is True for r in result['routes'] for leg in r['legs']))
        self.assertEqual(result['diversion']['provenance'], 'simulated')
        # AI owns final message and trace formatting; this test certifies its
        # calls into C-Route, not the separate public chat/trace acceptance gate.


if __name__ == '__main__':
    unittest.main()
