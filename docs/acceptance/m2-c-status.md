# M2 C-Side Status

Date: 2026-10-01
Scope: C-owned M2 work in `docs/plan/05-timeline.md` and T9.2 in `docs/plan/04-workstreams.md`.

## Completed or Available

- **M1 backend event-to-reroute path is implemented.** The combined app wraps the event store so creates and updates synchronize active published events to the route engine snapshot (`backend/app/main.py`). The route API queries the current engine. `scripts/demo_m1_story.py` describes checks for report intake, event merge, human publication, graph closure, and route recomputation.
- **Frontend API mode has refresh wiring.** The event API subscribes to SSE and the application refreshes published events and routes (`frontend/src/api/eventApi.ts`, `frontend/src/App.tsx`). Fixed seed mode remains a static illustrative scenario.
- **Seed files are present and readable.** `scripts/preflight.py` completed successfully and reported: “PASS: four seed files readable; 1 documented warning(s).” The warning is that `evt_seed_003` is a simulated published demo event.
- **Local and container launch instructions exist.** See `scripts/start.bat`, `scripts/start.sh`, and `deploy/docker-compose.yml`.
- **M2 documentation deliverables are present.** The root README describes current functionality and limits; the editable architecture source and PNG are in `docs/architecture/`.

## Not Yet Verified or Incomplete

- **M1 end-to-end demo: completed once per A's report.** The run log or screenshot is not checked into this repository, so the report is team-confirmed rather than independently artifact-audited here. A repeat attempt in this environment was blocked before startup because the bundled Python lacks `uvicorn`; no system `python` or `py` executable is available.
- **M1 browser evidence is not archived.** A reports running the demo, but this repository does not include a recording or screenshot of the map and route-card refresh. Preserve the successful run as completed; add the capture if submission evidence is required.
- **T9.2 C-side deployment package is ready; live API deployment is not verified.** The frontend is available at `https://resilient-public-travel.pages.dev/`, but this is not evidence that the Render API is deployed or connected. `render.yaml` now defines the API service, exact Pages CORS origin, build preflight, health check, and safe offline defaults. The Pages build still needs the Render URL in `VITE_API_BASE_URL`, and the repository Actions variable `RENDER_API_URL` must be set before health pings can run. Those steps require account access and must be performed by a repository/Render administrator.
- **Keep-alive and cold-start target need an explicit limitation.** The scheduled GitHub Actions ping is prepared, but only runs after the workflow is on the repository's default branch and `RENDER_API_URL` is set. Render Free may sleep after 15 minutes idle and can take about one minute to wake, so the plan's 30-second cold-start criterion cannot be guaranteed on that tier. Its filesystem is ephemeral, so SQLite report/review data is not durable.
- **Seed contract validation is complete on this branch.** All four seed bundles pass their JSON Schemas; Event and Signal items also pass Pydantic validation. Cross-file checks cover declared network counts, line-stop and walk-link node references, route leg endpoints and line IDs, persona route IDs, and simulation route IDs. `contracts/seed/sim.seed.json` remains an explicitly simulated placeholder per `backend/app/sim/M0_HANDOFF.md`.
- **C-Sim outputs are not operational evidence.** `/api/sim/load` computes a capacity allocation from supplied route estimates, and `/api/sim/result` serves precomputed results. M0 verification is algorithm consistency against simulated fixtures, not validation of measured demand or operator capacity.

## M2 and P3/M3 Boundary

The 10,000-person strategy comparison is assigned to P3/M3 in `docs/plan/05-timeline.md` (10/5–10/11). Files named `data/sim/m2-*` are early preparation, not M2 interim deliverables or acceptance evidence. Their inputs and outputs are simulated. In the current comparison, guided total delay is 24,682.4 person-minutes versus 15,088.4 baseline (63.6% higher), and the model does not account for shared capacity across overlapping route segments. This run does not show a benefit or establish real-world capacity.

## Checks Run

| Check | Result |
|---|---|
| `python scripts/preflight.py` using the bundled Python runtime | Passed; four seed files readable, one documented simulated-event warning |
| `python scripts/validate_contract_seeds.py` | Passed; all four seeds satisfy JSON Schema, Event / Signal satisfy Pydantic, and cross-file IDs/counts are consistent |
| `python -m unittest backend.tests.test_contract_seeds -v` | Passed; 14 focused tests, including rejection of malformed fields and invalid cross-file references |
| M2 route, multi-OD, adapter, seed and runtime CORS config tests | Passed; 26 focused tests in the bundled runtime |
| A's M1 end-to-end demo run | Reported complete once; run evidence is not checked into the repository |
| Repeat the local API/demo run in this environment | Blocked before startup: bundled Python has no `uvicorn`; system Python launchers unavailable |
| Render deployment / external API smoke test | Pending administrator connection of the `ZYC-M2` branch and Render account |
| Cloudflare-to-Render browser test / keep-alive / cold-start timing | Pending Render URL, Pages environment update, and default-branch merge; Free-tier wake-up may exceed 30 seconds |
