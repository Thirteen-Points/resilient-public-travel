"""CI-only storage probe, run inside a dedicated, disposable Compose project.

Seed application-owned EventStore/AdminStore data, recreate the container, then
check the same records. No external requests, real credentials or publication.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.admin.store import AdminStore, password_hash
from backend.app.ai.budget import ModelBudget
from backend.app.services.event_store import DEFAULT_DB_PATH, EventStore


def verify(phase: str) -> None:
    if os.getenv("P3_PERSISTENCE_FIXTURE") != "true":
        raise SystemExit("Run only in a disposable CI container with P3_PERSISTENCE_FIXTURE=true")
    os.environ["ADMIN_USERNAME"] = "p3-ci-fixture"
    os.environ["ADMIN_PASSWORD_HASH"] = password_hash("fixture-password-never-use-in-production")
    os.environ["ADMIN_ENCRYPTION_KEY"] = "p3-ci-fixture-encryption-key-never-use-in-production"
    events = EventStore(DEFAULT_DB_PATH)
    events.initialize()
    admin = AdminStore(DEFAULT_DB_PATH.parent / "admin.sqlite3", DEFAULT_DB_PATH)
    admin.initialize()
    budget = ModelBudget(DEFAULT_DB_PATH.parent / "ai_usage.sqlite3")
    if phase == "seed":
        fixture = json.loads(Path("contracts/seed/event.seed.json").read_text(encoding="utf-8"))["events"][0]
        fixture["event_id"] = "p3-container-persistence-fixture"
        fixture["title"] = "Simulated container recreation persistence fixture"
        events.create_event(fixture, actor="p3-ci")
        config = admin.settings()
        config["revision"] = 1
        config["sources"]["hko"]["poll_interval_seconds"] = 123
        admin.save_settings(config, 0, "p3-ci")
        budget.reserve("deepseek", {"base_url": "https://api.deepseek.com", "model": "deepseek-flash"},
                       {"system_prompt": "Simulated persistence probe", "user_prompt": "No external request"})
    else:
        event = events.get_event("p3-container-persistence-fixture")
        assert event.title == "Simulated container recreation persistence fixture"
        assert event.audit_log[0].actor == "p3-ci"
        assert admin.settings()["revision"] == 1
        assert admin.settings()["sources"]["hko"]["poll_interval_seconds"] == 123
        assert budget.summary()["calls"] == 1
        assert budget.summary()["spent_cny"] > 0
    print(json.dumps({"phase": phase, "passed": True,
                      "event_db": str(DEFAULT_DB_PATH), "admin_db": str(admin.path)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "check"])
    verify(parser.parse_args().phase)
