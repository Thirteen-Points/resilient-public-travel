# Offline map alignments

`geometry.snapshot.json` is a frontend display sidecar. It does not extend the
frozen Network/Route API, change graph nodes or stop order, recalculate journey
times/fares/walking distances, or certify accessibility. No geometry API is
called by the application at runtime.

The snapshot contains GeoJSON `[longitude, latitude]` coordinates. `geometry.ts`
converts them to Leaflet `[latitude, longitude]` and provides one resolver for
network lines, route legs and event overlays. Separate source paths are separate
parts: a missing station-area alignment is never filled by a curve or a straight
join. Known stops omitted from the simplified routing graph retain their actual
intervening rail/road geometry.

The bundled capture contains 63 directional segments (40 rail, 9 bus and 14
walking), 19 attributed source records and 8,111 coordinate vertices. Three
directional segments intentionally remain schematic: both ferry directions
and the modeled 985B return direction.

## Railway: official Lands Department alignment

- Dataset: [1:50 000 Topographic Map of Hong Kong](https://portal.csdi.gov.hk/csdi-webpage/dataset/landsd_rcd_1637221775627_85634).
- [TSPTLINE layer and schema](https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637221775627_85634/MapServer/4?f=json).
- Query: `CLASS='RAI' AND TYPE='MTR' AND PHYSICALSTATUS=3`, `outSR=4326`, bbox `114.15,22.27,114.21,22.38`.
- The layer is a generalized, official geographic alignment. It contains
  underground and cross-harbour rail features; it is not a turn-by-turn map.
  Station areas can be omitted or represented by map symbols.
- The source has no MTR service identifier. The explicit `GRAPHICID` chains in
  `scripts/precompute_map_geometry.py` associate the existing ERL, TML, KTL,
  TWL and ISL lines with their geographic features. The chain is not inferred
  afresh by runtime shortest-path routing. ERL uses the cross-harbour features
  `649719` (Hung Hom–Exhibition Centre) and `649713` (Exhibition Centre–Admiralty).
- Projected anchors lie on existing source geometry; the original modeled
  station coordinate is not appended to force the map line through a centroid.
  `endpointOffsetM` records this display offset, including generalized station
  areas. The graph's station coordinate and catchment circle remain unchanged.
  Current station-center offsets reach 248.2 m in the generalized source.

## Bus: official Transport Department directional geometry

- Dataset: [Bus Route](https://portal.csdi.gov.hk/csdi-webpage/dataset/td_rcd_1638844988873_41214).
- [FB_ROUTE_LINE layer and schema](https://portal.csdi.gov.hk/server/rest/services/common/td_rcd_1638844988873_41214/MapServer/0?f=json).
- This is a genuine road polyline layer, separate from the TD route/stop point
  GeoJSON and GTFS feeds. TD's headway GTFS has no `shapes.txt` here.

| Modeled line | Verified source variant | Display direction |
| --- | --- | --- |
| BUS_182 | ROUTE_ID 1051, ROUTE_SEQ 1 / 2 | Tai Wai→Admiralty / return |
| BUS_81C | ROUTE_ID 1336, ROUTE_SEQ 1 / 2 | Tai Wai→Tsim Sha Tsui / return |
| BUS_982X | ROUTE_ID 8104, ROUTE_SEQ 1 | Morning Tai Wai→Admiralty slice |
| BUS_982X | ROUTE_ID 8644, ROUTE_SEQ 1 | Evening Admiralty→Tai Wai slice |
| BUS_985B | ROUTE_ID 8705, ROUTE_SEQ 1 | Tin Sum→Admiralty slice |

The variant and direction are retained. The reverse of the 985B source is not
claimed as an official return service; that missing direction remains schematic.
The source full route is clipped to the existing model's stops without changing
their abstract identity. Some modeled bus points are approximate; a projected
alignment endpoint is not a verified boarding bay.
Current modeled bus-point offsets reach 283.4 m at Hung Hom; the geometry does
not move that abstract interchange point or claim its exact boarding location.

## Walking: official 3D Pedestrian Network

- Dataset: [3D Pedestrian Network](https://portal.csdi.gov.hk/csdi-webpage/dataset/landsd_rcd_1637222018065_52265).
- [PedestrianRoute layer and schema](https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637222018065_52265/MapServer/0?f=json).
- The preprocessing script downloads small bounds around the seven existing
  transfer links, pages all results, and builds a display path over actual
  source features. Every used `PedestrianRouteID` and every paged capture URL/
  SHA-256 is recorded. Z coordinates participate in junction identity, so
  bridges and underground footways cannot connect merely because they cross
  on the flat map. Disabled and paid-area links are excluded; source direction
  restrictions are respected and reverse paths are computed independently.
- Endpoints are projections or existing source endpoints near the modeled
  transfer points. No synthetic connector is added between a station center
  and an exit. Exact exit selection, lift operation and continuous step-free
  access remain unverified; existing route accessibility and warnings are
  preserved. These static paths illustrate a transfer's geography and do not
  introduce another passenger route planner.
- Matching favors nearby source anchors over a deceptively short intermediate
  edge. A captured path must span at least half the modeled transfer's endpoint
  separation; a nearby fragment failing that check remains unavailable. Final
  transfer paths were inspected against the model points. Hung Hom uses the
  continuous 302 m source footway, rather than an unrelated 11 m fragment.

| Transfer (forward model order) | Source endpoint offsets, metres |
| --- | --- |
| ETS→TST | 22.4 / 13.4 |
| BS_TAW→TAW | 27.2 / 20.7 |
| BS_TIN_SUM→TAW | 25.4 / 39.0 |
| BS_HUH_TUNNEL→HUH | 34.3 / 25.7 |
| BS_ADM_E→ADM | 21.2 / 4.0 |
| PIER_TST→TST | 8.7 / 13.4 |
| PIER_CEN→CEN | 93.0 / 18.4 |

The Tai Wai source edge is about 44 m long, appropriate for the model's short
transfer despite its offset. The Central pier endpoint remains 93 m from the
modeled pier point: that final approach is unverified and no connector is
invented. All seven paths have geographic endpoint spans of 85–109% of their
modeled spans; offsets and absent exit/boarding precision remain explicit.

## Unverified geometry and fallback

- [TD ferry GeoJSON](https://static.data.gov.hk/td/routes-fares-geojson/JSON_FERRY.json)
  contains pier points only. Tsim Sha Tsui–Central is route 7030, with stop IDs
  101119 / 101339; no navigational track is supplied.
- An OSM official API snapshot of the harbour was inspected. The matching
  [way 224759247](https://www.openstreetmap.org/way/224759247) carries
  `historic=yes`; it is deliberately excluded from current-route geometry.
  The ferry therefore remains explicitly schematic rather than presenting a
  historical track as verified. No OSM-derived coordinates are shipped.
- Unknown geometry with two usable modeled endpoints is shown as a labeled
  schematic connection. Missing or non-finite node coordinates remain missing
  and are never fabricated. If a larger leg combines verified and schematic
  sections, `partQualities` identifies each part and overall quality is `mixed`.
- 481B is excluded from the current runnable Network. The sidecar does not
  restore that minibus route or create its missing terminus.

## Attribution and reproduction

All shipped coordinates derive from Hong Kong SAR Government CSDI datasets.
The [CSDI Terms and Conditions](https://static.csdi.gov.hk/csdi-webpage/doc/TNC)
permit free browsing, downloading, distribution and reproduction for commercial
and non-commercial purposes, with clear identification of the Government and
CSDI as the data source and acknowledgment of the Government and relevant
organizations' intellectual-property ownership. Show the map attribution
`Government of the Hong Kong SAR · CSDI Portal · Lands Department / Transport Department`
and retain source/terms links in Sources. These data are supplied as-is.

Generate with Python standard library only:

```powershell
python scripts/precompute_map_geometry.py
python scripts/precompute_map_geometry.py --check
```

Captures live in the ignored `.cache/map-geometry/` directory. Cached captures
make regeneration deterministic; `--refresh` explicitly fetches new source
data. Review changed source chains, multipart continuity and variant identities
before replacing the bundled snapshot. Do not rebuild the snapshot automatically
on every frontend build or require network access for tests.
