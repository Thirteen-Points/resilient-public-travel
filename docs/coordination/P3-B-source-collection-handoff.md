# P3 B source collection handoff to C and A

The shared `backend/app/main.py` now registers the source router and collector
with the durable Signal/Event database. Local shared-app tests cover status,
reviewer protection, and disabled offline polling. The integration uses:

```python
from .api.sources import router as sources_router
from .services.ingest.collection import SourceCollectionService

# During app construction, using the same durable db_path as SignalStore:
collector = SourceCollectionService(db_path, signal_store=store, event_store=event_store)
application.include_router(sources_router)

# In lifespan after SignalStore/EventStore initialize:
application.state.source_collection = collector
collector.start()
try:
    yield
finally:
    collector.stop()
```

The existing lifespan keeps its other state assignments and cleanup. The collector
defaults off. It starts only with `SOURCE_COLLECTION_ENABLED=true` and
`OFFLINE_MODE=false`. Render currently sets `OFFLINE_MODE=true`; enabling live
polling requires a deliberate deployment setting change by C.

`GET /api/sources/status` is public, read-only and contains one entry per HKO/MTR
source: `source`, `enabled`, `last_attempt`, `last_success`, `source_time`,
`source_time_note`, `last_error`, `stale`, `new_signals`, `result`, `provenance`.
`result=no_new_signals` means a successful fetch found no new evidence. HKO
source time comes from warning issue/update time; MTR uses `curr_time` when
present. Missing source time is `null`, never the collection clock.

`GET /api/sources/review-queue` requires the existing reviewer token. It shows
collected Signal processing state and any unreviewed draft. `pending_review`
requires a human to create the first complete Event card; no route changes from
this queue. `simulated` test replay must instantiate the service with
`simulated=True`, which also relabels stored Signals.

A should label HKO as a real official weather-warning source and MTR as an
official-data-derived *suspected* delay, not an official delay announcement.
