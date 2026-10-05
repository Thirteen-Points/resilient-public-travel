"""Run the prepared local API and frontend without downloading dependencies."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.p4_readiness import frontend_readiness, media_readiness, simulation_readiness


def readiness() -> dict:
    dependencies = {name: importlib.util.find_spec(name) is not None for name in ("fastapi", "uvicorn", "cryptography", "httpx")}
    checks = {"dependencies": dependencies, "frontend": frontend_readiness(ROOT), "simulations": simulation_readiness(ROOT), "media": media_readiness(ROOT)}
    return {"ok": all(dependencies.values()) and checks["frontend"]["ok"] and checks["simulations"]["ok"], **checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--duration-seconds", type=float, help="Optional bounded local rehearsal; then stop both servers.")
    args = parser.parse_args()
    if args.duration_seconds is not None and args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")
    report = readiness()
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report["ok"] or args.check_only:
        return 0 if report["ok"] else 1
    for port in (8000, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                print(f"Port {port} is already in use. Stop the known local demo yourself before restarting.")
                return 1
    runtime = ROOT / ".cache/offline-demo"
    runtime.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "OFFLINE_MODE": "true", "AI_ENABLED": "false", "AI_DISABLE_EXTERNAL": "true",
                   "COLLECTION_ENABLED": "false", "DB_PATH": str(runtime / "events.sqlite3"),
                   "APP_BUILD_SHA": report["frontend"]["build"]["commit_sha"], "PYTHONPATH": str(ROOT)}
    backend = None
    server = None
    try:
        with (runtime / "backend.log").open("a", encoding="utf-8") as log:
            backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                                       cwd=ROOT, env=environment, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            for _ in range(100):
                if backend.poll() is not None:
                    raise RuntimeError("Backend exited; inspect .cache/offline-demo/backend.log")
                try:
                    with urlopen("http://127.0.0.1:8000/api/health", timeout=1) as response:
                        if json.load(response).get("ok") is True:
                            break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Backend did not become ready within the startup timeout")
            server = ThreadingHTTPServer(("127.0.0.1", 5173), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "frontend/dist")))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            print("Offline demo ready: http://127.0.0.1:5173/\nAPI: http://127.0.0.1:8000\nCtrl+C stops both local servers.", flush=True)
            if not report["media"]["ok"]:
                print("Technical rehearsal only: recorded WebM/PDF backup is still missing.", flush=True)
            deadline = time.monotonic() + args.duration_seconds if args.duration_seconds else None
            while backend.poll() is None:
                if deadline is not None and time.monotonic() >= deadline:
                    return 0
                time.sleep(0.2)
            raise RuntimeError("Backend stopped unexpectedly")
    except KeyboardInterrupt:
        return 0
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if backend and backend.poll() is None:
            # Windows venv executables may spawn a runtime child. Stop the
            # complete tree created by this launcher, not only its wrapper.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(backend.pid), "/T", "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
