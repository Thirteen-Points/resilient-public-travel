"""Run startup argument parsing without installing packages or starting servers."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def launch_script(arguments: list[str], values: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for name in ("OFFLINE_MODE", "AI_ENABLED", "LLM_ENABLED", "AI_DISABLE_EXTERNAL", "PORT"):
        env.pop(name, None)
    env.update(values)
    if os.name == "nt":
        command = ["cmd.exe", "/c", str(ROOT / "scripts" / "start.bat")]
    else:
        shell = shutil.which("bash")
        assert shell, "Startup regression requires bash"
        command = [shell, str(ROOT / "scripts" / "start.sh")]
    return subprocess.run(command + arguments, cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=10)


@pytest.mark.parametrize("arguments", [
    ["--offline", "--no-llm", "--check-config"],
    ["--check-config", "--no-llm", "--offline"],
])
def test_explicit_flags_override_enabled_environment(arguments):
    result = launch_script(arguments, {"OFFLINE_MODE": "false", "AI_ENABLED": "true",
                                      "LLM_ENABLED": "true", "PORT": "8123"})
    assert result.returncode == 0, result.stderr
    assert "OFFLINE_MODE=true" in result.stdout
    assert "AI_ENABLED=false" in result.stdout
    assert "AI_DISABLE_EXTERNAL=true" in result.stdout
    assert "PORT=8123" in result.stdout


def test_defaults_and_legacy_flag():
    result = launch_script(["--check-config"], {})
    assert result.returncode == 0, result.stderr
    assert "OFFLINE_MODE=true" in result.stdout
    assert "AI_ENABLED=false" in result.stdout
    result = launch_script(["--check-config"], {"LLM_ENABLED": "true"})
    assert "AI_ENABLED=true" in result.stdout


def test_unknown_startup_flag_fails_before_installing_packages():
    assert launch_script(["--typo"], {}).returncode == 2
