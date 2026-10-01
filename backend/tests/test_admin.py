"""Admin acceptance: real services/SQLite, mocked external network only."""
import json
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.admin.store import password_hash
from backend.app.admin import collect
from backend.app.services.ingest.hko import HkoWarningPoller
from backend.app.services.ingest.mtr_eta import MtrEtaAnomalyPoller, MtrDetectionConfig

ORIGIN="https://testserver"
PASSWORD="local-test-password"
HASH=password_hash(PASSWORD)
@pytest.fixture
def admin(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME","operator")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH",HASH)
    monkeypatch.setenv("ADMIN_ENCRYPTION_KEY","test-encryption-key-"*3)
    monkeypatch.delenv("RENDER_EXTERNAL_URL",raising=False)
    monkeypatch.setenv("ADMIN_COOKIE_SECURE","true")
    app=create_app(db_path=tmp_path/"events.sqlite3",review_token="legacy-token")
    with TestClient(app,base_url=ORIGIN) as client:
        yield app,client

def login(client):
    response=client.post("/api/admin/login",json={"username":"operator","password":PASSWORD},headers={"Origin":ORIGIN})
    assert response.status_code==200,response.text
    return {"Origin":ORIGIN,"X-CSRF-Token":response.json()["csrf_token"]}

def writable(client):
    value=client.get("/api/admin/settings").json()
    for provider in value["ai"]["providers"].values():
        provider.pop("base_url");provider.pop("key_configured")
    return value

def test_unconfigured_public_api_keeps_working(tmp_path,monkeypatch):
    for name in ("ADMIN_USERNAME","ADMIN_PASSWORD_HASH","ADMIN_ENCRYPTION_KEY"):
        monkeypatch.delenv(name,raising=False)
    with TestClient(create_app(db_path=tmp_path/"events.sqlite3")) as client:
        assert client.get("/api/admin/status").json()=={"configured":False}
        assert client.get("/api/admin/settings").status_code==503
        assert client.get("/api/health/deep").status_code==200
        assert client.get("/admin/").status_code==200

def test_session_security_and_legacy_compatibility(admin):
    app,client=admin
    assert client.get("/api/admin/events").status_code==401
    r=client.post("/api/admin/login",json={"username":"operator","password":PASSWORD},headers={"Origin":"https://untrusted.example"})
    assert r.status_code==403
    r=client.post("/api/admin/login",json={"username":"operator","password":PASSWORD},headers={"Origin":ORIGIN})
    cookie=r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/api/admin" in cookie
    csrf=r.json()["csrf_token"]
    assert client.get("/api/admin/session").status_code==200
    assert client.get("/api/signals").status_code==401  # Admin cookie cannot authorize legacy endpoint.
    assert client.get("/api/signals",headers={"x-review-token":"legacy-token"}).status_code==200
    assert client.post("/api/admin/logout",json={},headers={"Origin":ORIGIN}).status_code==403
    assert client.post("/api/admin/logout",json={},headers={"Origin":"https://untrusted.example","X-CSRF-Token":csrf}).status_code==403
    assert client.post("/api/admin/logout",json={},headers={"Origin":ORIGIN,"X-CSRF-Token":csrf}).status_code==200
    assert client.get("/api/admin/session").status_code==401

def test_expiry_and_rate_limit(admin):
    app,client=admin
    login(client)
    with app.state.admin_store.connect() as db:
        db.execute("UPDATE sessions SET expires=0")
    assert client.get("/api/admin/session").status_code==401
    for _ in range(5):
        assert client.post("/api/admin/login",json={"username":"operator","password":"wrong"},headers={"Origin":ORIGIN}).status_code==401
    assert client.post("/api/admin/login",json={"username":"operator","password":PASSWORD},headers={"Origin":ORIGIN}).status_code==429

def test_encrypted_config_immediate_use_and_conflict(admin,monkeypatch):
    app,client=admin;headers=login(client)
    value=writable(client)
    assert value["ai"]["enabled"] is False and not value["sources"]["mtr"]["enabled"]
    value["ai"]["enabled"]=True;value["ai"]["providers"]["deepseek"]["api_key"]="private-test-key-abcdef"
    response=client.post("/api/admin/settings",json=value,headers=headers)
    assert response.status_code==200,response.text
    assert "private-test-key" not in response.text
    assert response.json()["ai"]["providers"]["deepseek"]["key_configured"]
    assert b"private-test-key" not in app.state.admin_store.path.read_bytes()
    assert client.post("/api/admin/settings",json=value,headers=headers).status_code==409
    seen=[]
    from backend.app.services.structure.llm_api_client import OpenAiCompatJsonClient
    def fake(self,**kwargs):
        seen.append(self.api_key);raise TimeoutError()
    monkeypatch.setattr(OpenAiCompatJsonClient,"generate_json",fake)
    sid=client.post("/api/signals",json={"raw_text":"东铁线红磡至会展信号故障，暂停服务。"}).json()["signal_id"]
    assert client.post("/api/admin/events/ingest",json={"signal_id":sid},headers=headers).status_code==200
    assert seen and all(key=="private-test-key-abcdef" for key in seen)
    value=writable(client);value["ai"]["enabled"]=False;value["ai"]["providers"]["deepseek"]["clear_key"]=True
    assert client.post("/api/admin/settings",json=value,headers=headers).status_code==200
    assert not client.get("/api/admin/settings").json()["ai"]["providers"]["deepseek"]["key_configured"]
    assert client.post("/api/admin/test/ai",json={"provider":"deepseek","confirm_external_request":True},headers=headers).status_code==409

def test_validation_and_ai_test_do_not_leak_secrets(admin,monkeypatch):
    app,client=admin;headers=login(client);value=writable(client)
    value["ai"]["providers"]["deepseek"]["api_key"]="private-test-key"
    value["ai"]["timeout_s"]=0
    r=client.post("/api/admin/settings",json=value,headers=headers)
    assert r.status_code==422 and "private-test-key" not in r.text
    value["ai"]["timeout_s"]=10
    value["ai"]["providers"]["deepseek"]["base_url"]="http://127.0.0.1"
    r=client.post("/api/admin/settings",json=value,headers=headers)
    assert r.status_code==422 and "127.0.0.1" not in r.text
    del value["ai"]["providers"]["deepseek"]["base_url"]
    assert client.post("/api/admin/settings",json=value,headers=headers).status_code==200
    assert client.post("/api/admin/test/ai",json={"provider":"deepseek"},headers=headers).status_code==422
    from backend.app.services.structure.llm_api_client import OpenAiCompatJsonClient
    def fake(*args,**kwargs):raise RuntimeError("private-test-key")
    monkeypatch.setattr(OpenAiCompatJsonClient,"generate_json",fake)
    r=client.post("/api/admin/test/ai",json={"provider":"deepseek","confirm_external_request":True},headers=headers)
    assert r.status_code==200 and not r.json()["ok"] and "private-test-key" not in r.text
    assert "private-test-key" not in client.get("/api/admin/activity").text

def test_report_review_lifecycle_and_version_conflict(admin):
    app,client=admin;headers=login(client)
    text="【模拟】东铁线红磡至会展信号故障，暂停服务。"
    def report(author):return client.post("/api/signals",json={"raw_text":text,"author_hint":author}).json()["signal_id"]
    first=report("one")
    assert client.post("/api/admin/events/ingest",json={"signal_id":first},headers=headers).json()["state"]=="needs_review"
    root=Path(__file__).resolve().parents[2]
    payload=json.loads((root/"contracts/seed/event.seed.json").read_text(encoding="utf-8"))["events"][0]
    signal=app.state.signal_store.get_signal(first);at=signal.received_at.isoformat()
    payload.update(event_id="evt-admin-flow",version=1,created_at=at,updated_at=at,window={"start":at,"end":None,"end_confidence":"unknown"},signals=[first],audit_log=[],published_at=None,reviewed_by=None,status="pending_review")
    r=client.post("/api/admin/events",json=payload,headers=headers)
    assert r.status_code==201,r.text
    assert r.json()["confidence"]==0.2 and r.json()["audit_log"][0]["actor"]=="operator"
    for author in ("two","three"):
        sid=report(author);r=client.post("/api/admin/events/ingest",json={"signal_id":sid},headers=headers);assert r.status_code==200,r.text
    event=r.json()["event"]
    path="/api/admin/events/evt-admin-flow/review"
    r=client.post(path,json={"action":"edit","expected_version":event["version"],"edits":{"title":"Reviewed title"}},headers=headers)
    assert r.status_code==200,r.text
    assert client.post(path,json={"action":"approve","expected_version":event["version"]},headers=headers).status_code==409
    r=client.post(path,json={"action":"approve","expected_version":r.json()["version"]},headers=headers)
    assert r.status_code==200 and r.json()["reviewed_by"]=="operator",r.text
    assert len(client.get("/api/events/published").json())==1
    assert client.get("/api/graph/snapshot").json()["affected_edges"]
    r=client.post(path,json={"action":"expire","expected_version":r.json()["version"]},headers=headers)
    assert r.status_code==200 and client.get("/api/events/published").json()==[]
    assert client.get("/api/graph/snapshot").json()["affected_edges"]==[]
    assert client.post(path,json={"action":"approve","expected_version":r.json()["version"],"actor":"spoofed"},headers=headers).status_code==422

def test_collection_state_survives_restart_without_duplicate_signals(admin,monkeypatch):
    app,client=admin;headers=login(client);value=writable(client);value["sources"]["hko"]["enabled"]=True
    assert client.post("/api/admin/settings",json=value,headers=headers).status_code==200
    summary={"WFIRE":{"code":"WFIRE","name":"Fire Danger Warning","type":"Red","issueTime":"2026-10-01T08:00:00+08:00"}}
    fake=SimpleNamespace(fetch_warnsum=lambda:summary,fetch_warning_info=lambda:{"details":[]},endpoint_url=lambda _:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php')
    monkeypatch.setattr(collect,"make_poller",lambda source,cfg:HkoWarningPoller(fake))
    path="/api/admin/sources/hko/collect"
    test=client.post("/api/admin/sources/hko/test",json={},headers=headers)
    assert test.status_code==200 and len(app.state.signal_store.list_signals())==0 and app.state.admin_store.source_state("hko")=={}
    r=client.post(path,json={},headers=headers);assert r.status_code==200 and r.json()["added"]==1,r.text
    assert client.post(path,json={},headers=headers).status_code==429
    # Recreate the app against the same disk and carry the existing session cookie.
    other=create_app(db_path=app.state.signal_store.db_path,review_token="legacy-token")
    monkeypatch.setattr(collect.time,"time",lambda:time.monotonic()+10**10)
    # Existing session expiry should not block the collector persistence test: authenticate at the new time.
    with TestClient(other,base_url=ORIGIN) as second:
        headers2=login(second)
        r=second.post(path,json={},headers=headers2);assert r.status_code==200 and r.json()["added"]==0,r.text
        assert len(other.state.signal_store.list_signals())==1
        summary.clear()
        monkeypatch.setattr(collect.time,"time",lambda:time.monotonic()+10**10+120)
        r=second.post(path,json={},headers=headers2);assert r.status_code==200 and r.json()["added"]==1,r.text
        assert len(other.state.signal_store.list_signals())==2
        assert other.state.admin_store.public_settings()["sources"]["hko"]["enabled"]

def test_mtr_intervals_consecutive_state_and_partial_failure(admin,monkeypatch):
    app,client=admin;headers=login(client);value=writable(client);value["sources"]["mtr"]["enabled"]=True
    client.post("/api/admin/settings",json=value,headers=headers)
    def fetch_station(code):return {"status":1,"isdelay":"Y","data":{f"EAL-{code}":{"UP":[{"valid":"Y","ttnt":"12"}]}}}
    fake=SimpleNamespace(fetch_station=fetch_station)
    monkeypatch.setattr(collect,"make_poller",lambda source,cfg:MtrEtaAnomalyPoller(fake,MtrDetectionConfig()))
    path="/api/admin/sources/mtr/collect"
    r=client.post(path,json={},headers=headers);assert r.status_code==200 and r.json()["added"]==0
    assert r.json()["details"]["consecutive_polls"]==1
    original=time.time()
    monkeypatch.setattr(collect.time,"time",lambda:original+120)
    r=client.post(path,json={},headers=headers);assert r.status_code==200 and r.json()["added"]==1,r.text
    monkeypatch.setattr(collect.time,"time",lambda:original+240)
    r=client.post(path,json={},headers=headers);assert r.status_code==200 and r.json()["added"]==0
    from backend.app.services.ingest.mtr_eta import MtrEtaFetchError
    def partial(code):
        if code=="TAW":raise MtrEtaFetchError("upstream failure")
        return fetch_station(code)
    fake.fetch_station=partial
    monkeypatch.setattr(collect.time,"time",lambda:original+360)
    r=client.post(path,json={},headers=headers);assert r.status_code==200 and r.json()["status"]=="partial_failure"
    assert r.json()["failures"]==1

def test_encryption_key_mismatch_only_disables_admin(admin,monkeypatch):
    app,client=admin;headers=login(client);client.post("/api/admin/settings",json=writable(client),headers=headers)
    monkeypatch.setenv("ADMIN_ENCRYPTION_KEY","another-encryption-key-"*3)
    with TestClient(create_app(db_path=app.state.signal_store.db_path)) as other:
        assert other.get("/api/admin/status").json()["configured"] is False
        assert other.get("/api/health/deep").status_code==200

def test_official_redirects_and_static_content(admin):
    from urllib.request import Request
    request=Request("https://api.deepseek.com/chat/completions")
    with pytest.raises(ValueError):
        collect.OfficialRedirects().redirect_request(request,None,302,"Found",{},"http://127.0.0.1/admin")
    app,client=admin
    r=client.get("/admin/")
    assert r.status_code==200 and "Administration" in r.text and r.headers["cache-control"]=="no-store"
    assert r.headers["x-frame-options"]=="DENY"
    for path in (Path(__file__).resolve().parents[1]/"app/admin_static").rglob("*"):
        if path.is_file():assert b"legacy-token" not in path.read_bytes() and b"private-test-key" not in path.read_bytes()


def test_password_rotation_revokes_sessions_and_unicode_login_is_safe(admin,monkeypatch):
    app,client=admin;login(client)
    r=client.post("/api/admin/login",json={"username":"操作者","password":PASSWORD},headers={"Origin":ORIGIN})
    assert r.status_code==401
    monkeypatch.setenv("ADMIN_PASSWORD_HASH",password_hash("new-local-password"))
    with TestClient(create_app(db_path=app.state.signal_store.db_path),base_url=ORIGIN) as other:
        other.cookies.update(client.cookies)
        assert other.get("/api/admin/session").status_code==401
        assert other.get("/api/health/deep").status_code==200

def test_session_survives_app_recreation_without_credential_change(admin):
    app,client=admin;login(client)
    with TestClient(create_app(db_path=app.state.signal_store.db_path),base_url=ORIGIN) as other:
        other.cookies.update(client.cookies)
        assert other.get("/api/admin/session").status_code==200
