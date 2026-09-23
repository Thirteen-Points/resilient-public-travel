"""Synthetic top3 soft fallback and unknown-data safety at public boundaries."""
import json
import unittest
from fastapi.testclient import TestClient
from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.engine.candidates import search_paths,select_diverse,intermediate_nodes,jaccard
from backend.app.engine.constraints import normalize_profile
from backend.app.engine.tests.test_c_route import ROOT, AT, line, make_engine
from backend.app.graph import SnapshotStore,build_graph


def fixture_engine(blocked=False):
    ids=['O','A','B','C','E','F','G','H','J','Y','U','V','D']
    data={'meta':{'provenance':'simulated','built_at':AT},
          'nodes':[{'id':n,'lat':22,'lng':114,'accessible':True,'provenance':'simulated'} for n in ids],
          'lines':[line(id='L1',stops=['O','A','B','C','Y'],bidirectional=False),
                   line(id='L2',stops=['O','E','F','G','H','Y'],bidirectional=False),
                   line(id='L3',stops=['O','J','A','B','C','Y'],bidirectional=False),
                   line(id='MAIN',stops=['Y','U','V','D'],bidirectional=False)],'walk_links':[]}
    if blocked:
        next(n for n in data['nodes'] if n['id']=='J')['accessible']='partial'
    return make_engine(SnapshotStore(build_graph(data)))


class WheelchairTopThreeTests(unittest.TestCase):
    profile={'mobility':'wheelchair','max_transfers':1,'max_walk_m':400}

    def test_synthetic_public_top3_warns_high_overlap_without_safety_relaxation(self):
        engine=fixture_engine();client=TestClient(create_app(engine))
        response=client.post('/api/routes/query',json={'origin':'O','destination':'D','depart_at':AT,'profile':self.profile})
        self.assertEqual(response.status_code,200)
        routes=response.json();self.assertEqual(len(routes),3)
        added=next(r for r in routes if r['legs'][0]['line']=='L3')
        self.assertTrue(any('局部回退' in w and 'Y' in w and '高度重合' in w and '0.857' in w for w in added['warnings']))
        for route in routes:
            self.assertLessEqual(route['total']['walk_m'],400)
            self.assertLessEqual(route['total']['transfers'],2)
            self.assertTrue(all(l['accessible'] is True and l['mode']!='MINIBUS' for l in route['legs']))

    def test_original_diversity_and_other_profiles_are_unchanged(self):
        engine=fixture_engine()
        found=search_paths(engine.snapshots.current,'O','D',AT,normalize_profile(self.profile))
        self.assertEqual(len(found.paths),3)
        self.assertEqual(len(select_diverse(found.paths)),2)
        self.assertGreater(max(jaccard(intermediate_nodes(p),intermediate_nodes(q))
                              for i,p in enumerate(found.paths) for q in found.paths[i+1:]),.7)
        self.assertEqual(len(engine.query('O','D',AT)),2)
        self.assertEqual(len(engine.query('O','D',AT,{'mobility':'reduced','max_transfers':1})),2)

    def test_fallback_respects_query_limit_and_tighter_hard_constraints(self):
        engine=fixture_engine()
        self.assertEqual(len(engine.query('O','D',AT,self.profile,limit=2)),2)
        self.assertEqual(engine.query('O','D',AT,{**self.profile,'max_transfers':0}),[])
        routes=fixture_engine(blocked=True).query('O','D',AT,self.profile)
        self.assertEqual(len(routes),2)
        self.assertTrue(all(r['legs'][0]['line']!='L3' for r in routes))

    def test_current_seed_unknown_endpoints_use_default_policy_and_picks_match_api(self):
        engine=RouteEngine.from_seed(events_path=ROOT/'contracts/seed/event.seed.json')
        self.assertIsNot(engine.snapshots.network.nodes['TAW']['accessible'],True)
        self.assertIsNot(engine.snapshots.network.nodes['ADM']['accessible'],True)
        client=TestClient(create_app(engine))
        policy=json.loads((ROOT/'backend/app/engine/fixtures/seed_policy.json').read_text(encoding='utf-8'))
        seed=json.loads((ROOT/'contracts/seed/routes.seed.json').read_text(encoding='utf-8'))
        for persona in seed['persona_top_picks']:
            result=client.post('/api/routes/query',json={'origin':'TAW','destination':'ADM','depart_at':AT,
                                                       'profile':policy['profiles'][persona['persona']]}).json()
            self.assertEqual(persona['top'],[r['route_id'] for r in result[:3]])
            if persona['persona']=='wheelchair':
                self.assertTrue(result)
                self.assertTrue(all(leg['accessible'] and leg['mode'] != 'MINIBUS'
                                    for route in result for leg in route['legs']))


if __name__=='__main__':unittest.main()
