"""Atomic source checkpoints and Signals in the application's shared database."""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
from typing import Any

from ..signal_store import SignalStore
from .online_models import SourcePost


class IngestStore(SignalStore):
    def initialize(self):
        super().initialize()
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ingest_source_state (
                    source TEXT PRIMARY KEY, state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ingest_records (
                    source TEXT NOT NULL, post_id TEXT NOT NULL, revision TEXT NOT NULL,
                    published_at TEXT, collected_at TEXT NOT NULL, author_hint TEXT,
                    repost_json TEXT NOT NULL, original_json TEXT NOT NULL,
                    disposition TEXT NOT NULL, signal_id TEXT,
                    PRIMARY KEY (source, post_id, revision)
                );
                CREATE TABLE IF NOT EXISTS ingest_leases (
                    source TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at REAL NOT NULL
                );
            """)

    def state(self, source: str) -> dict[str, Any]:
        with self._connection() as db:
            row = db.execute("SELECT state_json FROM ingest_source_state WHERE source=?", (source,)).fetchone()
        return json.loads(row[0]) if row else {}

    @staticmethod
    def _write_state(db, source, state):
        db.execute("INSERT INTO ingest_source_state VALUES (?,?) "
                   "ON CONFLICT(source) DO UPDATE SET state_json=excluded.state_json",
                   (source, json.dumps(state, ensure_ascii=False)))

    def acquire(self, source, now=None, seconds=180):
        now = time.time() if now is None else now
        owner = secrets.token_hex(16)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM ingest_leases WHERE expires_at<=?", (now,))
            try:
                db.execute("INSERT INTO ingest_leases VALUES (?,?,?)", (source, owner, now + seconds))
            except sqlite3.IntegrityError:
                return None
        return owner

    @staticmethod
    def _require_lease(db, source, owner, now):
        row = db.execute("SELECT owner, expires_at FROM ingest_leases WHERE source=?", (source,)).fetchone()
        if row is None or row[0] != owner or row[1] <= now:
            raise RuntimeError("source_lease_lost")

    def save_state(self, source, owner, state, now):
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_lease(db, source, owner, now)
            self._write_state(db, source, state)
            db.execute("UPDATE ingest_leases SET expires_at=? WHERE source=? AND owner=?", (now + 180, source, owner))

    def commit_page(self, source, owner, records, state, collected_at):
        """Commit a full page or none of it, including its continuation cursor."""
        added = duplicate = 0
        # Validate every Signal before the write lock, preserving all-or-none.
        prepared = [(post, reason, post.to_signal(collected_at) if reason is None else None)
                    for post, reason in records]
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_lease(db, source, owner, collected_at.timestamp())
            for post, reason, signal in prepared:
                if signal:
                    existing = db.execute("SELECT 1 FROM signals WHERE signal_id=?", (signal.signal_id,)).fetchone()
                    if existing:
                        duplicate += 1
                    else:
                        self._insert_signal(db, signal)
                        added += 1
                db.execute(
                    "INSERT INTO ingest_records VALUES (?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(source, post_id, revision) DO UPDATE SET "
                    "published_at=COALESCE(excluded.published_at, ingest_records.published_at), "
                    "disposition=CASE WHEN excluded.signal_id IS NOT NULL OR ingest_records.signal_id IS NULL "
                    "THEN excluded.disposition ELSE ingest_records.disposition END, "
                    "original_json=CASE WHEN excluded.signal_id IS NOT NULL AND ingest_records.signal_id IS NULL "
                    "THEN excluded.original_json ELSE ingest_records.original_json END, "
                    "signal_id=COALESCE(ingest_records.signal_id, excluded.signal_id)",
                    (source, post.post_id, post.revision,
                     post.published_at.isoformat() if post.published_at else None,
                     collected_at.isoformat(), post.author_hint, json.dumps(post.repost_of),
                     json.dumps(post.original, ensure_ascii=False), reason or "accepted",
                     signal.signal_id if signal else None),
                )
            state["counts"]["added"] += added
            state["counts"]["duplicate"] += duplicate
            self._write_state(db, source, state)
            db.execute("UPDATE ingest_leases SET expires_at=? WHERE source=? AND owner=?",
                       (collected_at.timestamp() + 180, source, owner))
        return added, duplicate

    def release(self, source, owner):
        with self._connection() as db:
            db.execute("DELETE FROM ingest_leases WHERE source=? AND owner=?", (source, owner))

    def records(self, source):
        with self._connection() as db:
            return [dict(x) for x in db.execute(
                "SELECT source, post_id, revision, published_at, collected_at, author_hint, "
                "disposition, signal_id, repost_json FROM ingest_records WHERE source=? "
                "ORDER BY collected_at, post_id", (source,)).fetchall()]
