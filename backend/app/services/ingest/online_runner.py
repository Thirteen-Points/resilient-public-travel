"""Independent-process source runner; no event, confidence or route writes."""
from __future__ import annotations

import threading
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from .online_http import SourceFailure
from .online_models import SourceAdapter, filter_reason, utcnow
from .online_store import IngestStore

BLOCKED = {
    "xiaohongshu": "no_verified_public_search_entry",
    "threads": "missing_token_and_approved_search_permission",
    "instagram": "missing_token_professional_account_and_read_permissions",
    "facebook": "missing_token_and_page_content_access",
}
SOURCES = ("mtr_mobile", *BLOCKED)


@dataclass(frozen=True)
class IngestConfig:
    sources: tuple[str, ...] = ("mtr_mobile",)
    enabled: bool = False
    offline: bool = True
    interval: int = 300
    lookback_hours: int = 24
    max_items: int = 100
    page_size: int = 25
    extra_keywords: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.sources or any(x not in SOURCES for x in self.sources):
            raise ValueError("unknown or empty INGEST_SOURCES")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("INGEST_SOURCES must be unique")
        if self.interval < 300 or not 1 <= self.lookback_hours <= 720:
            raise ValueError("interval must be >=300; lookback must be 1..720 hours")
        if not 1 <= self.max_items <= 10000 or not 1 <= self.page_size <= 100:
            raise ValueError("max_items must be 1..10000; page_size must be 1..100")


class IngestRunner:
    def __init__(self, store: IngestStore, config: IngestConfig,
                 adapters: dict[str, SourceAdapter], *, stop=None,
                 clock: Callable[[], datetime] = utcnow):
        self.store, self.config, self.adapters = store, config, adapters
        self.stop = stop or threading.Event()
        self.clock = clock

    def run_source(self, name):
        owner = self.store.acquire(name, self.clock().timestamp())
        if owner is None:
            return {"source": name, "status": "busy", "error": "source_already_running"}
        try:
            return self._run_source(name, owner)
        finally:
            self.store.release(name, owner)

    def _run_source(self, name, owner):
        now, cfg = self.clock(), self.config
        old = self.store.state(name)
        base = {**old, "source": name}
        unavailable = ("offline" if cfg.offline else "disabled" if not cfg.enabled
                       else "blocked" if name in BLOCKED else None)
        if unavailable:
            base.update(status=unavailable, error=BLOCKED.get(name) if unavailable == "blocked" else None)
            self.store.save_state(name, owner, base, now.timestamp())
            return base
        if self.stop.is_set():
            return {"source": name, "status": "stopped"}
        if now.timestamp() < old.get("next_attempt", 0):
            return {**base, "status": "waiting"}
        adapter = self.adapters.get(name)
        if adapter is None:
            raise ValueError("adapter_unavailable")
        since = (datetime.fromisoformat(old["window_start"]) if old.get("cursor")
                 else now - timedelta(hours=cfg.lookback_hours))
        interval = max(cfg.interval, adapter.min_interval_seconds, old.get("minimum_interval", 0))
        state = {
            **base, "status": "running", "error": None,
            "last_attempt": now.isoformat(), "next_attempt": now.timestamp() + interval,
            "window_start": since.isoformat(), "cursor": old.get("cursor"),
            "counts": {"processed": 0, "added": 0, "duplicate": 0, "skipped": {}},
        }
        self.store.save_state(name, owner, state, now.timestamp())
        visited = set()
        started = now
        try:
            while state["counts"]["processed"] < cfg.max_items:
                if self.stop.is_set():
                    raise SourceFailure("stopped")
                if (self.clock() - started).total_seconds() > 120:
                    raise SourceFailure("round_deadline")
                remaining = cfg.max_items - state["counts"]["processed"]
                page = adapter.fetch_page(state["cursor"], min(cfg.page_size, remaining))
                if len(page.posts) > min(cfg.page_size, remaining):
                    raise SourceFailure("adapter_page_exceeds_limit", permanent=True)
                if self.stop.is_set():
                    raise SourceFailure("stopped")
                at = self.clock()
                page_state = copy.deepcopy(state)
                records = []
                for post in page.posts:
                    if post.platform != name:
                        raise SourceFailure("adapter_identity_mismatch", permanent=True)
                    reason = filter_reason(post, since, at, cfg.extra_keywords)
                    records.append((post, reason))
                    if reason:
                        skipped = page_state["counts"]["skipped"]
                        skipped[reason] = skipped.get(reason, 0) + 1
                page_state["counts"]["processed"] += len(records)
                page_state["cursor"] = page.next_cursor
                page_state["diagnostics"] = page.diagnostics
                key = json.dumps(page.next_cursor, sort_keys=True)
                if page.next_cursor is not None and (
                    key in visited or page.next_cursor == state["cursor"] or not page.posts
                ):
                    raise SourceFailure("pagination_stalled", permanent=True)
                self.store.commit_page(name, owner, records, page_state, at)
                state = page_state
                if page.next_cursor is None:
                    break
                visited.add(key)
            state.update(status="success", consecutive_failures=0, last_success=self.clock().isoformat())
            state["completed_rounds"] = old.get("completed_rounds", 0) + 1
            state["minimum_interval"] = max(cfg.interval, adapter.min_interval_seconds)
            state["next_attempt"] = self.clock().timestamp() + state["minimum_interval"]
        except SourceFailure as exc:
            failures = old.get("consecutive_failures", 0) + 1
            state.update(status="stopped" if exc.code == "stopped" else "error", error=exc.code,
                         consecutive_failures=failures)
            state["next_attempt"] = self.clock().timestamp() + max(
                interval, min(900, interval * 2 ** min(failures, 4)), exc.retry_after)
        except Exception:
            state.update(status="error", error="internal_collection_error",
                         consecutive_failures=old.get("consecutive_failures", 0) + 1)
            state["next_attempt"] = self.clock().timestamp() + max(interval, 900)
        self.store.save_state(name, owner, state, self.clock().timestamp())
        return state

    def cycle(self):
        def safe_run(name):
            try:
                return self.run_source(name)
            except Exception:
                return {"source": name, "status": "error", "error": "storage_or_runner_unavailable"}
        with ThreadPoolExecutor(max_workers=len(self.config.sources), thread_name_prefix="ingest") as executor:
            return list(executor.map(safe_run, self.config.sources))
