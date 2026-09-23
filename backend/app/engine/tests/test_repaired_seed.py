"""The accepted route cards are computed simulated paths, never legacy facts."""
import json
import unittest
from backend.app.engine.tests.test_c_route import ROOT
from scripts.integration.checks import check_route, closed_crossings


class RepairedSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads((ROOT/'contracts/seed/routes.seed.json').read_text(encoding='utf-8'))
        cls.network=json.loads((ROOT/'contracts/seed/network.seed.json').read_text(encoding='utf-8'))
        cls.events=json.loads((ROOT/'contracts/seed/event.seed.json').read_text(encoding='utf-8'))['events']

    def test_ten_stable_distinct_cards_satisfy_contract_and_closed_boundaries(self):
        routes=self.bundle['routes']
        self.assertEqual(len(routes),10)
        self.assertEqual(len({r['route_id'] for r in routes}),10)
        self.assertEqual(len({tuple((l['mode'],l.get('line'),l['from'],l['to']) for l in r['legs']) for r in routes}),10)
        for row in routes:
            self.assertFalse(row['route_id'].startswith('r_seed_'))
            self.assertEqual(check_route(row,self.network,'TAW','ADM'),[])
            self.assertEqual(closed_crossings(row,self.network,self.events),[])
            self.assertEqual(row['provenance'],'simulated')
            self.assertAlmostEqual(row['total']['walk_m'],sum(l['walk_m'] for l in row['legs']))
            self.assertAlmostEqual(row['total']['fare_hkd'],sum(l['fare_hkd'] for l in row['legs']))
            self.assertAlmostEqual(row['score'],sum(b['contribution'] for b in row['score_breakdown']))
            self.assertAlmostEqual(sum(b['weight'] for b in row['score_breakdown']),1)
            for leg in row['legs']:
                self.assertEqual(leg['provenance'],'simulated')
                self.assertTrue(leg['evidence'])
                self.assertNotIn('travel_s',leg)
                if leg['mode']=='WALK': self.assertNotIn('headway_s',leg)
                else: self.assertGreater(leg['headway_s'],0)

    def test_persona_picks_resolve_and_do_not_pad_wheelchair_top3(self):
        by_id={r['route_id']:r for r in self.bundle['routes']}
        firsts={}
        for persona in self.bundle['persona_top_picks']:
            self.assertTrue(set(persona['top'])<=by_id.keys())
            if persona['top']: firsts[persona['persona']]=persona['top'][0]
            if persona['persona']=='wheelchair':
                self.assertEqual(len(persona['top']),3)
                for rid in persona['top']:
                    self.assertEqual(check_route(by_id[rid],self.network,'TAW','ADM',wheelchair=True),[])
                    self.assertLessEqual(by_id[rid]['total']['transfers'],2)
        self.assertIn('commuter',firsts)
        self.assertIn('wheelchair',firsts)

    def test_all_seed_ids_follow_current_directed_edge_fingerprints(self):
        import hashlib
        from backend.app.engine import RouteEngine
        from backend.app.engine.constraints import normalize_profile
        from backend.app.engine.candidates import search_paths, route_from_path
        engine=RouteEngine.from_seed(events_path=ROOT/'contracts/seed/event.seed.json')
        at=self.bundle['meta']['od']['depart_at']
        found=search_paths(engine.snapshots.current,'TAW','ADM',at,normalize_profile())
        paths={'r_'+hashlib.sha256('|'.join(t.edge.id for t in path).encode()).hexdigest()[:16]:path for path in found.paths}
        network_bytes=(ROOT/'contracts/seed/network.seed.json').read_bytes().replace(b'\r\n',b'\n')
        digest=hashlib.sha256(network_bytes).hexdigest()
        for route in self.bundle['routes']:
            self.assertIn(route['route_id'],paths)
            rebuilt=route_from_path(paths[route['route_id']],engine.snapshots.current,at,fares=engine.fares)
            signature=lambda r:[(l['mode'],l.get('line'),l['from'],l['to']) for l in r['legs']]
            self.assertEqual(signature(route),signature(rebuilt))
            sources=[x for x in route['evidence'] if x.get('source')=='contracts/seed/network.seed.json']
            self.assertTrue(sources)
            self.assertTrue(all(x['sha256']==digest for x in sources))

    def test_invalid_legacy_cards_are_archived_not_reused_under_old_ids(self):
        review=json.loads((ROOT/'backend/app/engine/reports/route-seed-repair-review.json').read_text(encoding='utf-8'))
        self.assertEqual(len(review['old_cards']),8)
        self.assertTrue(set(review['old_id_to_new_path_id'].values()) <= {r['route_id'] for r in self.bundle['routes']})
        self.assertTrue(all(l.get('line') not in ('BUS_982X','GMB_481B','982X','481B')
                            for r in self.bundle['routes'] for l in r['legs']))
        self.assertTrue(any(r['total']['walk_m']>800 for r in self.bundle['routes']))


if __name__=='__main__': unittest.main()
