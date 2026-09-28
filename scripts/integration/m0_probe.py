"""Read-only M0 process/HTTP probe. No replacement health or business handlers."""
from __future__ import annotations

import json
from dataclasses import asdict
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from .contracts import validate_payload, validate_response

ROOT = Path(__file__).resolve().parents[2]


def request(base, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return {"status": response.status, "body": json.load(response)}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": json.loads(exc.read())}


def probe(*, synthetic=False, smoke_output=None):
    env = os.environ.copy()
    env.update(AI_ENABLED="false", LLM_ENABLED="false", OFFLINE_MODE="true")
    # Default probe must exercise default paths, not inherit a developer override.
    for key in ("SEED_NETWORK", "SEED_EVENTS", "DEEP_HEALTH_ORIGIN",
                "DEEP_HEALTH_DESTINATION", "DEEP_HEALTH_DEPART_AT"):
        env.pop(key, None)
    if synthetic:
        env["SEED_NETWORK"] = str(ROOT / "backend/app/engine/fixtures/network.synthetic.json")
        env["SEED_EVENTS"] = str(ROOT / "backend/app/engine/fixtures/events.synthetic.json")
        # Use the new DevOps configuration boundary for the existing O/D fixture.
        env.update(DEEP_HEALTH_ORIGIN="O", DEEP_HEALTH_DESTINATION="D",
                   DEEP_HEALTH_DEPART_AT="2026-09-22T08:20:00+08:00")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [sys.executable, "-m", "uvicorn", "backend.app.main:app",
               "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result = {"configuration": "explicit_simulated_fixture" if synthetic else "defaults",
                  "command": ["python", *command[1:]], "simulated": True,
                  "configured_deep_health": {k: env[k] for k in ("DEEP_HEALTH_ORIGIN",
                      "DEEP_HEALTH_DESTINATION", "DEEP_HEALTH_DEPART_AT") if k in env}}
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 12
            while True:
                try:
                    result["health"] = request(base, "/api/health")
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("Server did not expose health before deadline")
                    time.sleep(0.1)
            if smoke_output is not None:
                smoke_command = [sys.executable, str(ROOT / "scripts/od_smoke.py"),
                                 "--base-url", base, "--depart-at", "2026-09-22T08:20:00+08:00",
                                 "--output", str(smoke_output)]
                smoke = subprocess.run(smoke_command, cwd=ROOT, env=env, capture_output=True,
                                       text=True, encoding="utf-8", timeout=180)
                result["od_smoke"] = {"command": ["python", *smoke_command[1:]],
                                      "returncode": smoke.returncode, "stderr": smoke.stderr}
            result["deep_health"] = request(base, "/api/health/deep")
            result["health_deep_query"] = request(base, "/api/health?deep=true")
            result["route"] = request(base, "/api/routes/query", {
                "origin": "O" if synthetic else "TAW",
                "destination": "D" if synthetic else "ADM",
                "depart_at": "2026-09-22T08:20:00+08:00"})
            if result["route"]["status"] == 200:
                result["route"]["contract_errors"] = [asdict(f) for f in validate_response(
                    "POST", "/api/routes/query", 200, result["route"]["body"])]
            result["sim_result"] = request(base, "/api/sim/result?scenario_id=scn_huh_exc_closed_am_peak")
            result["ai_chat"] = request(base, "/api/ai/chat", {
                "message": "simulated route query", "origin": "O" if synthetic else "TAW",
                "destination": "D" if synthetic else "ADM", "depart_at": "2026-09-22T08:20:00+08:00"})
            if result["sim_result"]["status"] == 200:
                result["sim_result"]["contract_errors"] = [asdict(f) for f in validate_payload(
                    "SimResult", result["sim_result"]["body"])]
            if result["ai_chat"]["status"] == 200:
                chat = result["ai_chat"]["body"]
                result["ai_chat"]["contract_errors"] = [asdict(f) for f in validate_response(
                    "POST", "/api/routes/query", 200, chat.get("routes"))]
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.seek(0)
            result["server_log"] = log.read().decode("utf-8", errors="replace")[-5000:]
        return result


def assess(observation):
    label = observation["configuration"]
    if "error" in observation:
        return [{"name": f"runtime.{label}", "status": "FAIL", "detail": observation["error"]}]
    health = observation["health"]
    route = observation["route"]
    health_ok = health["status"] == 200 and health["body"].get("ok") is True
    route_ok = (route["status"] == 200 and isinstance(route["body"], list) and
                bool(route["body"]) and not route.get("contract_errors") and
                all(r.get("provenance") == "simulated" for r in route["body"]))
    return [
        {"name": f"runtime.{label}.health", "status": "CONDITIONAL" if health_ok else "FAIL",
         "detail": f"HTTP {health['status']}; health availability is not database/four-seed acceptance"},
        {"name": f"runtime.{label}.route", "status": "CONDITIONAL" if route_ok else "FAIL",
         "detail": f"HTTP {route['status']}; simulated routes only; no verified transport data"},
    ]


def main():
    observations = [probe(), probe(synthetic=True)]
    checks = [check for observation in observations for check in assess(observation)]
    # §8 asks for database and seed state. Record concrete returned fields,
    # and do not treat a generic health 200 as satisfying this requirement.
    body = observations[1].get("health", {}).get("body", {})
    database = body.get("database", body.get("db"))
    checks.append({"name": "section8.health_database", "status": "UNVERIFIED" if database else "BLOCKED",
                   "detail": "Database field returned; inspect semantics" if database else "No database status returned"})
    for observation in observations:
        label = observation["configuration"]
        deep = observation.get("deep_health", {})
        ok = deep.get("status") == 200 and deep.get("body", {}).get("ok") is True
        checks.append({"name": f"runtime.{label}.deep_health", "status": "CONDITIONAL" if ok else "BLOCKED",
                       "detail": f"HTTP {deep.get('status')}; local checks only; inspect captured route/seed/cache checks"})
        for endpoint in ("ai_chat", "sim_result"):
            response = observation.get(endpoint, {})
            body = response.get("body", {})
            ok = response.get("status") == 200 and not response.get("contract_errors")
            if endpoint == "ai_chat":
                calls = body.get("tool_calls", [])
                ok = ok and isinstance(body.get("message"), str) and len(calls) >= 2 and all(c.get("ok") for c in calls)
            else:
                ok = ok and body.get("provenance") == "simulated"
            checks.append({"name": f"runtime.{label}.{endpoint}", "status": "CONDITIONAL" if ok else "FAIL",
                           "detail": f"HTTP {response.get('status')}; simulated local results, no live-data claim"})
    print(json.dumps({"observations": observations, "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if any(row["status"] == "FAIL" for row in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
