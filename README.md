# Resilient Public Travel

A hackathon project by **Thirteen Points** — building a resilient public transit routing system for Hong Kong's East Rail Line corridor.

## What This Project Does

When a major transit disruption hits the East Rail Line (Tai Wai → Admiralty), the system:
1. **Detects** the event from multiple sources (HKO weather, MTR eta anomalies, social media, user reports)
2. **Routes** passengers via alternative modes (bus, minibus, ferry, parallel MTR lines) with accessibility-aware scoring
3. **Simulates** 10,000 travellers under selfish vs guided diversion strategies, showing honest capacity gaps
4. **Displays** everything on an interactive map with provenance badges and confidence animations

## Quick Start

### Prerequisites
- Python 3.11+
- No API keys required — the system runs fully offline by default

### One-Click Run

**Linux / macOS:**
```bash
./scripts/start.sh
```

**Windows:**
```cmd
scripts\start.bat
```

This will:
1. Create a virtual environment and install dependencies
2. Validate all data files
3. Start the FastAPI server on `http://localhost:8000`

### Offline Mode
```bash
./scripts/start.sh --offline    # Linux/macOS
scripts\start.bat --offline     # Windows
```

All data is loaded from local JSON files — no internet connection needed.

### Docker
```bash
cd deploy && docker-compose up --build
```

The Docker image defaults to offline mode with LLM disabled.

## Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Basic liveness — is the process alive? |
| `GET /api/health/deep` | Deep readiness — are data files loaded, directories present, core functions available? |
| `GET /api/meta` | Data freshness, sources, and disclaimer |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/health/deep` | Readiness check with data/LLM status |
| GET | `/api/meta` | Freshness, sources, disclaimer |
| GET | `/api/graph/network` | Full transit network (nodes, lines, walk links) |
| GET | `/api/graph/snapshot` | Current snapshot with affected edges |

> Route query, simulation, and AI chat endpoints will be added by C-Route, C-Sim, and C-AI agents respectively.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │           Frontend (A)           │
                    │   React + Leaflet + TypeScript  │
                    └──────────┬──────────┬───────────┘
                               │          │
                    /api/routes  /api/sim  /api/graph
                               │          │
                    ┌──────────▼──────────▼───────────┐
                    │         FastAPI Backend          │
                    │  ┌─────────┐ ┌────────────────┐  │
                    │  │ Event   │ │  Graph Engine  │  │
                    │  │ Pipeline│ │  (C-Route)     │  │
                    │  │ (B)     │ │                │  │
                    │  └────┬────┘ └───────┬────────┘  │
                    │       │              │            │
                    │  ┌────▼──────────────▼────────┐  │
                    │  │   Simulation Engine (C-Sim) │  │
                    │  └─────────────┬───────────────┘  │
                    │       ┌───────▼────────┐         │
                    │       │  AI Layer (C-AI)│         │
                    │       │  DeepSeek→Qwen   │         │
                    │       │  →GLM→rules      │         │
                    │       └──────────────────┘         │
                    └──────────────────────────────────┘
                               │
                    ┌──────────▼──────────────────────┐
                    │         Data Layer (C-Data)      │
                    │  stations.json  lines.json       │
                    │  walk_links.json  bus_routes.json│
                    │  calendar.json  weather_impact   │
                    │  PROVENANCE.md  DATA_QUALITY.md   │
                    └─────────────────────────────────┘
```

## Data Provenance

Every data value is tagged with one of three levels:

| Level | Badge Color | Meaning |
|---|---|---|
| `real` | Green | From official source, verified |
| `real-derived` | Yellow | Computed/estimated from real data |
| `simulated` | Blue | Synthetic, for demonstration only |

See `data/PROVENANCE.md` for the full provenance ledger.

## Configuration

Copy `.env.example` to `.env` and adjust as needed. All settings have safe defaults:

```bash
cp .env.example .env
```

Key defaults:
- `LLM_ENABLED=false` — system works without any LLM API key
- `OFFLINE_MODE=false` — but all data is local, so it works offline anyway
- `API_HOST=0.0.0.0`, `API_PORT=8000`

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run data validation
python scripts/validate_data.py

# Run preflight check (demo readiness)
python scripts/preflight.py
```

## Project Structure

```
resilient-public-travel/
├── data/                    # Transit data with provenance
│   ├── network/             # Stations, lines, walk links, bus routes
│   ├── access/              # 800m catchment access points
│   ├── PROVENANCE.md        # Data source ledger
│   ├── DATA_QUALITY.md      # Quality check results
│   ├── calendar.json        # Service calendar (weekday/Sat/Sun+PH)
│   ├── capacity_method.md   # Capacity calculation methodology
│   └── weather_impact.json  # Weather penalty factors
├── backend/                 # FastAPI backend
│   └── app/
│       ├── api/             # Health, meta, graph endpoints
│       ├── config/          # Pydantic settings
│       └── ...              # graph/engine/sim/ai (stubs for other agents)
├── scripts/                 # Startup, validation, preflight
├── deploy/                  # Docker, offline package, docs
├── tests/                   # Automated tests
├── contracts/               # Interface contracts and seed data
└── docs/                    # Project documentation
```

## Deployment

See `deploy/DEPLOYMENT.md` for the full deployment guide and `deploy/TROUBLESHOOTING.md` for common issues.

## License

This is an academic/hackathon project. Data sources are attributed in `data/PROVENANCE.md`.
