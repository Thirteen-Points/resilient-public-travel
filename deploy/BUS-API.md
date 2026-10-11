# Corridor buses

The public planner imports Transport Department GTFS bus patterns that have at
least one stop within 800 m straight-line distance of Tai Wai, Kowloon Tong,
Mong Kok East, Hung Hom, Exhibition Centre or Admiralty. The current catalogue
contains 1,129 direction/variant records (544 operator/route combinations) for
KMB, LWB and Citybus. 507 patterns connect at least two corridor catchments and
have complete boarding/alighting fare pairs, so they participate in routing.
Single-catchment feeders remain searchable for current arrivals. This does not
claim a full Hong Kong road or walking network.

## Sources and updating

The [Mobility Database reference](https://mobilitydatabase.org/feeds/gtfs/mdb-1924)
points to the [official TD feed](https://static.data.gov.hk/td/pt-headway-en/gtfs.zip).
Download that archive and rebuild the committed catalogue:

```powershell
Invoke-WebRequest 'https://static.data.gov.hk/td/pt-headway-en/gtfs.zip' -OutFile '.cache/hk-gtfs.zip'
python scripts/import_corridor_buses.py --archive .cache/hk-gtfs.zip
```

The catalogue records its archive checksum, retrieval time, stop IDs, ordered
stops, pickup/drop-off flags, directional adult fare pairs, weekday calendars,
exceptions, exact departures and frequency bands. The importer verifies that
trips grouped into a direction have identical ordered stops. A changed pattern
fails import instead of attaching another pattern's timetable.

Intermediate stop times are largely absent from this source. Routing estimates
them in proportion to distance along the full ordered stop sequence, using its
timed endpoints. Vehicle capacity (137), straight-line walking links, journey
uncertainty and accessibility remain modelling assumptions. Unknown bus and
walking accessibility excludes those edges for wheelchair profiles. Concession
and interchange discounts are not inferred. Bus fares come from the compiled
GTFS stop-pair table; the existing persistent MTR/ferry fare store is retained.

## Runtime

`BUS_NETWORK_ENABLED=true` enables the imported graph locally or on a server.
It defaults to enabled on Render (`RENDER_GIT_COMMIT` is present) and disabled
in the frozen offline demo/test package. Explicit `false` overrides that default.
Static GTFS never requires a runtime download. Other deployment hosts should
set this flag explicitly.

- `GET /api/buses/status`: source/coverage and server/browser ETA availability.
- `GET /api/buses/services?station=TAW&q=182&offset=0&limit=30`: paginated
  official services and nearby stops; all six corridor station codes work.
- `GET /api/buses/eta?service_id=TD_1051_1&td_stop_id=859`: validated service
  and stop lookup, using only fixed official hostnames.

Official arrivals use [KMB/LWB](https://data.etabus.gov.hk/v1/transport/kmb)
and [Citybus](https://data.gov.hk/en-data/dataset/ctb-eta-transport-realtime-eta).
TD IDs are not assumed to equal operator stop IDs. Ordered termini, target
coordinates, route, direction, service variant and ETA stop sequence are checked.
Unverified matches are unavailable rather than guessed. Operator APIs do not
expose every special GTFS variant; static routing still uses its official calendar.

When `OFFLINE_MODE=true`, the server performs no ETA network requests. API-mode
pages obtain a validated public lookup descriptor and request the same operator
APIs from the browser (both support CORS). Seed/offline UI mounts no arrival
widgets and makes no official bus calls. Arrival responses cache for 60 seconds,
metadata for 24 hours; only the selected route/service is polled each minute
while the tab is visible. Missing, failed or older-than-three-minute observations
are shown explicitly and never publish a closure. Current ETA observations do
not replace a future selected-date timetable estimate. Reviewer-approved bus
events use the existing graph publication/withdrawal path.

## Verification

```text
python -m pytest --import-mode=importlib backend/tests/test_bus_api.py -q
cd frontend
npm test
npm run build
npm run build:admin
```

Verify API mode on the public site: Plan journey → Bus · 公交 → corridor station.
The searchable bus catalogue includes feeders; a selected journey card also
shows arrivals for its actual bus boarding stop. Use morning/evening service
times to check daytime route results, and an operating night route for late-night
live ETA verification.
