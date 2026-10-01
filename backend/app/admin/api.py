"""Same-origin administration API. Existing public/token APIs remain compatible."""
import hashlib
import os
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import Field, SecretStr
from .config import Strict, SettingsEdit, merge_settings, llm_client
from .store import verify_password
from .collect import source_operation
from ..api import events, signals, review
from ..services.event_models import Event

COOKIE = "rr_admin_session"
router = APIRouter(prefix="/api/admin", tags=["administration"])

def available(request):
    store=request.app.state.admin_store
    if not store.ready:
        raise HTTPException(503,"Administrator access is not configured. Configure the Render administrator variables.")
    return store

def same_origin(request):
    expected=os.getenv("RENDER_EXTERNAL_URL",str(request.base_url).rstrip("/"))
    if request.headers.get("origin") != expected:
        raise HTTPException(403,"Same-origin administrator request required.")

def authenticated(request: Request):
    store=available(request)
    session=store.session(request.cookies.get(COOKIE))
    if not session:
        raise HTTPException(401,"Administrator login required.")
    if request.method not in {"GET","HEAD","OPTIONS"}:
        same_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token",""),session["csrf"]):
            raise HTTPException(403,"Invalid CSRF token. Reload and try again.")
    request.state.admin_identity=session["identity"]
    return session

class Login(Strict):
    username: str = Field(min_length=1,max_length=100)
    password: SecretStr

@router.get("/status")
def status(request: Request):
    return {"configured":request.app.state.admin_store.ready}

@router.post("/login")
def login(body: Login, request: Request, response: Response):
    store=available(request)
    same_origin(request)
    if len(body.password.get_secret_value())>1024:
        raise HTTPException(401,"Invalid username or password.")
    # The socket peer is used rather than a spoofable client-supplied forwarding header.
    bucket=hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()
    if not store.login_attempt(bucket):
        raise HTTPException(429,"Too many attempts. Try again in 15 minutes.",headers={"Retry-After":"900"})
    valid=verify_password(body.password.get_secret_value(),store.password)
    if not valid or not secrets.compare_digest(body.username.encode(),store.username.encode()):
        store.record("anonymous","login","administrator","failed")
        raise HTTPException(401,"Invalid username or password.")
    store.clear_attempts(bucket)
    token,csrf=store.new_session()
    response.set_cookie(COOKIE,token,max_age=8*3600,httponly=True,secure=os.getenv("ADMIN_COOKIE_SECURE","true").lower()!="false",samesite="strict",path="/api/admin")
    store.record(store.username,"login","administrator")
    return {"username":store.username,"csrf_token":csrf}

@router.get("/session")
def session(session=Depends(authenticated)):
    return {"username":session["identity"],"csrf_token":session["csrf"]}

@router.post("/logout")
def logout(request: Request,response: Response, session=Depends(authenticated)):
    available(request).revoke(request.cookies[COOKIE])
    available(request).record(session["identity"],"logout","administrator")
    response.delete_cookie(COOKIE,path="/api/admin",secure=os.getenv("ADMIN_COOKIE_SECURE","true").lower()!="false",httponly=True,samesite="strict")
    return {"ok":True}

@router.get("/overview")
def overview(request: Request, session=Depends(authenticated)):
    from ..main import runtime
    store=available(request)
    event_list=request.app.state.event_store.list_events()
    signal_list=request.app.state.signal_store.list_signals()
    linked={sid for event in event_list for sid in event.signals}
    return {"health":runtime.health(),"reports":len(signal_list),"unlinked_reports":sum(s.signal_id not in linked for s in signal_list),
            "pending_review":sum(e.status in {"pending_review","updated"} for e in event_list),
            "published":sum(e.status=="published" for e in event_list),"ai":store.public_settings()["ai"],
            "sources":{name:store.source_state(name).get("last_result") for name in ("mtr","hko")}}

@router.get("/settings")
def settings(request: Request, session=Depends(authenticated)):
    return available(request).public_settings()

@router.post("/settings")
def save_settings(body: SettingsEdit, request: Request, session=Depends(authenticated)):
    store=available(request)
    try:
        value=merge_settings(store.settings(),body)
        store.save_settings(value,body.revision,session["identity"])
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409,str(exc)) from exc
    return store.public_settings()

class AiTest(Strict):
    provider: Literal["deepseek","qwen","glm"]
    confirm_external_request: Literal[True]

@router.post("/test/ai")
def test_ai(body: AiTest, request: Request, session=Depends(authenticated)):
    store=available(request)
    config=store.settings()
    config["ai"].update(enabled=True,provider=body.provider)
    client=llm_client(config)
    if client is None:
        raise HTTPException(409,"Save an API key before testing this provider.")
    try:
        output=client.generate_json(system_prompt='Return only {"ok": true} as JSON.',user_prompt="Connection test. No user reports are included.",json_schema={"type":"object"},timeout_seconds=config["ai"]["timeout_s"])
        import json
        if json.loads(output).get("ok") is not True:
            raise ValueError("Unexpected test response")
    except Exception:
        store.record(session["identity"],"ai_tested",body.provider,"failed","Connection, authentication, timeout or response validation failed.")
        return {"ok":False,"message":"Connection, authentication, timeout or response validation failed. Check the saved key and model."}
    store.record(session["identity"],"ai_tested",body.provider)
    return {"ok":True,"message":"Provider returned valid JSON. One external request was sent."}

@router.post("/sources/{source}/{operation}")
def source_action(source: Literal["mtr","hko"], operation: Literal["test","collect"], request: Request, session=Depends(authenticated)):
    try:
        return source_operation(available(request),source,session["identity"],test=operation=="test")
    except HTTPException:
        raise
    except Exception:
        available(request).record(session["identity"],"source_"+operation,source,"failed","Source operation failed; retry after checking configuration.")
        raise HTTPException(502,"Source operation failed. No automatic event was published.")

@router.get("/activity")
def activity(request: Request,before: int|None=Query(default=None,ge=1),limit: int=Query(default=100,ge=1,le=100), session=Depends(authenticated)):
    return available(request).activities(before,limit)

@router.get("/signals")
def inbox(request: Request,unlinked_only: bool=False,session=Depends(authenticated)):
    return signals.list_signals(request,unlinked_only,None)

@router.get("/events")
def event_list(request: Request, session=Depends(authenticated)):
    return events.list_events(request,None,None)

@router.get("/events/{event_id}/signals")
def evidence(event_id: str,request: Request, session=Depends(authenticated)):
    return events.get_event_signals(event_id,request,None)

@router.post("/events/ingest")
def ingest(body: events.IngestRequest,request: Request,session=Depends(authenticated)):
    result=events.ingest_signal(body,request,None)
    available(request).record(session["identity"],"report_structured",body.signal_id,detail=result.state)
    return result

@router.post("/events",status_code=201)
def create(body: Event,request: Request,session=Depends(authenticated)):
    result=events.create_review_candidate(body,request,None)
    available(request).record(session["identity"],"event_created",result.event_id)
    return result

class AdminReview(Strict):
    action: Literal["approve","edit","reject","expire"]
    expected_version: int = Field(ge=1)
    edits: review.ReviewEdits | None = None
    reason: str = Field(default="",max_length=800)

@router.post("/events/{event_id}/review")
def review_action(event_id: str,body: AdminReview,request: Request,session=Depends(authenticated)):
    result=review.review_event(event_id,review.ReviewRequest(action=body.action,edits=body.edits,expected_version=body.expected_version,actor=session["identity"]),request,None)
    available(request).record(session["identity"],"review_"+body.action,event_id,detail=body.reason.strip())
    return result
