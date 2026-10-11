"""A large graph calculation must not block public status/arrival requests."""
import asyncio
import threading
import httpx
from fastapi import FastAPI
from backend.app.engine.api import create_router


def test_route_calculation_leaves_the_api_event_loop_responsive():
    started, release = threading.Event(), threading.Event()

    class BlockingEngine:
        def query_details(self, **payload):
            started.set()
            release.wait(3)
            return {'routes': [], 'graph_snapshot': 'responsiveness-test'}

    app = FastAPI()
    app.include_router(create_router(BlockingEngine()))

    @app.get('/status')
    async def status():
        return {'ok': True}

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            query = asyncio.create_task(client.post('/api/routes/query', json={
                'origin': 'TAW', 'destination': 'ADM', 'depart_at': '2026-10-12T08:20:00+08:00'}))
            try:
                assert await asyncio.to_thread(started.wait, 1)
                response = await asyncio.wait_for(client.get('/status'), 1)
                assert response.json() == {'ok': True}
                assert not query.done()
            finally:
                release.set()
                assert (await query).status_code == 200

    asyncio.run(check())
