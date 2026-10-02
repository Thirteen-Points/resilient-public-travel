"""Ordered provider/key failover with durable, redacted diagnostics."""
import hashlib
import json
import time
from .llm_network import public_https_open, ProviderHTTPError
from ..services.structure.llm_api_client import OpenAiCompatJsonClient
from ..ai.budget import BudgetExceeded, external_ai_allowed

def fingerprint(provider, key):
    return hashlib.sha256(json.dumps([provider['base_url'], provider['model'], key['value']]).encode()).hexdigest()

def error_category(exc):
    status = getattr(exc, 'status', getattr(exc, 'code', None))
    if status in (401, 403): return 'Authentication rejected. Check the key and account permissions.'
    if status == 429: return 'Rate limit or quota exceeded.'
    if status == 404: return 'Endpoint or model not found. Check the base URL and model.'
    if isinstance(exc, TimeoutError): return 'Request timed out.'
    if status: return 'Provider returned an HTTP error.'
    if isinstance(exc, ValueError): return 'Invalid response or blocked endpoint.'
    return 'Connection or response validation failed.'

class OrderedClient:
    def __init__(self, candidates, timeout, store, budget=None):
        self.candidates, self.timeout, self.store = candidates, timeout, store
        self.used = None
        self.errors = []
        self.budget = budget
        self.cached = False
    def generate_json(self, **kwargs):
        self.used = None
        self.cached = False
        if not external_ai_allowed():
            self.errors.append({'provider': 'none', 'key_id': 'none', 'message': 'External AI disabled by offline/startup configuration.'})
            raise RuntimeError('External AI disabled')
        deadline = time.monotonic() + min(kwargs['timeout_seconds'], self.timeout)
        for index, (name, provider, key) in enumerate(self.candidates):
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Provider chain timeout')
            remaining /= len(self.candidates) - index
            client = OpenAiCompatJsonClient(base_url=provider['base_url'], model=provider['model'], api_key=key['value'],
                opener=public_https_open, request_timeout_s=remaining)
            # Connection tests are always a real request; reusable extraction/
            # wording results are keyed by model, secret hash, schema and input.
            connection_test = 'ok' in kwargs['json_schema'].get('properties', {})
            cache_key = self.budget.cache_key(provider, key, kwargs) if self.budget else None
            cached = self.budget.cached(cache_key, name, provider['model']) if self.budget and not connection_test else None
            if cached is not None:
                self.used = {'provider': name, 'name': provider['name'], 'model': provider['model'], 'key_id': key['id']}
                self.cached = True
                return cached
            reservation = None
            try:
                if self.budget:
                    reservation = self.budget.reserve(name, provider, kwargs)
                output = client.generate_json(**{**kwargs, 'timeout_seconds': remaining})
                if kwargs['json_schema'].get('title') == 'StructuredEventDraft':
                    from ..services.structure.llm_structurer import StructuredEventDraft
                    StructuredEventDraft.model_validate(json.loads(output) if isinstance(output, str) else output)
                elif 'ok' in kwargs['json_schema'].get('properties', {}):
                    if json.loads(output).get('ok') is not True: raise ValueError('Invalid connection response')
                elif kwargs['json_schema'].get('title') == 'RouteWording':
                    from ..ai.schemas import validate_chat_response
                    wording = validate_chat_response(output, json.loads(kwargs['user_prompt'])['tool_results'])
                    if wording['tool_calls'] or not wording['message'].strip():
                        raise ValueError('Wording must contain text and must not schedule tools')
            except Exception as exc:
                if reservation:
                    self.budget.finish(*reservation, client.usage, 'failed')
                message = 'Model budget exhausted; deterministic fallback remains available.' if isinstance(exc, BudgetExceeded) else error_category(exc)
                self.errors.append({'provider': name, 'key_id': key['id'], 'message': message})
                if self.store: self.store.record_llm(name, provider, key, False, message, 'connection' if kwargs['json_schema'].get('title') != 'StructuredEventDraft' else 'structure')
                continue
            if reservation:
                self.budget.finish(*reservation, client.usage, 'success')
                if not connection_test:
                    self.budget.remember(cache_key, output)
            self.used = {'provider': name, 'name': provider['name'], 'model': provider['model'], 'key_id': key['id']}
            if self.store: self.store.record_llm(name, provider, key, True, 'Valid response received.', 'structure' if kwargs['json_schema'].get('title') == 'StructuredEventDraft' else 'connection')
            return output
        raise ValueError('All configured providers failed')
