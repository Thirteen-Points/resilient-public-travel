"""Validate the four shared seed files against their committed contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from jsonschema import Draft202012Validator  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from backend.app.services.event_models import Event  # noqa: E402
from backend.app.services.signal_models import Signal  # noqa: E402


SEED_DIRECTORY = REPOSITORY_ROOT / "contracts" / "seed"
SEED_FILENAMES = (
    "network.seed.json",
    "event.seed.json",
    "routes.seed.json",
    "sim.seed.json",
)
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "contracts" / "schemas"
SCHEMA_FILENAMES = {
    "network.seed.json": "network.schema.json",
    "event.seed.json": "event-seed.schema.json",
    "routes.seed.json": "routes.schema.json",
    "sim.seed.json": "sim.schema.json",
}


def load_seed_documents(directory: Path = SEED_DIRECTORY) -> dict[str, Any]:
    """Load all four shared seed files and fail clearly on a missing/bad file."""

    documents: dict[str, Any] = {}
    for filename in SEED_FILENAMES:
        path = directory / filename
        documents[filename] = json.loads(path.read_text(encoding="utf-8"))
    return documents


def load_contract_schemas(directory: Path = SCHEMA_DIRECTORY) -> dict[str, dict[str, Any]]:
    """Load the schemas used for seed validation, including the B-owned Signal."""

    schemas = {
        filename: json.loads((directory / schema_name).read_text(encoding="utf-8"))
        for filename, schema_name in SCHEMA_FILENAMES.items()
    }
    schemas["event_item"] = json.loads(
        (directory / "event.schema.json").read_text(encoding="utf-8")
    )
    schemas["signal_item"] = json.loads(
        (directory / "signal.schema.json").read_text(encoding="utf-8")
    )
    return schemas


def _schema_errors(document: Any, schema: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(document),
        key=lambda value: tuple(str(part) for part in value.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label} [{location}]: {error.message}")
    return errors


def _unique_ids(items: Any, key: str, label: str) -> list[str]:
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return []
    values = [item.get(key) for item in items]
    errors: list[str] = []
    if any(not isinstance(value, str) or not value for value in values):
        errors.append(f"{label}: every item must have a non-empty {key}")
    valid_values = [value for value in values if isinstance(value, str)]
    if len(valid_values) != len(set(valid_values)):
        errors.append(f"{label}: duplicate {key} values")
    return errors


def _validate_event_seed(
    document: dict[str, Any],
    event_schema: dict[str, Any],
    signal_schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    events = document.get("events")
    signals = document.get("signals")
    if not isinstance(events, list):
        return ["event.seed.json [events]: must be an array"]
    if not isinstance(signals, list):
        return ["event.seed.json [signals]: must be an array"]

    if len(events) != 3:
        errors.append(f"event.seed.json [events]: expected 3 Events, found {len(events)}")
    if len(signals) != 5:
        errors.append(f"event.seed.json [signals]: expected 5 Signals, found {len(signals)}")

    event_ids: list[str] = []
    signal_ids: list[str] = []
    referenced_signal_ids: set[str] = set()
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("event_id", f"event[{index}]"))
        event_ids.append(event_id)
        referenced_signal_ids.update(
            signal_id for signal_id in item.get("signals", []) if isinstance(signal_id, str)
        )
        errors.extend(_schema_errors(item, event_schema, f"event.seed.json [event {event_id}]"))
        try:
            Event.model_validate(item)
        except ValidationError as exc:
            errors.append(f"event.seed.json [{event_id}] [Pydantic]: {exc}")

    for index, item in enumerate(signals):
        if not isinstance(item, dict):
            continue
        signal_id = str(item.get("signal_id", f"signal[{index}]"))
        signal_ids.append(signal_id)
        errors.extend(_schema_errors(item, signal_schema, f"event.seed.json [signal {signal_id}]"))
        try:
            Signal.model_validate(item)
        except ValidationError as exc:
            errors.append(f"event.seed.json [signal {signal_id}] [Pydantic]: {exc}")

    if len(event_ids) != len(set(event_ids)):
        errors.append("event.seed.json [events]: duplicate event_id values")
    if len(signal_ids) != len(set(signal_ids)):
        errors.append("event.seed.json [signals]: duplicate signal_id values")
    missing = sorted(referenced_signal_ids - set(signal_ids))
    unused = sorted(set(signal_ids) - referenced_signal_ids)
    if missing:
        errors.append(f"event.seed.json: missing referenced Signals: {', '.join(missing)}")
    if unused:
        errors.append(f"event.seed.json: unreferenced Signals: {', '.join(unused)}")

    expected_states = [("pending_review", 0.20), ("pending_review", 0.55), ("published", 0.90)]
    actual_states = [
        (item.get("status"), item.get("confidence"))
        for item in events
        if isinstance(item, dict)
    ]
    if actual_states != expected_states:
        errors.append(
            "event.seed.json [events]: expected demonstration states "
            f"{expected_states}, found {actual_states}"
        )
    return errors


def _validate_cross_file_references(documents: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    network = documents.get("network.seed.json", {})
    routes_doc = documents.get("routes.seed.json", {})
    sim = documents.get("sim.seed.json", {})
    if not all(isinstance(value, dict) for value in (network, routes_doc, sim)):
        return errors

    nodes = network.get("nodes", [])
    lines = network.get("lines", [])
    links = network.get("walk_links", [])
    routes = routes_doc.get("routes", [])
    if not all(isinstance(value, list) for value in (nodes, lines, links, routes)):
        return errors
    node_ids = {
        item["id"] for item in nodes
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    line_ids = {
        item["id"] for item in lines
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    route_ids = {
        item["route_id"] for item in routes
        if isinstance(item, dict) and isinstance(item.get("route_id"), str)
    }

    network_meta = network.get("meta")
    counts = network_meta.get("counts") if isinstance(network_meta, dict) else None
    if not isinstance(counts, dict):
        counts = {}
    for field, actual in (("nodes", len(nodes)), ("lines", len(lines)), ("walk_links", len(links))):
        if counts.get(field) != actual:
            errors.append(
                f"network.seed.json [meta.counts.{field}]: expected {actual}, found {counts.get(field)}"
            )
    errors.extend(_unique_ids(nodes, "id", "network.seed.json [nodes]"))
    errors.extend(_unique_ids(lines, "id", "network.seed.json [lines]"))
    errors.extend(_unique_ids(routes, "route_id", "routes.seed.json [routes]"))

    for line in lines:
        if not isinstance(line, dict):
            continue
        line_id = line.get("id", "<unknown>")
        stops = line.get("stops", [])
        segment_times = line.get("seg_time_s", [])
        if isinstance(stops, list) and isinstance(segment_times, list) and len(segment_times) != len(stops) - 1:
            errors.append(
                f"network.seed.json [lines.{line_id}.seg_time_s]: expected one time per adjacent stop pair"
            )
        stop_ids = {stop for stop in stops if isinstance(stop, str)} if isinstance(stops, list) else set()
        missing_stops = sorted(stop_ids - node_ids)
        if missing_stops:
            errors.append(
                f"network.seed.json [lines.{line_id}.stops]: unknown node IDs {', '.join(missing_stops)}"
            )

    for index, link in enumerate(links):
        if isinstance(link, dict):
            endpoints = {
                endpoint for endpoint in (link.get("from"), link.get("to"))
                if isinstance(endpoint, str)
            }
            missing = sorted(endpoints - node_ids)
            if missing:
                errors.append(
                    f"network.seed.json [walk_links[{index}]]: unknown node IDs {', '.join(missing)}"
                )

    routes_meta = routes_doc.get("meta")
    expected_route_count = routes_meta.get("included_here") if isinstance(routes_meta, dict) else None
    if expected_route_count != len(routes):
        errors.append(
            f"routes.seed.json [meta.included_here]: expected {len(routes)}, found {expected_route_count}"
        )
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            continue
        legs = route.get("legs", [])
        if not isinstance(legs, list):
            continue
        for leg_index, leg in enumerate(legs):
            if not isinstance(leg, dict):
                continue
            for endpoint in ("from", "to"):
                endpoint_id = leg.get(endpoint)
                if not isinstance(endpoint_id, str) or endpoint_id not in node_ids:
                    errors.append(
                        f"routes.seed.json [routes[{index}].legs[{leg_index}].{endpoint}]: "
                        f"unknown node ID {endpoint_id!r}"
                    )
            line_id = leg.get("line")
            if line_id is not None and (not isinstance(line_id, str) or line_id not in line_ids):
                errors.append(
                    f"routes.seed.json [routes[{index}].legs[{leg_index}].line]: "
                    f"unknown line ID {line_id!r}"
                )

    picks = routes_doc.get("persona_top_picks", [])
    for index, pick in enumerate(picks if isinstance(picks, list) else []):
        if isinstance(pick, dict):
            top_ids = pick.get("top", [])
            top_ids = {item for item in top_ids if isinstance(item, str)} if isinstance(top_ids, list) else set()
            missing = sorted(top_ids - route_ids)
            if missing:
                errors.append(
                    f"routes.seed.json [persona_top_picks[{index}].top]: "
                    f"unknown route IDs {', '.join(missing)}"
                )

    if isinstance(sim, dict):
        sim_meta = sim.get("meta")
        sim_meta_id = sim_meta.get("scenario_id") if isinstance(sim_meta, dict) else None
        if sim.get("scenario_id") != sim_meta_id:
            errors.append("sim.seed.json: scenario_id must match meta.scenario_id")
        baseline = sim.get("baseline")
        guided = sim.get("guided")
        baseline_load = baseline.get("route_load", []) if isinstance(baseline, dict) else []
        guided_shares = guided.get("shares", []) if isinstance(guided, dict) else []
        for section, collection in (("baseline.route_load", baseline_load), ("guided.shares", guided_shares)):
            for index, item in enumerate(collection if isinstance(collection, list) else []):
                route_id = item.get("route_id") if isinstance(item, dict) else None
                if isinstance(route_id, str) and route_id not in route_ids:
                    errors.append(
                        f"sim.seed.json [{section}[{index}].route_id]: "
                        f"unknown route ID {route_id!r}"
                    )
    return errors


def validate_seed_documents(
    documents: dict[str, Any], schemas: dict[str, dict[str, Any]]
) -> list[str]:
    """Validate each seed shape, then validate references shared across files."""

    errors: list[str] = []
    for filename in SEED_FILENAMES:
        if filename not in documents:
            errors.append(f"missing seed document: {filename}")
            continue
        if filename not in schemas:
            errors.append(f"missing schema for {filename}")
            continue
        schema = schemas[filename]
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # jsonschema raises several schema-validation types
            errors.append(f"invalid schema for {filename}: {exc}")
            continue
        errors.extend(_schema_errors(documents[filename], schema, filename))

    event_document = documents.get("event.seed.json")
    if isinstance(event_document, dict) and isinstance(schemas.get("event.seed.json"), dict):
        errors.extend(
            _validate_event_seed(
                event_document,
                schemas["event_item"],
                schemas["signal_item"],
            )
        )
    errors.extend(_validate_cross_file_references(documents))
    return errors


def main() -> int:
    try:
        documents = load_seed_documents()
        schemas = load_contract_schemas()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"contract seed validation could not start: {exc}", file=sys.stderr)
        return 2

    errors = validate_seed_documents(documents, schemas)
    if errors:
        print("contract seed validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "contract seed validation passed: all four seeds satisfy their JSON Schemas; "
        "Event/Signal satisfy Pydantic models; cross-file IDs and counts are consistent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
