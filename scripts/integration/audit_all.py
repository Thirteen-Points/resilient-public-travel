"""Unified local audit. It reports missing owners/artifacts; it never substitutes them."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from .provenance_audit import audit_provenance

ROOT = Path(__file__).resolve().parents[2]
# Four acceptance commands requested by the integrator owner remain explicit.
COMMANDS = [
    ("compile_backend", ["-m", "compileall", "-q", "backend/app"], None, None),
    ("route", ["-m", "unittest", "discover", "-s", "backend/app/engine/tests", "-v"], None, 30),
    ("sim", ["-m", "unittest", "discover", "-s", "tests", "-v"], None, 21),
    ("ai", ["-m", "unittest", "discover", "-s", "backend/tests", "-p", "test_ai.py", "-v"], None, 7),
    ("sim_adapters", ["-m", "unittest", "discover", "-s", "backend/tests", "-p", "test_sim_adapters.py", "-v"],
     "backend/tests/test_sim_adapters.py", 1),
    ("backend_tests", ["-m", "unittest", "discover", "-s", "backend/tests", "-v"], None, 7),
    ("consumer_contracts", ["-m", "unittest", "discover", "-s", "tests/integration", "-v"], None, 40),
    ("cross_module", ["-m", "unittest", "discover", "-s", "tests/cross_module", "-v"], None, 1),
    ("validate_data", ["scripts/validate_data.py"], "scripts/validate_data.py", None),
    ("preflight", ["scripts/preflight.py"], "scripts/preflight.py", None),
]

def fingerprints(root):
    patterns = ["backend/**/*.py", "backend/**/*.json", "tests/**/*.py", "tests/**/*.json",
                "scripts/**/*.py", "contracts/**/*.json", "data/**/*.json", "data/**/*.md",
                "docs/plan/03-contracts.md", "contracts/README.md", "backend/.env.example",
                "scripts/*.ps1", "agent_work/**/reports/*.md"]
    return {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for pattern in patterns for path in sorted(root.glob(pattern)) if path.is_file()}

def classify_process(returncode, output, minimum=None, missing=False):
    counts = re.findall(r"Ran (\d+) tests?", output)
    count = int(counts[-1]) if counts else None
    if count is None:
        summaries = re.findall(r"(?:^|\n)([^\n]*\d+ (?:passed|failed|error|skipped)[^\n]* in [\d.]+s)", output)
        if summaries:
            count = sum(int(n) for n in re.findall(r"(\d+) (?:passed|failed|errors?|skipped|xfailed|xpassed)", summaries[-1]))
    if missing:
        return "BLOCKED", count
    if returncode != 0:
        return "FAIL", count
    if minimum is not None and (count is None or count < minimum):
        return "FAIL", count
    if re.search(r"skipped=\d+|expected failures=\d+|\d+ (?:skipped|xfailed|xpassed)", output):
        return "CONDITIONAL", count
    return "PASS", count

def run_command(name, args, required, minimum, root, output_dir, env, timeout):
    before = fingerprints(root)
    started = time.perf_counter()
    try:
        run = subprocess.run([sys.executable, *args], cwd=root, env=env, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=timeout)
        code, output = run.returncode, run.stdout + run.stderr
    except subprocess.TimeoutExpired as exc:
        code = -1
        output = "Timed out; this check did not pass.\n"
        output += str(exc.stdout or "") + str(exc.stderr or "")
    status, count = classify_process(code, output, minimum, required is not None and not (root / required).is_file())
    if name in {"m0_http", "seed_boundaries"} and code == 2:
        status = "BLOCKED"
    changed = [path for path, digest in before.items() if fingerprints_after.get(path) != digest] if (
        fingerprints_after := fingerprints(root)) != before else []
    changed += [path for path in fingerprints_after if path not in before]
    if changed and status == "PASS":
        status = "CONDITIONAL"
    log = output_dir / (name + ".txt")
    log.write_text(output, encoding="utf-8")
    return dict(name=name, status=status, command=["python", *args], returncode=code,
                tests=count, expected_minimum=minimum, elapsed_s=round(time.perf_counter()-started, 4),
                log=str(log.relative_to(output_dir)), files_changed_during_check=sorted(set(changed)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/acceptance/evidence/cross-module")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--m0", action="store_true", help="Include non-merge M0 seeds, HTTP process and pytest checks")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Both app.* and backend.app.* are currently used by different owners.
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "backend")])
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               AI_ENABLED="false", LLM_ENABLED="false", OFFLINE_MODE="true")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    sources = fingerprints(ROOT)
    checks = []
    with tempfile.TemporaryDirectory(prefix="integration-pycache-") as cache:
        env["PYTHONPYCACHEPREFIX"] = cache
        commands = list(COMMANDS)
        if args.m0:
            commands.extend([
                ("seed_boundaries", ["-m", "scripts.integration", "--suite", "contracts",
                    "--output", str(args.output_dir / "seed-boundaries.json")], None, None),
                ("data_pytest", ["-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "tests/test_data_integrity.py"], "tests/test_data_integrity.py", 1),
                ("related_pytest", ["-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--import-mode=importlib", "backend/app/engine/tests", "backend/tests", "tests"], None, 1),
                ("m0_http", ["-m", "scripts.integration.m0_probe"], "backend/app/main.py", None),
            ])
        for name, command, required, minimum in commands:
            row = run_command(name, command, required, minimum, ROOT, args.output_dir, env, args.timeout)
            checks.append(row)
            print(f"{row['status']:12} {name}: exit={row['returncode']} tests={row['tests']}", flush=True)
    if args.m0 and (args.output_dir / "m0_http.txt").is_file():
        try:
            runtime = json.loads((args.output_dir / "m0_http.txt").read_text(encoding="utf-8"))
            checks.extend(runtime["checks"])
        except (ValueError, KeyError):
            checks.append({"name": "runtime.evidence", "status": "FAIL", "detail": "HTTP probe did not emit valid evidence"})
    provenance = audit_provenance(ROOT)
    (args.output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    checks.extend(provenance["checks"])
    status = 1 if any(c["status"] == "FAIL" for c in checks) else 2 if any(
        c["status"] in {"BLOCKED", "UNVERIFIED", "CONDITIONAL"} for c in checks) else 0
    report = dict(generated_at=datetime.now(timezone.utc).isoformat(), revision=revision,
                  python=sys.version, python_executable=sys.executable,
                  git_status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
                  section8_merge="NOT_EXECUTED: user explicitly excludes A/B/C merge and main changes",
                  end_source_sha256=fingerprints(ROOT),
                  environment={key:env[key] for key in ("PYTHONPATH","AI_ENABLED","LLM_ENABLED","OFFLINE_MODE")},
                  source_sha256=sources, checks=checks, exit_code=status,
                  scope="Tests use simulated fixtures. PASS is not transport verification or a deployed/offline demo.")
    (args.output_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Audit exit {status}; see {args.output_dir / 'summary.json'}")
    return status

if __name__ == "__main__":
    raise SystemExit(main())
