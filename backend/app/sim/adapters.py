"""Validated adapters for C-Route output and B replanning updates.

C-Route keeps simulation-only parameters outside the public RouteCandidate
contract.  ``query_details`` therefore returns ``routes`` plus a
``route_parameters`` mapping keyed by the same stable ``route_id``.  This
module consumes that internal integration shape without adding fields to the
public contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math

from backend.app.engine.load import RouteSupply

from .models import RouteOption
from .replanning import ReplanDecision, ReplanningMonitor


PROVENANCE_VALUES = {"real", "real-derived", "simulated"}
EVENT_STATUSES = {"draft", "pending_review", "published", "updated", "expired", "rejected"}


def _mapping(value: object, path: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _number(value: object, path: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{path} must be finite and >= {minimum}")
    return result


def _fixture_provenance(payload: Mapping, path: str, fixture: bool) -> str:
    provenance = payload.get("provenance")
    if provenance not in PROVENANCE_VALUES:
        raise ValueError(f"{path}.provenance is required and must use the contract enum")
    if fixture and provenance != "simulated":
        raise ValueError(f"{path}.provenance must remain simulated for fixtures")
    return str(provenance)


def _aware_datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{path} must be an ISO-8601 date-time") from exc
    else:
        raise ValueError(f"{path} must be an ISO-8601 date-time")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{path} must include a timezone")
    return parsed


def _route_option(payload: object, index: int, *, fixture: bool) -> RouteOption:
    route = _mapping(payload, f"routes[{index}]")
    _nonempty_string(route.get("route_id"), f"routes[{index}].route_id")
    _fixture_provenance(route, f"routes[{index}]", fixture)
    total = _mapping(route.get("total"), f"routes[{index}].total")
    _number(total.get("time_s"), f"routes[{index}].total.time_s", minimum=1e-12)
    transfers = _number(total.get("transfers"), f"routes[{index}].total.transfers")
    if not transfers.is_integer():
        raise ValueError(f"routes[{index}].total.transfers must be an integer")
    _number(total.get("walk_m"), f"routes[{index}].total.walk_m")
    _number(total.get("fare_hkd"), f"routes[{index}].total.fare_hkd")
    reliability = _number(total.get("reliability"), f"routes[{index}].total.reliability")
    if reliability > 1:
        raise ValueError(f"routes[{index}].total.reliability must be <= 1")
    _number(total.get("freshness_s"), f"routes[{index}].total.freshness_s")
    legs = route.get("legs")
    if not isinstance(legs, list) or not legs:
        raise ValueError(f"routes[{index}].legs must be a non-empty array")
    for leg_index, value in enumerate(legs):
        leg = _mapping(value, f"routes[{index}].legs[{leg_index}]")
        _nonempty_string(leg.get("mode"), f"routes[{index}].legs[{leg_index}].mode")
        if "accessible" not in leg or leg["accessible"] not in {True, False, "partial"}:
            raise ValueError(
                f"routes[{index}].legs[{leg_index}].accessible must be true, false or partial"
            )
        _fixture_provenance(leg, f"routes[{index}].legs[{leg_index}]", fixture)
    return RouteOption.from_route_candidate(dict(route))


def _supply(
    payload: object, path: str, *, fixture: bool, require_capacity_per_hour: bool
) -> RouteSupply:
    item = _mapping(payload, path)
    _nonempty_string(item.get("route_id"), f"{path}.route_id")
    _number(item.get("headway_s"), f"{path}.headway_s", minimum=1e-12)
    if item.get("capacity_per_hour") is not None:
        _number(item.get("capacity_per_hour"), f"{path}.capacity_per_hour", minimum=1e-12)
    elif require_capacity_per_hour:
        raise ValueError(f"{path}.capacity_per_hour must be numeric")
    else:
        # Backward-compatible offline seam. C-Route's standard output must
        # always take the branch above; declared offline fixtures may retain
        # their auditable vehicle-capacity calculation inputs.
        _number(item.get("vehicle_capacity"), f"{path}.vehicle_capacity", minimum=1e-12)
    _fixture_provenance(item, path, fixture)
    return RouteSupply.from_route_output(dict(item))


def routes_from_contract(
    route_payload: dict,
    supply_payload: list[dict] | Mapping[str, dict] | None = None,
    *,
    fixture: bool = False,
) -> tuple[tuple[RouteOption, ...], tuple[RouteSupply, ...]]:
    """Adapt RouteCandidate fields plus C-Route simulation parameters.

    Passing only ``route_payload`` consumes C-Route's standard
    ``query_details`` output.  ``supply_payload`` remains supported for the
    existing offline precompute input; it is an adapter seam, not a second
    public contract.
    """

    root = _mapping(route_payload, "C-Route output")
    route_items = root.get("routes")
    if not isinstance(route_items, list) or not route_items:
        raise ValueError("C-Route output.routes must be a non-empty array")
    routes = tuple(_route_option(item, index, fixture=fixture) for index, item in enumerate(route_items))
    route_ids = [route.route_id for route in routes]
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("C-Route output contains duplicate route_id values")

    raw_supplies: list[dict]
    standard_c_route_output = supply_payload is None
    if supply_payload is None:
        parameters = root.get("route_parameters")
        if not isinstance(parameters, Mapping):
            raise ValueError("C-Route output.route_parameters must be an object")
        raw_supplies = []
        for route_id, value in parameters.items():
            parameter = dict(_mapping(value, f"route_parameters[{route_id!r}]"))
            parameter["route_id"] = route_id
            raw_supplies.append(parameter)
    elif isinstance(supply_payload, Mapping):
        raw_supplies = []
        for route_id, value in supply_payload.items():
            parameter = dict(_mapping(value, f"supply_payload[{route_id!r}]"))
            parameter["route_id"] = route_id
            raw_supplies.append(parameter)
    elif isinstance(supply_payload, list):
        raw_supplies = supply_payload
    else:
        raise ValueError("supply_payload must be an array or route_id mapping")

    if not raw_supplies:
        raise ValueError("C-Route output contains no capacity parameters")
    supplies = tuple(
        _supply(
            item,
            f"route supply[{index}]",
            fixture=fixture,
            require_capacity_per_hour=standard_c_route_output,
        )
        for index, item in enumerate(raw_supplies)
    )
    supply_ids = [supply.route_id for supply in supplies]
    if len(supply_ids) != len(set(supply_ids)):
        raise ValueError("C-Route output contains duplicate capacity route_id values")
    if set(route_ids) != set(supply_ids):
        missing_supply = sorted(set(route_ids) - set(supply_ids))
        unknown_supply = sorted(set(supply_ids) - set(route_ids))
        raise ValueError(
            f"route/supply ids differ; missing_supply={missing_supply}, unknown_supply={unknown_supply}"
        )
    return routes, supplies


def routes_from_c_route_output(
    output: dict, *, fixture: bool = False
) -> tuple[tuple[RouteOption, ...], tuple[RouteSupply, ...]]:
    """Named entrypoint for C-Route ``query_details`` output."""

    return routes_from_contract(output, fixture=fixture)


@dataclass(frozen=True, slots=True)
class ODRouteSet:
    """Internal C-Sim wrapper around one C-Route query result."""

    origin: str
    destination: str
    routes: tuple[RouteOption, ...]
    supplies: tuple[RouteSupply, ...]
    demand_weight: float
    provenance: str

    @property
    def od(self) -> tuple[str, str]:
        return self.origin, self.destination


def od_route_sets_from_contract(
    payload: dict, *, fixture: bool = False
) -> tuple[ODRouteSet, ...]:
    """Adapt a private list of per-OD C-Route ``query_details`` outputs.

    Each item keeps the standard ``routes`` and ``route_parameters`` shape.
    The outer OD wrapper is C-Sim integration metadata, not a public contract.
    """

    root = _mapping(payload, "C-Sim OD route input")
    _fixture_provenance(root, "C-Sim OD route input", fixture)
    items = root.get("od_route_sets")
    if not isinstance(items, list) or not items:
        raise ValueError("C-Sim OD route input.od_route_sets must be a non-empty array")

    result: list[ODRouteSet] = []
    seen_ods: set[tuple[str, str]] = set()
    seen_route_ids: set[str] = set()
    for index, value in enumerate(items):
        path = f"od_route_sets[{index}]"
        item = _mapping(value, path)
        origin = _nonempty_string(item.get("origin"), f"{path}.origin")
        destination = _nonempty_string(item.get("destination"), f"{path}.destination")
        if origin == destination:
            raise ValueError(f"{path} must use distinct origin and destination")
        od = (origin, destination)
        if od in seen_ods:
            raise ValueError(f"duplicate OD route set: {origin}->{destination}")
        seen_ods.add(od)
        provenance = _fixture_provenance(item, path, fixture)
        demand_weight = _number(
            item.get("demand_weight", 1.0), f"{path}.demand_weight", minimum=1e-12
        )
        route_items = item.get("routes")
        route_parameters = item.get("route_parameters")
        if route_items == []:
            if not isinstance(route_parameters, Mapping) or route_parameters:
                raise ValueError(
                    f"{path}.route_parameters must be an empty object when routes is empty"
                )
            routes: tuple[RouteOption, ...] = ()
            supplies: tuple[RouteSupply, ...] = ()
        else:
            routes, supplies = routes_from_contract(dict(item), fixture=fixture)
        duplicate_route_ids = seen_route_ids & {route.route_id for route in routes}
        if duplicate_route_ids:
            raise ValueError(
                "route_id values must be unique across OD route sets: "
                + ", ".join(sorted(duplicate_route_ids))
            )
        seen_route_ids.update(route.route_id for route in routes)
        result.append(
            ODRouteSet(
                origin=origin,
                destination=destination,
                routes=routes,
                supplies=supplies,
                demand_weight=demand_weight,
                provenance=provenance,
            )
        )
    return tuple(result)


def od_route_sets_from_simulated_fixture(payload: dict) -> tuple[ODRouteSet, ...]:
    """Expand compact, explicitly simulated route profiles for offline M0 tests."""

    root = _mapping(payload, "multi-OD fixture")
    if root.get("fixture") is not True:
        raise ValueError("multi-OD fixture.fixture must be true")
    _fixture_provenance(root, "multi-OD fixture", True)
    profiles = _mapping(root.get("candidate_profiles"), "multi-OD fixture.candidate_profiles")
    items = root.get("od_route_sets")
    if not isinstance(items, list) or not items:
        raise ValueError("multi-OD fixture.od_route_sets must be a non-empty array")

    expanded_items: list[dict] = []
    for index, value in enumerate(items):
        path = f"multi-OD fixture.od_route_sets[{index}]"
        item = _mapping(value, path)
        origin = _nonempty_string(item.get("origin"), f"{path}.origin")
        destination = _nonempty_string(item.get("destination"), f"{path}.destination")
        provenance = _fixture_provenance(item, path, True)
        profile_ids = item.get("candidate_profiles")
        if not isinstance(profile_ids, list):
            raise ValueError(f"{path}.candidate_profiles must be an array")
        if any(not isinstance(profile_id, str) or not profile_id for profile_id in profile_ids):
            raise ValueError(f"{path}.candidate_profiles must contain non-empty strings")
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError(f"{path}.candidate_profiles must not duplicate candidates")

        routes: list[dict] = []
        route_parameters: dict[str, dict] = {}
        for profile_id in profile_ids:
            profile = _mapping(
                profiles.get(profile_id), f"multi-OD fixture.candidate_profiles[{profile_id!r}]"
            )
            _fixture_provenance(
                profile, f"multi-OD fixture.candidate_profiles[{profile_id!r}]", True
            )
            route = dict(
                _mapping(
                    profile.get("route"),
                    f"multi-OD fixture.candidate_profiles[{profile_id!r}].route",
                )
            )
            parameter = dict(
                _mapping(
                    profile.get("route_parameters"),
                    f"multi-OD fixture.candidate_profiles[{profile_id!r}].route_parameters",
                )
            )
            route_id = f"sim_{origin.lower()}_{destination.lower()}_{profile_id}"
            route["route_id"] = route_id
            routes.append(route)
            route_parameters[route_id] = parameter
        expanded_items.append(
            {
                "origin": origin,
                "destination": destination,
                "demand_weight": item.get("demand_weight", 1.0),
                "routes": routes,
                "route_parameters": route_parameters,
                "provenance": provenance,
            }
        )
    return od_route_sets_from_contract(
        {"od_route_sets": expanded_items, "provenance": "simulated"}, fixture=True
    )


@dataclass(frozen=True, slots=True)
class BEventUpdate:
    event_id: str
    version: int
    status: str
    confidence: float
    observed_at: datetime
    provenance: str


@dataclass(frozen=True, slots=True)
class BLoadUpdate:
    route_id: str
    load_factor: float
    observed_at: datetime
    provenance: str


@dataclass(frozen=True, slots=True)
class BWeatherUpdate:
    weather_warning_code: str
    observed_at: datetime
    provenance: str


BUpdate = BEventUpdate | BLoadUpdate | BWeatherUpdate


def adapt_b_event(payload: dict, *, fixture: bool = False) -> BEventUpdate:
    item = _mapping(payload, "B event")
    event_id = _nonempty_string(item.get("event_id"), "B event.event_id")
    version = item.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("B event.version must be a positive integer")
    status = _nonempty_string(item.get("status"), "B event.status")
    if status not in EVENT_STATUSES:
        raise ValueError("B event.status is outside the frozen contract enum")
    confidence = _number(item.get("confidence"), "B event.confidence")
    if confidence > 1:
        raise ValueError("B event.confidence must be <= 1")
    return BEventUpdate(
        event_id=event_id,
        version=version,
        status=status,
        confidence=confidence,
        observed_at=_aware_datetime(item.get("observed_at"), "B event.observed_at"),
        provenance=_fixture_provenance(item, "B event", fixture),
    )


def adapt_b_load(payload: dict, *, fixture: bool = False) -> BLoadUpdate:
    item = _mapping(payload, "B load")
    return BLoadUpdate(
        route_id=_nonempty_string(item.get("route_id"), "B load.route_id"),
        load_factor=_number(item.get("load_factor"), "B load.load_factor"),
        observed_at=_aware_datetime(item.get("observed_at"), "B load.observed_at"),
        provenance=_fixture_provenance(item, "B load", fixture),
    )


def adapt_b_weather(payload: dict, *, fixture: bool = False) -> BWeatherUpdate:
    item = _mapping(payload, "B weather")
    return BWeatherUpdate(
        weather_warning_code=_nonempty_string(
            item.get("weather_warning_code"), "B weather.weather_warning_code"
        ).upper(),
        observed_at=_aware_datetime(item.get("observed_at"), "B weather.observed_at"),
        provenance=_fixture_provenance(item, "B weather", fixture),
    )


def adapt_b_update(payload: dict, *, fixture: bool = False) -> BUpdate:
    """Infer one of B's three update shapes without introducing a new field."""

    item = _mapping(payload, "B update")
    shapes = [
        ({"event_id", "version", "status", "confidence"}, adapt_b_event),
        ({"route_id", "load_factor"}, adapt_b_load),
        ({"weather_warning_code"}, adapt_b_weather),
    ]
    matches = [adapter for fields, adapter in shapes if fields <= set(item)]
    if len(matches) != 1:
        raise ValueError("B update must match exactly one event, load or weather shape")
    return matches[0](dict(item), fixture=fixture)


def apply_b_update(monitor: ReplanningMonitor, update: BUpdate) -> ReplanDecision:
    """Bridge validated B fields to the deterministic replanning monitor."""

    if isinstance(update, BEventUpdate):
        return monitor.observe_event(
            {
                "event_id": update.event_id,
                "version": update.version,
                "status": update.status,
                "confidence": update.confidence,
            },
            observed_at=update.observed_at,
        )
    if isinstance(update, BLoadUpdate):
        return monitor.observe_load(
            update.route_id, update.load_factor, observed_at=update.observed_at
        )
    if isinstance(update, BWeatherUpdate):
        return monitor.observe_weather(
            {update.weather_warning_code}, observed_at=update.observed_at
        )
    raise TypeError("unsupported B update")
