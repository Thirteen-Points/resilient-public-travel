# M2 C-Side Status

Date: 2026-09-30
Scope: C-owned M2 work in `docs/plan/05-timeline.md` and T9.2 in `docs/plan/04-workstreams.md`.

## Completed or Available

- **M1 backend event-to-reroute path is implemented.** The combined app wraps the event store so creates and updates synchronize active published events to the route engine snapshot (`backend/app/main.py`). The route API queries the current engine. `scripts/demo_m1_story.py` describes checks for report intake, event merge, human publication, graph closure, and route recomputation.
- **Frontend API mode has refresh wiring.** The event API subscribes to SSE and the application refreshes published events and routes (`frontend/src/api/eventApi.ts`, `frontend/src/App.tsx`). Fixed seed mode remains a static illustrative scenario.
- **Seed files are present and readable.** `scripts/preflight.py` completed successfully and reported: “PASS: four seed files readable; 1 documented warning(s).” The warning is that `evt_seed_003` is a simulated published demo event.
- **Local and container launch instructions exist.** See `scripts/start.bat`, `scripts/start.sh`, and `deploy/docker-compose.yml`.
- **M2 documentation deliverables are present.** The root README describes current functionality and limits; the editable architecture source and PNG are in `docs/architecture/`.

## Not Yet Verified or Incomplete

- **M1 live demo run is blocked in this environment.** Attempted to launch the app with an isolated temporary SQLite database on port 18080. The bundled Python raised `ModuleNotFoundError: No module named 'uvicorn'`. No system `python` or `py` executable is available, and the bundled runtime also lacks FastAPI, Uvicorn, and NetworkX. Therefore the demo script has not produced a successful run result here.
- **M1 visual end-to-end acceptance remains unverified.** The demo script exercises backend HTTP behavior; it does not capture a browser run proving that the map and route cards visibly refresh after publication.
- **T9.2 public deployment is incomplete/unverified.** No public frontend or API URL, Cloudflare Pages/Render deployment record, keep-alive monitor, or 10-minute idle/30-second wake-up evidence was found. `deploy/DEPLOYMENT.md` contains instructions and a placeholder URL only.
- **Seed contract coverage is partial.** The four files parse, but `contracts/README.md` says Network, Route, and Simulation do not yet have JSON Schemas for full contract validation. `contracts/seed/sim.seed.json` is explicitly a simulated placeholder per `backend/app/sim/M0_HANDOFF.md`.
- **C-Sim outputs are not operational evidence.** `/api/sim/load` computes a capacity allocation from supplied route estimates, and `/api/sim/result` serves precomputed results. M0 verification is algorithm consistency against simulated fixtures, not validation of measured demand or operator capacity.

## M2 and P3/M3 Boundary

The 10,000-person strategy comparison is assigned to P3/M3 in `docs/plan/05-timeline.md` (10/5–10/11). Files named `data/sim/m2-*` are early preparation, not M2 interim deliverables or acceptance evidence. Their inputs and outputs are simulated. In the current comparison, guided total delay is 24,682.4 person-minutes versus 15,088.4 baseline (63.6% higher), and the model does not account for shared capacity across overlapping route segments. This run does not show a benefit or establish real-world capacity.

## Checks Run

| Check | Result |
|---|---|
| `python scripts/preflight.py` using the bundled Python runtime | Passed; four seed files readable, one documented simulated-event warning |
| Start a local API with temporary SQLite, then run `scripts/demo_m1_story.py` | Blocked before startup: bundled Python has no `uvicorn`; system Python launchers unavailable |
| Cloud deployment / idle wake-up | Not tested; no deployed address or credentials available in the repository |
