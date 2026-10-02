"""Read-only source freshness and reviewer collection queue."""

from fastapi import APIRouter, Header, Request

from .review import require_reviewer

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/status")
def source_status(request: Request) -> list[dict]:
    return request.app.state.source_collection.status()


@router.get("/review-queue")
def collection_review_queue(request: Request, x_review_token: str | None = Header(default=None)) -> list[dict]:
    require_reviewer(request, x_review_token)
    return request.app.state.source_collection.store.review_queue()
