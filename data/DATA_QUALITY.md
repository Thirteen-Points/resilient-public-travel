# Seed data quality record

Reviewed: 2026-09-23. The four seed files are offline demonstration inputs,
not a live timetable. Quality gates are reproducible with:

```text
python scripts/validate_data.py
python -m pytest -q tests/test_data_integrity.py
```

## Gate results

| Gate | Result | Notes |
|---|---|---|
| JSON parsing | pass | four seed roots parse as JSON objects |
| provenance enum | pass | only `real`, `real-derived`, `simulated` |
| node/line uniqueness | pass | duplicate IDs rejected; `meta.counts.lines=10` matches the 10 line records |
| route/simulation references | pass | route IDs and event reference resolve |
| excluded demo reference | warning | GMB_481B removed from runnable network lines after manual confirmation `BS_TW` is invalid; any historical simulated route-card reference is warn-only and excluded from recommendations |
| route/leg evidence | pass | every route and every leg has source IDs, fields, and a status; unavailable rows remain unverified |
| 982X/985B headway | corrected conservatively | stale `1800 s` values removed; exact departure-derived headway remains unverified/null |
| operational truth | not asserted | live service, fares, capacities, accessibility and incident text need human/source refresh |

## Six-core coverage boundary

The current corridor scope is six core MTR nodes and 30 directed OD pairs:
`TAW`, `KOT`, `MKK`, `HUH`, `EXC`, `ADM`. The seed contains all six station
nodes and the ERL topology, but it does not yet contain 30 generated route
lists; route generation remains C-Route work.

| Core point | Confirmed access data in this seed | Missing / unverified |
|---|---|---|
| TAW | 8 iGeoCom MTA access points + RSN station reference point; prior bus walk links remain `real-derived` | path continuity and step-free access; bus stop/node mapping |
| KOT | 11 iGeoCom MTA access points + RSN station reference point | path continuity and step-free access; no graph access links asserted |
| MKK | 4 iGeoCom MTA access points + RSN station reference point | path continuity and step-free access; no graph access links asserted |
| HUH | 14 iGeoCom MTA access points + RSN station reference point; prior bus walk link remains `real-derived` | path continuity and step-free access; bus stop/node mapping |
| EXC | 6 iGeoCom MTA access points + RSN station reference point | path continuity and step-free access; no graph access links asserted |
| ADM | 7 iGeoCom MTA access points + RSN station reference point; prior bus walk link remains `real-derived` | path continuity and step-free access; bus stop/node mapping |

Bus evidence is partial and conservative: official TD ROUTE_BUS,
RSTOP_BUS and STOP_BUS rows for 182, 982X, 985B and 81C were checked, but the
stop IDs do not safely map all existing abstract nodes. Lines remain
`real-derived`; no field is promoted to `real`. Official MTR street maps show
station-area bus/minibus access features at MKK, KOT and EXC, but no verified
machine-readable stop coordinates/path mapping was captured, so no graph edge
was added. `BS_TW` is manually confirmed invalid; GMB_481B is removed from
runnable network data.

Station access coordinates are now sourced from 50 exact LandsD iGeoCom MTA
records and six RSN station reference points; see
`data/access/station_entrances.json` and provenance S23. Network station
coordinates use the RSN point coordinates. Access records do not establish
walk connectivity or step-free access; no walk links were added. TD GTFS
stops.txt has only ordinary stop records in this snapshot.

The warning is intentional: historical simulated references to the excluded
481B line remain auditable but must not be treated as operational facts.
Consumers should exclude them from production recommendations.

The `800 m` value is only the origin/destination access-point search radius. It
does not cap cumulative walking across a complete multi-leg route; therefore
`r_seed_007`'s `total.walk_m=900` is not rejected by this rule. Minibus legs
remain excluded from wheelchair recommendations unless separate official
accessibility evidence exists.

## M1 data-layer verification update (2026-09-25)

Scope: the `data/` documentation layer only (six core stations, the default
demo interruption segment HUH–EXC, and alternative-route data). The frozen
`contracts/seed/` files were NOT modified; residual divergences are listed in
`data/PROVENANCE.md` § "M1 data verification pass".

What changed, all evidence-backed:

| Area | Change | Evidence |
|---|---|---|
| Station coordinates | All 16 modelled stations now carry official iGeoCom RSN point coordinates (six core re-verified byte-identical; ten non-core newly captured and transformed via the official Geodetic API); the false "coordinates from MTR open data" claim removed | S23/S30 |
| Station accessibility | `accessible: true` now backed by per-station rows in the MTR barrier-free CSV (every modelled station has paid-area lift AJ8=Y plus step-free exits; AJ codes cited in notes). Per-entrance mapping and live lift outages remain unmodelled; abstract access points set `accessible: null` instead of unsupported `true` | S25 |
| Line topology | EAL stop order and all 16 stations' line membership verified; KTL/TML collapsed-stop notes added | S25 |
| ERL headway | Official band verified (AM peak 2.7–5.5 min etc.); single values kept as documented in-band modelling choices; ERL record provenance downgraded to `real-derived` (capacity/seg-times still estimates) | S28 |
| Runnable lines | GMB_481B removed from `data/network/lines.json` (aligned with seed `missing_nodes_note`); route existence itself verified in TD ROUTE_GMB row 2003214 | S31 |
| Bus headways | 982X/985B `weekday_peak` set to `null` + `headway_status: unverified_exact_departures` (aligned with seed); 182/81C/170 headways kept as explicitly-estimated values (TD GTFS variable bands) | S20/S31 |
| Bus fares | 982X full fare 16.0→20.8, 985B 19.5→20.8, 81C 10.2 added; section fares (182 $16, 982X $6) remain flagged unverified | S31 |
| Bus routes log | Evidence basis switched from the unverifiable KMB API (S11) to TD XML; 985B/985A/985 destinations corrected to 灣仔(軒尼詩道), 83X to 觀塘碼頭, 182X direction to 中環→愉翠苑; 182P/80M absent from master data; 88K confirmed NOT cancelled (excluded as non-corridor feeder); all ten exclusions re-verified against stop sequences | S31 |
| Ferry | Timetable bands, adult fares ($4.0/$5.6 lower, $5.0/$6.5 upper), wheelchair limit (4/sailing) verified; capacity and typhoon threshold stay unverified | S27 |
| Calendar | Three in-window holidays verified against GovHK; ERL/bus operating-hours provenance downgraded to `real-derived` (first/last-train page under maintenance; KMB API unverifiable) | S26 |

### 982X schedule evidence & capacity-doc closure (2026-09-25, second pass)

- `bus_routes.json` 982X now carries `schedule_evidence`: two weekday
  direction panels from **user-provided timetable screenshots** (to Fleming
  Road 06:55–08:10, gaps 20/15/9/12/13/6 min; to Yu Chui Court 17:47–18:27,
  uniform 8 min, board code ST871 as displayed). The images show no capture
  date and no verifiable official origin, so the times are recorded verbatim
  and are **not** operator-verified; no provenance upgrade was made.
- `lines.json` BUS_982X: `headway_s` stays all-null; `headway_status` is now
  `no_single_headway_applicable_unverified_official` — a single headway value
  cannot express the direction/time-varied gaps, and consumers should read
  the per-trip schedule instead. Nothing beyond the two weekday panels is
  claimed (no off-peak / Sat / Sun / PH evidence exists).
- `capacity_method.md`: the old fixed-30-min-headway example (2 veh/h → 233
  pax/hour) is **retired** as an outdated assumption and must not be quoted
  as an M1 demo conclusion. The directly observed facts are the trip counts
  (7 departures in the 06:55–08:10 AM span to Wan Chai; 6 in the 17:47–18:27
  PM span to Yu Chui Court). Any frequency follows the document's own
  `3600 / average-headway` formula — AM 75/6 = 12.5 min → 4.8 veh/h,
  PM 8 min → 7.5 veh/h — giving derived illustrations of ≈559 and ≈873
  pax/hour with explicit basis/direction/span/assumptions. These are not
  all-day capacities: each rests on a single narrow span (the PM span alone
  is shorter than an hour) computed from user-provided, unverified
  screenshots. The GMB_481B worked example and summary
  row are prominently marked **historical / hypothetical — not in the
  runnable network** and are excluded from current demo capacity conclusions.

For the HUH–EXC interruption demo specifically: the segment closure itself is
contract/event data (`HUH`–`EXC` and `EXC`–`ADM` affected segments, simulated
and clearly labelled); the supporting alternative data is now verified at
line/topology/fare/accessibility level (TML divert via DIH/HOM, KTL/TWL
combos, ERL fares incl. HUH-EXC 10.6 Octopus), while the EXC-island walk
(WAC↔EXC ~700 m) and all walk-link continuity remain unverified and are
labelled as such.

Gates unchanged (they validate `contracts/seed/`, not `data/`):

```text
python scripts/validate_data.py
python -m pytest -q tests/test_data_integrity.py
```

## C runtime data mapping (2026-09-25, analysis only — no engine changes)

**Key caveat: data-layer verification does NOT mean runtime loading
（data/ 已核验 ≠ C 运行时已加载）。** C's runtime currently loads
`contracts/seed/network.seed.json` (+ optional event seed) via
`SeedDataAdapter` (`backend/app/graph/adapter.py`), with fares/baseline/
profiles from the simulated-only fixture
`backend/app/engine/fixtures/seed_policy.json`. On load, `SeedDataAdapter`
**forcibly relabels every node/line/walk-link record `simulated`**
(`mark_simulated`) — so even `real-derived` seed values are treated as demo
data at runtime. No backend module reads anything under `data/`;
`data/network/*.json` and `data/access/*.json` are the documentation /
evidence layer.

| Field / concern | Where it lives in data/ | Where C runtime reads it today | Mapping status |
|---|---|---|---|
| Graph nodes (stations / bus stops / piers) | `network/stations.json` (three arrays) | `network.seed.json` `nodes` — one flat array | Shape difference: C must merge the three arrays into `nodes` before any `JsonDataAdapter`-style load; ids/kind/lat/lng/name fields otherwise line up |
| Node coordinates | `stations.json` — official iGeoCom RSN points, all 16 stations | seed: six core = same RSN points; ten non-core = old rounded estimates | Divergence (data newer, recorded in PROVENANCE S30); seed untouched by design |
| Station accessibility | `stations.json` `accessible: true` + per-station AJ evidence notes | seed holds `accessible: null` + `accessibility_status: "unknown"`; `find_access_points` surfaces `accessible is True` → the six core currently report **False** at runtime, bus-stop nodes report True | Semantic divergence; C must decide which semantics ships (station-level CSV evidence vs conservative null) |
| Line topology / seg times / headways / capacity | `network/lines.json` | seed `lines` | Aligned values; `validate_network` accepts the all-null 982X/985B `headway_s` dicts (key present, values None) |
| Bus fares | `lines.json` `fare_hkd` (982X 20.8, 985B 20.8, 81C 10.2 — TD-verified) | seed flow charges `max(line.fare_hkd)` as simulated: **982X still bills 16, 985B still bills 19.5** (stale); MTR bills policy baseline 12.5 | Divergence with runtime effect; reconcile via policy `fares` overrides (or a freeze-change seed update) |
| `headway_status` vocabulary | data: `no_single_headway_applicable_unverified_official` (982X) | seed: `unverified_exact_departures`; runtime does not read the field | Informational divergence (PROVENANCE divergence item 4) |
| 982X per-trip weekday departures | `network/bus_routes.json` 982X `schedule_evidence` (user-provided screenshots, unverified) | runtime has no per-trip field; BUS_982X headway is all-null → no headway-driven service for it today | C decision: implement per-trip schedule support, or agree a documented representative headway |
| Walk links | `network/walk_links.json` | seed `walk_links` (same 7 links, same times) | Aligned; data adds the evidence_note on station-level vs link-level accessibility |
| Bus route verification log | `network/bus_routes.json` | not loaded | Documentation only (incl. 982X `schedule_evidence` and 88K/80M/182P findings) |
| Access points | `access/access_points.json` (approximations) + `access/station_entrances.json` (50 official iGeoCom MTA records) | `find_access_points` scans the 22 seed graph nodes within the 800 m radius only | Neither access file is wired; official entrance records remain an unwired evidence layer |
| Service calendar / holidays | `calendar.json` | `RoutingData.holidays` is populated only from a policy JSON (`MappingDataAdapter`/`JsonDataAdapter`); `SeedDataAdapter` passes none | Not wired; wire via policy `holidays` if service-day behaviour is wanted |
| Weather factors | `weather_impact.json` | `engine/eco.py` hardcodes the same per-mode CVs (labelled simulated); mode-penalty tables are not implemented; weather only enters via `event_type == "weather"` events | Partially duplicated semantics; C decides: implement the penalty tables or keep hardcoded CVs and say so |
| Sim fixtures | `sim/*.json` | `scripts/precompute_sim.py` / `verify_sim_*` + engine tests | Aligned by design (all simulated) |

### C adaptation items (decisions/implementations for C, not done here)

1. Keep `contracts/seed/` as the runtime input until a deliberate
   contract-freeze change; do not point adapters at `data/` casually.
2. For a future `JsonDataAdapter` switch: export one normalized network JSON
   (merge the three `stations.json` arrays into `nodes`; attach
   `lines.json`/`walk_links.json`) plus a policy JSON with explicit
   `baseline_fare`, `fares` (MTR lines have no `fare_hkd` in data/ and
   `fare_table` fails without overrides), `holidays`, `profiles`.
3. Resolve the accessibility semantics divergence (seed null vs data
   verified-true) before relying on `find_access_points`' accessible flag.
4. Decide the 982X service model (per-trip schedule vs representative
   headway); today its all-null headway means the runtime never schedules it.
5. Reconcile runtime bus fares (stale 16 / 19.5) with the TD-verified 20.8.
6. Wire `calendar.json` holidays through policy `holidays` if needed.
7. Reconcile weather handling (hardcoded eco CVs vs `weather_impact.json`
   penalty tables) and keep the simulated labelling honest.

Recorded seed-vs-data divergences live in `data/PROVENANCE.md`
§ "Divergences from frozen contracts/seed"; this mapping adds the runtime
view on top and changes nothing in `backend/` or `contracts/`.

## data-layer validator coverage (scripts/validate_data_layer.py, 2026-09-25)

Read-only, stdlib-only structural checker for the `data/` layer, separate
from `scripts/validate_data.py` (which checks the frozen `contracts/seed/`
files and does NOT cover `data/`). Current coverage:

- every JSON file under `data/` parses;
- provenance enum (real / real-derived / simulated) on every record;
- **fare validation**: any `fare_hkd` value must be a finite non-negative
  number or a non-empty list of them; a two-element pair (the observed
  schema) must be ascending; strings, booleans, negatives, NaN and infinity
  are rejected (Python's JSON parser accepts NaN/Infinity literals, so the
  finite check is explicit); the field stays optional (MTR lines carry none);
- node/line/bus-route/access-point references resolve; line stops match
  `seg_time_s` lengths; `headway_s` is null or a **finite positive** number,
  `capacity_per_vehicle` a **finite positive** number, weather
  `mode_penalties` **finite non-negative** numbers (NaN and ±Infinity are
  rejected — Python's JSON parser accepts them as literals); coordinates stay
  within Hong Kong bounds; `481B` cannot reappear on network nodes;
- 982X `schedule_evidence` internal consistency: departure times strictly
  increasing, `gaps_min` equals adjacent time differences, `window` equals
  first-last;
- **982X schedule evidence-level canaries**: `schedule_evidence` must keep
  the user-provided / Monday-to-Friday marking, and the BUS_982X line record
  must not be silently upgraded — `provenance` may not become `real`,
  `data_status` may not become `verified`, `headway_s` must stay all-null,
  and `headway_status` must keep an `unverified` marker. These guard the
  SCHEDULE tier only; the route-level `verified` flag in `bus_routes.json`
  (TD-verified route existence/OD/fare) is a different tier and is
  intentionally not conflated or flagged.

What it does NOT do: verify any value against an external source, judge
authenticity of the screenshots or operator pages, extrapolate the 982X
panels to other days/windows/directions, or promote unverified items.
Source authenticity remains a human process recorded in
`data/PROVENANCE.md`. Tests: `tests/test_data_layer_integrity.py`.
