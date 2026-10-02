"""One bounded source observation shared by manual and scheduled collection.

Only raw Signals and collector state are persisted; collection never publishes
an Event. Official requests recheck offline/disable/shutdown guards per request.
"""
import contextvars
import os
import time
from dataclasses import asdict
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler
from fastapi import HTTPException
from ..services.ingest.mtr_eta import MtrEtaClient, MtrEtaAnomalyPoller, MtrDetectionConfig, CORRIDOR_STATIONS
from ..services.ingest.hko import HkoClient, HkoWarningPoller

ALLOWED_HOSTS = {"api.deepseek.com", "dashscope.aliyuncs.com", "open.bigmodel.cn", "rt.data.gov.hk", "data.weather.gov.hk"}
_SOURCE_GUARD = contextvars.ContextVar("source_collection_guard", default=None)


def offline_mode():
    return os.getenv("OFFLINE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}

class OfficialRedirects(HTTPRedirectHandler):
    def __init__(self, deadline=None):
        self.deadline = deadline

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        original = urlsplit(req.full_url)
        if parsed.scheme != "https" or parsed.hostname != original.hostname or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None,443) or parsed.username:
            raise ValueError("Redirect outside the official API is blocked")
        guard = _SOURCE_GUARD.get()
        if offline_mode() or (guard is not None and not guard()):
            raise OSError("External source collection stopped")
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Official source request deadline exceeded")
            req.timeout = min(req.timeout, remaining)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class BoundedOfficialResponse:
    """Bound a slowly streamed body as well as the initial socket connection."""
    def __init__(self, response, deadline, guard):
        self.response, self.deadline, self.guard = response, deadline, guard

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def read(self):
        chunks, total = [], 0
        while True:
            if offline_mode() or (self.guard and not self.guard()):
                raise OSError("External source collection stopped")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Official source request deadline exceeded")
            # urllib HTTPS responses expose the active socket through the raw
            # reader. Tighten its timeout before every read to the total deadline.
            sock = getattr(getattr(getattr(self.response, "fp", None), "raw", None), "_sock", None)
            if sock is not None:
                sock.settimeout(remaining)
            reader = getattr(self.response, "read1", self.response.read)
            chunk = reader(64 * 1024)
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > 2 * 1024 * 1024:
                raise OSError("Official source response exceeds size limit")
            chunks.append(chunk)

def official_open(request, timeout):
    guard = _SOURCE_GUARD.get()
    if offline_mode() or (guard is not None and not guard()):
        raise OSError("External source collection is stopped by runtime configuration")
    parsed = urlsplit(request.full_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None,443) or parsed.username:
        raise ValueError("Unsupported API endpoint")
    deadline = time.monotonic() + timeout
    response = build_opener(OfficialRedirects(deadline)).open(request, timeout=timeout)
    return BoundedOfficialResponse(response, deadline, guard)

def make_poller(source, cfg):
    if source == "mtr":
        fields = {k:v for k,v in cfg.items() if k not in {"enabled","timeout_s"}}
        return MtrEtaAnomalyPoller(MtrEtaClient(timeout_seconds=cfg["timeout_s"], opener=official_open), MtrDetectionConfig(**fields))
    return HkoWarningPoller(HkoClient(timeout_s=cfg["timeout_s"],lang=cfg["lang"],opener=official_open),poll_interval_s=cfg["poll_interval_seconds"])

def source_operation(store, source, actor, test=False, *, cancel_check=None):
    if offline_mode():
        raise HTTPException(409, "External source collection is disabled in offline mode.")
    cfg=store.settings()["sources"][source]
    if not test and not cfg["enabled"]:
        raise HTTPException(409, "Enable and save this source before collecting.")
    try:
        owner=store.acquire(source)
    except RuntimeError as exc:
        raise HTTPException(409,str(exc)) from exc
    def permitted():
        return (not offline_mode() and not (cancel_check and cancel_check())
                and (test or store.settings()["sources"][source]["enabled"]))
    requests = len(CORRIDOR_STATIONS) if source == "mtr" else 2
    source_deadline = time.monotonic() + requests * cfg["timeout_s"] + 10
    def network_permitted():
        allowed = permitted()
        return allowed and time.monotonic() < source_deadline
    token = _SOURCE_GUARD.set(network_permitted)
    try:
        old=store.source_state(source)
        now = time.time()
        next_due = max(old.get("last_attempt", 0) + cfg["poll_interval_seconds"], old.get("next_attempt", 0))
        if not test and now < next_due:
            remaining=max(1,int(next_due-now))
            raise HTTPException(429, f"Minimum observation interval: try again in {remaining} seconds.",headers={"Retry-After":str(remaining)})
        poller=make_poller(source,cfg)
        signature={k:v for k,v in cfg.items() if k not in {"enabled","timeout_s","poll_interval_seconds","lang"}}
        if not test and old.get("config")==signature:
            poller.restore_state(old.get("poller",{}))
        if not permitted():
            raise HTTPException(409, "Collection stopped by runtime configuration; no reports were written.")
        try:
            outcome=poller.poll_once()
        except Exception:
            if not test and permitted():
                failures = old.get("consecutive_failures", 0) + 1
                failed = {"status": "failed", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "failures": 1, "added": 0, "duplicate": 0, "details": {}}
                state = {**old, "last_attempt": now, "consecutive_failures": failures,
                         "next_attempt": time.time() + backoff_seconds(cfg["poll_interval_seconds"], failures)}
                store.finish_collection(source, state, (), actor, failed)
            raise
        if not permitted():
            raise HTTPException(409, "Collection stopped by runtime configuration; no reports were written.")
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
        streak = 0 if status == "success" else old.get("consecutive_failures", 0) + 1
        state={"last_attempt":now,"config":signature,"poller":poller.export_state(),
               "consecutive_failures": streak,
               "next_attempt": time.time() + backoff_seconds(cfg["poll_interval_seconds"], streak)}
        return store.finish_collection(source,state,outcome.signals,actor,result)
    finally:
        _SOURCE_GUARD.reset(token)
        store.release(source,owner)


def backoff_seconds(interval, failures):
    """At least the configured observation cadence; failures back off to 15 min."""
    return max(interval, min(900, interval * 2 ** min(max(failures, 0), 4)))
