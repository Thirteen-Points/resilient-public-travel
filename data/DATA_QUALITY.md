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
