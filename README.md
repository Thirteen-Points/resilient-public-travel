# ResilientRoute

ResilientRoute is an academic prototype for exploring disruption-aware journeys on a modelled Hong Kong East Rail corridor from Tai Wai to Admiralty. It combines a route engine, map, public reports, human review, optional AI assistance and precomputed simulations.

**This is not an official transport service, a live timetable or an accessibility guarantee.** Seed routes, event examples, capacities and simulations include derived or simulated assumptions. Check operator announcements for real travel decisions.

## What the project does

| Area | Current behavior | Boundary |
| --- | --- | --- |
| Journey planner and map | Queries the backend route engine, shows route alternatives, estimates, warnings, provenance and approved event impacts. | The network and service assumptions are modelled. A successful API query does not mean the transport data is live. |
| Reports and review | Anyone can submit an unverified report. Reviewers can structure reports, merge evidence, create pending events, edit, approve, reject or withdraw them. | A submitted report is a Signal, not a verified incident. Only the last approved event revision affects routes. |
| Journey companion and preferences | In API mode, uses the requested journey, travel profile and event context. Preference parsing presents a preview before applying a new route query. Deterministic backend tools provide route numbers; an optional model can provide validated wording. | Estimates and accessibility constraints remain modelled; seed conversations use local templates. |
| Backend simulations | The retained API exposes precomputed baseline and guided scenarios, including modelled shared-segment capacity results. | There is no public Simulation page. Results are simulated scenarios, not measured demand or real capacity. |
| Source collection | Optional HKO and MTR collectors can create reports for human review. Safe collection and replanning status endpoints are available. | Collection must be configured and enabled. It does not publish events automatically; live source behavior still requires operational verification. |
| Administrator console | `/admin/` provides a separate login for report review, encrypted AI settings and source configuration. | Configure server-side credentials and storage before deployment; see the administrator guide. |

## Run locally

Requirements: Python 3.11+, Node.js 20.19+ or 22.12+, and Git. The commands below use PowerShell on Windows. On macOS or Linux, use `python3`, `.venv/bin/python`, and `export NAME=value` for the corresponding commands.

Clone the repository and start the API:

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

Open <http://localhost:5173>. The API is at `http://127.0.0.1:8000`; interactive API documentation is at <http://127.0.0.1:8000/docs>. Check <http://127.0.0.1:8000/api/health/deep> for local readiness.

To point Vite at a different API, set `VITE_API_BASE_URL` in `frontend/.env.local` and restart Vite:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not put API keys, reviewer tokens, passwords or other secrets in `VITE_*` variables. Vite embeds those values in browser assets.

## Data modes and review access

API mode is the default. It queries the deterministic route engine and applies approved events effective at the requested departure time. A query uses repository data and the local SQLite database; it is not a live service feed.

The fixed seed demo is an explicit alternative: open `http://localhost:5173/?data=seed`. It supports its fixture journey only. Seed routes do not recalculate for a new departure time. Switching modes reloads the page.

Public route queries, approved-event reads and report submission do not need reviewer credentials. Review is available in the separate `/admin/` console; configure its server-side login using the [administrator guide](deploy/ADMIN.md). The public frontend has no Compare, Simulation or Review screen and does not request or store reviewer credentials. Protected legacy reviewer APIs remain available to trusted clients.

Public updates are checked every three seconds, with source status every fifteen seconds. Healthy refreshes stay quiet. Failures retain existing results with an inline retry notice; recovery clears the notice. Actual route updates use a short notification.

Map lines use bundled, attributed geographic snapshots without runtime geometry requests. Verified rail, bus and pedestrian paths retain real bends and multipart boundaries; unavailable paths remain visibly schematic. See [path sources and limits](frontend/src/map/GEOMETRY_SOURCES.md).

## Trust and data limits

- Provenance is reported as `real`, `real-derived` or `simulated`. A user report marked `real` describes its source channel; it does not verify the report's facts.
- Events affect route calculations only after human approval. Pending edits do not replace the active approved revision.
- Unknown accessibility stays unknown. Modelled wheelchair constraints do not certify a real step-free journey.
- AI can help structure report text or explain tool results. It does not set route numbers, confidence, capacity or simulation metrics.
- Offline mode and `AI_DISABLE_EXTERNAL=true` block external model and collector calls, including calls enabled in saved administrator settings.

See the [data provenance ledger](data/PROVENANCE.md) and [data quality notes](data/DATA_QUALITY.md) before interpreting seed values.

## API quick reference

| Method | Endpoint | Access and purpose |
| --- | --- | --- |
| `GET` | `/api/health`, `/api/health/deep`, `/api/meta` | Public readiness, build identity and metadata |
| `GET` | `/api/graph/network`, `/api/graph/snapshot?at=<ISO time>` | Public modelled network and time-specific impact |
| `POST` | `/api/routes/query` | Public deterministic route candidates |
| `POST` | `/api/signals` | Public unverified report intake |
| `GET` | `/api/events/published?at=<ISO time>` | Public last-approved events effective at that time |
| `POST` | `/api/ai/chat`, `/api/persona/parse` | Public tool-backed chat and conservative preference parsing |
| `POST`, `GET` | `/api/sim/load`, `/api/sim/result?scenario_id=...` | Modelled diversion plan and precomputed scenario results |
| `GET` | `/api/sources/status`, `/api/replanning/status` | Public safe source and replanning status |
| `GET` | `/api/events`, `/api/signals`, `/api/stream/events` | Reviewer queue, evidence and authenticated event stream |
| `POST` | `/api/events`, `/api/events/ingest`, `/api/events/{id}/review` | Reviewer event creation, evidence intake and review actions |
| `POST` | `/api/replanning/load-observations` | Reviewer-authenticated, explicitly simulated load exercise |

Protected reviewer routes require `X-Review-Token`; the SSE stream accepts reconnect cursors. Administrator routes under `/api/admin` use the administrator session. See [administrator setup](deploy/ADMIN.md) for credentials, CSRF handling and encrypted settings.

Example route query:

```json
{
  "origin": "TAW",
  "destination": "ADM",
  "depart_at": "2026-10-05T08:30:00+08:00",
  "profile": { "preset": "fastest" }
}
```

## Validate changes

Install the backend and test dependencies, then validate the checked-in data and run the full backend suite:

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

Run frontend checks from `frontend`:

```powershell
npm ci
npm run typecheck
npm run test
npm run build
npm run build:admin
```

The isolated browser regression starts a temporary API/database and Vite server, signs into `/admin/`, submits scripted reports, and checks publication, route refresh, recovery and mobile layout. It prints its checks and three publication-to-render timings, creates no media, and requires Playwright plus Chromium:

```powershell
npm install --prefix .cache/p3-playwright --no-audit --no-fund --package-lock=false playwright@1.56.1
node .cache/p3-playwright/node_modules/playwright/cli.js install chromium
$env:M2_PLAYWRIGHT = Join-Path (Get-Location) '.cache/p3-playwright/node_modules/playwright'
$env:M2_PYTHON = Join-Path (Get-Location) '.venv/Scripts/python.exe'
node tests/browser/m2.e2e.cjs
```

GitHub Actions also runs a disposable Docker container recreation check for database and encrypted-setting persistence. A local unit test does not replace that container check. See [P3 regression and deployment acceptance](deploy/P3-ACCEPTANCE.md) for its fixture guard and production acceptance steps.

## Deployment and project notes

The repository includes a Render Blueprint and deployment guidance for a Cloudflare Pages frontend. Before relying on a deployed instance, verify `/api/health/deep`, `/api/meta` and the deployed build SHA; local tests do not establish live source, model, latency or storage behavior.

- [Deployment guide](deploy/DEPLOYMENT.md)
- [Administrator guide](deploy/ADMIN.md)
- [DeepSeek configuration](deploy/DEEPSEEK.md)
- [Simulation data and assumptions](data/sim/README.md)
- [P3 integration status and outstanding acceptance](docs/acceptance/p3-integration-report.md)
- [Editable architecture diagram](docs/architecture/resilient-public-travel.svg)
