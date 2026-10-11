"""Exercise readiness failures without starting services or changing repository data."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from scripts import package_offline, preflight
from scripts.p4_readiness import (
    MEDIA,
    SCENARIOS,
    frontend_readiness,
    frozen_text_matches,
    media_readiness,
    simulation_readiness,
    text_sha256,
)
from scripts.package_offline import package_files


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2) + "\n").encode("utf-8"))


@pytest.fixture
def prepared_simulation(tmp_path):
    """Small independent fixture for the delivery contract, not the simulation model."""
    versions = {}
    for kind, name in (("network", "contracts/network.json"), ("route_policy", "contracts/policy.json")):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = b'{"fixture": "local simulated data"}\n'
        path.write_bytes(content)
        versions[f"{kind}_file"] = name
        versions[f"{kind}_sha256"] = hashlib.sha256(content).hexdigest()
    payload = {"data_version": versions}
    input_path = tmp_path / "data/sim/m2-route-input.json"
    write_json(input_path, payload)
    frozen_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    for scenario in SCENARIOS:
        strategy = {
            "total_delay_person_min": 100.0,
            "p95_wait_min": 2.0,
            "served_demand": 9900,
            "unmet_demand": 100,
            "overloaded_routes": 1,
            "resource_load": [{"resource_id": "shared-segment-1"}, {"resource_id": "shared-segment-2"}],
        }
        result = {
            "scenario_id": scenario,
            "provenance": "simulated",
            "population": 10000,
            "seed": 20260922,
            "od_count": 30,
            "input_sha256": frozen_hash,
            "data_version": versions,
            "assumptions": ["Simulated inputs; observed passenger demand is unavailable."],
            "input_version": "fixture-input-v1",
            "model_version": "shared-directed-segments-v1",
            "generated_at": "2026-10-05T08:00:00+00:00",
            "query_time": "2026-09-22T08:00:00+08:00",
            "metric_units": {
                "total_delay_person_min": "person-minutes",
                "unmet_demand": "people/window",
                "served_demand": "people/window",
                "service_capacity_per_hour": "people/hour",
            },
            "capacity_model": {"shared_resource_count": 2, "partial_segment_overlap_modelled": True},
            "baseline": strategy,
            "guided": strategy,
            "delta": {"total_delay_person_min": -10.0},
        }
        write_json(tmp_path / "data/sim" / f"{scenario}.json", result)
    return tmp_path


def modify_result(root: Path, modify, scenario=SCENARIOS[0]):
    path = root / "data/sim" / f"{scenario}.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    modify(result)
    write_json(path, result)


def test_prepared_delivery_accepts_negative_benefit_without_rewriting(prepared_simulation):
    path = prepared_simulation / "data/sim" / f"{SCENARIOS[0]}.json"
    before = path.read_bytes()
    assert simulation_readiness(prepared_simulation)["ok"] is True
    assert path.read_bytes() == before
    assert json.loads(before)["delta"]["total_delay_person_min"] < 0


@pytest.mark.parametrize("stored_line_ending", [b"\n", b"\r\n"])
@pytest.mark.parametrize("historical_line_ending", [b"\n", b"\r\n"])
def test_historical_frozen_hash_survives_git_line_ending_conversion(tmp_path, stored_line_ending, historical_line_ending):
    path = tmp_path / "snapshot.json"
    path.write_bytes(b'{"capacity": 10}' + stored_line_ending)
    historical_hash = hashlib.sha256(b'{"capacity": 10}' + historical_line_ending).hexdigest()
    assert frozen_text_matches(path, historical_hash)
    assert text_sha256(path) == hashlib.sha256(b'{"capacity": 10}\n').hexdigest()
    path.write_bytes(b'{"capacity": 11}' + stored_line_ending)
    assert not frozen_text_matches(path, historical_hash)


def test_simulation_contract_survives_crlf_checkout(prepared_simulation):
    for path in prepared_simulation.rglob("*.json"):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert simulation_readiness(prepared_simulation)["ok"] is True


@pytest.mark.parametrize("missing", ["input", "network", "cache"])
def test_missing_required_simulation_file_reports_failure(prepared_simulation, missing):
    paths = {
        "input": "data/sim/m2-route-input.json",
        "network": "contracts/network.json",
        "cache": f"data/sim/{SCENARIOS[0]}.json",
    }
    (prepared_simulation / paths[missing]).unlink()
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    errors = [report.get("error", ""), *(row.get("error", "") for row in report["scenarios"])]
    assert any(errors)


@pytest.mark.parametrize("field", ["assumptions", "input_version", "model_version", "input_sha256", "generated_at", "query_time", "metric_units"])
def test_missing_result_metadata_is_not_inferred(prepared_simulation, field):
    modify_result(prepared_simulation, lambda result: result.pop(field))
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    assert report["scenarios"][0]["ok"] is False
    assert report["scenarios"][1]["ok"] is True


@pytest.mark.parametrize("field", ["total_delay_person_min", "unmet_demand", "served_demand", "service_capacity_per_hour"])
def test_missing_metric_unit_fails(prepared_simulation, field):
    modify_result(prepared_simulation, lambda result: result["metric_units"].pop(field))
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    assert "missing metric unit" in report["scenarios"][0]["error"]


@pytest.mark.parametrize("field", ["generated_at", "query_time"])
def test_timestamp_without_timezone_fails(prepared_simulation, field):
    modify_result(prepared_simulation, lambda result: result.update({field: "2026-10-05T08:00:00"}))
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    assert "timezone" in report["scenarios"][0]["error"]


@pytest.mark.parametrize("strategy", ["baseline", "guided"])
def test_repeated_shared_resource_is_rejected(prepared_simulation, strategy):
    def repeat_resource(result):
        rows = result[strategy]["resource_load"]
        rows[1]["resource_id"] = rows[0]["resource_id"]
    modify_result(prepared_simulation, repeat_resource)
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    assert "duplicated" in report["scenarios"][0]["error"]


def test_demand_gap_must_be_explicit(prepared_simulation):
    modify_result(prepared_simulation, lambda result: result["guided"].update({"unmet_demand": 0}))
    report = simulation_readiness(prepared_simulation)
    assert report["ok"] is False
    assert "demand accounting" in report["scenarios"][0]["error"]


@pytest.fixture
def prepared_frontend(tmp_path):
    directory = tmp_path / "frontend/dist"
    directory.mkdir(parents=True)
    (directory / "index.html").write_text("<html>Local demo</html>", encoding="utf-8")
    write_json(directory / "build-info.json", {"commit_sha": "a" * 40})
    marker = {
        "api_base_url": "http://127.0.0.1:8000",
        "source_revision": "a" * 40,
        "file_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()},
    }
    write_json(directory / "offline-build.json", marker)
    return tmp_path


@pytest.mark.parametrize("change", ["content", "remove", "inject", "identity", "remote_api"])
def test_frontend_integrity_gate_detects_changed_delivery(prepared_frontend, change):
    directory = prepared_frontend / "frontend/dist"
    assert frontend_readiness(prepared_frontend)["ok"] is True
    if change == "content":
        (directory / "index.html").write_text("changed", encoding="utf-8")
    elif change == "remove":
        (directory / "build-info.json").unlink()
    elif change == "inject":
        (directory / "unlisted.js").write_text("unexpected", encoding="utf-8")
    else:
        marker_path = directory / "offline-build.json"
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker.update({"source_revision": "b" * 40} if change == "identity" else {"api_base_url": "https://example.invalid"})
        write_json(marker_path, marker)
    assert frontend_readiness(prepared_frontend)["ok"] is False


@pytest.mark.parametrize("identity", [None, []])
def test_nonobject_frontend_build_identity_is_structured_failure(prepared_frontend, identity):
    directory = prepared_frontend / "frontend/dist"
    identity_path = directory / "build-info.json"
    write_json(identity_path, identity)
    marker_path = directory / "offline-build.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["file_sha256"]["build-info.json"] = hashlib.sha256(identity_path.read_bytes()).hexdigest()
    write_json(marker_path, marker)
    report = frontend_readiness(prepared_frontend)
    assert report["ok"] is False
    assert "identities" in report["error"]


@pytest.mark.parametrize("content", [None, b"", b"A text file renamed to pretend to be media."])
def test_missing_empty_or_extension_disguised_media_fails(tmp_path, content):
    directory = tmp_path / "deploy/offline/media"
    directory.mkdir(parents=True)
    if content is not None:
        (tmp_path / MEDIA["video"]).write_bytes(content)
        (directory / "slides.pdf").write_bytes(content)
    report = media_readiness(tmp_path)
    assert report["ok"] is False
    assert not any(row["format_ok"] for row in report["files"].values())


def test_unavailable_api_keeps_all_failed_checks(monkeypatch):
    calls = []
    def unavailable(url, *, timeout):
        calls.append(url)
        raise URLError("demo service is not ready")
    monkeypatch.setattr(preflight, "urlopen", unavailable)
    report = preflight.api_readiness("http://127.0.0.1:8000", require_offline=True)
    assert report["ok"] is False
    assert len(calls) == len(SCENARIOS) + 3
    assert all(not row["ok"] and "not ready" in row["error"] for row in report["checks"])


@pytest.mark.parametrize("origin", ["ftp://127.0.0.1", "http://user:secret@127.0.0.1", "http://127.0.0.1/path", "http://127.0.0.1?token=secret"])
def test_invalid_api_origin_is_rejected_before_network(monkeypatch, origin):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Invalid origin must not issue a request")
    monkeypatch.setattr(preflight, "urlopen", unexpected_call)
    assert preflight.api_readiness(origin)["ok"] is False


@pytest.mark.parametrize("body", [{"ok": False}, [], None])
def test_degraded_or_nonobject_api_response_fails(monkeypatch, body):
    monkeypatch.setattr(preflight, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps(body).encode()))
    report = preflight.api_readiness("http://127.0.0.1:8000")
    assert report["ok"] is False
    assert report["checks"][0]["ok"] is False


@pytest.mark.parametrize("build", [None, []])
def test_malformed_api_build_identity_is_structured_failure(monkeypatch, build):
    def response(url, *, timeout):
        body = {"build": build} if url.endswith("/api/meta") else {"ok": True}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(preflight, "urlopen", response)
    report = preflight.api_readiness("http://127.0.0.1:8000", expected_sha="a" * 40)
    meta = next(row for row in report["checks"] if row["path"] == "/api/meta")
    assert report["ok"] is False
    assert meta["ok"] is False
    assert "build" in meta["error"]


@pytest.mark.parametrize("change", [None, "metric_units", "population", "unmet_demand", "data_version"])
def test_api_must_serve_the_exact_release_cache(prepared_simulation, monkeypatch, change):
    monkeypatch.setattr(preflight, "ROOT", prepared_simulation)
    def response(url, *, timeout):
        if "/api/sim/result?scenario_id=" in url:
            scenario = url.split("=", 1)[1]
            body = json.loads((prepared_simulation / "data/sim" / f"{scenario}.json").read_text(encoding="utf-8"))
            if change and scenario == SCENARIOS[0]:
                if change == "metric_units":
                    body["metric_units"]["total_delay_person_min"] = "minutes"
                elif change == "population":
                    body["population"] = 9999
                elif change == "unmet_demand":
                    body["guided"]["unmet_demand"] = 0
                else:
                    body["data_version"]["network_sha256"] = "b" * 64
        elif url.endswith("/api/meta"):
            body = {"build": {"commit_sha": "a" * 40}}
        else:
            body = {"ok": True, "mode": "offline"}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(preflight, "urlopen", response)
    report = preflight.api_readiness("http://127.0.0.1:8000", expected_sha="a" * 40, require_offline=True)
    assert report["ok"] is (change is None)
    failed = [row for row in report["checks"] if not row["ok"]]
    if change:
        assert len(failed) == 1
        assert failed[0]["path"].endswith(SCENARIOS[0])
        assert "cached result differs" in failed[0]["error"]
    else:
        assert not failed


def test_offline_package_excludes_private_runtime_files(tmp_path):
    directory = tmp_path / "backend/app"
    for name in ("main.py", ".env", ".env.production", "events.sqlite3", "events.sqlite3-wal", "backend.log", "__pycache__/main.pyc"):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    names = [name for _, name in package_files(tmp_path)]
    assert names == ["backend/app/main.py"]


@pytest.mark.parametrize("require_media, expected_status", [(False, 0), (True, 1)])
def test_preflight_reports_missing_media_and_final_gate_fails(prepared_simulation, monkeypatch, capsys, require_media, expected_status):
    monkeypatch.setattr(preflight, "ROOT", prepared_simulation)
    monkeypatch.setattr(preflight.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"ok": true}'))
    monkeypatch.setattr(preflight.sys, "argv", ["preflight.py", *(["--require-media"] if require_media else [])])
    assert preflight.main() == expected_status
    report = json.loads(capsys.readouterr().out)
    assert report["final_offline_media_ready"] is False
    assert report["media"]["ok"] is False
    assert report["api"]["checked"] is False
    assert report["ok"] is (not require_media)


def test_final_package_refuses_missing_media(prepared_simulation, prepared_frontend, monkeypatch, capsys):
    assert prepared_simulation == prepared_frontend
    output = prepared_simulation / "final-demo.zip"
    monkeypatch.setattr(package_offline, "ROOT", prepared_simulation)
    monkeypatch.setattr(package_offline.sys, "argv", ["package_offline.py", "--require-media", "--output", str(output)])
    assert package_offline.main() == 1
    assert not output.exists()
    report = json.loads(capsys.readouterr().out)
    assert report["checks"]["simulation"]["ok"] is True
    assert report["checks"]["frontend"]["ok"] is True
    assert report["checks"]["media"]["ok"] is False


def test_generator_uses_frozen_network_after_live_seed_changes(tmp_path, monkeypatch):
    from scripts import precompute_sim_p3

    source = Path(__file__).resolve().parents[1]
    payload = json.loads((source / "data/sim/m2-route-input.json").read_text(encoding="utf-8"))
    write_json(tmp_path / "data/sim/m2-route-input.json", payload)
    for field in ("network_file", "route_policy_file"):
        relative = payload["data_version"][field]
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / relative).read_bytes())
    # The live network is intentionally unusable. Historical simulations must
    # resolve the manifest snapshot and still enforce its exact content hash.
    write_json(tmp_path / "contracts/seed/network.seed.json", {})
    monkeypatch.setattr(precompute_sim_p3, "ROOT", tmp_path)
    actual, _, resources, _ = precompute_sim_p3.simulation_inputs()
    assert actual["data_version"] == payload["data_version"]
    assert len(resources) == 44
    snapshot = tmp_path / payload["data_version"]["network_file"]
    changed = json.loads(snapshot.read_text(encoding="utf-8"))
    changed["meta"]["note"] = "tampered frozen snapshot"
    write_json(snapshot, changed)
    with pytest.raises(ValueError, match="network hash differs"):
        precompute_sim_p3.simulation_inputs()
