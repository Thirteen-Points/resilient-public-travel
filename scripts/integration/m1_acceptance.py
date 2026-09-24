"""C-receipt M1 acceptance; no B publication endpoint or A UI is simulated.

Run: python -m scripts.integration.m1_acceptance --output-dir docs/acceptance/evidence/m1-baseline
Exit 1: failed executable check; 2: C checks passed, full-chain dependencies remain.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
from importlib.metadata import version
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from .checks import closed_crossings, load_json
from .module_bridge import ModuleBridge

ROOT = Path(__file__).resolve().parents[2]


def published_event(engine, details, depart_at):
    """Choose a used edge from actual routing output, not an assumed real line."""
    leg = next(leg for route in details['routes'] for leg in route['legs'] if leg['mode'] != 'WALK')
    edge = next(edge for edge in engine.snapshots.network.edges
                if edge.source == leg['from'] and edge.line == leg['line'])
    event = deepcopy(load_json(ROOT / 'backend/app/engine/fixtures/events.synthetic.json')['events'][0])
    event.update(event_id='m1_simulated_receipt', version=2, status='published',
                 line=edge.line, mode=edge.mode, published_at=depart_at, updated_at=depart_at, expires_at=None,
                 title='Simulated C-receipt closure', summary='Test injection, not a B publication',
                 provenance='simulated', reviewed_by='simulated-c-receipt-fixture', signals=[], audit_log=[])
    for factor in event['confidence_factors']:
        factor['note'] = 'Simulated test evidence; no actual authority or report'
    event['window'] = {'start': depart_at, 'end': None, 'end_confidence': 'unknown'}
    event['affected_segments'] = [{'from_node': edge.source, 'to_node': edge.target,
                                  'impact': 'closed', 'capacity_factor': 0}]
    event.pop('ui_state', None)
    return event


@contextmanager
def integrated_client(bridge):
    """Use the shipped application factory, with isolated real C services/SQLite."""
    from fastapi.testclient import TestClient
    from backend.app import main, runtime_config
    from backend.app.ai.handlers import build_engine_handlers
    from backend.app.ai.query import NoLLMQueryService
    from backend.app.ai.tools import build_default_registry
    from backend.app.sim.service import build_diversion_plan

    runtime = copy(main.runtime)
    runtime.engine, runtime.error, runtime.ai_error = bridge.engine, None, None
    runtime.ai_service = NoLLMQueryService(build_default_registry(
        build_engine_handlers(bridge.engine, build_diversion_plan)))
    # No production database, app-global engine, or source file is mutated.
    with tempfile.TemporaryDirectory(prefix='m1-receipt-') as directory:
        with patch.object(main, 'runtime', runtime), patch.object(
                runtime_config, 'settings', replace(runtime_config.settings, ai_enabled=False, offline_mode=True)):
            with TestClient(main.create_app(db_path=Path(directory) / 'signals.sqlite3')) as client:
                yield client


def http_observation():
    from backend.app.ai.llm_client import LLMClient
    bridge = ModuleBridge()
    request = {key: bridge.config[key] for key in ('origin', 'destination', 'depart_at')}
    details = bridge.query()
    event = published_event(bridge.engine, details, request['depart_at'])
    with patch.object(LLMClient, '_post', side_effect=AssertionError('LLM transport forbidden')) as transport:
        with integrated_client(bridge) as client:
            before = client.post('/api/routes/query', json=request)
            old_snapshot = client.get('/api/graph/snapshot').json()
            # This is the explicitly disclosed C receive boundary, NOT B's API.
            bridge.engine.snapshots.update_event(event)
            after = client.post('/api/routes/query', json=request)
            snapshot = client.get('/api/graph/snapshot').json()
            chat = client.post('/api/ai/chat', json={**request, 'message': 'Show simulated alternatives'})
            openapi = client.get('/openapi.json').json()
            required = {'/api/events/published': 'get', '/api/events/{id}/review': 'post',
                        '/api/stream/events': 'get'}
            mounted = {re.sub(r'\{[^}]+\}', '{}', path): methods
                       for path, methods in openapi.get('paths', {}).items()}
            missing = [f'{method.upper()} {path}' for path, method in required.items()
                       if method not in mounted.get(re.sub(r'\{[^}]+\}', '{}', path), {})]
            checks = {
                'http_queries_ok': before.status_code == after.status_code == 200,
                'snapshot_changed': old_snapshot['snapshot_id'] != snapshot['snapshot_id'],
                'routes_recomputed': {r['route_id'] for r in before.json()} != {r['route_id'] for r in after.json()},
                'closed_edge_absent': bool(after.json()) and not any(closed_crossings(r, bridge.network, [event]) for r in after.json()),
                'ai_off_query_ok': chat.status_code == 200 and chat.json().get('fallback') is True,
                'ai_matches_refreshed_routes': chat.json().get('routes') == after.json(),
                'no_llm_transport': transport.call_count == 0,
            }
            return {'scope': 'ASGI integrated app; event injected at C receive boundary',
                    'provenance': 'simulated', 'checks': checks,
                    'snapshot_before': old_snapshot, 'snapshot_after': snapshot,
                    'route_ids_before': [r['route_id'] for r in before.json()],
                    'route_ids_after': [r['route_id'] for r in after.json()],
                    'event': event, 'missing_b_endpoints': missing,
                    'mounted_paths': sorted(openapi.get('paths', {})), 'llm_transport_calls': transport.call_count}


def benchmark(samples):
    from backend.app.engine import RouteEngine
    from backend.app.graph.build import thaw
    od = load_json(ROOT / 'contracts/seed/routes.seed.json')['meta']['od']
    rows = []
    for dataset in ('synthetic', 'repository_seed'):
        observations = []
        for _ in range(samples):
            start = time.perf_counter()
            if dataset == 'synthetic':
                bridge = ModuleBridge()
                engine = bridge.engine
                query = {key: bridge.config[key] for key in ('origin', 'destination', 'depart_at')}
            else:
                engine = RouteEngine.from_seed(ROOT / 'contracts/seed/network.seed.json')
                query = {key: od[key] for key in ('origin', 'destination', 'depart_at')}
            before = engine.query_details(**query)
            cold = time.perf_counter() - start
            assert before['routes'], 'Cold query returned no candidates'
            start = time.perf_counter()
            cached = engine.query_details(**query)
            warm = time.perf_counter() - start
            assert cached == before and engine.cache.hits > 0
            event = published_event(engine, before, query['depart_at'])
            network = thaw(engine.snapshots.network.source)
            assert any(closed_crossings(route, network, [event]) for route in before['routes']), 'Vacuous closure fixture'
            start = time.perf_counter()
            changed = engine.snapshots.update_event(event)
            swap = time.perf_counter() - start
            after = engine.query_details(**query)
            refresh = time.perf_counter() - start
            assert changed.snapshot_id == after['graph_snapshot'] != before['graph_snapshot']
            assert after['routes'] and not any(closed_crossings(route, network, [event]) for route in after['routes'])
            assert {r['route_id'] for r in before['routes']} != {r['route_id'] for r in after['routes']}
            observations.append({'cold_build_query_s': cold, 'cached_query_s': warm,
                                 'snapshot_swap_s': swap, 'receipt_to_route_s': refresh,
                                 'routes_before': len(before['routes']), 'routes_after': len(after['routes'])})
        statistics = {}
        for metric in ('cold_build_query_s', 'cached_query_s', 'snapshot_swap_s', 'receipt_to_route_s'):
            ordered = sorted(row[metric] for row in observations)
            statistics[metric] = {'p50_s': ordered[math.ceil(samples * .5)-1],
                                  'p95_s': ordered[math.ceil(samples * .95)-1], 'max_s': max(ordered)}
        rows.append({'dataset': dataset, 'provenance': 'simulated', 'samples': observations, 'statistics': statistics,
                     'snapshot_under_2s': all(row['snapshot_swap_s'] < 2 for row in observations)})
    return {'scope': 'Single process serial engine timings, cold includes JSON/build/query; excludes process startup, B, A, HTTP and live-data validation',
            'percentile_method': 'nearest rank', 'datasets': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/acceptance/evidence/m1-baseline')
    parser.add_argument('--samples', type=int, default=25)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from .audit_all import fingerprints, run_command
    sources = fingerprints(ROOT)
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT), str(ROOT/'backend')]),
           'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'AI_ENABLED': 'false',
           'LLM_ENABLED': 'false', 'OFFLINE_MODE': 'true'}
    commands = [
        ('cross_module', ['-m', 'unittest', 'discover', '-s', 'tests/cross_module', '-v'], 1),
        ('consumer_contracts', ['-m', 'unittest', 'discover', '-s', 'tests/integration', '-v'], 40),
        ('owner_regression', ['-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--import-mode=importlib',
                              'backend/app/engine/tests', 'backend/tests'], 1),
        ('validate_data', ['scripts/validate_data.py'], None),
        ('preflight', ['scripts/preflight.py'], None),
    ]
    checks = []
    with tempfile.TemporaryDirectory(prefix='m1-pycache-') as cache:
        env['PYTHONPYCACHEPREFIX'] = cache
        checks.append(run_command('compile_backend', ['-m', 'compileall', '-q', 'backend/app'], None, None,
                                  ROOT, args.output_dir, env, 180))
        for name, command, minimum in commands:
            check = run_command(name, command, None, minimum, ROOT, args.output_dir, env, 180)
            checks.append(check)
            print(f"{check['status']} {name}: exit={check['returncode']} tests={check['tests']}", flush=True)
    evidence = {}
    for name, operation in [('http', http_observation), ('performance', lambda: benchmark(args.samples))]:
        try:
            evidence[name] = operation()
        except Exception as exc:
            evidence[name] = {'error': f'{type(exc).__name__}: {exc}'}
    after = fingerprints(ROOT)
    failed = (any(row['status'] != 'PASS' for row in checks) or sources != after or
              any('error' in value for value in evidence.values()) or
              not all(evidence.get('http', {}).get('checks', {}).values()) or
              not all(row['snapshot_under_2s'] for row in evidence.get('performance', {}).get('datasets', [])))
    report = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'generated_at': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
              'platform': platform.platform(), 'provenance': 'simulated', 'checks': checks, **evidence,
              'dependency_versions': {name: version(name) for name in ('fastapi', 'httpx', 'pytest', 'jsonschema')},
              'source_sha256': sources, 'end_source_sha256': after,
              'full_chain_status': 'BLOCKED: B delivery wiring and A live refresh not accepted; route PR/data refresh pending',
              'exit_code': 1 if failed else 2}
    (args.output_dir/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"M1 C baseline exit {report['exit_code']}; full-chain acceptance remains pending")
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
