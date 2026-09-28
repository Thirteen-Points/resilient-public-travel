"""Optional FastAPI router for the frozen simulation endpoints.

Core tests do not require FastAPI.  The integrator can call ``build_router``
when assembling the application and receives a clear error if the optional web
dependency is absent.
"""

from __future__ import annotations

from pathlib import Path

from .cache import PrecomputedResultStore
from .service import build_diversion_plan


def build_router(result_directory: Path):
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover - depends on integration environment
        raise RuntimeError("FastAPI is required to build the simulation router") from exc

    router = APIRouter(prefix="/api/sim", tags=["simulation"])
    store = PrecomputedResultStore(result_directory)

    @router.post("/load")
    def post_load(payload: dict) -> dict:
        try:
            return build_diversion_plan(payload)
        except (KeyError, TypeError, ValueError) as exc:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "INVALID_SIM_INPUT",
                        "message": str(exc),
                        "fallback": "请保留上一次成功的分流结果并标注数据较旧",
                    }
                },
            )

    @router.get("/result")
    def get_result(scenario_id: str) -> dict:
        try:
            return store.read(scenario_id)
        except FileNotFoundError as exc:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "SIM_RESULT_NOT_FOUND",
                        "message": f"No precomputed result for {scenario_id}",
                        "fallback": "请保留上一次成功的仿真结果并标注数据较旧",
                    }
                },
            )
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": {"code": "INVALID_SCENARIO_ID", "message": str(exc), "fallback": "请选择已预计算场景"}})

    return router
