# Data Quality Check Results (T7.1)

> Generated: 2026-09-22
> Checker: `scripts/validate_data.py`
> Data files checked: `data/network/stations.json`, `data/network/lines.json`, `data/network/walk_links.json`, `data/network/bus_routes.json`, `data/access/access_points.json`, `data/calendar.json`

---

## 1. Summary

| Check | Result | Issues Found |
|---|---|---|
| JSON validity | PASS | 0 |
| Coordinate range (HK: 22.0-23.0 lat, 113.5-114.5 lng) | PASS | 0 |
| Lat/lng order (lat first, lng second) | PASS | 0 |
| Line stops reference existing nodes | PASS | 0 |
| Walk link endpoints reference existing nodes | PASS | 0 |
| No duplicate station IDs | PASS | 0 |
| Station name/ID consistency | PASS | 0 |
| All lines have headway_s defined | PASS | 0 |
| All lines have capacity_per_vehicle | PASS | 0 |
| Provenance field present on all data items | PASS | 0 |
| No unverified data marked as "real" inappropriately | PASS | 0 |
| Bus route stops reference existing nodes | **WARN** | 2 (BUS_170 and GMB_481B have partial stop lists) |

---

## 2. Issues Found

### 2.1 Partial Stop Lists (WARN)

**BUS_170**: Only has `BS_HUH_TUNNEL` in stops. Full route is Sha Tin Station <-> Wah Fu (Central). HK Island end not modelled because it does not serve Admiralty/Central.

**GMB_481B**: Only has `BS_TAW` in stops. Full route is Tsuen Wan <-> Tai Wai. `BS_TW` (Tsuen Wan) node not yet in network.

**Impact**: These routes have limited utility in the graph. They are included for completeness but C-Route should be aware of their partial modelling.

**Resolution**: Add `BS_TW` and `BS_170_HK` nodes in P1 phase if needed.

### 2.2 Unverified Critical Items

| # | Item | Impact | Resolution |
|---|---|---|---|
| 1 | ETS<->TST walkway elevator | Wheelchair routing may fail | Must verify on-site or via MTR accessibility data |
| 2 | ERL 9-car capacity (2,845) | Simulation parameter accuracy | Find LegCo paper primary source |
| 3 | Alternative line capacities (~2,500) | Capacity bucket accuracy | Verify from MTR rolling stock specs |
| 4 | Bus headway values | Load estimation accuracy | Check KMB/CTB timetables |
| 5 | Star Ferry current fares | Fare accuracy | Check Star Ferry website |
| 6 | Star Ferry cancellation threshold | Ferry leg reliability | Verify from Star Ferry or TD |
| 7 | Wan Chai <-> Exhibition Centre walk | EXC island alternative | Verify on-site |

### 2.3 Coordinate Accuracy

All MTR station coordinates are sourced from MTR open data (data.gov.hk) and are considered `real` with `high` confidence. However:
- Precision is ~50-100m (station centre, not entrance)
- Bus stop coordinates are `real-derived` (approximated from station area)
- For 800m catchment circles, this precision is adequate
- For entrance-level routing, MTR barrier-free facilities CSV should be used

### 2.4 Provenance Compliance

All data items have provenance fields (`provenance`, `source`, `retrieved_at`, `confidence`, `data_status`). Items marked `real` are only those with traceable official sources. Items with estimated values are marked `real-derived`. Simulated data is marked `simulated`.

No unverified data is incorrectly marked as `real`.

---

## 3. Data Structure Summary

| File | Records | Provenance Distribution |
|---|---|---|
| stations.json | 16 MTR stations, 4 bus stops, 2 piers | 18 real, 4 real-derived |
| lines.json | 13 lines (6 MTR, 5 bus, 1 minibus, 1 ferry) | 3 real, 10 real-derived |
| walk_links.json | 7 walk links | 7 real-derived |
| bus_routes.json | 16 serving routes, 12 excluded routes | 1 real, 15 real-derived |
| access_points.json | 6 stations, 21 access points | 21 real-derived |
| calendar.json | 3 schedule types, 3 holidays, 5 exceptions | 1 real |
| weather_impact.json | 7 weather conditions | 1 real, 6 simulated |
