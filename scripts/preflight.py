"""Offline preflight for local startup and deterministic data readiness."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [sys.executable, str(ROOT / "scripts" / "validate_data.py")]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        validation = json.loads(run.stdout)
    except json.JSONDecodeError:
        # validate_data.py intentionally emits human-readable WARN/ERROR lines;
        # preserve them instead of treating documented warnings as a parse failure.
        validation = {"ok": run.returncode == 0, "output": run.stdout[-4000:]}
    report = {
        "ok": run.returncode == 0 and bool(validation.get("ok")),
        "offline": True,
        "llm_required": False,
        "validation": validation,
        "start_command": "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
        "health_url": "http://127.0.0.1:8000/api/health",
        "notes": ["No network call is made by this preflight.",
                  "When AI_ENABLED=true without a key, the service keeps deterministic fallback mode."],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
