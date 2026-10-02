"""Atomic precompute writer and traversal-safe result cache."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path


SCENARIO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

# Legacy checked-in results use milestone filenames rather than scenario IDs.
# Keep this explicit: never search arbitrary JSON inputs/manifests as results.
LEGACY_RESULT_FILES = {
    "m2_six_station_directed_od_am_peak": "m2-simulation-result.json",
}


def _result_path(directory: Path, scenario_id: str) -> Path:
    if not SCENARIO_ID.fullmatch(scenario_id):
        raise ValueError("invalid scenario_id")
    return directory / f"{scenario_id}.json"


def write_precomputed(result: dict, directory: Path) -> Path:
    scenario_id = str(result["scenario_id"])
    if not result.get("assumptions"):
        raise ValueError("precomputed result must contain assumptions")
    directory.mkdir(parents=True, exist_ok=True)
    target = _result_path(directory, scenario_id)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{scenario_id}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=False)
            stream.write("\n")
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return target


class PrecomputedResultStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self._cache: dict[Path, tuple[int, dict]] = {}

    def read(self, scenario_id: str) -> dict:
        path = _result_path(self.directory, scenario_id)
        if not path.exists() and scenario_id in LEGACY_RESULT_FILES:
            path = self.directory / LEGACY_RESULT_FILES[scenario_id]
        stat = path.stat()
        cached = self._cache.get(path)
        if cached and cached[0] == stat.st_mtime_ns and cached[1].get("scenario_id") == scenario_id:
            return cached[1]
        with path.open("r", encoding="utf-8") as stream:
            result = json.load(stream)
        if result.get("scenario_id") != scenario_id:
            raise ValueError("cached result scenario_id does not match requested scenario")
        if not result.get("assumptions"):
            raise ValueError("cached result has no assumptions")
        self._cache[path] = (stat.st_mtime_ns, result)
        return result
