"""Ordered provider/key failover with durable, redacted diagnostics."""
import hashlib
import json
import time
from .llm_network import public_https_open, ProviderHTTPError
from ..services.structure.llm_api_client import OpenAiCompatJsonClient

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
    def __init__(self, candidates, timeout, store):
        self.candidates, self.timeout, self.store = candidates, timeout, store
        self.used = None
        self.errors = []
    def generate_json(self, **kwargs):
        deadline = time.monotonic() + min(kwargs['timeout_seconds'], self.timeout)
        for index, (name, provider, key) in enumerate(self.candidates):
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Provider chain timeout')
            remaining /= len(self.candidates) - index
            client = OpenAiCompatJsonClient(base_url=provider['base_url'], model=provider['model'], api_key=key['value'],
                opener=public_https_open, request_timeout_s=remaining)
            try:
                output = client.generate_json(**{**kwargs, 'timeout_seconds': remaining})
                if kwargs['json_schema'].get('title') == 'StructuredEventDraft':
                    from ..services.structure.llm_structurer import StructuredEventDraft
                    StructuredEventDraft.model_validate(json.loads(output) if isinstance(output, str) else output)
                elif 'ok' in kwargs['json_schema'].get('properties', {}):
                    if json.loads(output).get('ok') is not True: raise ValueError('Invalid connection response')
            except Exception as exc:
                message = error_category(exc)
                self.errors.append({'provider': name, 'key_id': key['id'], 'message': message})
                if self.store: self.store.record_llm(name, provider, key, False, message, 'connection' if kwargs['json_schema'].get('title') != 'StructuredEventDraft' else 'structure')
                continue
            self.used = {'provider': name, 'name': provider['name'], 'model': provider['model'], 'key_id': key['id']}
            if self.store: self.store.record_llm(name, provider, key, True, 'Valid response received.', 'structure' if kwargs['json_schema'].get('title') == 'StructuredEventDraft' else 'connection')
            return output
        raise ValueError('All configured providers failed')
