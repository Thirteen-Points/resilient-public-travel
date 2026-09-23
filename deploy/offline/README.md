# Offline Package - ResilientRoute

> This directory contains the minimal offline data package for ResilientRoute.
> The system can run a complete demo without any internet connection.

## Quick Start (Offline Mode)

### Windows
```bash
scripts\start.bat --offline
```

### Linux/Mac
```bash
./scripts/start.sh --offline
```

### Docker
```bash
docker-compose -f deploy/docker-compose.yml up
```

### Direct Python
```bash
# Set OFFLINE_MODE=true in .env (or export OFFLINE_MODE=true)
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## What's Included

| Data | Description | Provenance |
|---|---|---|
| Network (stations/lines/walk) | 16 MTR stations, 4 bus stops, 2 piers, 13 lines, 7 walk links | real / real-derived |
| Service calendar | 3 schedule types, 2026 public holidays | real |
| Bus routes | 16 serving routes, 12 excluded routes | real-derived |
| Access points | 21 access points at 6 corridor stations | real-derived |
| Weather impact | 7 weather condition penalty factors | simulated |
| Seed events | 3 event cards (confidence 0.2/0.55/0.9) | simulated |
| Seed routes | 8 candidate routes for TAW->ADM | real-derived |
| Seed sim | 10k population guided vs unguided comparison | simulated (placeholder) |

## Data Sources & Provenance

See `data/PROVENANCE.md` for the complete provenance ledger.

**Key principle**: No unverified data is marked as `real`. All estimated values are
labelled `real-derived`. All simulated values are labelled `simulated`.

## Limitations in Offline Mode

1. No real-time weather warnings (HKO API not called)
2. No real-time MTR schedule (getSchedule API not called)
3. No real-time bus ETA (KMB API not called)
4. No LLM-based event structuring (uses rule-based fallback)
5. Sim results are placeholder values (must be replaced by C-Sim)

## Demo Scenario

The offline package supports the primary demo scenario:
- **Origin**: Tai Wai (TAW)
- **Destination**: Admiralty (ADM)
- **Event**: Signal failure on ERL Hung Hom -> Exhibition Centre (cross-harbour)
- **Result**: 8 alternative routes avoiding the affected segment

## Verification

Run `python scripts/validate_data.py` to verify all data files.
Run `python -m pytest tests/` to run all tests.
