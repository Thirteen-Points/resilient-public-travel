"""Opt-in, recoverable collection of official-source observations.

The collector owns only raw evidence and unreviewed drafts.  It never approves
an Event; the existing review service remains the publication gate.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..aggregate import AmbiguousEventMatchError, EventAggregator, StructuredObservation
from ..event_store import EventStore
from ..signal_models import Signal
from ..signal_store import SignalStore
from ..structure.llm_structurer import LlmEventStructurer
from .hko import HkoClient, HkoWarningPoller
from .mtr_eta import MtrEtaAnomalyPoller, MtrEtaClient


SOURCE_INTERVALS = {"hko": 90, "mtr": 60}
LOG = logging.getLogger(__name__)


class CollectionStore:
    """Collector-only tables in the durable Signal/Event SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS collection_sources (
                    source TEXT PRIMARY KEY, poller_state TEXT NOT NULL DEFAULT '{}',
                    last_attempt TEXT, last_success TEXT, source_time TEXT,
                    last_error TEXT, new_signals INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS collection_queue (
                    signal_id TEXT PRIMARY KEY, source TEXT NOT NULL,
                    state TEXT NOT NULL, draft_json TEXT, error TEXT,
                    FOREIGN KEY(signal_id) REFERENCES signals(signal_id)
                );
            """)
            for source in SOURCE_INTERVALS:
                db.execute("INSERT OR IGNORE INTO collection_sources(source) VALUES (?)", (source,))

    def poller_state(self, source: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT poller_state FROM collection_sources WHERE source=?", (source,)).fetchone()
        return json.loads(row["poller_state"]) if row else {}

    def save_poll(self, source: str, signals: tuple[Signal, ...], state: dict[str, Any],
                  *, attempted_at: datetime, success: bool, source_time: str | None,
                  error: str | None) -> int:
        """Commit Signals, queue entries and detector state as one transaction."""
        inserted = 0
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys = ON")
            for signal in signals:
                payload = json.dumps(signal.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
                cursor = db.execute(
                    "INSERT OR IGNORE INTO signals(signal_id,received_at,source_type,payload_json) VALUES (?,?,?,?)",
                    (signal.signal_id, signal.received_at.isoformat(), signal.source_type, payload))
                if cursor.rowcount:
                    inserted += 1
                    db.execute("INSERT INTO collection_queue(signal_id,source,state) VALUES (?,?,?)",
                               (signal.signal_id, source, "new"))
                else:
                    old = db.execute("SELECT payload_json FROM signals WHERE signal_id=?", (signal.signal_id,)).fetchone()
                    if old is None or json.loads(old["payload_json"]) != json.loads(payload):
                        raise ValueError("Signal ID collision with different content")
            db.execute("""UPDATE collection_sources SET poller_state=?,last_attempt=?,
                       last_success=CASE WHEN ? THEN ? ELSE last_success END,
                       source_time=CASE WHEN ? THEN ? ELSE source_time END,
                       last_error=?,new_signals=? WHERE source=?""",
                       (json.dumps(state, ensure_ascii=False), attempted_at.isoformat(),
                        int(success), attempted_at.isoformat(), int(success), source_time,
                        error, inserted, source))
        return inserted

    def status(self, source: str, *, enabled: bool, now: datetime | None = None,
               simulated: bool = False) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        with self._connect() as db:
            row = db.execute("SELECT * FROM collection_sources WHERE source=?", (source,)).fetchone()
        if row is None:
            raise KeyError(source)
        last_success = row["last_success"]
        age = (now - datetime.fromisoformat(last_success)).total_seconds() if last_success else None
        return {"source": source, "enabled": enabled, "last_attempt": row["last_attempt"],
                "last_success": last_success, "source_time": row["source_time"],
                "source_time_note": None if row["source_time"] else "source did not provide a usable timestamp",
                "last_error": row["last_error"], "stale": age is None or age > 2 * SOURCE_INTERVALS[source],
                "new_signals": row["new_signals"],
                "result": "new_signals" if row["new_signals"] else ("error" if row["last_error"] else "no_new_signals"),
                "provenance": "simulated" if simulated else ("real" if source == "hko" else "real-derived")}

    def pending(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM collection_queue WHERE state IN ('new','error') ORDER BY rowid").fetchall()
        return [dict(row) for row in rows]

    def review_queue(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM collection_queue ORDER BY rowid DESC").fetchall()
        return [{**dict(row), "draft": json.loads(row["draft_json"]) if row["draft_json"] else None}
                for row in rows]

    def mark(self, signal_id: str, state: str, *, draft: dict[str, Any] | None = None,
             error: str | None = None) -> None:
        with self._connect() as db:
            db.execute("UPDATE collection_queue SET state=?,draft_json=?,error=? WHERE signal_id=?",
                       (state, json.dumps(draft, ensure_ascii=False) if draft is not None else None,
                        error, signal_id))


class SourceCollectionService:
    """Two isolated scheduler loops; C registers this object in app lifespan."""

    def __init__(self, db_path: str | Path, *, enabled: bool | None = None,
                 offline_mode: bool | None = None, simulated: bool = False,
                 pollers: dict[str, Any] | None = None, sleeper: Any = None,
                 signal_store: SignalStore | None = None,
                 event_store: EventStore | None = None) -> None:
        self.enabled = (os.getenv("SOURCE_COLLECTION_ENABLED", "false").lower() == "true") if enabled is None else enabled
        self.offline_mode = (os.getenv("OFFLINE_MODE", "true").lower() == "true") if offline_mode is None else offline_mode
        self.simulated = simulated
        self.store = CollectionStore(db_path)
        self.signals = signal_store or SignalStore(db_path)
        self.events = event_store or EventStore(db_path)
        self.pollers = pollers or {"hko": HkoWarningPoller(HkoClient()),
                                   "mtr": MtrEtaAnomalyPoller(MtrEtaClient())}
        self._locks = {source: threading.Lock() for source in SOURCE_INTERVALS}
        self._process_lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: dict[str, threading.Thread] = {}
        self._sleep = sleeper or self._stop.wait
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self.signals.initialize()
        self.events.initialize()
        self.store.initialize()
        for source, poller in self.pollers.items():
            poller.restore_state(self.store.poller_state(source))
        self._initialized = True

    def start(self) -> bool:
        self.initialize()
        self.process_pending()
        if not self.enabled or self.offline_mode:
            return False
        if self._threads:
            return True
        self._stop.clear()
        for source in SOURCE_INTERVALS:
            thread = threading.Thread(target=self._loop, args=(source,), name=f"collector-{source}", daemon=True)
            self._threads[source] = thread
            thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads.values():
            thread.join()
        self._threads.clear()

    def _loop(self, source: str) -> None:
        while not self._stop.is_set():
            try:
                self.run_once(source)
            except Exception:
                LOG.exception("collector source %s failed; next interval will retry", source)
            self._stop.wait(SOURCE_INTERVALS[source])

    def run_once(self, source: str, *, at: datetime | None = None) -> int:
        self.initialize()
        if source not in self.pollers:
            raise KeyError(source)
        if not self.enabled or self.offline_mode:
            return 0
        if not self._locks[source].acquire(blocking=False):
            return 0
        try:
            when = at or datetime.now(timezone.utc)
            result = None
            error = None
            prior_state = self.pollers[source].export_state()
            for attempt in range(3):
                try:
                    result = self.pollers[source].poll_once(received_at=when)
                    failed = (source == "hko" and result.error and not result.signals and not result.changed) or (
                        source == "mtr" and result.insufficient_data)
                    if not failed:
                        break
                    error = result.error if source == "hko" else "; ".join(x.reason for x in result.failures)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                if attempt < 2:
                    self._sleep(2 ** attempt)
            if result is None:
                signals = ()
                success = False
                source_time = None
            else:
                signals = result.signals
                success = not ((source == "hko" and result.error and not result.signals and not result.changed) or
                               (source == "mtr" and result.insufficient_data))
                source_time = result.source_time
                if source == "hko":
                    error = result.error
                elif result.failures:
                    error = "; ".join(f"{failure.station_code}: {failure.reason}" for failure in result.failures)
                elif success:
                    error = None
            if self.simulated:
                signals = tuple(signal.model_copy(update={"provenance": "simulated"}) for signal in signals)
            try:
                inserted = self.store.save_poll(source, signals, self.pollers[source].export_state(),
                                                attempted_at=when, success=success, source_time=source_time, error=error)
            except Exception:
                # The detector may have advanced in memory before its atomic DB
                # write failed. Replaying that observation must still emit it.
                self.pollers[source].restore_state(prior_state)
                raise
            self.process_pending()
            return inserted
        finally:
            self._locks[source].release()

    def process_pending(self) -> None:
        self.initialize()
        with self._process_lock:
            self._process_pending_locked()

    def _process_pending_locked(self) -> None:
        for item in self.store.pending():
            signal_id = item["signal_id"]
            try:
                signal = self.signals.get_signal(signal_id)
                draft = LlmEventStructurer(None).structure(signal).draft
                observation = StructuredObservation(signal=signal, draft=draft)
                aggregator = EventAggregator(self.events, self.signals)
                match = aggregator.find_match(observation)
                if match is None:
                    self.store.mark(signal_id, "pending_review", draft=draft.model_dump(mode="json"))
                    continue
                from ..structure.rule_extractor import RuleEventExtractor
                rules = RuleEventExtractor()
                observations = [StructuredObservation(signal=old, draft=rules.extract(old))
                                for old_id in match.signals for old in [self.signals.get_signal(old_id)]]
                if signal_id not in match.signals:
                    observations.append(observation)
                aggregator.merge(match.event_id, observations)
                self.store.mark(signal_id, "merged", draft=draft.model_dump(mode="json"))
            except AmbiguousEventMatchError as exc:
                self.store.mark(signal_id, "pending_review", error=str(exc))
            except Exception as exc:
                self.store.mark(signal_id, "error", error=f"{type(exc).__name__}: {exc}")

    def status(self) -> list[dict[str, Any]]:
        self.initialize()
        return [self.store.status(source, enabled=self.enabled and not self.offline_mode,
                                  simulated=self.simulated) for source in SOURCE_INTERVALS]
