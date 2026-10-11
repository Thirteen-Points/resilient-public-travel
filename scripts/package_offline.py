"""Build a local frontend and package an allowlisted, secret-free offline demo."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.p4_readiness import frontend_readiness, media_readiness, sha256, simulation_readiness

INCLUDES = ("backend/app", "backend/__init__.py", "backend/requirements.txt", "contracts", "data",
            "frontend/dist", "deploy/offline", "scripts/preflight.py", "scripts/validate_data.py",
            "scripts/p4_readiness.py", "scripts/offline_demo.py", "scripts/package_offline.py",
            "scripts/precompute_sim_p3.py", "scripts/verify_p4.py", "deploy/P4-ACCEPTANCE.md",
            "deploy/DEPLOYMENT.md", "docs/acceptance/p4-c-acceptance.md",
            "docs/acceptance/evidence/p4/c")


def package_files(root: Path):
    for relative in INCLUDES:
        source = root / relative
        for path in ([source] if source.is_file() else sorted(source.rglob("*"))):
            if not path.is_file():
                continue
            name = path.relative_to(root)
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Package input resolves outside the local project")
            if any(part in {"__pycache__", "node_modules", ".git", ".cache"} for part in name.parts):
                continue
            if ".sqlite3" in path.name or path.name.startswith(".env") or path.suffix in {".pyc", ".log"}:
                continue
            yield path, name.as_posix()


def build_frontend(root: Path):
    import os
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Node/npm is required during online preparation, not during offline launch.")
    environment = {**os.environ, "VITE_API_BASE_URL": "http://127.0.0.1:8000", "VITE_BUILD_SHA": revision}
    subprocess.run([npm, "run", "build"], cwd=root / "frontend", env=environment, check=True)
    directory = root / "frontend/dist"
    marker = {"api_base_url": environment["VITE_API_BASE_URL"], "source_revision": revision,
              "source_dirty": subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=root).returncode != 0,
              "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "file_sha256": {path.relative_to(directory).as_posix(): sha256(path) for path in sorted(directory.rglob("*")) if path.is_file() and path.name != "offline-build.json"}}
    (directory / "offline-build.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Prepare frontend using already-installed npm dependencies.")
    parser.add_argument("--require-media", action="store_true", help="Refuse an archive without the recorded WebM and PDF.")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/offline/resilientroute-offline.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Archive output must stay inside the local project")
    if args.build:
        build_frontend(ROOT)
    checks = {"simulation": simulation_readiness(ROOT), "frontend": frontend_readiness(ROOT), "media": media_readiness(ROOT)}
    if not checks["simulation"]["ok"] or not checks["frontend"]["ok"] or (args.require_media and not checks["media"]["ok"]):
        print(json.dumps({"ok": False, "checks": checks}, ensure_ascii=False, indent=2))
        return 1
    files = list(package_files(ROOT))
    manifest = {"package_version": "p4-offline-v1", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_revision": checks["frontend"]["build"]["commit_sha"],
                "source_dirty": json.loads((ROOT / "frontend/dist/offline-build.json").read_text(encoding="utf-8")).get("source_dirty", True),
                "final_media_ready": checks["media"]["ok"], "checks": checks,
                "runtime_prerequisites": "Preinstalled Python 3.11+ and backend requirements; no pip/npm runs during launch.",
                "file_sha256": {name: sha256(path) for path, name in files}}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, name)
        archive.writestr("offline-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output)
    print(json.dumps({"ok": True, "archive": str(output.relative_to(ROOT)), "sha256": sha256(output),
                      "file_count": len(files), "final_media_ready": checks["media"]["ok"],
                      "missing_media": [name for name, row in checks["media"]["files"].items() if not row["present"] or not row["format_ok"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
