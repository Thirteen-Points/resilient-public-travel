"""Validate the shared Event/Signal seed against schemas and Pydantic models."""

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
SEED_PATH = SEED_DIRECTORY / "event.seed.json"
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "contracts" / "schemas"


def load_seed_documents(directory: Path = SEED_DIRECTORY) -> dict[str, Any]:
    """Load all four shared seed files and fail clearly on a missing/bad file."""

    documents: dict[str, Any] = {}
    for filename in SEED_FILENAMES:
        path = directory / filename
        documents[filename] = json.loads(path.read_text(encoding="utf-8"))
    return documents


def _schema_errors(
    item: dict[str, Any], schema: dict[str, Any], object_id: str
) -> list[str]:
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(item), key=lambda value: list(value.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{object_id} [{location}]: {error.message}")
    return errors


def validate_seed_payload(
    payload: dict[str, Any],
    event_schema: dict[str, Any],
    signal_schema: dict[str, Any],
) -> list[str]:
    """Return all validation errors instead of stopping at the first problem."""

    errors: list[str] = []
    events = payload.get("events")
    signals = payload.get("signals")
    if not isinstance(events, list):
        return ["seed [events]: must be an array"]
    if not isinstance(signals, list):
        return ["seed [signals]: must be an array"]

    if len(events) != 3:
        errors.append(f"seed [events]: expected 3 Events, found {len(events)}")
    if len(signals) != 5:
        errors.append(f"seed [signals]: expected 5 Signals, found {len(signals)}")

    event_ids: list[str] = []
    signal_ids: list[str] = []
    referenced_signal_ids: set[str] = set()

    for index, item in enumerate(events):
        if not isinstance(item, dict):
            errors.append(f"event[{index}]: must be an object")
            continue
        object_id = str(item.get("event_id", f"event[{index}]"))
        event_ids.append(object_id)
        referenced_signal_ids.update(item.get("signals", []))
        errors.extend(_schema_errors(item, event_schema, object_id))
        try:
            Event.model_validate(item)
        except ValidationError as exc:
            errors.append(f"{object_id} [Pydantic]: {exc}")

    for index, item in enumerate(signals):
        if not isinstance(item, dict):
            errors.append(f"signal[{index}]: must be an object")
            continue
        object_id = str(item.get("signal_id", f"signal[{index}]"))
        signal_ids.append(object_id)
        errors.extend(_schema_errors(item, signal_schema, object_id))
        try:
            Signal.model_validate(item)
        except ValidationError as exc:
            errors.append(f"{object_id} [Pydantic]: {exc}")

    if len(event_ids) != len(set(event_ids)):
        errors.append("seed [events]: duplicate event_id values")
    if len(signal_ids) != len(set(signal_ids)):
        errors.append("seed [signals]: duplicate signal_id values")

    known_signal_ids = set(signal_ids)
    missing = sorted(referenced_signal_ids - known_signal_ids)
    unused = sorted(known_signal_ids - referenced_signal_ids)
    if missing:
        errors.append(f"seed: missing referenced Signals: {', '.join(missing)}")
    if unused:
        errors.append(f"seed: unreferenced Signals: {', '.join(unused)}")

    expected_states = [
        ("pending_review", 0.20),
        ("pending_review", 0.55),
        ("published", 0.90),
    ]
    actual_states = [
        (item.get("status"), item.get("confidence"))
        for item in events
        if isinstance(item, dict)
    ]
    if actual_states != expected_states:
        errors.append(
            "seed [events]: expected demonstration states "
            f"{expected_states}, found {actual_states}"
        )
    return errors


def main() -> int:
    try:
        seed_documents = load_seed_documents()
        payload = seed_documents[SEED_PATH.name]
        event_schema = json.loads(
            (SCHEMA_DIRECTORY / "event.schema.json").read_text(encoding="utf-8")
        )
        signal_schema = json.loads(
            (SCHEMA_DIRECTORY / "signal.schema.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"contract seed validation could not start: {exc}", file=sys.stderr)
        return 2

    errors = validate_seed_payload(payload, event_schema, signal_schema)
    if errors:
        print("contract seed validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {SEED_PATH.relative_to(REPOSITORY_ROOT)}: {error}", file=sys.stderr)
        return 1

    print(
        "contract seed validation passed: 4 seed JSON files readable; "
        "3 Events and 5 Signals satisfy the B-owned contracts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
