"""
ResilientRoute - FastAPI Backend Application

Entry point: uvicorn backend.app.main:app --reload

This is a minimal but functional backend that:
- Serves graph/network data from local JSON files
- Provides health check endpoint (process alive + core function available)
- Serves meta (sources, freshness, disclaimer)
- Works WITHOUT any LLM API key
- Works WITHOUT any external data source (offline mode)
- Route queries use deterministic logic (not AI)
"""

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.settings import settings
from .api.health import router as health_router
from .api.meta import router as meta_router
from .api.graph import router as graph_router

# --- Logging setup ---
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper, logging.INFO)
    if hasattr(logging, settings.log_level.upper())
    else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resilient_route")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("ResilientRoute backend starting...")
    logger.info(f"  Environment: {settings.deploy_env}")
    logger.info(f"  Version: {settings.deploy_version}")
    logger.info(f"  Offline mode: {settings.offline_mode}")
    logger.info(f"  LLM enabled: {settings.llm_enabled}")

    # Ensure data directories exist
    for d in [settings.full_cache_dir, settings.graph_snapshot_dir]:
        full_path = settings.project_root / d
        full_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"  Ensured directory: {full_path}")

    logger.info("ResilientRoute backend ready.")

    yield

    # Shutdown
    logger.info("ResilientRoute backend shutting down.")


app = FastAPI(
    title="ResilientRoute API",
    description="Resilient public travel routing for Hong Kong East Rail Line corridor disruptions.",
    version=settings.deploy_version,
    lifespan=lifespan,
)

# CORS - allow frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dev: allow all. Production: restrict to known domains.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(meta_router, prefix="/api", tags=["meta"])
app.include_router(graph_router, prefix="/api", tags=["graph"])


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "ResilientRoute API",
        "version": settings.deploy_version,
        "docs": "/docs",
        "health": "/api/health",
    }
