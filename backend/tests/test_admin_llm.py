"""Custom LLM settings acceptance, no paid external calls."""
import json
import socket
from unittest.mock import patch
import pytest
from backend.tests.test_admin import admin, login
from backend.app.services.structure.llm_api_client import OpenAiCompatJsonClient
from backend.app.admin.llm_network import validate_url, PinnedHTTPS, public_https_open
from backend.app.admin.config import normalize_ai

DRAFT = {'event_type':'signal_failure','title':'LLM extracted signal failure','summary':'Southbound service paused from HUH to EXC.',
    'mode':'MTR','line':'ERL','direction':'southbound','affected_segments':[{'from_node':'HUH','to_node':'EXC','impact':'closed'}]}

def edit(client):
    value = client.get('/api/admin/settings').json()
    for p in value['ai']['providers'].values():
        p.pop('key_configured')
        p['keys'] = [{k:v for k,v in key.items() if k in ('id','label')} for key in p['keys']]
    return value

def configure(client, headers):
    value = edit(client)
    value['ai'].update(enabled=True,provider='custom',order=['custom','backup'],providers={
        'custom':{'name':'Custom model','base_url':'https://models.example.com/v1','model':'custom-model','keys':[
            {'id':'a','label':'First key','value':'secret-a'},{'id':'b','label':'Backup key','value':'secret-b'}]},
        'backup':{'name':'Backup provider','base_url':'https://other.example.com/v1','model':'backup-model','keys':[
            {'id':'c','label':'Provider backup','value':'secret-c'}]}})
    r=client.post('/api/admin/settings',json=value,headers=headers)
    assert r.status_code==200,r.text
    assert all(secret not in r.text for secret in ('secret-a','secret-b','secret-c'))
    return r.json()

def test_custom_keys_order_status_and_real_structure(admin, monkeypatch):
    app,client=admin;headers=login(client);configure(client,headers)
    seen=[]
    def fake(self,**kwargs):
        seen.append((self.base_url,self.api_key,kwargs['json_schema']))
        if self.api_key=='secret-a': raise TimeoutError()
        return json.dumps(DRAFT) if kwargs['json_schema'].get('title')=='StructuredEventDraft' else '{"ok":true}'
    monkeypatch.setattr(OpenAiCompatJsonClient,'generate_json',fake)
    r=client.post('/api/admin/test/ai',json={'provider':'custom','key_id':'b','confirm_external_request':True},headers=headers)
    assert r.json()['ok'] and r.json()['ai']['providers']['custom']['keys'][1]['status']['ok']
    sid=client.post('/api/signals',json={'raw_text':'紅磡至會展南行信號故障，暫停服務。'}).json()['signal_id']
    r=client.post('/api/admin/events/ingest',json={'signal_id':sid},headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['structure_method']=='llm' and r.json()['llm_used']['key_id']=='b'
    assert r.json()['draft']['title']==DRAFT['title']
    assert [x[1] for x in seen][-2:]==['secret-a','secret-b']
    public=client.get('/api/admin/settings').json()
    assert public['ai']['providers']['custom']['keys'][0]['status']['ok'] is False
    assert public['ai']['providers']['custom']['keys'][1]['status']['operation']=='structure'
    assert b'secret-a' not in app.state.admin_store.path.read_bytes()
    # Reorder providers; blank inputs retain keys. The next request uses the new order.
    value=edit(client);value['ai']['order']=['backup','custom']
    assert client.post('/api/admin/settings',json=value,headers=headers).status_code==200
    before=len(app.state.signal_store.list_signals())
    r=client.post('/api/admin/test/structure',json={'raw_text':'Test sample','confirm_external_request':True},headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['llm_used']['provider']=='backup'
    assert len(app.state.signal_store.list_signals())==before
    assert client.get('/api/admin/activity').text.find('secret-')==-1

def test_bad_schema_provider_fallback_key_removal_and_invalidated_status(admin,monkeypatch):
    _,client=admin;headers=login(client);configure(client,headers)
    def fake(self,**kwargs):
        return '{"wrong":"schema"}' if self.model=='custom-model' else json.dumps(DRAFT)
    monkeypatch.setattr(OpenAiCompatJsonClient,'generate_json',fake)
    r=client.post('/api/admin/test/structure',json={'raw_text':'Sample','confirm_external_request':True},headers=headers)
    assert r.json()['structure_method']=='llm' and r.json()['llm_used']['provider']=='backup'
    value=edit(client);value['ai']['providers']['backup']['model']='new-model'
    value['ai']['providers']['custom']['keys']=[]
    r=client.post('/api/admin/settings',json=value,headers=headers)
    assert r.status_code==200,r.text
    assert not r.json()['ai']['providers']['custom']['key_configured']
    assert r.json()['ai']['providers']['backup']['keys'][0]['status']=={}
    value=edit(client);value['ai']['order']=['backup','backup']
    assert client.post('/api/admin/settings',json=value,headers=headers).status_code==422

def test_all_failures_visible_and_disabled_preview_no_calls(admin,monkeypatch):
    _,client=admin;headers=login(client);configure(client,headers)
    def fail(*args,**kwargs): raise RuntimeError('secret-a should never appear')
    monkeypatch.setattr(OpenAiCompatJsonClient,'generate_json',fail)
    r=client.post('/api/admin/test/structure',json={'raw_text':'Sample','confirm_external_request':True},headers=headers)
    assert r.json()['structure_method']=='rule_fallback' and r.json()['structure_errors']
    assert 'secret-a' not in r.text
    value=edit(client);value['ai']['enabled']=False
    assert client.post('/api/admin/settings',json=value,headers=headers).status_code==200
    assert client.post('/api/admin/test/structure',json={'raw_text':'Sample','confirm_external_request':True},headers=headers).status_code==409

def test_custom_url_private_network_and_redirect_protection():
    for url in ['http://example.com','https://user:secret@example.com','https://127.0.0.1','https://[::1]','https://localhost','https://x.internal','https://example.com?key=secret']:
        with pytest.raises(ValueError): validate_url(url)
    assert validate_url('https://custom.example.com/v1/')=='https://custom.example.com/v1'
    connection=PinnedHTTPS('custom.example.com')
    with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]),patch('socket.create_connection') as connect:
        with pytest.raises(ValueError): connection.connect()
        connect.assert_not_called()

def test_schema_is_actually_sent_to_model():
    captured=[]
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode()
    def opener(req,timeout):captured.append(json.loads(req.data));return Reply()
    OpenAiCompatJsonClient(base_url='https://custom.example.com',api_key='test',model='m',opener=opener).generate_json(
        system_prompt='Extract.',user_prompt='Report',json_schema={'type':'object','properties':{'event_type':{'enum':['signal_failure']}}},timeout_seconds=3)
    assert 'signal_failure' in captured[0]['messages'][0]['content']


def test_legacy_migration_and_runtime_state_survive_restart(admin):
    from backend.app.admin.store import AdminStore
    app, client = admin
    headers = login(client)
    store = app.state.admin_store
    old = store.settings()
    old['ai'] = {'enabled':True,'provider':'deepseek','timeout_s':20,'providers':{
        'deepseek':{'model':'deepseek-chat','api_key':'legacy-encrypted-key'}}}
    old['revision'] = 1
    store.save_settings(old,0,'operator')
    config = store.settings()
    provider = config['ai']['providers']['deepseek']
    store.record_llm('deepseek', provider, provider['keys'][0],True,'Valid response received.','connection')
    recreated = AdminStore(store.path,store.event_db)
    recreated.initialize()
    assert recreated.settings()['ai']['providers']['deepseek']['keys'][0]['value']=='legacy-encrypted-key'
    public = recreated.public_settings()
    assert public['ai']['order']==['deepseek']
    assert public['ai']['providers']['deepseek']['keys'][0]['status']['ok']
    assert 'legacy-encrypted-key' not in json.dumps(public)
