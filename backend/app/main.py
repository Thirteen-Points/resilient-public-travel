"""Combined API for signals, reviewed events, routes, and simulation."""

from __future__ import annotations

import os
import asyncio
from time import monotonic
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load before Runtime()/settings read REVIEW_API_TOKEN and AI provider keys.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.events import router as events_router
from .api.review import router as review_router
from .api.signals import router as signals_router
from .api.stream import router as stream_router
from .runtime_config import parse_cors_origins
from .services.event_store import DEFAULT_DB_PATH, EventStore
from .services.signal_store import SignalStore
from .services.structure.llm_structurer import LlmJsonClient
from .build_info import get_build_info


ROOT = Path(__file__).resolve().parents[2]


def _path(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else ROOT / candidate


class Runtime:
    """Load C's deterministic offline services without blocking B's API."""

    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started_monotonic = monotonic()
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
            from .graph.corridor_bus import CorridorBusAdapter, enabled as bus_network_enabled
            if bus_network_enabled():
                from .graph.adapter import SeedDataAdapter
                self.engine = RouteEngine.from_adapter(CorridorBusAdapter(SeedDataAdapter(network, events)))
            else:
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
        from .runtime_metrics import memory_usage

        problems = settings.missing_runtime_config()
        if self.error:
            problems.append(f"seed load failed: {self.error}")
        if self.ai_error:
            problems.append(f"AI fallback unavailable: {self.ai_error}")
        return {
            "ok": self.engine is not None and not self.error,
            "service": "up",
            "build": get_build_info(),
            "runtime": {"started_at": self.started_at,
                        "uptime_s": round(monotonic() - self.started_monotonic, 1), **memory_usage()},
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


def sync_engine_events(event_store: EventStore) -> str | None:
    """Mirror reviewer-approved Events into the routing engine.

    The engine keeps its own immutable snapshots of the last approved facts.
    Unapproved edits never enter it. A sync failure must
    never fail the review write itself, so the previous snapshot stays live.
    """

    engine = runtime.engine
    if engine is None:
        return None
    try:
        events = [
            event.model_dump(mode="json")
            for event in event_store.approved_events()
        ]
        snapshot = engine.snapshots.replace_events(events)
        return snapshot.snapshot_id
    except Exception:
        return None


class EngineSyncEventStore(EventStore):
    """Push every persisted Event revision into the engine snapshot store."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path)
        self.last_synced_snapshot: str | None = None

    def _sync(self) -> None:
        coordinator = getattr(self, "replanner", None)
        if coordinator:
            try:
                result = coordinator.sync_approved_events()
                self.last_synced_snapshot = coordinator.engine.snapshots.current.snapshot_id
                return
            except Exception:
                # A completed reviewer write must not turn into a failed write
                # response just because an optional downstream recompute failed.
                pass
        self.last_synced_snapshot = sync_engine_events(self)

    def create_event(self, *args: Any, **kwargs: Any):
        event = super().create_event(*args, **kwargs)
        self._sync()
        return event

    def update_event(self, *args: Any, **kwargs: Any):
        event = super().update_event(*args, **kwargs)
        self._sync()
        return event


def create_app(
    *, db_path: str | Path = DEFAULT_DB_PATH,
    review_token: str | None = None,
    llm_client: LlmJsonClient | None = None,
) -> FastAPI:
    """Compose B's reviewed-event APIs and C's deterministic services."""
    store = SignalStore(db_path)
    event_store = EngineSyncEventStore(db_path)
    coordinator = None
    if runtime.engine is not None:
        from .sim.runtime_replanning import RuntimeReplanningCoordinator
        coordinator = RuntimeReplanningCoordinator(runtime.engine, event_store.approved_events)
        event_store.replanner = coordinator

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        event_store.initialize()
        event_store._sync()
        application.state.signal_store = store
        application.state.event_store = event_store
        application.state.review_token = review_token if review_token is not None else os.getenv("REVIEW_API_TOKEN")
        from .ai.budget import ModelBudget
        from .ai.runtime import env_client
        budget = ModelBudget(Path(db_path).parent / "ai_usage.sqlite3")
        application.state.llm_budget = budget
        application.state.llm_client = llm_client if llm_client is not None else env_client(budget)
        application.state.llm_injected = llm_client is not None
        from .admin.store import AdminStore
        admin = AdminStore(Path(db_path).parent / "admin.sqlite3", Path(db_path))
        try:
            admin.initialize()
        except Exception:
            admin.ready = False
        application.state.admin_store = admin
        admin.llm_budget = budget
        application.state.replanning = coordinator
        from .admin.scheduler import SourceScheduler
        scheduler = SourceScheduler(admin)
        admin.scheduler = scheduler
        application.state.source_scheduler = scheduler
        await scheduler.start()
        stopping = asyncio.Event()
        async def watch_approved_windows():
            while not stopping.is_set():
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=1)
                except TimeoutError:
                    if coordinator:
                        try:
                            await asyncio.to_thread(coordinator.sync_approved_events)
                            application.state.replanning_error = None
                        except Exception:
                            application.state.replanning_error = "approved_event_reconciliation_failed"
        monitor = asyncio.create_task(watch_approved_windows(), name="approved-event-windows")
        try:
            yield
        finally:
            stopping.set()
            await monitor
            await scheduler.stop()

    application = FastAPI(title="ResilientRoute API", version="m0-integrated", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(parse_cors_origins(
            os.getenv("CORS_ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS"))
        )),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "x-review-token", "Last-Event-ID"],
        expose_headers=["X-Route-Snapshot"],
    )
    application.include_router(signals_router)
    application.include_router(events_router)
    application.include_router(review_router)
    application.include_router(stream_router)
    from .api.persona import router as persona_router
    application.include_router(persona_router)
    from .api.buses import router as buses_router
    application.include_router(buses_router)
    from .admin.scheduler import router as sources_router
    application.include_router(sources_router)
    if coordinator:
        from .sim.runtime_replanning import build_router
        application.include_router(build_router(coordinator))
    from .admin.api import router as admin_router
    from fastapi.staticfiles import StaticFiles
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler
    application.include_router(admin_router)
    application.mount("/admin", StaticFiles(directory=str(Path(__file__).parent / "admin_static"), html=True, check_dir=False), name="admin")

    @application.middleware("http")
    async def admin_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/admin") or request.url.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @application.exception_handler(RequestValidationError)
    async def safe_validation(request, exc):
        if request.url.path.startswith("/api/admin"):
            return JSONResponse(status_code=422, content={"detail": [
                {"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]})
        return await request_validation_exception_handler(request, exc)


    @application.get("/api/health")
    def health() -> JSONResponse:
        body = runtime.health()
        return JSONResponse(status_code=200 if body["ok"] else 503, content=body)

    @application.get("/api/meta")
    def meta() -> dict[str, Any]:
        snapshot = runtime.engine.snapshots.current.snapshot_id if runtime.engine else None
        bus_meta = runtime.engine.snapshots.network.source.get('meta', {}).get('corridor_bus') if runtime.engine else None
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "build": get_build_info(),
            "graph_snapshot": snapshot,
            "sources": ["contracts/seed/network.seed.json", "contracts/seed/event.seed.json"] + (["Transport Department corridor GTFS buses", "KMB/LWB and Citybus official arrival APIs"] if bus_meta else []),
            "disclaimer": "Route durations, capacities and walking connections include model estimates. Official bus calendars/fares are imported when enabled; current operator arrivals are shown separately.",
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
    async def ai_chat(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        if runtime.ai_service is None:
            raise HTTPException(status_code=503, detail="AI fallback service unavailable")
        if not isinstance(payload.get("message"), str) or not payload["message"].strip():
            raise HTTPException(status_code=422, detail="Missing non-empty field: message")
        if len(payload["message"]) > 2000:
            raise HTTPException(status_code=422, detail="message must contain at most 2000 characters")
        required = ("origin", "destination", "depart_at")
        if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
            return {"message": "请提供起点、终点和出发时间，我才能调用确定性路线工具。",
                    "tool_calls": [], "fallback": True, "user_input": payload["message"],
                    "graph_snapshot": None, "effective_profile": None}
        # Tool handlers keep intermediate routes/parameters. Construct them per
        # request so simultaneous users cannot overwrite each other's context.
        from .ai.handlers import build_engine_handlers
        from .ai.query import NoLLMQueryService
        from .ai.tools import build_default_registry
        from .ai.runtime import add_wording, configured_client
        from .sim.service import build_diversion_plan
        service = NoLLMQueryService(build_default_registry(build_engine_handlers(runtime.engine, build_diversion_plan)))
        result = await service.query(
            user_input=payload["message"], origin=payload["origin"],
            destination=payload["destination"], depart_at=payload["depart_at"],
            profile_id=payload.get("profile_id"), event_id=payload.get("event_id"),
            profile=payload.get("profile"),
            demand=payload.get("demand"),
        )
        return await add_wording(result, configured_client(request.app))

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


app = create_app(db_path=_path(os.getenv("DB_PATH") or str(DEFAULT_DB_PATH)))
