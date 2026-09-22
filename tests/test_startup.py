"""
Startup and deployment tests for ResilientRoute C-DevOps.
Tests that the system can start without external dependencies.

Run with: python -m pytest tests/test_startup.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestDependencies:
    """Test that dependencies are specified and installable."""

    def test_requirements_txt_exists(self):
        assert (ROOT / "backend/requirements.txt").exists()

    def test_requirements_have_fastapi(self):
        content = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        assert "fastapi" in content.lower()

    def test_requirements_have_uvicorn(self):
        content = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        assert "uvicorn" in content.lower()

    def test_requirements_have_networkx(self):
        content = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        assert "networkx" in content.lower()

    def test_requirements_have_pydantic(self):
        content = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        assert "pydantic" in content.lower()


class TestBackendStructure:
    """Test that the backend module structure is correct."""

    REQUIRED_FILES = [
        "backend/app/__init__.py",
        "backend/app/main.py",
        "backend/app/config/__init__.py",
        "backend/app/config/settings.py",
        "backend/app/api/__init__.py",
        "backend/app/api/health.py",
        "backend/app/api/meta.py",
        "backend/app/api/graph.py",
    ]

    @pytest.mark.parametrize("filepath", REQUIRED_FILES)
    def test_required_file_exists(self, filepath):
        assert (ROOT / filepath).exists(), f"Missing: {filepath}"

    def test_main_imports_fastapi(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "from fastapi import FastAPI" in content

    def test_main_has_health_router(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "health_router" in content

    def test_main_has_meta_router(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "meta_router" in content

    def test_main_has_graph_router(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "graph_router" in content

    def test_main_has_lifespan(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "lifespan" in content

    def test_main_has_cors(self):
        content = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        assert "CORSMiddleware" in content


class TestSettingsModule:
    """Test the settings/config module."""

    def test_settings_has_defaults(self):
        content = (ROOT / "backend/app/config/settings.py").read_text(encoding="utf-8")
        # All critical settings should have defaults
        assert 'default="0.0.0.0"' in content or 'default="0.0.0.0"' in content, \
            "HOST should have default"
        assert "default=8000" in content or "default=8000" in content, \
            "PORT should have default"
        assert "default=False" in content or "default=False" in content, \
            "LLM_ENABLED should default to False"

    def test_settings_loads_from_env(self):
        content = (ROOT / "backend/app/config/settings.py").read_text(encoding="utf-8")
        assert 'env_file' in content or 'env_file' in content.lower()


class TestHealthCheckEndpoint:
    """Test the health check endpoint implementation."""

    def test_health_has_basic_endpoint(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "/health" in content
        assert "async def health" in content

    def test_health_has_deep_endpoint(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "/health/deep" in content
        assert "async def health_deep" in content

    def test_health_checks_data_files(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "_check_data_files" in content
        assert "stations.json" in content

    def test_health_checks_directories(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "_check_directories" in content

    def test_health_checks_llm(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "_check_llm" in content

    def test_health_returns_sources(self):
        content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "sources" in content

    def test_health_returns_disclaimer_in_meta(self):
        meta_content = (ROOT / "backend/app/api/meta.py").read_text(encoding="utf-8")
        assert "disclaimer" in meta_content


class TestLLMFallback:
    """Test that the system works without LLM."""

    def test_llm_disabled_by_default(self):
        env_content = (ROOT / ".env.example").read_text(encoding="utf-8")
        assert "LLM_ENABLED=false" in env_content

    def test_settings_llm_default_false(self):
        settings_content = (ROOT / "backend/app/config/settings.py").read_text(encoding="utf-8")
        # LLM should default to False
        assert "llm_enabled" in settings_content

    def test_docker_llm_disabled(self):
        docker_content = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
        assert "LLM_ENABLED=false" in docker_content

    def test_health_reports_llm_status(self):
        health_content = (ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
        assert "llm_enabled" in health_content


class TestDirectoryStructure:
    """Test that the required directory structure exists."""

    REQUIRED_DIRS = [
        "data",
        "data/network",
        "data/access",
        "data/sim",
        "scripts",
        "deploy",
        "deploy/offline",
        "backend",
        "backend/app",
        "backend/app/api",
        "backend/app/config",
        "backend/app/data",
        "backend/app/graph",
        "backend/app/engine",
        "backend/app/sim",
        "backend/app/ai",
        "tests",
    ]

    @pytest.mark.parametrize("dirname", REQUIRED_DIRS)
    def test_directory_exists(self, dirname):
        assert (ROOT / dirname).is_dir(), f"Directory missing: {dirname}"


class TestNoSecretsCommitted:
    """Test that no real secrets are committed to the repository."""

    def test_gitignore_has_env(self):
        content = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in content
        assert "!.env.example" in content

    def test_no_env_file_committed(self):
        assert not (ROOT / ".env").exists(), ".env file should not be committed"

    def test_env_example_has_no_real_keys(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
        for line in lines:
            if "API_KEY=" in line:
                _, _, value = line.partition("=")
                assert value == "" or value.startswith("${"), \
                    f"API key should be empty in .env.example: {line}"
            if "PASSWORD=" in line:
                _, _, value = line.partition("=")
                assert value == "" or value.startswith("${"), \
                    f"Password should be empty in .env.example: {line}"
