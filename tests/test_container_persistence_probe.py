"""Probe logic regression; the CI job separately verifies the real volume mount."""
from scripts import verify_container_persistence as probe


def test_probe_retains_application_event_audit_and_encrypted_admin_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "DEFAULT_DB_PATH", tmp_path / "events.sqlite3")
    monkeypatch.setenv("P3_PERSISTENCE_FIXTURE", "true")
    for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "ADMIN_ENCRYPTION_KEY"):
        monkeypatch.setenv(name, "")
    probe.verify("seed")
    probe.verify("check")


def test_probe_requires_explicit_disposable_fixture_mode(monkeypatch):
    import pytest
    monkeypatch.delenv("P3_PERSISTENCE_FIXTURE", raising=False)
    with pytest.raises(SystemExit, match="disposable"):
        probe.verify("seed")
