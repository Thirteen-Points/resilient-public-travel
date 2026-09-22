"""Minimal FastAPI application for B-owned endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .api.signals import router as signals_router
from .services.event_store import DEFAULT_DB_PATH
from .services.signal_store import SignalStore


def create_app(*, db_path: str | Path = DEFAULT_DB_PATH) -> FastAPI:
    """Create an app whose database is initialized only during startup."""

    store = SignalStore(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        app.state.signal_store = store
        yield

    application = FastAPI(title="ResilientRoute API", lifespan=lifespan)
    application.include_router(signals_router)
    return application


app = create_app()
