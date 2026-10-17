# ResilientRoute

**Read this in: [English](README.md) | [简体中文](README.zh-CN.md)**

ResilientRoute is a disruption-aware journey guidance prototype for a modelled Hong Kong East Rail corridor from **Tai Wai to Admiralty**. When a rail segment is disrupted, it turns multi-source signals into human-approved events, applies those events to a deterministic multimodal route engine, and gives every traveller — from a commuter in a hurry to a wheelchair user — personalised, honestly-labelled alternatives across MTR, bus, ferry and walking, with modelled fares and official bus arrival times.

It was built for the Hack4SDG 2026 hackathon by Team Thirteen-Points.

> **This is an academic prototype, not an official transport service.** The network, capacities, simulations and some fares are modelled or derived. Nothing here is a live timetable, an accessibility guarantee, or operational advice. Check operator announcements for real travel decisions.

## Live demo

| Component | URL |
| --- | --- |
| Public web app | <https://resilient-public-travel.pages.dev> |
| REST API (Render) | <https://resilient-public-travel-api.onrender.com> |
| Interactive API docs | <https://resilient-public-travel-api.onrender.com/docs> |

## What it does

**1 · Early detection with a human gate.** Anyone can submit an unverified report (a "Signal"). Reviewers structure the text, merge evidence, and create event cards with a computed confidence score. Only after a reviewer clicks publish does the affected segment turn red on the map and every route recalculate. A submitted report is a signal, never a verified incident.

**2 · Personalised, multimodal routing.** The engine searches rail, imported Transport Department GTFS bus patterns, ferry and walking links, then filters and ranks candidates by travel profile: the same disruption yields a different top route for a time-pressed commuter than for a wheelchair user, with different explanations. Hard accessibility constraints are enforced, not suggested.

**3 · Honest crowd diversion.** A precomputed 10,000-person sandbox compares unguided versus guided distribution of demand across shared segments. When alternative capacity runs out, the remaining unmet demand is reported as-is — the prototype narrates risk and gaps, it does not claim to "solve" congestion.

**4 · Real fares, real arrivals — where possible.** Fares are imported from official MTR, Transport Department bus and Star Ferry sources into a revisioned SQLite store; missing prices stay missing. Live-style bus arrivals come from the official KMB/LWB and Citybus open APIs, with unverified matches shown as unavailable rather than guessed.

**5 · Offline resilience.** A prepared offline bundle runs the full demo — API, built frontend, frozen data and media — with no network at all, because a demo that dies with the Wi-Fi is not a demo.

## Architecture

```
Signals (public reports, optional collectors)
        │
        ▼
Review console (/admin/, session login) ── approve / edit / withdraw
        │
        ▼
Approved events ──► Graph snapshot (capacity degrade / close)
        │
        ▼
Deterministic route engine (graph + fares + accessibility filters)
        │
        ▼
React + MapLibre frontend: map, journey cards, preferences, bus arrivals
```

- **Backend** — Python 3.11+ / FastAPI / SQLite. Route engine, graph builder, fare store, simulation, signal pipeline and the administrator console live in `backend/app/`.
- **Frontend** — React, TypeScript, Vite, MapLibre GL. Public pages plus a separate `/admin/` review console, in `frontend/`.
- **AI boundary** — an optional LLM (DeepSeek, Qwen or GLM) only reads text and writes wording: it structures report text, parses preferences and explains tool results. Route numbers, times, confidence, capacity and every other number come from the deterministic engine. With `AI_ENABLED=false` (the default) the system runs fully offline with deterministic fallbacks.
- **Provenance everywhere** — every data object is labelled `real`, `real-derived` or `simulated`, and the UI shows it.

## Run locally

Requirements: Python 3.11+, Node.js 20.19+ or 22.12+, Git. PowerShell commands shown; on macOS/Linux use `python3`, `.venv/bin/python` and `export NAME=value`.

Start the API:

```powershell
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:AI_ENABLED = 'false'
$env:OFFLINE_MODE = 'true'
$env:AI_DISABLE_EXTERNAL = 'true'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend:

```powershell
cd resilient-public-travel\frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The API is at <http://127.0.0.1:8000> with interactive docs at `/docs`; check `/api/health/deep` for local readiness. One-click launchers (`scripts/start.sh`, `scripts/start.bat`) and a Docker Compose file are also available — see the [deployment guide](deploy/DEPLOYMENT.md).

To point Vite at a different API, set `VITE_API_BASE_URL` in `frontend/.env.local` and restart Vite. Never put API keys, reviewer tokens or passwords in `VITE_*` variables — Vite embeds them in downloadable browser assets.

### Data modes and review access

- **API mode (default)** queries the deterministic engine and applies approved events effective at the requested departure time, using repository data and the local SQLite database.
- **Fixed seed demo** — open `http://localhost:5173/?data=seed` for a fixture journey that does not recalculate. Switching modes reloads the page.
- Public queries, published-event reads and report submission need no credentials. Review happens in the separate `/admin/` console; configure its server-side login with the [administrator guide](deploy/ADMIN.md). The public app has no Compare, Simulation or Review screen and never requests reviewer credentials.
- Updates refresh every three seconds and source status every fifteen; failures keep existing results with an inline retry notice.
- Map lines use bundled, attributed geometry snapshots with no runtime geometry requests; unverified paths stay visibly schematic. See [path sources and limits](frontend/src/map/GEOMETRY_SOURCES.md).

## API quick reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health`, `/api/health/deep`, `/api/meta` | Readiness, build identity, metadata |
| `GET` | `/api/graph/network`, `/api/graph/snapshot?at=<ISO>` | Modelled network and time-specific impact |
| `POST` | `/api/routes/query` | Deterministic multimodal route candidates |
| `GET` | `/api/buses/status`, `/api/buses/services`, `/api/buses/eta` | Corridor bus catalogue and validated official arrivals |
| `GET` | `/api/fares/status`, `/api/fares/lookup` | Fare database revision and dated fare lookup |
| `POST` | `/api/signals` | Public unverified report intake |
| `GET` | `/api/events/published?at=<ISO>` | Last-approved events effective at a time |
| `POST` | `/api/ai/chat`, `/api/persona/parse` | Tool-backed chat and conservative preference parsing |
| `POST`, `GET` | `/api/sim/load`, `/api/sim/result?scenario_id=...` | Modelled diversion plan and precomputed scenarios |
| `GET` | `/api/sources/status`, `/api/replanning/status` | Safe source and replanning status |
| `GET`, `POST` | `/api/events`, `/api/signals`, `/api/stream/events` | Reviewer queue, evidence and authenticated event stream |
| `POST` | `/api/events`, `/api/events/ingest`, `/api/events/{id}/review` | Reviewer event creation and review actions |

Protected reviewer routes require `X-Review-Token`; administrator routes under `/api/admin` use the administrator session. Example route query:

```json
{
  "origin": "TAW",
  "destination": "ADM",
  "depart_at": "2026-10-05T08:30:00+08:00",
  "profile": { "preset": "fastest" }
}
```

## Validate changes

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt "pytest-subtests>=0.14,<1"
$env:PYTHONPATH = '.;backend'
$env:AI_ENABLED = 'false'
$env:OFFLINE_MODE = 'true'
$env:AI_DISABLE_EXTERNAL = 'true'
.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py
.\.venv\Scripts\python.exe scripts/validate_data_layer.py
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend/tests backend/app/engine/tests tests -q
```

Frontend checks, from `frontend`:

```powershell
npm ci
npm run typecheck
npm run test
npm run build
npm run build:admin
```

A browser regression suite (`tests/browser/`) exercises real backend requests, publication, route refresh, recovery and mobile layout with Playwright; GitHub Actions adds a disposable container recreation check for database and encrypted-setting persistence. See [P3 acceptance](deploy/P3-ACCEPTANCE.md) and [P4 acceptance](deploy/P4-ACCEPTANCE.md) for the full procedures.

## Offline demo package

`deploy/offline/` ships a prepared bundle that starts the API and the built frontend with no installation and no network: a five-minute scripted tour of the corridor, frozen simulation evidence, and recorded media as the failure fallback. Build it with `scripts/package_offline.py`, verify with `python scripts/preflight.py --demo --require-media`, and launch with `deploy/offline/start.ps1` / `start.sh`. See the [offline package guide](deploy/offline/README.md).

## C++ sandbox simulation report

`sim_cpp/` is a standalone C++20 event simulation that replays the same 10,000-person synthetic population on the Kowloon Tong → Exhibition Centre corridor under a one-hour East Rail (Hung Hom–Exhibition Centre) closure, comparing three strategies: **A** (no-fault baseline), **B** (protected-first bucket allocation with a known planned closure window) and **C** (immediate fastest route, re-planning only when forced off the train). The headline finding: the 95% per-train physical cap never binds — the 3,400/460 planning cap does — and bucket allocation buys tail protection for protected groups (zero forced alights versus 633, max delay 30 versus 60 min) at a small cost to standard commuters. All reports, charts and the verification record can be read directly on GitHub:

- **[Simulation report](sim_cpp/report/SIMULATION_REPORT.md)** (Chinese, charts inline) · **[Conclusions](sim_cpp/report/CONCLUSIONS.md)** · **[Bucket comparison](sim_cpp/report/BUCKET_COMPARISON.md)** · **[Verification record](sim_cpp/report/VERIFICATION.md)** · **[One-slide summary](sim_cpp/report/SIMULATION_ONE_SLIDE.pptx)** (PPTX)

## Deployment

The repository contains a Render Blueprint (`render.yaml`) for the API — with a persistent disk for `events.sqlite3`, admin and AI-usage databases — and deploys the frontend to Cloudflare Pages. The backend permits only the exact production Pages origin via `CORS_ALLOWED_ORIGINS`; reviewer APIs are protected by `REVIEW_API_TOKEN`. Before relying on a deployed instance, verify `/api/health/deep`, `/api/meta` and the deployed build SHA. Full runbook: [deployment guide](deploy/DEPLOYMENT.md).

## Trust and data limits

- Provenance is `real`, `real-derived` or `simulated`. A report marked `real` describes its source channel; it does not verify the report's facts.
- Events affect routes only after human approval; pending edits never replace the active approved revision.
- Unknown accessibility stays unknown — modelled wheelchair constraints do not certify a real step-free journey.
- AI never produces numbers or routes; all figures come from the deterministic engine.
- Offline mode and `AI_DISABLE_EXTERNAL=true` block every external model and collector call, including ones enabled in saved administrator settings.

See the [data provenance ledger](data/PROVENANCE.md) and [data quality notes](data/DATA_QUALITY.md) before interpreting seed values.

## Repository layout

```
backend/app/     FastAPI app: engine, graph, sim, services, ai, admin
frontend/        React public app + /admin/ review console
contracts/       Schemas, seed data and interface contracts
data/            Network, calendar, fares, simulations, provenance ledger
deploy/          Deployment, admin, fares, offline package guides
docs/            Plan, acceptance records, architecture diagram
scripts/         Validation, import, packaging and preflight tools
tests/           Browser (Playwright) and integration tests
```

## Documentation

- [Deployment guide](deploy/DEPLOYMENT.md) · [Administrator guide](deploy/ADMIN.md) · [DeepSeek configuration](deploy/DEEPSEEK.md)
- [Bus catalogue and arrivals](deploy/BUS-API.md) · [Fare database](deploy/FARES.md)
- [Offline demo package](deploy/offline/README.md) · [P3 acceptance](deploy/P3-ACCEPTANCE.md) · [P4 acceptance](deploy/P4-ACCEPTANCE.md)
- [Simulation data and assumptions](data/sim/README.md) · [Provenance ledger](data/PROVENANCE.md)
- [Map geometry sources](frontend/src/map/GEOMETRY_SOURCES.md) · [Editable architecture diagram](docs/architecture/resilient-public-travel.svg)
- [Project plan index](docs/plan/00-INDEX.md) (Chinese)
