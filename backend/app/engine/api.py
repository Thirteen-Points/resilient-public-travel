"""Optional FastAPI adapter owned by C-Route; no application-global edits."""
import asyncio
from datetime import datetime
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from ..graph.adapter import DataUnavailable
from ..graph.build import thaw


def error(status, code, message):
    return JSONResponse(status_code=status, content={'error': {
        'code': code, 'message': message, 'fallback': 'Keep the last successful data and mark it as stale; retry if no cached data is available.'}})


def create_router(engine):
    router = APIRouter(prefix='/api')
    route_slot = asyncio.Semaphore(1)

    @router.get('/graph/network')
    def network():
        source = engine.snapshots.current.network.source
        # Full service-day departure tables belong to server routing. The
        # public map needs stop geometry and ETA identifiers, not calendars.
        return thaw({**source, 'lines': tuple({key: value for key, value in line.items()
                    if not key.startswith('gtfs_')} for line in source['lines'])})

    @router.get('/graph/snapshot')
    def snapshot(at: datetime | None = None):
        if at is not None and at.tzinfo is None:
            return error(422, 'INVALID_SNAPSHOT_TIME', 'at must include a timezone')
        return engine.snapshots.current.describe(at)

    @router.get('/fares/status')
    def fare_status():
        if engine.fare_store is None:
            return error(503,'DATA_UNAVAILABLE','No fare database configured')
        return engine.fare_store.status()

    @router.get('/fares/lookup')
    def fare_lookup(service_id: str, origin: str, destination: str, at: datetime,
                    direction: str = 'all', day_type: str = 'all', deck: str = 'all',
                    passenger: str = 'adult', payment: str = 'standard'):
        if engine.fare_store is None:
            return error(503,'DATA_UNAVAILABLE','No fare database configured')
        if at.tzinfo is None:
            return error(422,'INVALID_FARE_TIME','at must include a timezone')
        value = engine.fare_store.lookup(service_id,origin,destination,at,direction=direction,
                                        day_type=day_type,deck=deck,passenger=passenger,payment=payment)
        return value if value is not None else error(404,'FARE_UNAVAILABLE','No applicable fare for this journey')

    @router.post('/routes/query')
    async def query(request: Request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError('Query body must be an object')
            allowed = {'origin', 'destination', 'depart_at', 'profile', 'event_ids', 'modes', 'required_modes'}
            if set(payload) - allowed:
                raise ValueError('Unknown query fields')
            for key in ('origin', 'destination', 'depart_at'):
                if not isinstance(payload.get(key), str) or not payload[key]:
                    raise ValueError(f'{key} must be a nonempty string')
            if 'profile' in payload and not isinstance(payload['profile'], dict):
                raise ValueError('profile must be an object')
            if 'event_ids' in payload and (not isinstance(payload['event_ids'], list) or
                                          any(not isinstance(x, str) for x in payload['event_ids'])):
                raise ValueError('event_ids must be a string array')
            for key in ('modes', 'required_modes'):
                if key in payload and (not isinstance(payload[key], list) or not payload[key] or
                                       any(not isinstance(x, str) for x in payload[key])):
                    raise ValueError(f'{key} must be a nonempty string array')
            # One query_details call supplies both the body and the snapshot used
            # for this computation; the global current snapshot is never re-read.
            async with route_slot:
                details = await asyncio.to_thread(engine.query_details, **payload)
            return JSONResponse(content=details['routes'],
                                headers={'X-Route-Snapshot': details['graph_snapshot']})
        except DataUnavailable as exc:
            return error(503, 'DATA_UNAVAILABLE', str(exc))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return error(400, 'INVALID_ROUTE_QUERY', str(exc))
        except Exception:
            return error(500, 'ROUTE_ENGINE_ERROR', 'The route service is temporarily unavailable.')

    return router


def create_app(engine):
    """Standalone integration target; main app may include only create_router()."""
    app = FastAPI()
    app.include_router(create_router(engine))

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, 'HTTP_ERROR', str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(422, 'INVALID_REQUEST', 'Invalid request format.')

    @app.exception_handler(Exception)
    async def server_error(request, exc):
        return error(500, 'ROUTE_ENGINE_ERROR', 'The route service is temporarily unavailable.')

    return app
