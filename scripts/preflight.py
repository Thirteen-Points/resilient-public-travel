"""Check local data/cached scenarios; optionally check a running demo API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.p4_readiness import SCENARIOS, frontend_readiness, media_readiness, simulation_readiness


def api_readiness(base: str, *, expected_sha: str | None = None, require_offline: bool = False) -> dict:
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        return {"ok": False, "error": "Use an HTTP(S) origin without credentials, query or path."}
    base = base.rstrip("/")
    checks = []
    for path in ("/api/health", "/api/health/deep", "/api/meta", *(f"/api/sim/result?scenario_id={s}" for s in SCENARIOS)):
        try:
            with urlopen(base + path, timeout=5) as response:
                body = json.load(response)
            if not isinstance(body, dict):
                raise ValueError("API response is not an object")
            if path in {"/api/health", "/api/health/deep"} and body.get("ok") is not True:
                raise ValueError("service reports degraded health")
            if path == "/api/health" and require_offline and body.get("mode") != "offline":
                raise ValueError("demo API is not in offline mode")
            if path == "/api/meta" and expected_sha:
                if not isinstance(body.get("build"), dict) or body["build"].get("commit_sha") != expected_sha:
                    raise ValueError("running API build differs from expected commit")
            if path.startswith("/api/sim/result"):
                scenario = path.split("=", 1)[1]
                expected_result = json.loads((ROOT / "data/sim" / f"{scenario}.json").read_text(encoding="utf-8"))
                if body != expected_result:
                    raise ValueError("running API cached result differs from this release checkout")
            checks.append({"path": path, "ok": True, "build": body.get("build")})
        except (OSError, ValueError, TypeError) as exc:
            checks.append({"path": path, "ok": False, "error": str(exc)})
    return {"ok": all(row["ok"] for row in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", help="Opt-in HTTP checks; omitted means no network calls.")
    parser.add_argument("--expected-build-sha")
    parser.add_argument("--require-offline", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Also require the prepared public frontend build.")
    parser.add_argument("--require-media", action="store_true", help="Final offline gate: require the recorded WebM and slides PDF.")
    args = parser.parse_args()
    if args.expected_build_sha and not re.fullmatch(r"[0-9a-f]{40}", args.expected_build_sha):
        parser.error("--expected-build-sha must be a full lowercase commit SHA")
    if (args.expected_build_sha or args.require_offline) and not args.api_base_url:
        parser.error("build/offline API assertions require --api-base-url")
    command = [sys.executable, str(ROOT / "scripts" / "validate_data.py")]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        validation = json.loads(run.stdout)
    except json.JSONDecodeError:
        # validate_data.py intentionally emits human-readable WARN/ERROR lines;
        # preserve them instead of treating documented warnings as a parse failure.
        validation = {"ok": run.returncode == 0, "output": run.stdout[-4000:]}
    simulations = simulation_readiness(ROOT)
    media = media_readiness(ROOT)
    frontend = frontend_readiness(ROOT)
    api = api_readiness(args.api_base_url, expected_sha=args.expected_build_sha, require_offline=args.require_offline) if args.api_base_url else {"ok": True, "checked": False}
    report = {
        "ok": run.returncode == 0 and bool(validation.get("ok")) and simulations["ok"] and api["ok"] and (not args.demo or frontend["ok"]) and (not args.require_media or media["ok"]),
        "offline": not bool(args.api_base_url),
        "llm_required": False,
        "validation": validation,
        "simulations": simulations, "api": api, "frontend": frontend, "media": media,
        "final_offline_media_ready": media["ok"],
        "start_command": "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
        "health_url": "http://127.0.0.1:8000/api/health",
        "notes": ["HTTP calls occur only with explicit --api-base-url; defaults check repository files only.",
                  "Use --demo --require-media for the offline package gate; inspect actual media playback and PDF rendering separately.",
                  "When AI_ENABLED=true without a key, the service keeps deterministic fallback mode."],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
