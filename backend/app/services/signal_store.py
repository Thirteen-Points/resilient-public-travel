"""SQLite inbox for validated raw signals."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .event_store import DEFAULT_DB_PATH
from .signal_models import Signal


class SignalNotFoundError(KeyError):
    """Raised when a signal id does not exist."""


class SignalAlreadyExistsError(ValueError):
    """Raised when a signal id is already stored."""


class SignalStore:
    """Persist immutable Signals in the shared application SQLite database."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        """Create the inbox table idempotently without touching Event data."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_signals_received_at
                    ON signals(received_at, signal_id);
                """
            )

    def create_signal(self, signal: Signal | Mapping[str, Any]) -> Signal:
        """Validate and synchronously add one immutable Signal."""

        validated = signal if isinstance(signal, Signal) else Signal.model_validate(signal)
        payload_json = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            with self._connection() as connection:
                self._insert_signal(connection, validated, payload_json)
        except sqlite3.IntegrityError as exc:
            if "signals.signal_id" in str(exc):
                raise SignalAlreadyExistsError(validated.signal_id) from exc
            raise
        return self.get_signal(validated.signal_id)

    @staticmethod
    def _insert_signal(
        connection: sqlite3.Connection, signal: Signal, payload_json: str | None = None,
    ) -> None:
        """Internal transaction boundary also used by durable source ingestion."""
        connection.execute(
            "INSERT INTO signals (signal_id, received_at, source_type, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (signal.signal_id, signal.received_at.isoformat(), signal.source_type,
             payload_json if payload_json is not None else signal.model_dump_json()),
        )

    def get_signal(self, signal_id: str) -> Signal:
        """Read one Signal by id."""

        self._require_non_empty(signal_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM signals WHERE signal_id = ?", (signal_id,)
            ).fetchone()
        if row is None:
            raise SignalNotFoundError(signal_id)
        return Signal.model_validate(json.loads(row["payload_json"]))

    def list_signals(self) -> list[Signal]:
        """List the pending inbox oldest-first in deterministic order."""

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM signals
                ORDER BY received_at, signal_id
                """
            ).fetchall()
        return [Signal.model_validate(json.loads(row["payload_json"])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _require_non_empty(signal_id: str) -> None:
        if not signal_id or not signal_id.strip():
            raise ValueError("signal_id must not be empty")
