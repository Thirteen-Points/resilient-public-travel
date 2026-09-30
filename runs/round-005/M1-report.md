# M1 post-merge full-chain report

Status: **partial milestone acceptance; executable local chain passed**. Browser and local HTTP checks used simulated reports and modelled route data; no live incident, production deployment, or complete M1 card-content audit was certified.

## Work completed and files changed

- Started from fetched GitHub `main` `4e95f25`, which contains PR #85 (`XMQM1`) and PR #91 (`XMQM2`), in an isolated worktree. The original `XMQM2` checkout and its untracked `.venv-readme-b/` were not changed.
- Corrected `scripts/demo_m1_story.py`: the old check looked for a separate `HUH→EXC` public leg, but the route API combines ERL corridor edges into a `TAW→ADM` leg. The demo now uses the documented 08:20 HKT checkpoint, proves a direct ERL candidate exists before closure and disappears after closure, and verifies route IDs change.
- Created `runs/round-005/README.md` and this report. No other source files changed.

## Commands actually run and results

All commands ran in the isolated repository worktree on 2026-10-01, except the stated frontend subdirectory commands. `AI_ENABLED=false`, `OFFLINE_MODE=true`, and `PYTHONPATH=<worktree>;<worktree>/backend` were set for Python tests and the local server. A temporary SQLite database under Windows `%TEMP%` and a demo-only review token were used; no credential or generated environment was committed.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests/cross_module -v` | Initial run: 4 import errors because the existing virtual environment lacked declared `python-dotenv`. After installing that dependency, 20 tests passed, exit 0. |
| `python -m unittest discover -s backend/tests` | 189 passed, exit 0. |
| `python -m uvicorn` via `create_app(db_path=<temporary SQLite>, review_token=<demo token>)` | Local HTTP server started at `127.0.0.1:8765`. |
| `python scripts/demo_m1_story.py` against that server | All steps passed, exit 0: two reports accepted, confidence 0.20→0.55→0.60, published event closed `HUH↔EXC`, 08:20 route candidates changed 10→9, direct ERL `TAW→ADM` candidate 1→0, route IDs changed. |
| Frontend `tsc --noEmit` | Passed, exit 0. |
| Frontend `vite build --configLoader runner` | Passed, exit 0. A chunk-size warning remains. |
| Frontend `vitest run` | Did not start: this local pnpm/esbuild configuration could not resolve the Windows config path. No test pass is claimed. |
| `git diff --check` | Passed; Git noted possible local LF/CRLF conversion. |

The standard `vite build` and development server hit the same local config/dependency-scanner path problem. The production build with Vite's runner config loader and its preview server did run; browser observations below used that build. This is a local tooling limitation, not an inferred application failure.

## Browser observations

The in-app browser opened the built frontend at `127.0.0.1:5173` in API mode, connected to the local backend, and selected Tai Wai → Admiralty at 08:20 HKT. After the demo published its event, the page showed the disruption banner and three alternative route cards without the direct ERL option. After a reviewer `expire` API action, the banner disappeared and the first card became direct East Rail Line, 18–21 minutes. This occurred without a page reload, using the active event stream / polling session. Screenshots were visually inspected before and after; no timing SLA was measured. The map displayed the corridor and refreshed with the event state, but the route-card and banner changes are the strongest browser evidence recorded here.

## Findings, risks, and next action

- The full B→C HTTP chain and A route-card refresh now have local evidence. Source data and user reports in this run are simulated; the user-report channel's `real` label does not verify the incident.
- The seven required route-card elements and the five-minute demo script still need a separate M1 checklist. T2.6 real-model acceptance, live HKO/MTR sources, and production deployment are not established by this run.
- Next: push this focused M1 change to `XMQM1`, open a PR to `main`, then proceed to M2 tasks on a fresh `main` baseline.
