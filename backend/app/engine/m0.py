"""C-Route-only M0 seed consumer audit and deterministic demo evidence.

This is deliberately not a shared JSON Schema or a full M0 acceptance gate.
Reference routes/simulation are inspected, never used as executable route truth.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from ..graph.adapter import SeedDataAdapter, mark_simulated
from ..graph.build import timestamp
from .service import RouteEngine

SEEDS = ('network.seed.json', 'event.seed.json', 'routes.seed.json', 'sim.seed.json')
ROOT = Path(__file__).resolve().parents[3]


def _reject_constant(value):
    raise ValueError(f'Non-finite JSON number: {value}')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_seeds(seed_dir):
    """Read each complete document strictly; no rewriting of shared fixtures."""
    folder = Path(seed_dir)
    return {name: json.loads((folder / name).read_text(encoding='utf-8'),
                             parse_constant=_reject_constant, object_pairs_hook=_unique_object) for name in SEEDS}


def _labels(value):
    if isinstance(value, dict):
        return ([value['provenance']] if 'provenance' in value else []) + [p for v in value.values() for p in _labels(v)]
    if isinstance(value, list):
        return [p for v in value for p in _labels(v)]
    return []


def inspect_seeds(seed_dir):
    seed_dir = Path(seed_dir)
    documents = load_seeds(seed_dir)
    errors, findings = [], []
    expected = {
        'network.seed.json': {'meta': dict, 'nodes': list, 'lines': list, 'walk_links': list},
        'event.seed.json': {'meta': dict, 'events': list, 'signals': list},
        'routes.seed.json': {'meta': dict, 'routes': list, 'persona_top_picks': list},
        'sim.seed.json': {'meta': dict, 'population': int, 'baseline': dict, 'guided': dict, 'delta': dict},
    }
    for name, document in documents.items():
        for key, kind in expected[name].items():
            if not isinstance(document, dict) or type(document.get(key)) is not kind:
                errors.append(f'{name}: {key} must be {kind.__name__}')
        if 'real' in _labels(document):
            findings.append({'code': 'SEED_REAL_LABEL', 'file': name,
                             'detail': 'Unverified reference labels are present; runtime seed adapter downgrades copies to simulated'})
    if not errors:
        network, events, routes, sim = (documents[n] for n in SEEDS)
        nodes = {n['id'] for n in network['nodes']}
        route_ids = {r['route_id'] for r in routes['routes']}
        for line in network['lines']:
            missing = sorted(set(line['stops']) - nodes)
            if missing:
                findings.append({'code': 'UNMODELLED_NODE', 'file': SEEDS[0], 'line': line['id'], 'nodes': missing})
        for route in routes['routes']:
            rid = route['route_id']
            if any('travel_s' in leg and 'in_vehicle_s' not in leg for leg in route['legs']):
                findings.append({'code': 'LEGACY_TRAVEL_FIELD', 'file': SEEDS[2], 'route_id': rid})
            if 'evidence' not in route:
                findings.append({'code': 'MISSING_ROUTE_EVIDENCE', 'file': SEEDS[2], 'route_id': rid})
            if abs(route['score'] - sum(row['contribution'] for row in route['score_breakdown'])) > 1e-8:
                findings.append({'code': 'REFERENCE_SCORE_NOT_REPRODUCIBLE', 'file': SEEDS[2], 'route_id': rid})
        for picks in routes['persona_top_picks']:
            if set(picks['top']) - route_ids:
                errors.append(f"Unknown persona route references: {picks['profile_id']}")
            if picks.get('persona') == 'wheelchair':
                for route in routes['routes']:
                    if route['route_id'] in picks['top'] and (route['total']['walk_m'] > 400 or
                            any(leg['mode'] == 'MINIBUS' or leg['accessible'] is not True for leg in route['legs'])):
                        findings.append({'code': 'REFERENCE_WHEELCHAIR_CONFLICT', 'file': SEEDS[2], 'route_id': route['route_id']})
        if sim['meta'].get('event_ref') not in {e['event_id'] for e in events['events']}:
            errors.append('sim.seed.json: unknown event_ref')
        for policy in ('baseline', 'guided'):
            for row in sim[policy].get('route_load', sim[policy].get('shares', [])):
                if row['route_id'] not in route_ids:
                    errors.append(f"sim.seed.json: unknown route {row['route_id']}")
        if sim['meta'].get('placeholder'):
            findings.append({'code': 'SIM_PLACEHOLDER', 'file': SEEDS[3],
                             'detail': 'Read for UI shape only; never treat these numbers as measured/recomputed simulation'})
    schemas = sorted(p.name for p in (seed_dir.parent / 'schemas').glob('*.json'))
    return {'provenance': 'simulated', 'consumer_read_pass': not errors, 'consumer_errors': errors,
            'schema_validation': 'unavailable' if not schemas else 'not_executed_by_this_consumer_audit',
            'full_m0_accepted': False, 'findings': findings,
            'files': [{'name': name, 'sha256': hashlib.sha256((seed_dir / name).read_bytes()).hexdigest(),
                       'read': True, 'raw_provenance_labels': sorted(set(_labels(documents[name])))} for name in SEEDS]}


def _closed_legs(routes, engine, at):
    """Expand merged ride legs to modelled segments at this static demo instant."""
    network = engine.snapshots.network
    lines = {row['id']: row for row in network.source['lines']}
    closed = {e.id for e in network.edges if engine.snapshots.current.impact(e, timestamp(at))[0] == 0}
    violations = []
    for route in routes:
        for leg in route['legs']:
            if leg['mode'] == 'WALK':
                continue
            order = lines[leg['line']]['stops']
            a, b = order.index(leg['from']), order.index(leg['to'])
            indices = list(range(a, b + (1 if b > a else -1), 1 if b > a else -1))
            if any(f"{leg['line']}:{order[x]}>{order[y]}" in closed for x, y in zip(indices, indices[1:])):
                violations.append(route['route_id'])
    return violations


def demo_evidence(seed_dir=None):
    seed_dir = Path(seed_dir or ROOT / 'contracts/seed')
    policy = json.loads((Path(__file__).parent / 'fixtures/seed_policy.json').read_text(encoding='utf-8'))
    request = deepcopy(policy['query'])
    engine = RouteEngine.from_adapter(SeedDataAdapter(seed_dir / SEEDS[0]))
    baseline = engine.query(**request)
    events = mark_simulated(load_seeds(seed_dir)[SEEDS[1]])['events']
    engine.snapshots.replace_events(events)
    affected = engine.query(**request)
    repeated = engine.query(**request)
    wheelchair = engine.query(**request, profile=policy['profiles']['wheelchair'])
    checks = {
        'basic_query': bool(baseline),
        'published_closure_present': bool(engine.snapshots.current.describe(request['depart_at'])['affected_edges']),
        'closed_segments_excluded': bool(affected) and not _closed_legs(affected, engine, request['depart_at']),
        'wheelchair_accessible': bool(wheelchair) and all(r['total']['walk_m'] <= 400 and
            all(leg['accessible'] is True and leg['mode'] != 'MINIBUS' for leg in r['legs']) for r in wheelchair),
        'stable_route_ids': [r['route_id'] for r in affected] == [r['route_id'] for r in repeated],
        'simulated_results': all(r['provenance'] == 'simulated' and
            all(leg['provenance'] == 'simulated' for leg in r['legs']) for r in baseline + affected + wheelchair),
    }
    return {'provenance': 'simulated', 'request': request, 'checks': checks,
            'counts': {'baseline': len(baseline), 'closed': len(affected), 'wheelchair': len(wheelchair)},
            'snapshot': engine.snapshots.current.describe(request['depart_at']),
            'public_response_sample': affected[:3], 'wheelchair_route_ids': [r['route_id'] for r in wheelchair],
            'reference_routes_used_for_search': False, 'placeholder_sim_used_as_result': False}


def collect(seed_dir=None):
    seed_dir = Path(seed_dir or ROOT / 'contracts/seed')
    report = {'seed_audit': inspect_seeds(seed_dir), 'demo': demo_evidence(seed_dir)}
    report['route_m0_prework_pass'] = report['seed_audit']['consumer_read_pass'] and all(report['demo']['checks'].values())
    return report


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed-dir', type=Path, default=ROOT / 'contracts/seed')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = collect(args.seed_dir)
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding='utf-8')
    else:
        sys.stdout.reconfigure(encoding='utf-8')
        print(raw, end='')
    return 0 if result['route_m0_prework_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
