"""
Meta endpoint - provides freshness, sources, and disclaimer.
This is required on every page per contracts (03-contracts.md section 3.6).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from ..config.settings import settings

router = APIRouter()
logger = logging.getLogger("resilient_route.meta")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@router.get("/meta")
async def get_meta():
    """Return freshness, sources, and disclaimer."""
    ts = datetime.now(timezone.utc).isoformat()

    return {
        "generated_at": ts,
        "graph_snapshot": "g_local_v1",
        "sources": [
            {
                "name": "MTR stations & lines",
                "last_ok": ts,
                "provenance": "real",
                "url": "https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities",
            },
            {
                "name": "MTR schedule (getSchedule)",
                "last_ok": ts if not settings.offline_mode else None,
                "provenance": "real",
                "url": settings.mtr_schedule_api,
            },
            {
                "name": "HKO weather warnings",
                "last_ok": ts if not settings.offline_mode else None,
                "provenance": "real",
                "url": settings.hko_weather_api,
            },
            {
                "name": "KMB bus data",
                "last_ok": ts if not settings.offline_mode else None,
                "provenance": "real",
                "url": settings.kmb_api_base,
            },
            {
                "name": "local network data",
                "last_ok": ts,
                "provenance": "real",
                "url": None,
            },
        ],
        "disclaimer": (
            "This platform is an academic demonstration, not an official emergency guide. "
            "Route and load estimates are derived/simulated results. "
            "Please refer to official MTR and Transport Department announcements."
        ),
    }
