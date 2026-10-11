# ResilientRoute frontend · M2

React + TypeScript + Vite + Leaflet journey planner for the modelled Tai Wai → Admiralty corridor. See the root README for backend startup.

```powershell
cd frontend
npm ci
npm run dev
npm run typecheck
npm run test
npm run build
```

Use Node 20.19+ or 22.12+. The default API is `http://127.0.0.1:8000`; override its public URL with `VITE_API_BASE_URL` in `.env.local` and restart Vite. Never set `VITE_REVIEW_TOKEN` or any service secret in frontend environment variables.

## Data modes

API mode is the default. Queries use the deterministic engine and last approved event facts. It is a modelled service, not a live timetable. `?data=seed` explicitly switches to fixed, simulated fixture routes for the seed OD; changing departure does not recalculate those routes, and seed review actions are local. Switching mode reloads the page and discards unsaved state.

Journey endpoints can be East Rail stations or map points whose pedestrian route to a modelled East Rail station is at most 800 m. The map circles are straight-line search bounds; map clicks use Valhalla's OpenStreetMap pedestrian routing demo API and are rejected when distance cannot be verified. Access walks are displayed separately from station-to-station route totals. Station points are not surveyed entrances or step-free path guarantees. The external routing demo API is rate-limited; station-name selection remains available if it is unavailable.

API errors retain loaded data with a stale notice. An initial failure offers retry or an explicit fixed-seed switch. Maps retain their schematic overlays when the external basemap fails. Basemap preference is configured CARTO → OpenFreeMap → OSM → schematic; the current initial raster option is OSM. Map attribution remains visible. Reloading while completely offline is not supported as an installed PWA.

## Public and reviewer views

Public users can query routes, see effective approved events, and submit unverified reports without a reviewer credential. Protected reads are independent of the public snapshot: reviewer failures do not hide approved incidents from the map.

For a controlled local demo, enter a temporary server `REVIEW_API_TOKEN` in Review. It stays in memory until disconnect/reload. The SSE client uses streaming fetch with `X-Review-Token`, an abortable lifecycle and durable reconnect cursor. It never sends a token in a URL. Polling every three seconds continues during stream loss. Public deployment requires an identity/session or trusted proxy design.

The reviewer inbox supports extraction, first-card creation with explicit numeric facts and evidence merge. Review supports edit, publish, reject and withdrawal. A saved edit of a published card awaits reapproval; previous approved facts stay effective until replacement or withdrawal. Current time windows and the route departure instant control effects. The server owns confidence and audit history. A successful write remains successful when its following refresh fails; ambiguous writes require refreshing before retrying. Rejection reasons remain local notes.

## Data contract

- `accessible=null` means unknown. General station picking remains possible with a verification notice; verified-access-only picking excludes unknown stations.
- Route legs accept fixture `travel_s` or engine `in_vehicle_s`; missing values display as unavailable. No numeric duration is fabricated.
- Provenance is preserved, including simulated engine policy outputs. Approximate geometry uses supplied nodes only.
- Unknown source freshness is not inferred from response-generation time.
- The visible Agent panel uses local template replies. Backend AI and simulation endpoints are not evidence of corresponding frontend features.

See [M2-INTEGRATION.md](M2-INTEGRATION.md) for current integration behavior. M1 documents preserve historical implementation records.
