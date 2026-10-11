"""Refresh offline card fares and price scores from the executable fare policy.

Run from the repository root: python -m scripts.update_seed_fares
Keep path IDs and non-price reference fields stable for simulation consumers.
"""
import hashlib
import json
from pathlib import Path

from backend.app.engine import RouteEngine
from backend.app.engine.candidates import route_from_path, search_paths
from backend.app.engine.constraints import normalize_profile
from backend.app.engine.score import score_routes
from backend.app.graph.build import thaw

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / 'contracts/seed/routes.seed.json'
    bundle = json.loads(target.read_text(encoding='utf-8'))
    engine = RouteEngine.from_seed(events_path=ROOT / 'contracts/seed/event.seed.json')
    od = bundle['meta']['od']
    found = search_paths(engine.snapshots.current, od['origin'], od['destination'],
                         od['depart_at'], normalize_profile())
    paths = {'r_' + hashlib.sha256('|'.join(t.edge.id for t in path).encode()).hexdigest()[:16]: path
             for path in found.paths}
    fare_revision, fares = engine.fare_store.snapshot(thaw(engine.snapshots.network.source), od['depart_at'])
    fare_hash = hashlib.sha256(json.dumps(thaw(fares),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    for route in bundle['routes']:
        rebuilt = route_from_path(paths[route['route_id']], engine.snapshots.current,
                                  od['depart_at'], fares=fares)
        assert [(l['from'], l['to']) for l in route['legs']] == [(l['from'], l['to']) for l in rebuilt['legs']]
        for leg, computed in zip(route['legs'], rebuilt['legs']):
            leg['fare_hkd'] = computed['fare_hkd']
            leg['evidence'] = [e for e in leg['evidence'] if e.get('status') not in
                               ('simulated-fare-policy', 'official-adult-fare-policy')]
            leg['evidence'].append({'source': f'fare_database:r{fare_revision}', 'sha256': fare_hash,
                                    'fields': ['fare_hkd'], 'status': 'official-adult-fare-policy'})
        route['total']['fare_hkd'] = rebuilt['total']['fare_hkd']
        route['warnings'] = [w for w in route['warnings'] if '种子票价/区间上界/缺省票价' not in w]
        for w in rebuilt['warnings']:
            if ('票价' in w or '计费' in w) and w not in route['warnings']:
                route['warnings'].append(w)
        route['evidence'] = [e for e in route['evidence'] if e.get('source') != 'data/network/fares.json'
                             and not e.get('source','').startswith('fare_database')]
        route['evidence'].append({'source': f'fare_database:r{fare_revision}', 'sha256': fare_hash, 'freshness_s': 0})
    bundle['routes'] = score_routes(bundle['routes'], normalize_profile(), baseline_fare=engine.baseline_fare)
    bundle['meta'].pop('fare_policy', None)
    for picks in bundle['persona_top_picks']:
        if picks['persona'] == 'commuter':
            picks['top'] = [r['route_id'] for r in engine.query(od['origin'], od['destination'], od['depart_at'])[:3]]
            picks['reason'] = '仅使用模型可通行路径；时间和客流为模拟，票价来自官方成人收费表。'
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for route in bundle['routes']:
        print(f"{route['label']}: HK${route['total']['fare_hkd']:.2f}")


if __name__ == '__main__':
    main()
