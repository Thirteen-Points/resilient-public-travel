# ResilientRoute frontend (Role A · M0)

React + TypeScript + Vite + Leaflet prototype for the Tai Wai → Admiralty seed scenario.

```powershell
cd frontend
npm ci
npm run dev
npm run typecheck
npm run test
npm run build
```

Open the local URL printed by Vite. `src/api/seedDataSource.ts` implements the `TransitDataSource` interface and is the only module importing the four versioned JSON seeds. Components use the adapter; a future HTTP implementation can replace it. The snapshot is fixed at 22 Sep 2026 08:20 HKT; this is **not** a live journey planner. Other station pairs intentionally show an empty state.

The map shows the six corridor stations, geodesic 800 m access circles, available seed network lines, routes A/B/C and only `published` events that are effective at the snapshot time. An unresolved seed bus stop is omitted rather than assigned invented coordinates. Both the UI and map identify the data as schematic/estimated/simulated.

Basemap preference: an explicitly configured `VITE_CARTO_TILE_URL` (authorized CARTO tile endpoint) → key-free OpenFreeMap → OpenStreetMap → schematic background. Without a CARTO URL, OpenFreeMap is first. The public CARTO raster endpoint currently produces an API-key watermark in this environment, so the app does not use it by default. Basemap failure never removes the network overlays. OpenStreetMap tiles are requested only for the visible viewport and retain their attribution.

The full-bleed map workspace follows the five Figma P02 input states and the P03 results overlay. Search has keyboard navigation; map selection snaps to accessible modelled MTR stations within the fixture radius; free text recognizes only the seeded Tai Wai → Admiralty journey and is clearly labelled as deterministic, not AI. Figma's incorrect example interchange and invented fare/time are corrected from the seed legs. Results, update status, source/provenance and route details are explicit states.

M0 boundaries: no backend query, real-time event stream, review workflow, profile-specific ranking, live geocoding, microphone, AI parser or simulation dashboard yet. Preset sorting only reorders fixed seed candidates; changing departure does not recalculate them.
