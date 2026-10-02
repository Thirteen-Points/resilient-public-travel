"""Durable administration state, separate from the event database."""
from __future__ import annotations
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet

PROVIDERS = {
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
}

def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100_000 <= int(iterations) <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return secrets.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False

class AdminStore:
    def __init__(self, path: Path, event_db: Path):
        self.path, self.event_db = path, event_db
        self.username = os.getenv("ADMIN_USERNAME", "").strip()
        self.password = os.getenv("ADMIN_PASSWORD_HASH", "")
        key = os.getenv("ADMIN_ENCRYPTION_KEY", "")
        try:
            algorithm, rounds, salt, digest = self.password.split("$")
            valid_hash = algorithm == "pbkdf2_sha256" and 100_000 <= int(rounds) <= 2_000_000 and len(bytes.fromhex(salt)) >= 16 and len(bytes.fromhex(digest)) == 32
        except (ValueError, TypeError):
            valid_hash = False
        self.ready = bool(self.username and valid_hash and len(key) >= 32)
        self.cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())) if self.ready else None
        self.credential_revision = hashlib.sha256(self.password.encode()).hexdigest()

    def initialize(self):
        if not self.ready:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, identity TEXT NOT NULL, credential_revision TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS login_failures (bucket TEXT NOT NULL, at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS failure_time ON login_failures(bucket, at);
                CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, result TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS source_state (source TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS leases (source TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
            """)
        self.settings()  # Detect an unavailable/wrong encryption key without breaking public APIs.

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def settings(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE id=1").fetchone()
        if row:
            value = json.loads(self.cipher.decrypt(row[0].encode()))
            from .config import normalize_ai
            normalize_ai(value["ai"])
            return value
        providers = {name: {"model": model, "api_key": os.getenv(f"{name.upper()}_API_KEY", "")} for name, (_, model) in PROVIDERS.items()}
        for name in providers:
            providers[name]["model"] = os.getenv(f"{name.upper()}_MODEL", providers[name]["model"])
        return {"revision": 0, "ai": {"enabled": False, "provider": "deepseek", "timeout_s": 20, "providers": providers},
                "sources": {"mtr": {"enabled": False, "timeout_s": 10, "ttnt_threshold_minutes": 10,
                    "min_adjacent_stations": 2, "min_consecutive_polls": 2, "min_usable_stations": 4, "poll_interval_seconds": 60},
                    "hko": {"enabled": False, "timeout_s": 10, "lang": "tc", "poll_interval_seconds": 90}}}

    def public_settings(self):
        from .config import normalize_ai
        from .llm_runtime import fingerprint
        value = self.settings()
        normalize_ai(value["ai"])
        for name, provider in value["ai"]["providers"].items():
            provider.pop("api_key", None)
            provider["key_configured"] = any(k["value"] for k in provider["keys"])
            for key in provider["keys"]:
                state = self.source_state("llm:" + name + ":" + key["id"])
                key["status"] = state if state.get("fingerprint") == fingerprint(provider, key) else {}
                key["status"].pop("fingerprint", None)
                key["configured"] = bool(key.pop("value"))
        return value

    def record_llm(self, name, provider, key, ok, message, operation):
        from .llm_runtime import fingerprint
        state = {"fingerprint": fingerprint(provider, key), "ok": ok, "message": message,
            "operation": operation, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO source_state VALUES(?,?)", ("llm:" + name + ":" + key["id"], json.dumps(state)))
            self.record("administrator" if operation == "connection" else "system", "llm_" + operation,
                name + ":" + key["id"], "success" if ok else "failed", message, db)

    def save_settings(self, value, expected_revision, actor):
        encrypted = self.cipher.encrypt(json.dumps(value).encode()).decode()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM settings WHERE id=1").fetchone()
            revision = json.loads(self.cipher.decrypt(row[0].encode()))["revision"] if row else 0
            if revision != expected_revision:
                raise RuntimeError("Configuration changed. Reload before saving.")
            db.execute("INSERT OR REPLACE INTO settings VALUES (1, ?)", (encrypted,))
            self.record(actor, "config_saved", "API settings", "success", f"Revision {value['revision']}", db)

    def record(self, actor, action, target, result="success", detail="", db=None):
        if db is None:
            with self.connect() as connection:
                self.record(actor, action, target, result, detail, connection)
            return
        db.execute("INSERT INTO activity(at,actor,action,target,result,detail) VALUES(?,?,?,?,?,?)",
                   (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), actor, action, target, result, detail))

    def activities(self, before=None, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM activity WHERE id < ? ORDER BY id DESC LIMIT ?", (before or 2**63-1, limit)).fetchall()
        return [dict(row) for row in rows]

    def new_session(self):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), csrf, time.time()+8*3600, self.username, self.credential_revision))
        return token, csrf

    def session(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=? AND expires>? AND identity=? AND credential_revision=?", (hashlib.sha256(token.encode()).hexdigest(), time.time(), self.username, self.credential_revision)).fetchone()
        return dict(row) if row else None

    def revoke(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def login_attempt(self, bucket):
        # Reserve an attempt atomically, including concurrent failures; successful login clears it.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM login_failures WHERE at<?", (time.time()-900,))
            count = db.execute("SELECT COUNT(*) FROM login_failures WHERE bucket=?", (bucket,)).fetchone()[0]
            if count >= 5:
                return False
            db.execute("INSERT INTO login_failures VALUES(?,?)", (bucket, time.time()))
        return True

    def clear_attempts(self, bucket):
        with self.connect() as db:
            db.execute("DELETE FROM login_failures WHERE bucket=?", (bucket,))

    def source_state(self, source):
        with self.connect() as db:
            row = db.execute("SELECT value FROM source_state WHERE source=?", (source,)).fetchone()
        return json.loads(row[0]) if row else {}

    def acquire(self, source):
        owner = secrets.token_hex(16)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM leases WHERE expires<?", (time.time(),))
            try:
                db.execute("INSERT INTO leases VALUES(?,?,?)", (source, owner, time.time()+180))
            except sqlite3.IntegrityError:
                raise RuntimeError("This source is already running. Try again shortly.")
        return owner

    def release(self, source, owner):
        with self.connect() as db:
            db.execute("DELETE FROM leases WHERE source=? AND owner=?", (source, owner))

    def finish_collection(self, source, state, signals, actor, result):
        # Attached databases commit signals and poller state together (rollback journal on one disk).
        with self.connect() as db:
            db.execute("ATTACH DATABASE ? AS events_db", (str(self.event_db),))
            db.execute("BEGIN IMMEDIATE")
            added = duplicate = 0
            for signal in signals:
                cursor = db.execute("INSERT OR IGNORE INTO events_db.signals VALUES(?,?,?,?)",
                    (signal.signal_id, signal.received_at.isoformat(), signal.source_type, signal.model_dump_json()))
                added += cursor.rowcount
                duplicate += 1-cursor.rowcount
            result.update(added=added, duplicate=duplicate)
            state["last_result"] = result
            db.execute("INSERT OR REPLACE INTO source_state VALUES(?,?)", (source, json.dumps(state)))
            self.record(actor, "source_collected", source, result["status"], f"Added {added}; duplicates {duplicate}; failures {result['failures']}", db)
        return result
