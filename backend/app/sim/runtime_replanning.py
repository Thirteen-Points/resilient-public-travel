"""Trusted runtime bridge for approved events and explicit load observations.

No source of live passenger load is invented here. Callers must install a
provider separately, or identify observations as simulated manual exercises.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import math
from time import perf_counter
from threading import RLock

from ..engine.environment import approved_weather_conditions
from ..graph.snapshot import active
from .replanning import ReplanDecision, ReplanningMonitor, dispatch_replan
from pydantic import BaseModel, ConfigDict, Field


class LoadObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_id: str = Field(min_length=1)
    load_factor: float = Field(ge=0, allow_inf_nan=False)
    observed_at: datetime
    source: str
    provenance: str
    context: dict | None = None
    demand: int | None = Field(default=None, ge=0, strict=True)


class RuntimeReplanningCoordinator:
    def __init__(self, engine, approved_events_supplier, *, trusted_load_sources=None, diversion_replanner=None):
        self.engine = engine
        self.approved_events_supplier = approved_events_supplier
        self.trusted_load_sources = trusted_load_sources or {"manual_simulation": {"simulated"}}
        self.diversion_replanner = diversion_replanner
        self.monitor = ReplanningMonitor()
        self._lock = RLock()
        self._last_load_at = {}
        self._load_source = {}
        self._contexts = {}
        self._demands = {}
        self._active_signature = None
        self._weather_signature = set()
        self.latest = None

    def register_query(self, query_id, context):
        """Internal subscription, not a side effect of an unauthenticated query."""
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("query_id must be nonempty")
        with self._lock:
            if query_id not in self._contexts and len(self._contexts) >= 32:
                raise ValueError("At most 32 internal route subscriptions")
            self._contexts[query_id] = deepcopy(context)

    def register_simulation(self, query_id, context, demand):
        """Subscribe an explicit simulated demand; never infer it from supply."""
        self._validate_demand(demand)
        with self._lock:
            self.register_query(query_id, context)
            self._demands[query_id] = demand

    @staticmethod
    def _validate_demand(demand):
        if isinstance(demand, bool) or not isinstance(demand, int) or demand < 0:
            raise ValueError("demand must be an explicit nonnegative integer")

    def _execute(self, decision, *, context=None, observation=None, demand=None, started_at=None):
        def recompute(_):
            self.engine.cache.clear()
            contexts = {**self._contexts, **({"requested": context} if context else {})}
            routes = {key: self.engine.query_details(**query) for key, query in contexts.items()}
            demands = {**self._demands, **({"requested": demand} if demand is not None else {})}
            diversion = self.diversion_replanner(decision, routes) if self.diversion_replanner else {}
            if self.diversion_replanner is None:
                from .service import build_diversion_plan
                from .shared_capacity import resources_from_snapshot
                for key, explicit_demand in demands.items():
                    if key not in routes:
                        continue
                    detail = routes[key]
                    supplies = [dict(value, route_id=route_id) for route_id, value in detail["route_parameters"].items()
                                if value["headway_s"] > 0]
                    resources = resources_from_snapshot(self.engine.snapshots.current, detail,
                                                        contexts[key]["depart_at"])
                    plan = build_diversion_plan({"event_id": "runtime_" + detail["graph_snapshot"],
                                                 "demand": explicit_demand, "routes": supplies,
                                                 "shared_resources": [asdict(resource) for resource in resources]})
                    plan.update(graph_snapshot=detail["graph_snapshot"],
                                note="Explicit simulated demand; walking capacity is not modelled. Load observations trigger recomputation and do not alter route weights.")
                    diversion[key] = plan
            return {"graph_snapshot": self.engine.snapshots.current.snapshot_id,
                    "routes": routes, "diversion": diversion}
        execution = dispatch_replan(decision, recompute)
        elapsed_ms = ((perf_counter() - started_at) * 1000 if started_at is not None and decision.should_replan
                      else execution.elapsed_ms)
        result = {"should_replan": decision.should_replan, "recomputed": execution.recomputed,
                  "trigger": decision.trigger, "reason": decision.reason,
                  "occurred_at": decision.occurred_at.isoformat() if decision.occurred_at else None,
                  "elapsed_ms": elapsed_ms,
                  "within_five_second_budget": elapsed_ms <= 5000,
                  "details": deepcopy(decision.details), "result": execution.result,
                  "observation": observation}
        if decision.should_replan:
            self.latest = result
        return deepcopy(result)

    def sync_approved_events(self, *, observed_at=None):
        """Atomically mirror only approved facts, then recompute subscriptions.

        Call at startup, after reviewer writes, and periodically for expiry.
        approved_events_supplier must be EventStore.approved_events, not list_events.
        """
        now = observed_at or datetime.now(timezone.utc)
        started_at = perf_counter()
        with self._lock:
            events = [event.model_dump(mode="json") if hasattr(event, "model_dump") else deepcopy(event)
                      for event in self.approved_events_supplier()]
            # Defense in depth if a caller accidentally supplies all repository rows.
            events = [event for event in events if event.get("status") == "published"
                      and event.get("reviewed_by")]
            previous = self.engine.snapshots.current.snapshot_id
            snapshot = self.engine.snapshots.replace_events(events)
            signature = tuple(sorted((event["event_id"], event.get("version", 1))
                                     for event in events if active(event, now)))
            weather = set().union(*(approved_weather_conditions(event) for event in events if active(event, now)))
            active_changed = self._active_signature is not None and signature != self._active_signature
            weather_changed = weather != self._weather_signature
            self._active_signature, self._weather_signature = signature, weather
            changed = snapshot.snapshot_id != previous or active_changed
            reason = "Route updated: approved weather warnings changed" if weather_changed else "Route updated: approved events, withdrawals or effective times changed"
            return self._execute(ReplanDecision(changed, "weather_changed" if weather_changed else "approved_events_changed",
                                 reason if changed else None, now if changed else None,
                                 {"weather_conditions": sorted(weather), "graph_snapshot": snapshot.snapshot_id}),
                                 started_at=started_at)

    def observe_load(self, route_id, load_factor, *, observed_at, source, provenance, context=None, demand=None):
        with self._lock:
            if demand is not None:
                self._validate_demand(demand)
                if context is None:
                    raise ValueError("Explicit demand requires route context")
            if provenance not in self.trusted_load_sources.get(source, set()):
                raise ValueError("Source/provenance is not an installed trusted load provider")
            if not isinstance(route_id, str) or not route_id:
                raise ValueError("route_id must be nonempty")
            if isinstance(load_factor, bool) or not isinstance(load_factor, (float, int)) or not math.isfinite(load_factor) or load_factor < 0:
                raise ValueError("load_factor must be finite and nonnegative")
            if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
                raise ValueError("observed_at must include a timezone")
            previous = self._last_load_at.get(route_id)
            if previous and observed_at <= previous:
                raise ValueError("Load observations must arrive in increasing timestamp order")
            if previous is None and len(self._last_load_at) >= 512:
                raise ValueError("At most 512 observed routes")
            if provenance != "simulated" and observed_at > datetime.now(timezone.utc) + timedelta(minutes=1):
                raise ValueError("Real observations cannot be dated in the future")
            identity = (source, provenance)
            if previous and (observed_at - previous > timedelta(minutes=2) or self._load_source[route_id] != identity):
                # Two isolated samples do not prove five sustained minutes.
                self.monitor.observe_load(route_id, 0, observed_at=observed_at)
            self._last_load_at[route_id] = observed_at
            self._load_source[route_id] = identity
            decision = self.monitor.observe_load(route_id, load_factor, observed_at=observed_at)
            return self._execute(decision, context=context, demand=demand,
                                 observation={"source": source, "provenance": provenance,
                                              "route_id": route_id, "load_factor": load_factor,
                                              "observed_at": observed_at.isoformat()})

    def status(self):
        with self._lock:
            latest = {key: deepcopy(value) for key, value in (self.latest or {}).items()
                      if key in {"should_replan", "recomputed", "trigger", "reason", "occurred_at",
                                 "elapsed_ms", "within_five_second_budget"}} if self.latest else None
            return {"graph_snapshot": self.engine.snapshots.current.snapshot_id,
                    "latest": latest,
                    "trusted_load_sources": {key: sorted(value) for key, value in self.trusted_load_sources.items()},
                    "live_load_provider_installed": any("real" in values or "real-derived" in values
                                                         for values in self.trusted_load_sources.values())}


def build_router(coordinator):
    """Read-only public status; load writes require existing reviewer credentials."""
    from fastapi import APIRouter, Header, HTTPException, Request
    from ..api.review import require_reviewer

    router = APIRouter(prefix="/api/replanning", tags=["replanning"])

    @router.get("/status")
    def status():
        return coordinator.status()

    @router.post("/load-observations")
    def observe(body: LoadObservation, request: Request, x_review_token: str | None = Header(default=None)):
        require_reviewer(request, x_review_token)
        try:
            return coordinator.observe_load(**body.model_dump())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return router
