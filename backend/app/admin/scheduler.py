"""Lifecycle-owned collectors using persisted admin settings and source leases.

There is one serial worker per source. Network operations run in threads, and
shutdown drains those workers rather than cancelling a running to_thread call.
The official clients have configured request timeouts; source_operation also
checks shutdown/disable/offline before each request and before writing Signals.
"""
from __future__ import annotations

import asyncio
import time
from fastapi import APIRouter, Request

from .collect import offline_mode, source_operation

SOURCES = ("mtr", "hko")


class SourceScheduler:
    def __init__(self, store, *, operation=None, clock=None, poll_seconds=1.0, initial_delay=True):
        self.store = store
        self.operation = operation or source_operation
        self.clock = clock or time.time
        self.poll_seconds = poll_seconds
        self.initial_delay = initial_delay
        self._loop = None
        self._tasks = []
        self._stopping = False
        self._wake = {name: asyncio.Event() for name in SOURCES}
        self._active_since = {}
        self._local_next = {}
        self._running = {name: False for name in SOURCES}
        self._errors = {}

    async def start(self):
        if self._tasks or not self.store.ready:
            return
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        self._tasks = [asyncio.create_task(self._run(name), name=f"source-{name}") for name in SOURCES]

    def notify(self):
        """Safe from synchronous FastAPI handlers executed in worker threads."""
        if self._loop and not self._stopping:
            for event in self._wake.values():
                self._loop.call_soon_threadsafe(event.set)

    async def stop(self):
        self._stopping = True
        for event in self._wake.values():
            event.set()
        # Cancelling to_thread would leave its socket/SQLite work running after
        # application shutdown. Drain it; per-request guards stop later requests.
        await asyncio.gather(*self._tasks)
        self._tasks = []

    async def _wait(self, name, delay):
        try:
            await asyncio.wait_for(self._wake[name].wait(), timeout=max(.01, min(self.poll_seconds, delay)))
        except TimeoutError:
            pass
        self._wake[name].clear()

    async def _run(self, name):
        while not self._stopping:
            interval = 60
            try:
                cfg = (await asyncio.to_thread(self.store.settings))["sources"][name]
                interval = cfg["poll_interval_seconds"]
                if offline_mode() or not cfg["enabled"]:
                    self._active_since.pop(name, None)
                    await self._wait(name, self.poll_seconds)
                    continue
                now = self.clock()
                if name not in self._active_since:
                    self._active_since[name] = now
                state = await asyncio.to_thread(self.store.source_state, name)
                initial = self._active_since[name] + cfg["poll_interval_seconds"] if self.initial_delay else 0
                due = max(initial, state.get("last_attempt", 0) + cfg["poll_interval_seconds"],
                          state.get("next_attempt", 0), self._local_next.get(name, 0))
                if now < due:
                    await self._wait(name, due-now)
                    continue
                self._running[name] = True
                try:
                    await asyncio.to_thread(self.operation, self.store, name, "scheduled-collector",
                                            cancel_check=lambda: self._stopping)
                    self._errors.pop(name, None)
                finally:
                    self._running[name] = False
                    # The observation can commit before to_thread delivers its
                    # return value. Base the local guard on its start; persisted
                    # next_attempt independently protects completion/backoff.
                    self._local_next[name] = now + cfg["poll_interval_seconds"]
            except Exception:
                # No upstream exception text, URLs, credentials or report data
                # become public status. Persisted failed attempts retain backoff.
                self._errors[name] = "collection_unavailable"
                self._running[name] = False
                self._local_next[name] = self.clock() + interval
                await self._wait(name, self.poll_seconds)

    def status(self):
        return public_source_status(self.store, self)


def public_source_status(store, scheduler=None):
    offline = offline_mode()
    configured = bool(store and store.ready)
    sources = {}
    if configured:
        try:
            config = store.settings()["sources"]
            now = time.time()
            for name in SOURCES:
                cfg, state = config[name], store.source_state(name)
                result = state.get("last_result", {})
                interval = cfg["poll_interval_seconds"]
                # last_success_at survives later failures, partial results,
                # disabling, offline mode and process restarts (persisted state).
                # Pre-existing state is backfilled only from a stored success
                # result that carries its own completion time.
                last_success = state.get("last_success_at")
                if not last_success and result.get("status") == "success" and result.get("at"):
                    last_success = result["at"]
                sources[name] = {
                    "enabled": cfg["enabled"], "interval_seconds": interval,
                    "scheduled": bool(scheduler and scheduler._tasks and not scheduler._stopping
                                      and cfg["enabled"] and not offline),
                    "collecting": bool(scheduler and scheduler._running[name]),
                    "last_attempt": state.get("last_attempt"), "next_attempt": state.get("next_attempt"),
                    "status": "offline" if offline else "disabled" if not cfg["enabled"] else result.get("status", "waiting"),
                    "stale": not state or result.get("status") != "success"
                             or now - state.get("last_attempt", 0) > interval * 2,
                    "last_success_at": last_success,
                    "last_result": {key: result[key] for key in ("at", "status", "failures", "added", "duplicate") if key in result},
                }
                if scheduler and name in scheduler._errors:
                    sources[name]["error"] = scheduler._errors[name]
                    sources[name]["stale"] = True
        except Exception:
            configured = False
    if not configured:
        sources = {name: {"enabled": False, "scheduled": False, "collecting": False,
                          "status": "offline" if offline else "unconfigured", "stale": True,
                          "last_success_at": None}
                   for name in SOURCES}
    return {"offline": offline, "configured": configured, "sources": sources,
            "publishes_events": False}


router = APIRouter(prefix="/api/sources", tags=["source status"])


@router.get("/status")
def status(request: Request):
    return public_source_status(getattr(request.app.state, "admin_store", None),
                                getattr(request.app.state, "source_scheduler", None))
