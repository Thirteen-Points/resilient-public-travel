"""Exercise paid-request accounting at the real runtime boundary, no network."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.budget import BudgetExceeded, ModelBudget
from backend.app.admin.llm_runtime import OrderedClient
from backend.app.services.structure.llm_api_client import OpenAiCompatJsonClient
from backend.app.main import create_app
from backend.app.ai.handlers import build_engine_handlers
from backend.app.ai.tools import build_default_registry
from backend.app.engine.service import RouteEngine
from backend.app.sim.service import build_diversion_plan

PROVIDER = {'base_url': 'https://api.deepseek.com', 'model': 'deepseek-flash', 'name': 'DeepSeek'}
KEY = {'id': 'test', 'value': 'never-a-real-secret'}
REQUEST = {'system_prompt': 'Return JSON.', 'user_prompt': 'Test',
           'json_schema': {'type': 'object'}, 'timeout_seconds': 5}


@pytest.fixture
def model_env(monkeypatch):
    monkeypatch.setenv('OFFLINE_MODE', 'false')
    monkeypatch.delenv('AI_DISABLE_EXTERNAL', raising=False)
    monkeypatch.setenv('AI_BUDGET_CNY', '50')


def test_schema_failure_and_provider_cache_usage_are_billed(tmp_path, monkeypatch, model_env):
    from backend.app.admin.llm_runtime import public_https_open
    budget = ModelBudget(tmp_path/'usage.sqlite3')
    replies = [{'choices': [{'message': {'content': 'invalid JSON'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'prompt_cache_hit_tokens': 80}}]
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(replies.pop()).encode()
    monkeypatch.setattr('backend.app.admin.llm_runtime.public_https_open', lambda *a, **k: Reply())
    client = OrderedClient([('deepseek', PROVIDER, KEY)], 5, None, budget)
    with pytest.raises(ValueError): client.generate_json(**REQUEST)
    summary = budget.summary()
    assert summary['calls'] == 1 and summary['estimated_calls'] == 0
    assert summary['spent_cny'] == pytest.approx((20*2+80*.04+50*8)/1e6, abs=1e-6)
    assert summary['provider_cache_hit_tokens'] == 80


def test_cache_model_key_isolation_and_restart_budget(tmp_path, monkeypatch, model_env):
    budget = ModelBudget(tmp_path/'usage.sqlite3')
    seen = []
    def fake(self, **kwargs):
        seen.append(self.model)
        self.usage = {'prompt_tokens': 10, 'completion_tokens': 20}
        return '{"message":"工具已计算路线。","tool_calls":[]}'
    monkeypatch.setattr(OpenAiCompatJsonClient, 'generate_json', fake)
    client = OrderedClient([('deepseek', PROVIDER, KEY)], 5, None, budget)
    client.generate_json(**REQUEST)
    second = OrderedClient([('deepseek', PROVIDER, KEY)], 5, None, budget)
    assert second.generate_json(**REQUEST) and second.cached
    assert len(seen) == 1 and budget.summary()['local_cache_hits'] == 1
    changed = {**PROVIDER, 'model': 'another-model'}
    OrderedClient([('deepseek', changed, KEY)], 5, None, budget).generate_json(**REQUEST)
    assert len(seen) == 2
    recreated = ModelBudget(budget.path)
    assert recreated.summary() == budget.summary()
    assert b'never-a-real-secret' not in budget.path.read_bytes()
    assert b'Test' not in budget.path.read_bytes()


def test_concurrent_reservations_cannot_exceed_budget_and_failure_retains_cost(tmp_path, monkeypatch, model_env):
    monkeypatch.setenv('AI_BUDGET_CNY', '1.5')
    provider = {**PROVIDER, 'model': 'custom'}
    budget = ModelBudget(tmp_path/'usage.sqlite3')
    def reserve():
        try: return budget.reserve('custom', provider, REQUEST)
        except BudgetExceeded: return None
    with ThreadPoolExecutor(2) as pool:
        reservations = list(pool.map(lambda _: reserve(), range(2)))
    assert sum(item is not None for item in reservations) == 1
    reservation = next(item for item in reservations if item)
    budget.finish(*reservation, None, 'timeout')
    assert ModelBudget(budget.path).summary()['spent_cny'] == 1
    assert budget.summary()['estimated_calls'] == 1


@pytest.mark.parametrize('mode', ['OFFLINE_MODE', 'AI_DISABLE_EXTERNAL'])
def test_startup_override_blocks_actual_client(tmp_path, monkeypatch, model_env, mode):
    monkeypatch.setenv(mode, 'true')
    monkeypatch.setattr(OpenAiCompatJsonClient, 'generate_json', lambda *a, **k: pytest.fail('external request attempted'))
    client = OrderedClient([('deepseek', PROVIDER, KEY)], 5, None, ModelBudget(tmp_path/'usage.sqlite3'))
    with pytest.raises(RuntimeError): client.generate_json(**REQUEST)
    assert client.budget.summary()['calls'] == 0


def test_chat_uses_real_model_boundary_but_preserves_computed_routes(tmp_path, monkeypatch, model_env):
    monkeypatch.setenv('AI_ENABLED', 'true')
    monkeypatch.setenv('DEEPSEEK_API_KEY', KEY['value'])
    for name in ('ADMIN_USERNAME', 'ADMIN_PASSWORD_HASH', 'ADMIN_ENCRYPTION_KEY'):
        monkeypatch.delenv(name, raising=False)
    calls = []
    def fake(self, **kwargs):
        calls.append(self.model)
        self.usage = {'prompt_tokens': 100, 'completion_tokens': 20}
        return '{"message":"请查看工具计算的路线及模拟运力说明。","tool_calls":[]}'
    monkeypatch.setattr(OpenAiCompatJsonClient, 'generate_json', fake)
    app = create_app(db_path=tmp_path/'events.sqlite3')
    payload = {'message': '解释路线', 'origin': 'TAW', 'destination': 'ADM',
               'depart_at': '2026-10-02T08:20:00+08:00', 'profile_id': 'wheelchair'}
    with TestClient(app) as client:
        actual = client.post('/api/ai/chat', json=payload)
        assert actual.status_code == 200, actual.text
        body = actual.json()
        assert not body['fallback'] and body['llm_used']['model'] == 'deepseek-flash'
        assert body['routes'] == body['tool_calls'][0]['data']['routes']
        assert all(leg['mode'] != 'MINIBUS' for route in body['routes'] for leg in route['legs'])
        assert app.state.llm_budget.summary()['spent_cny'] > 0
        monkeypatch.setenv('AI_BUDGET_CNY', '0')
        # Different wording avoids a free local cache hit, which remains allowed.
        payload['message'] = '再次解释路线'
        fallback = client.post('/api/ai/chat', json=payload).json()
        assert fallback['fallback'] and fallback['routes']
        assert len(calls) == 1


def test_all_nine_tools_and_preferences_use_existing_services():
    engine = RouteEngine.from_seed()
    registry = build_default_registry(build_engine_handlers(engine, build_diversion_plan))
    async def exercise():
        parsed = await registry.call('parse_user_preference', {'text': '轮椅，别太贵'})
        routes = await registry.call('search_transit_routes', {'from': 'TAW', 'to': 'ADM',
            'depart_at': '2026-10-02T08:20:00+08:00', 'profile_id': 'wheelchair'})
        explained = await registry.call('explain_route', {'route_id': routes['data']['routes'][0]['route_id']})
        events = await registry.call('get_published_events', {'at': '2026-10-02T08:20:00+08:00'})
        malformed = await registry.call('get_published_events', '[1,2]')
        return parsed, routes, explained, events, malformed
    parsed, routes, explained, events, malformed = asyncio.run(exercise())
    assert parsed['data']['patch']['mobility'] == 'wheelchair'
    assert explained['ok'] and explained['data']['score_breakdown']
    assert events['ok'] and all(e['status'] == 'published' for e in events['data']['events'])
    assert malformed['error'] == 'invalid_arguments'
    assert routes['data']['routes'] == engine.query('TAW', 'ADM', '2026-10-02T08:20:00+08:00',
        dict(engine.routing_data.profiles['wheelchair']))


def test_environment_requests_have_separate_diagnostics_and_shared_budget(tmp_path, monkeypatch, model_env):
    from backend.app.ai.runtime import configured_client
    monkeypatch.setenv('AI_ENABLED', 'true')
    monkeypatch.setenv('DEEPSEEK_API_KEY', KEY['value'])
    for name in ('ADMIN_USERNAME', 'ADMIN_PASSWORD_HASH', 'ADMIN_ENCRYPTION_KEY'):
        monkeypatch.delenv(name, raising=False)
    app = create_app(db_path=tmp_path/'events.sqlite3')
    with TestClient(app):
        first, second = configured_client(app), configured_client(app)
        assert first is not second and first.budget is second.budget
        first.errors.append({'message': 'first request error'})
        first.used = {'provider': 'first'}
        assert second.errors == [] and second.used is None


def test_invalid_wording_never_cached_and_tries_next_provider(tmp_path, monkeypatch, model_env):
    from backend.app.ai.schemas import CHAT_RESPONSE_SCHEMA
    budget = ModelBudget(tmp_path/'usage.sqlite3')
    seen = []
    def fake(self, **kwargs):
        seen.append(self.api_key)
        self.usage = {'prompt_tokens': 10, 'completion_tokens': 10}
        return ('{"message":"","tool_calls":[]}' if self.api_key == KEY['value']
                else '{"message":"工具路线已就绪。","tool_calls":[]}')
    monkeypatch.setattr(OpenAiCompatJsonClient, 'generate_json', fake)
    client = OrderedClient([('deepseek', PROVIDER, KEY), ('deepseek', PROVIDER, {**KEY, 'value': 'backup-test'})], 5, None, budget)
    request = {**REQUEST, 'json_schema': {**CHAT_RESPONSE_SCHEMA, 'title': 'RouteWording'},
               'user_prompt': json.dumps({'tool_results': []})}
    assert json.loads(client.generate_json(**request))['message']
    assert seen == [KEY['value'], 'backup-test']
    assert budget.summary()['calls'] == 2 and not client.cached
