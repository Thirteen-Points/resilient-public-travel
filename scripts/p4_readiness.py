"""Dependency-free checks shared by preflight and the offline package."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

SCENARIOS = (
    "m2_six_station_directed_od_am_peak_p3_shared_segments",
    "m2_six_station_directed_od_am_peak_p3_shared_segments_residual_10pct",
)
MEDIA = {"video": "deploy/offline/media/demo.webm", "slides_pdf": "deploy/offline/media/slides.pdf"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen_text_matches(path: Path, expected: str) -> bool:
    """Accept historical LF or CRLF byte hashes without changing text content."""
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    return expected in {hashlib.sha256(normalized).hexdigest(),
                       hashlib.sha256(normalized.replace(b"\n", b"\r\n")).hexdigest()}


def simulation_readiness(root: Path) -> dict:
    checks = []
    try:
        input_path = root / "data/sim/m2-route-input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        input_hash = text_sha256(input_path)
        for file_key, hash_key in (("network_file", "network_sha256"), ("route_policy_file", "route_policy_sha256")):
            if not frozen_text_matches(root / payload["data_version"][file_key], payload["data_version"][hash_key]):
                raise ValueError(f"frozen {file_key} hash differs")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "error": str(exc), "scenarios": []}
    for scenario in SCENARIOS:
        try:
            result = json.loads((root / "data/sim" / f"{scenario}.json").read_text(encoding="utf-8"))
            if result["scenario_id"] != scenario or result["provenance"] != "simulated":
                raise ValueError("scenario identity or provenance differs")
            if (result["population"], result["seed"], result["od_count"]) != (10000, 20260922, 30):
                raise ValueError("frozen population, seed or OD count differs")
            if result["input_sha256"] != input_hash or result["data_version"] != payload["data_version"]:
                raise ValueError("result refers to a different frozen input")
            if not result["assumptions"] or not result["input_version"] or not result["model_version"]:
                raise ValueError("missing assumptions or input/model version")
            for field in ("generated_at", "query_time"):
                if datetime.fromisoformat(result[field]).tzinfo is None:
                    raise ValueError(f"{field} must include a timezone")
            if not isinstance(result["metric_units"], dict):
                raise ValueError("metric_units must be an object")
            for field in ("total_delay_person_min", "unmet_demand", "served_demand", "service_capacity_per_hour"):
                if not result["metric_units"].get(field):
                    raise ValueError(f"missing metric unit: {field}")
            count = result["capacity_model"]["shared_resource_count"]
            if count <= 0 or not result["capacity_model"]["partial_segment_overlap_modelled"]:
                raise ValueError("shared directed-segment model is missing")
            for strategy in ("baseline", "guided"):
                metrics = result[strategy]
                for field in ("total_delay_person_min", "p95_wait_min", "served_demand", "unmet_demand", "overloaded_routes"):
                    if not isinstance(metrics[field], (int, float)) or not math.isfinite(metrics[field]) or metrics[field] < 0:
                        raise ValueError(f"invalid {strategy}.{field}")
                if metrics["served_demand"] + metrics["unmet_demand"] != result["population"]:
                    raise ValueError(f"{strategy} demand accounting differs")
                ids = [row["resource_id"] for row in metrics["resource_load"]]
                if len(ids) != count or len(set(ids)) != count:
                    raise ValueError("shared resource IDs are missing or duplicated")
            checks.append({"scenario_id": scenario, "ok": True, "sha256": sha256(root / "data/sim" / f"{scenario}.json")})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append({"scenario_id": scenario, "ok": False, "error": str(exc)})
    return {"ok": all(row["ok"] for row in checks), "input_sha256": input_hash, "scenarios": checks}


def media_readiness(root: Path) -> dict:
    rows = {}
    for name, relative in MEDIA.items():
        path = root / relative
        present = path.is_file() and path.stat().st_size > 0
        header = b""
        if present:
            with path.open("rb") as stream:
                header = stream.read(12)
        valid = header.startswith(b"%PDF-") if name == "slides_pdf" else header.startswith(b"\x1aE\xdf\xa3")
        rows[name] = {"path": relative, "present": present, "format_ok": valid}
    return {"ok": all(row["present"] and row["format_ok"] for row in rows.values()), "files": rows}


def frontend_readiness(root: Path) -> dict:
    directory = root / "frontend/dist"
    try:
        marker = json.loads((directory / "offline-build.json").read_text(encoding="utf-8"))
        if marker["api_base_url"] != "http://127.0.0.1:8000":
            raise ValueError("frontend was not prepared for the local offline API")
        hashes = marker["file_sha256"]
        if not isinstance(hashes, dict):
            raise ValueError("frontend hash inventory must be an object")
        actual_files = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file() and path.name != "offline-build.json"}
        if set(hashes) != actual_files or "index.html" not in hashes or "build-info.json" not in hashes:
            raise ValueError("frontend build inventory differs")
        for name, expected in hashes.items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory.resolve()) or sha256(path) != expected:
                raise ValueError("frontend build file hash differs")
        identity = json.loads((directory / "build-info.json").read_text(encoding="utf-8"))
        if not isinstance(identity, dict) or identity.get("commit_sha") != marker["source_revision"]:
            raise ValueError("frontend build identities differ")
        return {"ok": True, "build": identity, "file_count": len(hashes)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"ok": False, "error": str(exc), "prepare_command": "python scripts/package_offline.py --build"}
