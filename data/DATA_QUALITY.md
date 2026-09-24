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
