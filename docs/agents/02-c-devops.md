# Agent 2 — C-DevOps

Base branch: ZYC
Working location: ZYC (direct commits; no Agent branch)
Model: gpt-6-astra, reasoning high

## Scope
Implement T9.1, T9.3–T9.4: one-click startup scripts, deployment configuration, health check endpoints (basic liveness + deep readiness), offline fallback package, preflight verification script, deployment guide, and troubleshooting documentation.

## Files
Own `backend/app/` (skeleton: main, config, api/health, api/meta, api/graph), `scripts/` (start.sh, start.bat, preflight.py), `deploy/` (Dockerfile, docker-compose.yml, offline/), `.env.example`, `backend/requirements.txt`, and `tests/test_health.py` + `tests/test_startup.py`. Do not modify `data/` or `contracts/`.

## Startup guarantees
System must start without real API keys. LLM unavailable → deterministic logic still works. Missing external data → local example data from `data/`. Health check distinguishes "process alive" (basic) from "core function available" (deep). No real secrets in any committed file.

## Definition of done
One-click startup works on Linux/Mac (start.sh) and Windows (start.bat); `GET /api/health` returns liveness; `GET /api/health/deep` checks data files, directories, LLM config, and data sources; `.env.example` has all vars with safe defaults (LLM disabled, no keys); Docker image builds and runs offline by default; offline package includes all data files and README; preflight script gives all-green/all-red output; deployment and troubleshooting docs cover common issues; 77+ automated tests pass.
