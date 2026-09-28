# C-Data & C-DevOps Final Report

**Project:** Thirteen-Points/resilient-public-travel
**Branch:** ZYC
**Commit SHA:** `d3436792786db74aebe50fc24f933d1b2ad143e9`
**Date:** 2026-09-22

---

## 1. Modified / Created Files List

### New Files (43 files, 4533 insertions)

**C-Data (data layer):**
| File | Description |
|---|---|
| `data/network/stations.json` | 22 nodes: 16 MTR stations, 4 bus stops, 2 piers |
| `data/network/lines.json` | 13 transit lines with headways, capacities, fares |
| `data/network/walk_links.json` | 7 walk links between transfer nodes |
| `data/network/bus_routes.json` | 16 verified bus routes + 12 excluded with reasons |
| `data/access/access_points.json` | 21 access points within 800m catchment |
| `data/calendar.json` | 3 schedule types + 3 public holidays + 5 service exceptions |
| `data/capacity_method.md` | Capacity formula documentation + 5 worked examples |
| `data/weather_impact.json` | 7 weather conditions with mode penalties |
| `data/PROVENANCE.md` | Full provenance ledger (10 sections) |
| `data/DATA_QUALITY.md` | Quality check results + 7 unverified items |
| `scripts/validate_data.py` | Automated data validation (10 checks) |
| `tests/test_data_integrity.py` | 34 pytest tests across 8 test classes |

**C-DevOps (infrastructure):**
| File | Description |
|---|---|
| `.env.example` | Complete env config template (LLM disabled, no secrets) |
| `backend/requirements.txt` | Production dependencies |
| `backend/requirements-dev.txt` | Dev dependencies |
| `backend/app/__init__.py` | Package init |
| `backend/app/main.py` | FastAPI app with lifespan, CORS, routers |
| `backend/app/config/__init__.py` | Config package init |
| `backend/app/config/settings.py` | Pydantic Settings with safe defaults |
| `backend/app/api/__init__.py` | API package init |
| `backend/app/api/health.py` | Basic + deep health check endpoints |
| `backend/app/api/meta.py` | Freshness, sources, disclaimer endpoint |
| `backend/app/api/graph.py` | Network + snapshot endpoints |
| `backend/app/{graph,engine,sim,ai,data}/__init__.py` | Stub packages for other agents |
| `scripts/start.sh` | One-click startup (Linux/Mac) |
| `scripts/start.bat` | One-click startup (Windows) |
| `scripts/preflight.py` | Pre-demo verification (5 checks) |
| `deploy/Dockerfile` | Python 3.12-slim, offline by default |
| `deploy/docker-compose.yml` | Service config with volumes + healthcheck |
| `deploy/offline/README.json` | Offline package manifest |
| `deploy/offline/README.md` | Offline package documentation |
| `deploy/DEPLOYMENT.md` | Full deployment guide |
| `deploy/TROUBLESHOOTING.md` | 8 sections of common issues + fixes |
| `tests/test_health.py` | 25 health check tests |
| `tests/test_startup.py` | 52 startup/structure tests |

**Agent Docs:**
| File | Description |
|---|---|
| `docs/agents/01-c-data.md` | C-Data agent scope, files, DoD |
| `docs/agents/02-c-devops.md` | C-DevOps agent scope, files, DoD |

### Modified Files
| File | Change |
|---|---|
| `README.md` | Replaced 2-line placeholder with full English documentation |

### Files NOT Modified (by rule)
- `docs/plan/03-contracts.md` — unchanged (contracts compliance verified)
- `contracts/` — unchanged (no schema modifications)
- `main`, `FreddyHu`, `Mingquan-Xia` branches — untouched
- Existing agent docs (03–06) — untouched

---

## 2. C-Data Completed Content

### Network Data (`data/network/`)
- **Stations:** 16 MTR stations (ERL, TML, TWL, KTL, ISL, SIL), 4 bus stops, 2 piers — each with `id`, `name_zh`, `name_en`, `kind`, `lat`, `lng`, `lines`, `accessible`, and full provenance fields
- **Lines:** 13 transit lines (6 MTR, 5 bus, 1 minibus, 1 ferry) with `headway_s` per 4 schedule types, `capacity_per_vehicle`, `fare_hkd`, `provenance`
- **Walk links:** 7 inter-station walk connections, all `real-derived` (straight-line × 1.3 detour factor)
- **Bus routes:** 16 routes verified as serving Tai Wai; 12 excluded routes with documented reasons (680/681/682/307/673/978/968/948X confirmed not serving Tai Wai)

### Access Data (`data/access/`)
- 21 access points covering all 6 corridor stations within 800m catchment
- Types: MTR entrances, bus stops, taxi stands, walk access points
- All coordinates approximated (`real-derived`)

### Service Calendar (`data/calendar.json`)
- 3 schedule types: weekday, Saturday, Sunday+PH
- 3 public holidays in 2026 (National Day, Chung Yeung Festival, Christmas Day)
- 5 service exceptions for peak-only bus routes (982X, 985A, 985B, 182P, 182X)
- Operating hours for all modes

### Capacity Methodology (`data/capacity_method.md`)
- Formula: `capacity_r = frequency × capacity_per_vehicle × eta_max (0.85)`
- Vehicle type lookup table with sources and confidence
- 5 worked examples: ERL, BUS_182, BUS_982X, GMB_481B, FERRY
- Key insight: one ERL train ≈ 20 double-decker buses

### Weather Impact (`data/weather_impact.json`)
- 7 conditions: normal, amber/red/black rainstorm, T1/T3/T8
- Mode penalties and walk speed factors per condition
- Reliability CV values per mode (MTR 0.08, BUS 0.35, etc.)

### Provenance Ledger (`data/PROVENANCE.md`)
- 10 sections tracking every data item to source URL, retrieval date, confidence level, data status
- Three-level system: `real`, `real-derived`, `simulated`
- No unverified data labelled as `real` (compliance verified)

### Data Quality (`data/DATA_QUALITY.md`)
- All checks PASS except 2 warnings (partial stop lists for BUS_170 and GMB_481B)
- 7 unverified critical items listed with impact and resolution path

### Automated Validation (`scripts/validate_data.py`)
- 10 automated checks: JSON validity, coordinate ranges, duplicate IDs, line stop references, walk link endpoints, provenance fields, capacity/headway fields, seed data, bus route data
- All 10 checks PASS with 0 warnings

---

## 3. C-DevOps Completed Content

### Backend Skeleton (`backend/app/`)
- FastAPI app with lifespan management, CORS middleware, structured logging
- Routers mounted: health, meta, graph
- Stub packages created for: `graph/`, `engine/`, `sim/`, `ai/`, `data/` (for C-Route, C-Sim, C-AI agents)

### Health Check (`backend/app/api/health.py`)
- `GET /api/health` — basic liveness: process alive, timestamp, version, environment
- `GET /api/health/deep` — deep readiness: data files present/loadable, directories exist, LLM config status, data sources status
- Distinguishes "process alive" vs "core function available" as required

### Configuration (`.env.example` + `settings.py`)
- All settings have safe defaults: `LLM_ENABLED=false`, no API keys, `OFFLINE_MODE=false` (but all data is local)
- Pydantic Settings loads from environment with fallback to defaults
- No real secrets in any committed file (verified by automated test)

### Startup Scripts
- `scripts/start.sh` — Linux/Mac one-click: check Python → create venv → install deps → validate data → start server
- `scripts/start.bat` — Windows equivalent
- Both support `--offline` and `--no-llm` flags

### Docker (`deploy/`)
- `Dockerfile`: Python 3.12-slim, installs requirements, copies data/contracts/scripts
- Defaults: `OFFLINE_MODE=true`, `LLM_ENABLED=false`
- `HEALTHCHECK` with 30s interval
- `docker-compose.yml`: port mapping, env vars, read-only data volumes, separate cache/snapshot volumes

### Offline Package (`deploy/offline/`)
- Manifest with file list, startup instructions, data version
- All data files included for fully offline operation
- Limitations documented

### Preflight Script (`scripts/preflight.py`)
- 5 checks: data files present, graph loadable, offline package exists, health endpoint reachable, core API responds
- Single-command demo readiness verification

### Documentation
- `deploy/DEPLOYMENT.md`: quick start (3 options), configuration, offline mode, health check, API endpoints, production deployment, security notes
- `deploy/TROUBLESHOOTING.md`: 8 sections covering server startup, data validation, health check, LLM, Docker, offline mode, development, getting help

---

## 4. Executed Tests and Results

### Data Validation Script (`scripts/validate_data.py`)
```
RESULT: PASS (0 warnings)
```
All 10 checks passed:
1. JSON validity (11 files) ✓
2. Coordinate ranges (all within HK) ✓
3. No duplicate node IDs ✓
4. Line stops reference existing nodes ✓
5. Walk link endpoints reference existing nodes ✓
6. Provenance fields present on all items ✓
7. Capacity and headway defined for all lines ✓
8. Seed data files valid ✓
9. Bus route data consistent ✓
10. Summary: 22 nodes, 13 lines, 7 walk links, 16 bus routes checked ✓

### Pytest Suite (`tests/`)
```
111 passed, 1 warning in 0.46s
```

| Test File | Tests | Result |
|---|---|---|
| `tests/test_data_integrity.py` | 34 tests (8 classes) | ALL PASS |
| `tests/test_health.py` | 25 tests (8 classes) | ALL PASS |
| `tests/test_startup.py` | 52 tests (7 classes) | ALL PASS |
| **Total** | **111 tests** | **ALL PASS** |

The 1 warning is a Pydantic V2 deprecation notice about class-based `config` (cosmetic, not a failure).

### Pre-Commit Checklist
1. ✓ `git status` — only task-related modifications
2. ✓ No `main` branch modifications (on ZYC)
3. ✓ No real secrets in any file (automated scan clean)
4. ✓ All new data has provenance tags (`real`/`real-derived`/`simulated`)
5. ✓ `03-contracts.md` unchanged (zero diff)
6. ✓ All 111 tests pass
7. ✓ Data validation passes with 0 warnings
8. ✓ No .env file committed (only .env.example)

---

## 5. Simulated Data Used

The following data items are marked `simulated`:

| Item | File | Reason |
|---|---|---|
| GMB 481B headway (600s) | `data/network/lines.json` | No official timetable found; estimated from typical green minibus frequency |
| Ferry TST_CEN headway (1200s) | `data/network/lines.json` | No Star Ferry real-time schedule API; estimated from published 20-min off-peak interval |
| Ferry capacity (350) | `data/network/lines.json` | Typical vessel capacity; not verified against specific vessel assignment |
| Weather reliability CV values | `data/weather_impact.json` | Statistical estimates based on general transit research, not Hong Kong specific |
| Walk speed factors per weather | `data/weather_impact.json` | Estimated penalties, not from empirical HK study |

All other data is either `real` (from MTR open data / data.gov.hk / official sources) or `real-derived` (computed from real coordinates using standard formulas).

---

## 6. Unverified Data

7 critical items flagged as unverified in `data/DATA_QUALITY.md`:

| # | Item | Impact | Resolution Path |
|---|---|---|---|
| 1 | ERL train capacity (2845 pax) | Affects all ERL load calculations | Verify against MTR/LegCo latest fleet spec; 9-car vs 12-car discrepancy |
| 2 | ETS→TST walk link accessibility | Wheelchair routing may be wrong | Verify elevator/escalator availability at interchange |
| 3 | 88K bus route status | May be cancelled; route may not exist | Check Transport Department route database |
| 4 | 80M proposed cancellation | Route may disappear before demo | Monitor Transport Department notices |
| 5 | BUS_170 partial stop list | Route geometry incomplete | Obtain full stop list from KMB/CTB |
| 6 | GMB_481B partial stop list | Route geometry incomplete | Obtain full stop list from Transport Department |
| 7 | Bus headway estimates | Some off-peak/saturday headways estimated | Cross-reference with KMB/CTB official timetables |

---

## 7. Interface Compatibility Risks

### Low Risk (Safe)
- **`/api/health` and `/api/health/deep`**: New endpoints, not in `03-contracts.md` §4. No existing contract violated. C-Integrator should add to contract.
- **`/api/meta`**: Matches `03-contracts.md` §3.6 `Meta` object. `sources[]` and `disclaimer` fields align.
- **`/api/graph/network`**: Returns nodes/lines from local JSON. Matches seed data structure. C-Route can consume directly.
- **`/api/graph/snapshot`**: Returns snapshot_id and affected_edges. Matches contract §4.

### Medium Risk (Requires C-Route Attention)
- **Station/line IDs**: Must match what C-Route's graph builder expects. IDs follow MTR official codes (TAW, SHS, KOT, HUH, EXC, ADM, etc.) — C-Route should verify against `03-contracts.md` §2 line list.
- **Headway format**: 4 schedule types per line (`weekday_peak`, `weekday_offpeak`, `saturday`, `sunday_ph`). C-Route's `build.py` must handle all 4; if it expects a single headway, it will need adaptation.
- **Walk link structure**: `from`/`to` use node IDs, `distance_m` and `walk_s` provided. C-Route's `walk.py` module may have its own distance estimation — potential double-counting if not coordinated.

### Low Risk (Requires C-Sim Attention)
- **Capacity values**: `capacity_per_vehicle` and `headway_s` provided per line. C-Sim's `load.py` should use these directly rather than re-deriving.
- **Calendar-dependent headways**: C-Sim must switch headways based on `data/calendar.json` schedule type for correct simulation results.

### No Risk
- **`03-contracts.md`**: Not modified. Zero diff verified.
- **`contracts/seed/`**: Not modified. Zero diff verified.
- **Existing agent docs (03–06)**: Not modified.

---

## 8. Commit SHA on ZYC Branch

```
Commit: d3436792786db74aebe50fc24f933d1b2ad143e9
Message: [C-Data+C-DevOps] Complete data layer and DevOps infrastructure
Files:  43 files changed, 4533 insertions(+), 2 deletions(-)
Pushed: origin/ZYC (a78ee67..d343679)
```

---

## 9. Follow-Up Items for C-Route, C-Sim, C-Integrator

### For C-Route (Agent 3)
1. **Consume network data**: Read `data/network/stations.json` + `lines.json` + `walk_links.json` in `graph/build.py`. Node IDs and line IDs are stable.
2. **Headway selection**: Implement schedule-type-aware headway selection using `data/calendar.json` to pick the correct `headway_s` slot.
3. **Walk link integration**: Use `walk_links.json` distances or implement own estimation (but not both — avoid double-counting).
4. **Accessibility flags**: Use `accessible` field on stations and walk links for wheelchair routing. Note: `accessible` on walk links is `real-derived` (estimated).
5. **Bus route filtering**: Use `bus_routes.json` `included` list; excluded routes have documented reasons.

### For C-Sim (Agent 4)
1. **Capacity calculation**: Use `capacity_per_vehicle` × `headway_s` from `lines.json` and formula from `capacity_method.md`. Do not re-derive independently.
2. **Population OD weights**: Currently no OD data file exists. C-Sim should generate simulated OD and label it `simulated` per provenance rules.
3. **Calendar integration**: Simulation scenarios must respect `calendar.json` schedule types for realistic headways.
4. **Weather factors**: If simulating weather scenarios, use `weather_impact.json` penalty factors.

### For C-Integrator (Agent 6)
1. **Add `/api/health` and `/api/health/deep` to contract**: These endpoints exist but are not in `03-contracts.md` §4 REST API table. Should be formalized.
2. **Validate headway format**: Confirm that 4-slot headway structure (`weekday_peak`/`weekday_offpeak`/`saturday`/`sunday_ph`) is acceptable to all consumers. If C-Route needs a different format, a contract note is required.
3. **Cross-module regression test**: Run data validation + health check + route query end-to-end. Add integration test that verifies network data → graph build → route query → load estimate chain.
4. **Provenance compliance check**: Verify that C-Route and C-Sim outputs carry `provenance` fields as required by `03-contracts.md` §2 (`["real", "real-derived", "simulated"]`).
5. **Preflight in CI**: Add `scripts/preflight.py` and `scripts/validate_data.py` to CI pipeline.

### For C-AI (Agent 5)
1. **Health check reports LLM status**: The deep health endpoint already checks `settings.llm_enabled` and reports it. C-AI should ensure `llm_client.py` integrates with the same settings.
2. **No-LLM fallback test**: `tests/test_startup.py::TestLLMFallback` already verifies LLM is disabled by default. C-AI should add a test that confirms the full route query flow works with LLM disabled.
