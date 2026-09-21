"""SQLite persistence for the Event contract and append-only audit history."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .event_models import AuditEntry, Event, EventStatus


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "events.sqlite3"


class EventNotFoundError(KeyError):
    """Raised when an event id does not exist."""


class EventAlreadyExistsError(ValueError):
    """Raised when creating an event whose id is already stored."""


class EventStore:
    """Persist validated events and immutable audit entries in SQLite.

    The Event JSON is stored without ``audit_log``.  Audit history lives in its
    own append-only table and is attached whenever an Event is read.  This
    prevents a later event update from overwriting its history.
    """

    _IMMUTABLE_UPDATE_FIELDS = {
        "event_id",
        "version",
        "created_at",
        "updated_at",
        "audit_log",
    }

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        """Create storage objects if absent without changing existing data."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL CHECK (version >= 1),
                    status TEXT NOT NULL CHECK (status IN (
                        'draft', 'pending_review', 'published',
                        'updated', 'expired', 'rejected'
                    )),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_status
                    ON events(status);
                CREATE INDEX IF NOT EXISTS idx_events_updated_at
                    ON events(updated_at DESC);

                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence_after REAL NOT NULL
                        CHECK (confidence_after >= 0 AND confidence_after <= 1)
                );

                CREATE INDEX IF NOT EXISTS idx_audit_event_id
                    ON audit_log(event_id, audit_id);

                CREATE TRIGGER IF NOT EXISTS audit_log_no_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END;
                """
            )

    def create_event(
        self,
        event: Event | Mapping[str, Any],
        *,
        actor: str = "system",
    ) -> Event:
        """Validate and create an Event plus its first audit record."""

        validated = event if isinstance(event, Event) else Event.model_validate(event)
        self._require_non_empty(actor, "actor")
        payload = self._payload_without_audit(validated)

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO events (
                        event_id, version, status, created_at, updated_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        validated.event_id,
                        validated.version,
                        validated.status,
                        validated.created_at.isoformat(),
                        validated.updated_at.isoformat(),
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                self._append_audit(
                    connection,
                    event_id=validated.event_id,
                    at=validated.created_at,
                    actor=actor,
                    action="created",
                    confidence_after=validated.confidence,
                )
        except sqlite3.IntegrityError as exc:
            if "events.event_id" in str(exc):
                raise EventAlreadyExistsError(validated.event_id) from exc
            raise

        return self.get_event(validated.event_id)

    def get_event(self, event_id: str) -> Event:
        """Return one Event with its complete audit history."""

        self._require_non_empty(event_id, "event_id")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                raise EventNotFoundError(event_id)
            return self._event_from_row(connection, row)

    def list_events(self, *, status: EventStatus | None = None) -> list[Event]:
        """List Events newest-first, optionally filtered by contract status."""

        if status is None:
            sql = "SELECT payload_json FROM events ORDER BY updated_at DESC, event_id"
            parameters: tuple[str, ...] = ()
        else:
            # Validate the filter using the contract rather than accepting an
            # arbitrary value that would silently return an empty list.
            valid_statuses = {
                "draft",
                "pending_review",
                "published",
                "updated",
                "expired",
                "rejected",
            }
            if status not in valid_statuses:
                raise ValueError(f"invalid event status: {status}")
            sql = (
                "SELECT payload_json FROM events WHERE status = ? "
                "ORDER BY updated_at DESC, event_id"
            )
            parameters = (status,)

        with self._connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
            return [self._event_from_row(connection, row) for row in rows]

    def update_event(
        self,
        event_id: str,
        updates: Mapping[str, Any],
        *,
        actor: str,
        action: str = "updated",
        at: datetime | None = None,
    ) -> Event:
        """Apply a validated partial update and append one audit record.

        Review transition rules are deliberately not implemented here; those
        belong to T2.10.  This storage layer only enforces contract validity.
        """

        self._require_non_empty(actor, "actor")
        self._require_non_empty(action, "action")
        forbidden = self._IMMUTABLE_UPDATE_FIELDS.intersection(updates)
        if forbidden:
            fields = ", ".join(sorted(forbidden))
            raise ValueError(f"immutable fields cannot be updated: {fields}")

        current = self.get_event(event_id)
        timestamp = at or datetime.now(timezone.utc)
        merged = current.model_dump(mode="python")
        merged.update(dict(updates))
        merged["event_id"] = current.event_id
        merged["version"] = current.version + 1
        merged["created_at"] = current.created_at
        merged["updated_at"] = timestamp
        merged["audit_log"] = []
        validated = Event.model_validate(merged)
        payload = self._payload_without_audit(validated)

        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE events
                SET version = ?, status = ?, updated_at = ?, payload_json = ?
                WHERE event_id = ? AND version = ?
                """,
                (
                    validated.version,
                    validated.status,
                    validated.updated_at.isoformat(),
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    event_id,
                    current.version,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("event was updated concurrently; retry the operation")
            self._append_audit(
                connection,
                event_id=event_id,
                at=timestamp,
                actor=actor,
                action=action,
                confidence_after=validated.confidence,
            )

        return self.get_event(event_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a transaction and always release the SQLite file handle."""

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _payload_without_audit(event: Event) -> dict[str, Any]:
        payload = event.model_dump(mode="json")
        payload["audit_log"] = []
        return payload

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        event_id: str,
        at: datetime,
        actor: str,
        action: str,
        confidence_after: float,
    ) -> None:
        entry = AuditEntry(
            at=at,
            actor=actor,
            action=action,
            confidence_after=confidence_after,
        )
        connection.execute(
            """
            INSERT INTO audit_log (
                event_id, at, actor, action, confidence_after
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                entry.at.isoformat(),
                entry.actor,
                entry.action,
                entry.confidence_after,
            ),
        )

    @staticmethod
    def _event_from_row(
        connection: sqlite3.Connection, row: sqlite3.Row
    ) -> Event:
        payload = json.loads(row["payload_json"])
        audit_rows = connection.execute(
            """
            SELECT at, actor, action, confidence_after
            FROM audit_log
            WHERE event_id = ?
            ORDER BY audit_id
            """,
            (payload["event_id"],),
        ).fetchall()
        payload["audit_log"] = [dict(audit_row) for audit_row in audit_rows]
        return Event.model_validate(payload)

    @staticmethod
    def _require_non_empty(value: str, field_name: str) -> None:
        if not value or not value.strip():
            raise ValueError(f"{field_name} must not be empty")
