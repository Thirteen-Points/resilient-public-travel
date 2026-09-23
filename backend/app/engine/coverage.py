"""Dynamic directed-OD audit. Counts only; never substitutes reference routes."""
import argparse
import json
from itertools import permutations
from collections.abc import Mapping
from pathlib import Path

from ..graph.build import timestamp
from .service import RouteEngine

CORRIDOR_NODES = ('TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM')


def coverage_matrix(engine, depart_at, *, nodes=CORRIDOR_NODES, profile=None, target=10):
    """Use the same dynamic RouteCandidate generation as the public query.

    Structural observations are not proof of causal attribution for every missing
    candidate. No network edits, seed-route lookup, or synthesized connections.
    """
    nodes = tuple(nodes)
    network = engine.snapshots.current.network
    if len(set(nodes)) != len(nodes) or set(nodes) - set(network.nodes):
        raise ValueError('Coverage nodes must be unique modelled node IDs')
    at = timestamp(depart_at)
    gaps = {}
    for node in nodes:
        outgoing = network.adjacency[node]
        incoming = [edge for edge in network.edges if edge.target == node]
        access = {'out': any(e.mode == 'WALK' for e in outgoing),
                  'in': any(e.mode == 'WALK' for e in incoming)}
        lines = sorted({e.line for e in (*outgoing, *incoming) if e.mode != 'WALK'})
        gaps[node] = {'walking_access': access, 'transit_lines': lines,
                      'single_line_dependency': len(lines) == 1}
    unavailable = []
    for line in network.source.get('lines', ()):
        edges = [edge for edge in network.edges if edge.line == line['id']]
        if not edges:
            unavailable.append({'line': line['id'], 'reason': 'excluded_or_unresolved'})
        elif not any(network.boarding(edge, at) for edge in edges):
            unavailable.append({'line': line['id'], 'reason': 'no_service_at_departure'})
    rows = []
    for origin, destination in permutations(nodes, 2):
        result = engine.query_details(origin, destination, depart_at, profile, limit=target)
        routes = result['routes']
        stats = result['search_statistics']
        reasons = []
        if stats['shortfall']:
            if stats['diversity_filtered']:
                reasons.append('DIVERSITY_OR_CANDIDATE_LIMIT')
            if stats['feasible_paths'] < target:
                reasons.append('FEWER_FEASIBLE_PATHS_THAN_TARGET')
            if stats['bounded']:
                reasons.append('SEARCH_BUDGET')
            if not gaps[origin]['walking_access']['out']:
                reasons.append('NO_MODELLED_ORIGIN_WALK_ACCESS')
            if not gaps[destination]['walking_access']['in']:
                reasons.append('NO_MODELLED_DESTINATION_WALK_ACCESS')
            if any(gaps[n]['single_line_dependency'] for n in (origin, destination)):
                reasons.append('SINGLE_LINE_ENDPOINT_DEPENDENCY')
            if unavailable:
                reasons.append('NETWORK_HAS_UNAVAILABLE_SERVICES')
            if profile and profile.get('mobility') in ('wheelchair', 'reduced'):
                reasons.append('MOBILITY_FILTERS_APPLIED')
            if engine.snapshots.current.events:
                reasons.append('EVENT_SNAPSHOT_APPLIED')
        rows.append({'origin': origin, 'destination': destination, **stats,
                     'modes': sorted({leg['mode'] for r in routes for leg in r['legs']}),
                     'reasons': reasons, 'diagnostics': result['diagnostics']})
    return {'nodes': list(nodes), 'depart_at': at.isoformat(), 'profile': profile or {},
            'graph_snapshot': engine.snapshots.current.snapshot_id, 'target_per_od': target,
            'od_count': len(rows), 'covered': sum(row['selected'] > 0 for row in rows),
            'at_target': sum(row['selected'] == target for row in rows),
            'selected_total': sum(row['selected'] for row in rows),
            'endpoint_topology': gaps, 'unavailable_services': unavailable, 'rows': rows,
            'provenance': 'simulated',
            'note': 'Counts are model outputs, not verified operational coverage. Structural gaps are observations, not isolated causal experiments.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depart-at', required=True)
    parser.add_argument('--events')
    parser.add_argument('--wheelchair', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = coverage_matrix(RouteEngine.from_seed(events_path=args.events), args.depart_at,
                             profile={'mobility': 'wheelchair'} if args.wheelchair else None)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + '\n', encoding='utf-8')
    else:
        print(payload)


if __name__ == '__main__':
    main()
