"""Combined API for signals, reviewed events, routes, and simulation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.events import router as events_router
from .api.review import router as review_router
from .api.signals import router as signals_router
from .api.stream import router as stream_router
from .services.event_store import DEFAULT_DB_PATH, EventStore
from .services.signal_store import SignalStore
from .services.structure.llm_structurer import LlmJsonClient


ROOT = Path(__file__).resolve().parents[2]


def _path(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else ROOT / candidate


class Runtime:
    """Load C's deterministic offline services without blocking B's API."""

    def __init__(self) -> None:
        self.engine = None
        self.error: str | None = None
        self.seed_status: dict[str, Any] = {}
        self.ai_service: Any | None = None
        self.ai_error: str | None = None
        self.load()

    def load(self) -> None:
        from .runtime_config import settings
        from .engine.service import RouteEngine

        network = _path(settings.seed_network)
        events = _path(settings.seed_events)
        routes = ROOT / "contracts" / "seed" / "routes.seed.json"
        simulation = ROOT / "contracts" / "seed" / "sim.seed.json"
        self.seed_status = {
            "network": {"path": str(network), "present": network.is_file()},
            "events": {"path": str(events), "present": events.is_file()},
            "routes": {"path": str(routes), "present": routes.is_file()},
            "sim": {"path": str(simulation), "present": simulation.is_file()},
        }
        try:
            self.engine = RouteEngine.from_seed(network_path=network, events_path=events)
            self.error = None
            self.seed_status["loaded"] = True
            try:
                from .ai.handlers import build_engine_handlers
                from .ai.query import NoLLMQueryService
                from .ai.tools import build_default_registry
                from .sim.service import build_diversion_plan

                handlers = build_engine_handlers(self.engine, build_diversion_plan)
                self.ai_service = NoLLMQueryService(build_default_registry(handlers))
                self.ai_error = None
            except Exception as exc:
                self.ai_service = None
                self.ai_error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            self.engine = None
            self.error = f"{type(exc).__name__}: {exc}"
            self.seed_status["loaded"] = False

    def health(self) -> dict[str, Any]:
        from .runtime_config import settings

        problems = settings.missing_runtime_config()
        if self.error:
            problems.append(f"seed load failed: {self.error}")
        if self.ai_error:
            problems.append(f"AI fallback unavailable: {self.ai_error}")
        return {
            "ok": self.engine is not None and not self.error,
            "service": "up",
            "mode": "offline" if settings.offline_mode else "online-optional",
            "llm": {"enabled": settings.ai_enabled, "required_for_startup": False},
            "database": {"configured": True, "status": "available"},
            "components": {
                "signals": "ready",
                "route": "ready" if self.engine else "failed",
                "ai_fallback": "ready" if self.ai_service else "failed",
                "simulation_cache": "ready" if (ROOT / "data" / "sim").is_dir() else "missing",
            },
            "seed": self.seed_status,
            "sources": ["repository seed files", "deterministic route engine"],
            "failures": problems,
        }


runtime = Runtime()


def create_app(
    *, db_path: str | Path = DEFAULT_DB_PATH,
    review_token: str | None = None,
    llm_client: LlmJsonClient | None = None,
) -> FastAPI:
    """Compose B's reviewed-event APIs and C's deterministic services."""
    store = SignalStore(db_path)
    event_store = EventStore(db_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        event_store.initialize()
        application.state.signal_store = store
        application.state.event_store = event_store
        application.state.review_token = review_token if review_token is not None else os.getenv("REVIEW_API_TOKEN")
        application.state.llm_client = llm_client
        yield

    application = FastAPI(title="ResilientRoute API", version="m0-integrated", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(signals_router)
    application.include_router(events_router)
    application.include_router(review_router)
    application.include_router(stream_router)

    @application.get("/api/health")
    def health() -> JSONResponse:
        body = runtime.health()
        return JSONResponse(status_code=200 if body["ok"] else 503, content=body)

    @application.get("/api/meta")
    def meta() -> dict[str, Any]:
        snapshot = runtime.engine.snapshots.current.snapshot_id if runtime.engine else None
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "graph_snapshot": snapshot,
            "sources": ["contracts/seed/network.seed.json", "contracts/seed/event.seed.json"],
            "disclaimer": "Seed values may be simulated and do not represent live transit conditions.",
        }

    @application.get("/api/health/deep")
    def deep_health() -> JSONResponse:
        from .runtime_config import settings

        checks: dict[str, Any] = {}
        if runtime.engine is None:
            checks["route"] = {"ok": False, "error": runtime.error or "engine_unavailable"}
        else:
            try:
                details = runtime.engine.query_details(
                    settings.deep_health_origin,
                    settings.deep_health_destination,
                    settings.deep_health_depart_at,
                )
                checks["route"] = {"ok": bool(details["routes"]), "routes": len(details["routes"]),
                                    "snapshot": details["graph_snapshot"],
                                    "origin": settings.deep_health_origin,
                                    "destination": settings.deep_health_destination}
            except Exception as exc:
                checks["route"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        scenario = ROOT / "data" / "sim" / "scn_huh_exc_closed_am_peak.json"
        try:
            from .sim.cache import PrecomputedResultStore

            result = PrecomputedResultStore(scenario.parent).read(scenario.stem)
            checks["simulation"] = {
                "ok": True,
                "scenario_id": result["scenario_id"],
                "population": result.get("population"),
            }
        except Exception as exc:
            checks["simulation"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        checks["ai_fallback"] = {"ok": runtime.ai_service is not None,
                                  "error": runtime.ai_error, "external_call": False}
        checks["seed"] = {"ok": bool(runtime.seed_status.get("loaded")) and all(
            item.get("present") is True for item in runtime.seed_status.values()
            if isinstance(item, dict) and "present" in item
        )}
        ok = all(item.get("ok") is True for item in checks.values())
        return JSONResponse(status_code=200 if ok else 503,
                            content={"ok": ok, "checks": checks, "offline": settings.offline_mode})

    @application.post("/api/ai/chat")
    async def ai_chat(payload: dict[str, Any]) -> dict[str, Any]:
        if runtime.ai_service is None:
            raise HTTPException(status_code=503, detail="AI fallback service unavailable")
        if not isinstance(payload.get("message"), str) or not payload["message"].strip():
            raise HTTPException(status_code=422, detail="Missing non-empty field: message")
        required = ("origin", "destination", "depart_at")
        if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
            return {"message": "请提供起点、终点和出发时间，我才能调用确定性路线工具。",
                    "tool_calls": [], "fallback": True, "user_input": payload["message"]}
        return await runtime.ai_service.query(
            user_input=payload["message"], origin=payload["origin"],
            destination=payload["destination"], depart_at=payload["depart_at"],
            profile_id=payload.get("profile_id"), event_id=payload.get("event_id"),
            demand=payload.get("demand"),
        )

    @application.get("/health")
    def health_alias() -> JSONResponse:
        body = runtime.health()
        return JSONResponse(status_code=200 if body["ok"] else 503, content=body)

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": "resilient-public-travel", "health": "/api/health"}

    if runtime.engine is not None:
        from .engine.api import create_router
        from .sim.api import build_router as build_sim_router

        application.include_router(create_router(runtime.engine))
        application.include_router(build_sim_router(ROOT / "data" / "sim"))
    return application


app = create_app()
