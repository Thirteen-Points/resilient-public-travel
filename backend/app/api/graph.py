"""
Graph network endpoint.
Serves station/line/walk link data from local JSON files.
This is C's responsibility per contracts (03-contracts.md section 4).
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config.settings import settings

router = APIRouter()
logger = logging.getLogger("resilient_route.graph")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _load_json(filepath: Path) -> dict:
    """Load JSON from file path."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data file not found: {filepath.name}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON parse error: {e}")


@router.get("/graph/network")
async def get_network():
    """
    Return the full transit network: nodes, lines, walk links.
    Used by frontend for map rendering.
    """
    data_dir = PROJECT_ROOT / "data" / "network"

    stations = _load_json(data_dir / "stations.json")
    lines = _load_json(data_dir / "lines.json")
    walk_links = _load_json(data_dir / "walk_links.json")

    # Combine into a single network response
    nodes = []
    nodes.extend(stations.get("stations", []))
    nodes.extend(stations.get("bus_stops", []))
    nodes.extend(stations.get("piers", []))

    return {
        "nodes": nodes,
        "lines": lines.get("lines", []),
        "walk_links": walk_links.get("walk_links", []),
        "catchment_m": 800,
        "meta": {
            "version": stations.get("meta", {}).get("version", "1.0"),
            "source": "local data files",
            "provenance": "real / real-derived (see data/PROVENANCE.md)",
        },
    }


@router.get("/graph/snapshot")
async def get_snapshot():
    """
    Return current graph snapshot version and affected edges.
    In this minimal version, no events are published so no edges are affected.
    """
    return {
        "snapshot_id": "g_local_v1",
        "affected_edges": [],
        "version": 1,
        "note": "No published events. All edges at normal capacity.",
    }
