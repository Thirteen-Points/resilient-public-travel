# ResilientRoute frontend

React, TypeScript, Vite and Leaflet/MapLibre journey planner for the modelled
Tai Wai–Admiralty corridor. See the root README for backend startup.

```powershell
cd frontend
npm ci
npm run dev
npm run typecheck
npm run test
npm run build
npm run build:admin
```

Use Node 20.19+ or 22.12+. The default API is `http://127.0.0.1:8000`; override
its public URL with `VITE_API_BASE_URL` in `.env.local` and restart Vite. Secrets
and reviewer credentials must never be embedded in frontend environment variables.

## Passenger and administrator flows

The public application retains Journey, route results/details, Report, Agent,
Updates and How it works, including the preference preview/editor. Public
Compare, Simulation and Review pages have been removed. The simulation APIs and
shared review components remain available to their backend/administrator clients.

Review takes place in the separate `/admin/` console using a server-side session.
It supports evidence extraction/merge, event creation/editing, approval,
rejection and withdrawal. Previous approved facts remain active while a revised
event awaits reapproval. A confirmed write stays successful when its following
queue refresh fails. See [administrator setup](../deploy/ADMIN.md).

## Refresh and data modes

API mode queries the deterministic engine and last approved event facts. Public
polling remains every three seconds; collector status is read every fifteen
seconds. Healthy polling has no persistent popup. Refresh failure, offline state
or stale routes display an inline notice with retry while retaining the previous
results. Recovery clears that notice. Actual route updates use a 4.2-second
notification. Latest-request cancellation and stale-response guards remain active.

`?data=seed` explicitly selects fixed simulated fixture routes for the seed OD;
departure input does not recalculate those routes, and the Agent uses local
templates. Switching mode reloads the application.

## Map geometry and appearance

OpenFreeMap Positron is the default vector basemap. Optional `VITE_CARTO_TILE_URL`
overrides it; failure falls back to OpenStreetMap tiles, then retains the route
overlays without a basemap. MapLibre 6's worker is bundled through Vite's
`?worker&url` pipeline, following the [MapLibre setup documentation](https://maplibre.org/maplibre-gl-js/docs/#installation).
The vector layer waits until the viewport is visible and fitted, including
mobile pages that initially show a list.

One offline geometry resolver serves network lines, route legs and event
overlays. It preserves verified bends, direction/variants and separate source
parts. There are no runtime geometry requests. Unverified sections are dotted
and labelled schematic; missing coordinates are never invented. Ranking, times,
fares, walking distances and accessibility judgments stay unchanged. See
[geometry sources, offsets and limitations](src/map/GEOMETRY_SOURCES.md).

Network lines are subdued at 2 px; candidates A/B/C use blue/purple/teal, at
4 px or 6 px when selected. Catchment circles appear during point selection.
The legend starts collapsed; fit and zoom controls remain keyboard accessible.

## Design and verification

Shared tokens follow the [original design specification](../design/ResilientRoute-Prototype-Spec.md).
Body text is 16/24, supporting text 14/20, buttons 48 px, inputs 56 px and main
interactive targets at least 44 px. Large text scales route metrics; high
contrast preserves inverse badge text. Reduced motion suppresses animation.
Below 1024 px, navigation folds and journey/result/detail views have map/list
tabs. Long passenger pages use document flow; Updates no longer clips on phones.

The geometry suite covers undersea rail, omitted intermediate stops, reverse
directions, bus variants, multipart boundaries, pedestrian matching, missing
coordinates and identical event/route paths. `tests/browser/p4.e2e.cjs` exercises
real backend requests, preference/request cancellation, recovery, five viewport
widths and three administrator approvals with painted map/cards within five
seconds. The older M2/P3 browser entry points delegate to that shared regression.

Historical M1/M2/P3 integration documents describe their original milestones;
this README describes the current public application.
