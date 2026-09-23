# M0 source-check evidence summary

Checked 2026-09-22 (Asia/Hong_Kong). This is a human-readable summary of the
official URLs attempted for the seed-data ledger; it is not a live cache.

- MTR system map page: readable; station/line names are visible, but no seed
  coordinate or capacity was copied.
- MTR DATA.GOV.HK dataset page: readable; monthly CSV resources for routes,
  fares and barrier-free access are listed. Resource files were not imported in
  this M0 pass.
- MTR station CSV and MTR schedule API: attempted but inaccessible to the
  checker (CSV content type/query endpoint); status is `unverified`.
- Transport Department bus page: readable as an operator directory.
- Transport Department headway page: readable; biweekly GTFS/CSV resources and
  route/stop/frequency/fare file families are listed. No file rows were copied.
- Transport Department route-fares page and KMB/Citybus API examples: attempted
  but inaccessible to the checker; status is `unverified`.
- Special traffic news page: readable; identifies real-time Transport
  Department traffic/public-transport arrangements and XML resources. It was not
  used to upgrade the simulated event seed.
- Hong Kong Observatory hourly weather API: readable JSON. Observed fields were
  rainfall by district (`unit`, `max`, `startTime`, `endTime`), temperatures,
  `warningMessage`, and `updateTime`. No weather value was written to seeds.
- HKO warning page: attempted but inaccessible to the checker; status is
  `unverified`.
- Star Ferry operator service page: readable. It exposes current timetable
  frequencies, weekday/weekend fares, wheelchair lower-deck limit (maximum four
  per ferry), and a caveat that sailing times vary with marine/weather/traffic
  conditions. It does not publish vessel capacity, so capacity remains pending.
- 2026 government holiday page: attempted but returned no readable content;
  status is `unverified` and no service calendar was changed.

## Additional official field checks (2026-09-23)

- Fetched TD `ROUTE_BUS.xml`, `RSTOP_BUS.xml`, and `STOP_BUS.xml`; exact
  resource URLs, route IDs, stop IDs, field names, row update dates where
  captured, and the audited values are in the S17–S19 table in
  `data/PROVENANCE.md`.
- Fetched TD headway GTFS resources including routes, trips, frequencies,
  calendar and stop-time files. The 182/81C route records have variable
  frequency bands; 982X route variants are represented as scheduled trips.
  The one-number-per-day seed representation cannot safely encode these
  schedules. No headway or weekday label was promoted from a service ID alone.
- Read MTR's official MKK, KOT and EXC street maps. They show station exits
  and access features (including bus/minibus points and PTI), but do not
  provide machine-readable point coordinates or a confirmed link to existing
  abstract seed nodes. No edge was added from visual proximity alone.
- STOP_BUS `X`,`Y` values are projected Hong Kong grid coordinates. They were
  not copied into decimal `lat`/`lng` fields or transformed without a verified
  coordinate operation and stop-to-node match.
- The user manually confirmed `BS_TW` is not a valid stop. `GMB_481B` was
  removed from runnable `network.seed.json`; historical route-card references
  remain only if explicitly simulated/demo-only and validator-warned.
- Follow-up station-coordinate check: initial iGeoCom access timed out, but
  the official CSV was subsequently downloaded and parsed. Exact MTA rows
  yielded 50 named access points (8/11/4/14/6/7 for TAW/KOT/MKK/HUH/EXC/ADM);
  exact RSN rows yielded the six station reference points. Source file SHA-256,
  all record IDs/raw grid coordinates/revision dates, and transformed WGS84
  coordinates are in `data/access/station_entrances.json`. Coordinates were
  transformed with the official HK Geodetic Survey API and independently
  checked for one access row per station. Network station coordinates now use
  the RSN points. GTFS `stops.txt` still has only `location_type=0` rows, so it
  supplied no station entrances. No walk links or accessibility claims were
  inferred; continuity/step-free access remains unknown.

No response body containing secrets was saved. Exact URLs, fields, scope and
limitations are recorded in `data/PROVENANCE.md`.
