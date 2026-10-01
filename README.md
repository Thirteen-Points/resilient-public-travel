# Resilient Public Travel

Resilient Public Travel is a Hong Kong East Rail Line corridor prototype for helping passengers find alternatives during service disruptions. It combines reviewed incident reports, a deterministic route engine, accessibility-aware route data, and simulation tools. It is a prototype, not an official MTR service or live operational guidance.

## Current Capabilities

- **Event-to-reroute API path (M1):** reports can enter the signal API, be merged into an event, reviewed and published, then synchronized into a versioned route-engine snapshot. Route queries use the updated snapshot. `scripts/demo_m1_story.py` exercises this backend flow against a running local API; A reports one successful end-to-end run. A run log is not checked into the repository; see [M2 C status](docs/acceptance/m2-c-status.md).
- **Interactive frontend:** includes a fixed seed-scenario mode and an API mode. In API mode, review actions use the backend and event-stream changes trigger refreshed event and route queries. The fixed seed mode is illustrative and does not recalculate routes.
- **C-Sim:** `/api/sim/load` computes a capacity-bucket diversion plan from supplied route estimates, while `/api/sim/result` serves a precomputed scenario. M0 verification covers deterministic behavior against simulated fixtures. These checks do not establish real passenger demand or verified operating capacity.
- **Data transparency:** source records and model inputs are classified as `real`, `real-derived`, or `simulated`; see [data/PROVENANCE.md](data/PROVENANCE.md) and [data/DATA_QUALITY.md](data/DATA_QUALITY.md).

The 10,000-person multi-OD sandbox belongs to **P3/M3**, not M2, in the project timeline. Files named `data/sim/m2-*` are early simulated preparation and are not M2 interim deliverables or acceptance evidence. In the current comparison, guided total delay is higher than baseline; the simulated result does not show a benefit. Its route-level capacities also do not account for shared capacity across overlapping route segments. M3 acceptance and performance targets remain separate from the M2 interim package.

## Run Locally

Requirements: Python 3.11 or newer. The deterministic backend does not require an LLM key.

Windows:

```cmd
scripts\start.bat
```

Linux or macOS:

```bash
./scripts/start.sh
```

Open `http://127.0.0.1:8000` locally, or visit `http://127.0.0.1:8000/docs` for the API reference. The scripts create a local virtual environment and install backend requirements, so the first run needs package access. For container startup:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Run the offline data preflight:

```bash
python scripts/preflight.py
```

To exercise the M1 backend story, start the API with `REVIEW_API_TOKEN=dev-demo-token` and run:

```bash
REVIEW_API_TOKEN=dev-demo-token python scripts/demo_m1_story.py
```

On Windows PowerShell, set the token with `$env:REVIEW_API_TOKEN='dev-demo-token'` before running the Python command. The script creates demo reports and an event in the configured event database, publishes the event after review, and checks the graph snapshot and route response. Use a disposable local database for repeated demonstrations.

## API Surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/signals` | Submit a passenger report |
| `POST` | `/api/events/ingest` | Structure or merge a submitted signal into an event |
| `GET` | `/api/events` / `/api/events/published` | Read review queue or published events |
| `POST` | `/api/events/{id}/review` | Approve, edit, reject, or expire an event |
| `GET` | `/api/stream/events` | Receive event changes over SSE |
| `GET` | `/api/graph/network` / `/api/graph/snapshot` | Read network and active disruption snapshot |
| `POST` | `/api/routes/query` | Recompute route candidates against the current snapshot |
| `POST` | `/api/sim/load` | Estimate route allocation and capacity shortfall from supplied estimates |
| `GET` | `/api/sim/result?scenario_id=...` | Read a checked-in precomputed simulation result |
| `GET` | `/api/health` / `/api/health/deep` | Check process health or core local readiness |
| `GET` | `/api/meta` | Read snapshot and data-source disclaimer |

## Architecture

The diagram shows the implemented event-to-route API flow, the optional AI assistance boundary, and the separately scoped simulation work. The editable SVG is the source for the PNG.

![Resilient Public Travel architecture](docs/architecture/resilient-public-travel.png)

Source: [SVG diagram](docs/architecture/resilient-public-travel.svg). The broader product and algorithm design is documented in [docs/plan/02-architecture.md](docs/plan/02-architecture.md).

## Data and Limitations

Some source data comes from public agency feeds or published records. Derived values and synthetic fixtures are labelled separately. Current simulation inputs, passenger demand, route capacities, and residual capacity are simulated or estimated; they are not live measurements. A report or inferred anomaly is not an official service bulletin. Review decisions are required before an event changes the route graph.

The backend and frontend have local startup and container configuration. **No public deployment address or external wake-up check is currently verified.** Cloud hosting instructions are in [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md); those instructions are not evidence of a live deployment. For current M2 C-side evidence and gaps, see [docs/acceptance/m2-c-status.md](docs/acceptance/m2-c-status.md).

## Project Layout

```text
backend/                 FastAPI event composition, route engine, and C-Sim
contracts/seed/          Frozen demo inputs and API contract fixtures
data/                    Network data, provenance, quality notes, and simulation results
deploy/                  Docker, offline fallback, and deployment instructions
docs/architecture/       Editable SVG architecture diagram and PNG export
docs/plan/               Scope, contracts, architecture, and milestone plan
frontend/                React and TypeScript user interface
scripts/                 Startup, validation, preflight, and M1 demo
```

## Deployment

See [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md) for local, Docker, and proposed cloud deployment instructions. Cloud deployment remains unverified.

## License

This is an academic hackathon project. Data sources are attributed in [data/PROVENANCE.md](data/PROVENANCE.md).
