"""Minimal FastAPI application for B-owned endpoints."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .api.events import router as events_router
from .api.review import router as review_router
from .api.signals import router as signals_router
from .api.stream import router as stream_router
from .services.event_store import DEFAULT_DB_PATH, EventStore
from .services.signal_store import SignalStore
from .services.structure.llm_structurer import LlmJsonClient


def create_app(
    *, db_path: str | Path = DEFAULT_DB_PATH,
    review_token: str | None = None,
    llm_client: LlmJsonClient | None = None,
) -> FastAPI:
    """Create an app whose database is initialized only during startup."""

    store = SignalStore(db_path)
    event_store = EventStore(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        event_store.initialize()
        app.state.signal_store = store
        app.state.event_store = event_store
        app.state.review_token = review_token if review_token is not None else os.getenv("REVIEW_API_TOKEN")
        app.state.llm_client = llm_client
        yield

    application = FastAPI(title="ResilientRoute API", lifespan=lifespan)
    application.include_router(signals_router)
    application.include_router(events_router)
    application.include_router(review_router)
    application.include_router(stream_router)
    return application


app = create_app()
