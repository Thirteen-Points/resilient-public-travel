# Deployment Guide - ResilientRoute

> How to deploy, configure, and run ResilientRoute.

---

## 1. Prerequisites

- Python 3.11+ (3.12 recommended)
- Git
- (Optional) Docker & Docker Compose
- (Optional) Node.js 18+ for frontend development

---

## 2. Quick Start

### Option A: One-click script (recommended)

**Linux/Mac:**
```bash
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
./scripts/start.sh
```

**Windows:**
```cmd
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
scripts\start.bat
```

The script will:
1. Create a virtual environment
2. Install Python dependencies
3. Validate data files
4. Start the FastAPI server on port 8000

### Option B: Docker

```bash
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
docker-compose -f deploy/docker-compose.yml up
```

### Option C: Manual

```bash
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -r backend/requirements.txt
python scripts/validate_data.py
python -m uvicorn backend.app.main:app --reload --port 8000
```

---

## 3. Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

### Key settings:

| Setting | Default | Purpose |
|---|---|---|
| `HOST` | 0.0.0.0 | Server bind address |
| `PORT` | 8000 | Server port |
| `OFFLINE_MODE` | false | If true, no external API calls |
| `AI_ENABLED` | false | If true, LLM-based features enabled (`LLM_ENABLED` is a legacy alias) |
| `DEEPSEEK_API_KEY` | (empty) | Server-side provider API key; Qwen/GLM have their own named keys |
| `DEBUG` | true | Enable debug logging |

**The system starts without any API key.** LLM is optional and never on the critical path.

See [P3 acceptance](P3-ACCEPTANCE.md) for persistent database migration, CI,
startup flag verification and the online redeployment acceptance procedure.

---

## 4. Offline Mode

For demos without internet:

```bash
./scripts/start.sh --offline
```

Or set `OFFLINE_MODE=true` in `.env`. In offline mode:
- No external API calls (HKO, MTR, KMB)
- LLM disabled (deterministic fallback)
- All data served from local JSON files
- Full demo scenario (TAW->ADM, ERL cross-harbour closed) works

---

## 5. Health Check

### Basic (process alive):
```bash
curl http://localhost:8000/api/health
```

### Deep (core function available):
```bash
curl http://localhost:8000/api/health/deep
```

### Pre-flight check (before demo):
```bash
python scripts/preflight.py
```

---

## 6. API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Root info |
| GET | `/docs` | Swagger UI |
| GET | `/api/health` | Basic health check |
| GET | `/api/health/deep` | Deep health check |
| GET | `/api/meta` | Sources, freshness, disclaimer |
| GET | `/api/graph/network` | Full transit network |
| GET | `/api/graph/snapshot` | Current graph snapshot |

---

## 7. Production Deployment

### Cloudflare Pages (Frontend) + Render (Backend)

The repository now includes a Render Blueprint at `render.yaml`. From the
Render Dashboard, create a Blueprint instance from this repository and select
the `main` branch. Leave Root Directory empty (repository root). Render builds
with `pip install -r backend/requirements.txt`, starts with
`uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`, and checks
`/api/health/deep`. The Blueprint generates a private `REVIEW_API_TOKEN`.

After the first successful deploy:

1. Copy the service origin, such as `https://<service>.onrender.com`.
2. In the Cloudflare Pages project, set the production build variable
   `VITE_API_BASE_URL` to that origin, then redeploy the frontend.
3. Add the repository Actions variable `RENDER_API_URL` with the same origin.
   `.github/workflows/render-health-ping.yml` can then be run manually and,
   after this branch is merged to the repository's default branch, on a
   ten-minute schedule.
4. Check `https://<service>.onrender.com/api/health` and
   `/api/health/deep`; both should return HTTP 200 before testing the site.

The backend permits only the exact production Pages origin configured by
`CORS_ALLOWED_ORIGINS`; do not replace it with `*`. The review API is protected
by `REVIEW_API_TOKEN`. Do not put that secret in `VITE_REVIEW_TOKEN` for a
public site: Vite embeds `VITE_*` values in downloadable browser code. Public
published-event reads and route queries are separate from protected review
operations. The review console needs a private/authenticated delivery path
before it can safely be enabled for public users.

The Blueprint uses a paid Starter instance with one 1 GB persistent disk mounted
at `/opt/render/project/src/backend/app/data`. This contains `events.sqlite3`,
shared by user reports, Events, and audit history. Initialization runs at startup,
when the disk is available. Do not remove the disk or switch to Free if reports
must survive redeploys. Disk-backed services run as one instance and have brief
downtime on deploys. Use SQLite-native backups for database recovery.

Live acceptance must include `/api/health/deep`, `/docs`, route queries,
published Events, simulation results, AI fallback, exact Pages CORS preflight,
and a clearly labelled test report. Read the report with reviewer authorization
before and after a redeploy to verify actual Render disk persistence.
Local tests alone do not establish live deployment or disk persistence.

---

## 8. Data Directory Structure

```
data/
├── network/
│   ├── stations.json      # Station/node data with coordinates
│   ├── lines.json         # Transit lines with headways, capacities
│   ├── walk_links.json    # Walking connections
│   └── bus_routes.json    # Bus route verification log
├── access/
│   └── access_points.json # Access points within 800m catchment
├── sim/
│   └── (sim results go here)
├── calendar.json          # Service calendar (4 schedule types)
├── weather_impact.json    # Weather penalty factors
├── capacity_method.md     # Capacity calculation methodology
├── PROVENANCE.md          # Data provenance ledger
└── DATA_QUALITY.md        # Data quality check results
```

---

## 9. Security Notes

- **No real secrets** are stored in the repository
- `.env` is in `.gitignore` and never committed
- `.env.example` contains only placeholders, no real values
- API keys are read from environment variables at runtime
- The system works without any API key (offline/deterministic mode)
