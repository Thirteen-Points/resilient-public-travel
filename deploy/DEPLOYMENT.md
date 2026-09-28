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
| `LLM_ENABLED` | false | If true, LLM-based features enabled |
| `LLM_API_KEY` | (empty) | Your DeepSeek/Qwen/GLM API key |
| `DEBUG` | true | Enable debug logging |

**The system starts without any API key.** LLM is optional and never on the critical path.

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

### Cloudflare Pages (Frontend) + Render Free (Backend)

1. **Frontend**: Deploy `frontend/` to Cloudflare Pages
2. **Backend**: Deploy to Render Free with:
   - Build: `pip install -r backend/requirements.txt`
   - Start: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - Set `OFFLINE_MODE=false`, `LLM_ENABLED=true` (with API key)
3. **Keep-alive**: Use UptimeRobot to ping `/api/health` every 10 minutes

### Keep-alive cron job:
```bash
# Add to crontab (Linux) or Task Scheduler (Windows)
*/10 * * * * curl -s https://your-app.onrender.com/api/health > /dev/null
```

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
