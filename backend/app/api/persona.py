"""B-owned router awaiting registration in the shared application entrypoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.persona import PersonaProfile, PreferenceResult, load_personas, load_presets, parse_preference


class ParsePreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    free_text: str = Field(min_length=1, max_length=500)
    current_profile: dict[str, Any] | None = None


router = APIRouter(prefix="/api/persona", tags=["persona"])
catalog_router = APIRouter(prefix="/api/personas", tags=["persona"])


@catalog_router.get("", response_model=list[PersonaProfile])
def list_personas() -> list[PersonaProfile]:
    """Expose B's five simulated defaults for A's profile selector."""
    return load_personas()


@catalog_router.get("/presets", response_model=dict[str, dict[str, float]])
def list_presets() -> dict[str, dict[str, float]]:
    """Expose B's three modeled weight presets for A's selector."""
    return load_presets()


@router.post("/parse", response_model=PreferenceResult)
def parse_persona(body: ParsePreferenceRequest, request: Request) -> PreferenceResult:
    try:
        return parse_preference(body.free_text,
                                client=getattr(request.app.state, "preference_client", None),
                                current_profile=body.current_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
