"""Generate committed JSON Schemas from the canonical Pydantic contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.services.event_models import Event  # noqa: E402
from backend.app.services.signal_models import Signal  # noqa: E402


SCHEMA_DIRECTORY = REPOSITORY_ROOT / "contracts" / "schemas"


def schema_documents() -> dict[str, dict[str, Any]]:
    """Return schemas generated from the only authoritative Python models."""

    return {
        "event.schema.json": Event.model_json_schema(),
        "signal.schema.json": Signal.model_json_schema(),
    }


def write_schemas(directory: Path = SCHEMA_DIRECTORY) -> list[Path]:
    """Write deterministic schema files and return their paths."""

    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, schema in schema_documents().items():
        path = directory / filename
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> int:
    for path in write_schemas():
        print(f"generated {path.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
