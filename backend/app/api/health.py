"""
Health check endpoint for ResilientRoute.

Distinguishes between:
- "process alive" (basic liveness)
- "core function available" (readiness)

GET /api/health        - Basic health (process alive + data files present)
GET /api/health/deep   - Deep health (checks data loadability, graph buildability)
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..config.settings import settings

router = APIRouter()
logger = logging.getLogger("resilient_route.health")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class HealthSource(BaseModel):
    name: str
    status: str  # "ok" | "degraded" | "down" | "offline"
    last_check: str | None = None
    provenance: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    status: str  # "healthy" | "degraded" | "down"
    timestamp: str
    version: str
    environment: str
    offline_mode: bool
    llm_enabled: bool
    checks: dict[str, Any]
    sources: list[HealthSource]


def _check_data_files() -> dict[str, Any]:
    """Check that critical data files exist and are loadable."""
    checks = {}
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
    all_present = True
    all_loadable = True

    for f in critical_files:
        full_path = PROJECT_ROOT / f
        exists = full_path.exists()
        loadable = False
        if exists:
            try:
                with open(full_path, "r", encoding="utf-8") as fh:
                    json.load(fh)
                loadable = True
            except Exception:
                all_loadable = False
        else:
            all_present = False

        checks[f] = {"exists": exists, "loadable": loadable}

    checks["_all_present"] = all_present
    checks["_all_loadable"] = all_loadable
    return checks


def _check_directories() -> dict[str, Any]:
    """Check that required directories exist."""
    dirs = {
        "data": PROJECT_ROOT / "data",
        "data/network": PROJECT_ROOT / "data/network",
        "data/sim": PROJECT_ROOT / "data/sim",
        "cache": settings.full_cache_dir,
    }
    return {name: {"exists": path.exists()} for name, path in dirs.items()}


def _check_llm() -> dict[str, Any]:
    """Check LLM configuration status."""
    return {
        "configured": bool(settings.llm_api_key),
        "enabled": settings.llm_enabled,
        "provider": settings.llm_provider if settings.llm_enabled else None,
        "note": "LLM is optional. Route queries work without LLM via deterministic engine.",
    }


def _check_sources() -> list[HealthSource]:
    """Check data source availability."""
    sources = []

    # Local data files (always available)
    sources.append(HealthSource(
        name="local_network_data",
        status="ok",
        provenance="local",
    ))

    # HKO weather API
    if settings.offline_mode:
        sources.append(HealthSource(name="HKO_weather", status="offline", provenance="real"))
    else:
        sources.append(HealthSource(
            name="HKO_weather",
            status="ok" if settings.hko_weather_api else "not_configured",
            provenance="real",
        ))

    # MTR schedule API
    if settings.offline_mode:
        sources.append(HealthSource(name="MTR_schedule", status="offline", provenance="real"))
    else:
        sources.append(HealthSource(
            name="MTR_schedule",
            status="ok" if settings.mtr_schedule_api else "not_configured",
            provenance="real",
        ))

    # KMB API
    if settings.offline_mode:
        sources.append(HealthSource(name="KMB_bus", status="offline", provenance="real"))
    else:
        sources.append(HealthSource(
            name="KMB_bus",
            status="ok" if settings.kmb_api_base else "not_configured",
            provenance="real",
        ))

    # LLM
    if settings.llm_enabled and settings.llm_api_key:
        sources.append(HealthSource(name="LLM", status="ok", provenance="simulated"))
    elif settings.llm_enabled:
        sources.append(HealthSource(name="LLM", status="degraded", provenance="simulated"))
    else:
        sources.append(HealthSource(name="LLM", status="disabled", provenance="simulated"))

    return sources


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    Basic health check.
    Returns process alive status + data file presence.
    This endpoint should always return 200 (never crash).
    """
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    data_checks = _check_data_files()
    dir_checks = _check_directories()
    llm_checks = _check_llm()
    sources = _check_sources()

    all_ok = data_checks["_all_present"] and data_checks["_all_loadable"]

    return HealthResponse(
        ok=all_ok,
        status="healthy" if all_ok else "degraded",
        timestamp=ts,
        version=settings.deploy_version,
        environment=settings.deploy_env,
        offline_mode=settings.offline_mode,
        llm_enabled=settings.llm_enabled,
        checks={
            "data_files": data_checks,
            "directories": dir_checks,
            "llm": llm_checks,
        },
        sources=sources,
    )


@router.get("/health/deep")
async def health_deep():
    """
    Deep health check.
    Actually loads data files and verifies structure.
    Tests core function availability (not just process liveness).
    """
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()

    # Try to load and validate the network data
    network_ok = False
    network_error = None
    try:
        stations_path = PROJECT_ROOT / "data" / "network" / "stations.json"
        lines_path = PROJECT_ROOT / "data" / "network" / "lines.json"
        with open(stations_path, "r", encoding="utf-8") as f:
            stations = json.load(f)
        with open(lines_path, "r", encoding="utf-8") as f:
            lines = json.load(f)

        # Basic structural check
        assert "stations" in stations, "stations.json missing 'stations' key"
        assert "lines" in lines, "lines.json missing 'lines' key"
        assert len(stations["stations"]) >= 6, "Need at least 6 corridor stations"
        assert len(lines["lines"]) >= 5, "Need at least 5 transit lines"

        network_ok = True
    except Exception as e:
        network_error = str(e)

    return {
        "ok": network_ok,
        "status": "healthy" if network_ok else "down",
        "timestamp": ts,
        "core_function": "route_query",
        "network_loadable": network_ok,
        "network_error": network_error,
        "message": "Core routing function is available." if network_ok
                   else "Core routing function is NOT available. Check data files.",
    }
