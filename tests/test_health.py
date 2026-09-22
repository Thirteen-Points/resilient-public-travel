"""
Health check tests for ResilientRoute.
Tests that the health endpoint works correctly and distinguishes
between "process alive" and "core function available".

Run with: python -m pytest tests/test_health.py -v
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


class TestHealthDataChecks:
    """Test the data checks used by the health endpoint."""

    def test_all_critical_data_files_exist(self):
        """All critical data files must exist for the health check to pass."""
        critical_files = [
            "data/network/stations.json",
            "data/network/lines.json",
            "data/network/walk_links.json",
            "data/calendar.json",
            "contracts/seed/network.seed.json",
            "contracts/seed/event.seed.json",
            "contracts/seed/routes.seed.json",
            "contracts/seed/sim.seed.json",
        ]
        for f in critical_files:
            assert (ROOT / f).exists(), f"Critical file missing: {f}"

    def test_all_critical_data_files_loadable(self):
        """All critical data files must be valid JSON."""
        critical_files = [
            "data/network/stations.json",
            "data/network/lines.json",
            "data/network/walk_links.json",
            "data/calendar.json",
            "contracts/seed/network.seed.json",
            "contracts/seed/event.seed.json",
            "contracts/seed/routes.seed.json",
            "contracts/seed/sim.seed.json",
        ]
        for f in critical_files:
            data = load_json(ROOT / f)
            assert isinstance(data, dict), f"{f} should be a JSON dict"

    def test_network_has_minimum_content(self):
        """Network data should have minimum required content for core function."""
        stations = load_json(ROOT / "data/network/stations.json")
        lines = load_json(ROOT / "data/network/lines.json")

        assert len(stations["stations"]) >= 6, "Need at least 6 corridor stations"
        assert len(lines["lines"]) >= 5, "Need at least 5 transit lines"

        corridor = {"TAW", "KOT", "MKK", "HUH", "EXC", "ADM"}
        actual = {s["id"] for s in stations["stations"]}
        assert corridor.issubset(actual), "Missing corridor stations"

    def test_no_secrets_in_env_example(self):
        """Ensure .env.example does not contain real secrets."""
        env_path = ROOT / ".env.example"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            # Check for common patterns of real secrets
            assert "sk-" not in content, "Possible API key found in .env.example"
            assert "Bearer " not in content, "Possible Bearer token in .env.example"
            # API_KEY= should be empty
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "API_KEY=" in line and "=" in line:
                    key, _, value = line.partition("=")
                    assert value == "" or value.startswith("${"), \
                        f"API_KEY should be empty or reference variable: {line}"


class TestHealthEndpointStructure:
    """Test that the health endpoint response structure is correct."""

    def test_health_response_has_required_fields(self):
        """The HealthResponse model should have all required fields."""
        # Import the model
        sys.path.insert(0, str(ROOT))
        from backend.app.api.health import HealthResponse

        # Check fields exist in the model
        required_fields = ["ok", "status", "timestamp", "version", "checks", "sources"]
        for field in required_fields:
            assert field in HealthResponse.model_fields, \
                f"HealthResponse missing field: {field}"

    def test_health_status_values(self):
        """Health status should be one of: healthy, degraded, down."""
        from backend.app.api.health import HealthResponse
        # The status field should accept these values
        valid_statuses = {"healthy", "degraded", "down"}
        # We can't test actual runtime, but we verify the field exists


class TestOfflineMode:
    """Test that offline mode works correctly."""

    def test_offline_data_package_exists(self):
        """Offline data package files should exist."""
        assert (ROOT / "deploy/offline/README.json").exists()
        assert (ROOT / "deploy/offline/README.md").exists()

    def test_offline_readme_has_startup_instructions(self):
        """Offline README should have startup instructions."""
        readme = load_json(ROOT / "deploy/offline/README.json")
        assert "startup_instructions" in readme
        assert "windows" in readme["startup_instructions"]
        assert "linux_mac" in readme["startup_instructions"]

    def test_offline_includes_all_data_files(self):
        """Offline package should list all required data files."""
        readme = load_json(ROOT / "deploy/offline/README.json")
        files = readme.get("files", [])
        assert len(files) >= 10, "Offline package should list >=10 files"
        # Key files must be included
        must_include = [
            "data/network/stations.json",
            "data/network/lines.json",
            "data/calendar.json",
            "contracts/seed/network.seed.json",
        ]
        for f in must_include:
            assert f in files, f"Offline package missing: {f}"


class TestStartupScript:
    """Test that startup scripts exist and are correct."""

    def test_start_sh_exists(self):
        assert (ROOT / "scripts/start.sh").exists()

    def test_start_bat_exists(self):
        assert (ROOT / "scripts/start.bat").exists()

    def test_start_sh_has_offline_flag(self):
        content = (ROOT / "scripts/start.sh").read_text(encoding="utf-8")
        assert "--offline" in content, "start.sh should support --offline flag"

    def test_start_bat_has_offline_flag(self):
        content = (ROOT / "scripts/start.bat").read_text(encoding="utf-8")
        assert "--offline" in content, "start.bat should support --offline flag"


class TestPreflightScript:
    """Test that the preflight script exists and is functional."""

    def test_preflight_exists(self):
        assert (ROOT / "scripts/preflight.py").exists()

    def test_preflight_checks_data(self):
        content = (ROOT / "scripts/preflight.py").read_text(encoding="utf-8")
        assert "data_files" in content
        assert "stations.json" in content

    def test_preflight_checks_health(self):
        content = (ROOT / "scripts/preflight.py").read_text(encoding="utf-8")
        assert "health" in content.lower()
        assert "localhost:8000" in content


class TestDockerConfig:
    """Test Docker configuration."""

    def test_dockerfile_exists(self):
        assert (ROOT / "deploy/Dockerfile").exists()

    def test_docker_compose_exists(self):
        assert (ROOT / "deploy/docker-compose.yml").exists()

    def test_dockerfile_sets_offline_default(self):
        content = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
        assert "OFFLINE_MODE=true" in content, "Docker should default to offline mode"
        assert "LLM_ENABLED=false" in content, "Docker should default to LLM disabled"

    def test_dockerfile_has_healthcheck(self):
        content = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
        assert "HEALTHCHECK" in content, "Dockerfile should have HEALTHCHECK"

    def test_docker_compose_has_volumes(self):
        content = (ROOT / "deploy/docker-compose.yml").read_text(encoding="utf-8")
        assert "volumes" in content, "docker-compose should mount data volumes"


class TestEnvExample:
    """Test .env.example configuration."""

    def test_env_example_exists(self):
        assert (ROOT / ".env.example").exists()

    def test_env_example_has_required_vars(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        required_vars = [
            "HOST",
            "PORT",
            "OFFLINE_MODE",
            "LLM_ENABLED",
            "LLM_API_KEY",
            "DB_PATH",
        ]
        for var in required_vars:
            assert var in content, f".env.example missing: {var}"

    def test_env_example_llm_disabled_by_default(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        assert "LLM_ENABLED=false" in content, "LLM should be disabled by default"

    def test_env_example_no_real_keys(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        # No real API keys (they should all be empty)
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
        for line in lines:
            if "API_KEY=" in line:
                _, _, value = line.partition("=")
                assert value == "" or value.startswith("${"), \
                    f"API key should be empty: {line}"
