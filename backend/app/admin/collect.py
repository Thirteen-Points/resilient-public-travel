"""Explicit external operations: no background jobs, no implicit publication."""
import time
from dataclasses import asdict
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler
from fastapi import HTTPException
from ..services.ingest.mtr_eta import MtrEtaClient, MtrEtaAnomalyPoller, MtrDetectionConfig, CORRIDOR_STATIONS
from ..services.ingest.hko import HkoClient, HkoWarningPoller

ALLOWED_HOSTS = {"api.deepseek.com", "dashscope.aliyuncs.com", "open.bigmodel.cn", "rt.data.gov.hk", "data.weather.gov.hk"}
class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        original = urlsplit(req.full_url)
        if parsed.scheme != "https" or parsed.hostname != original.hostname or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None,443) or parsed.username:
            raise ValueError("Redirect outside the official API is blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def official_open(request, timeout):
    parsed = urlsplit(request.full_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None,443) or parsed.username:
        raise ValueError("Unsupported API endpoint")
    return build_opener(OfficialRedirects()).open(request, timeout=timeout)

def make_poller(source, cfg):
    if source == "mtr":
        fields = {k:v for k,v in cfg.items() if k not in {"enabled","timeout_s"}}
        return MtrEtaAnomalyPoller(MtrEtaClient(timeout_seconds=cfg["timeout_s"], opener=official_open), MtrDetectionConfig(**fields))
    return HkoWarningPoller(HkoClient(timeout_s=cfg["timeout_s"],lang=cfg["lang"],opener=official_open),poll_interval_s=cfg["poll_interval_seconds"])

def source_operation(store, source, actor, test=False):
    cfg=store.settings()["sources"][source]
    if not test and not cfg["enabled"]:
        raise HTTPException(409, "Enable and save this source before collecting.")
    try:
        owner=store.acquire(source)
    except RuntimeError as exc:
        raise HTTPException(409,str(exc)) from exc
    try:
        old=store.source_state(source)
        if not test and time.time()-old.get("last_attempt",0)<cfg["poll_interval_seconds"]:
            remaining=max(1,int(cfg["poll_interval_seconds"]-(time.time()-old["last_attempt"])))
            raise HTTPException(429, f"Minimum observation interval: try again in {remaining} seconds.",headers={"Retry-After":str(remaining)})
        poller=make_poller(source,cfg)
        signature={k:v for k,v in cfg.items() if k not in {"enabled","timeout_s","poll_interval_seconds","lang"}}
        if not test and old.get("config")==signature:
            poller.restore_state(old.get("poller",{}))
        outcome=poller.poll_once()
        if source=="mtr":
            failures=len(outcome.failures)
            status="failed" if not outcome.observations else "partial_failure" if failures else "success"
            details={"observations":len(outcome.observations),"consecutive_polls":outcome.consecutive_polls,"qualifying_stations":list(outcome.qualifying_stations),"insufficient_data":outcome.insufficient_data}
        else:
            failures=int(bool(outcome.error))
            status="partial_failure" if outcome.degraded and outcome.changed else "failed" if outcome.degraded else "success"
            details={"active_codes":sorted(outcome.active_codes),"changed":outcome.changed,"stale":outcome.stale}
        result={"status":status,"at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"failures":failures,"added":0,"duplicate":0,"details":details}
        if test:
            store.record(actor,"source_tested",source,status,f"Failures {failures}; no reports written")
            return result
        state={"last_attempt":time.time(),"config":signature,"poller":poller.export_state()}
        return store.finish_collection(source,state,outcome.signals,actor,result)
    finally:
        store.release(source,owner)
