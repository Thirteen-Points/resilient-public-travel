"""Read-only synthetic persona presets for frontend selection."""

from fastapi import APIRouter

from ..services.persona import UserProfile, load_personas


router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("", response_model=list[UserProfile])
def list_personas() -> list[UserProfile]:
    return list(load_personas())
