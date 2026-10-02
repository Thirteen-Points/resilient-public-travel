# P3 C integration report

Date: 2026-10-02. Working branch: **ZYC-P3**. Implementation base:
`6d112ca67b9d36ddaf7680de0bc71b389da34540`.
The existing remote ZYC-P3 history is retained; no implementation changes were
written or merged to main. Original ZYC-M1 working files remain intact.

## Independent work completed

| P3 gap | Local outcome | Remaining acceptance |
|---|---|---|
| R1 storage/config | Docker mounts the complete SQLite parent, including event/audit, admin/source state and model usage; flags override offline/AI settings; model defaults use `deepseek-flash` | Actual container recreation runs in the new CI job; existing deployments need the documented backup/migration before volume replacement |
| R2 publish/deploy | Isolated real browser publication, approval isolation, three refresh timings, polling recovery and mobile checks pass; API/public frontend build identities added | Live reviewer/UI timings and Render disk-preserving redeployment, with deployed SHAs |
| R3 Agent/tools | Nine registered tools; existing B preferences reused; request context and diagnostics isolated; optional model wording preserves computed routes; actual model paths share durable usage/cache/budget | A connects the visible Agent panel; intended DeepSeek key/model live acceptance |
| R4 collection | Main lifespan owns HKO/MTR workers; persisted configuration/state, source leases, cadence, backoff, offline/disable guards and graceful drain; public safe source status | B verifies official live signal behavior; A displays source status |
| R5 simulation/profiles | Shared directed-segment capacity, protected/wheelchair constraints, fixed-seed 10,000/30-OD results and explicit stress scenario; real calendar and approved-weather runtime consumption; load/weather/expiry triggers and reasons | A connects persona comparison/simulation dashboard and replan banners; verified live passenger-load provider remains absent |
| R6 regression | Backend/engine/cross-module tests, frontend tests/build/admin bundle, browser and real Docker recreation workflow on main/ZYC-P3/PR; failure evidence uploaded | GitHub execution and administrator-required checks must be recorded separately |

Load observations are reviewer-authenticated **simulated exercises** by default.
They trigger recalculation, not a fabricated live load feed or automatic route
weight changes. Collector Signals stay unverified until human review; only last
approved weather/event facts affect the route engine. A one-second local watcher
reconciles approved event windows and weather start/expiry changes.

## Local evidence

Final test/build counts and browser assertions are in
[`evidence/p3/c/local-validation.json`](evidence/p3/c/local-validation.json).
The real local browser measured publication refreshes of **262, 126, 239 ms** and
polling withdrawal of **3452 ms**, with no page errors. These are local measurements
on an isolated SQLite store, not an online SLA or percentile claim.

Local performance samples: fresh engine + query P95 **26.126 ms** (25 samples),
cached query P95 **3.053 ms** (50 samples), cached P3 simulation read P95
**0.069 ms** (25 samples). These use simulated seed data and exclude interpreter
startup/network latency. Raw values are in `evidence/p3/c/local-performance.json`.

Backend tests cover actual model runtime/fallback, billed schema failures,
provider cache tokens, restart accounting, concurrent reservations, per-request
diagnostics, invalid wording failover and offline/startup override. Source tests
cover collection dedup/state restart, disable/stop drain, observation cadence,
lease exclusion, failed observations and the commit-before-thread-return race.
The main lifecycle test verifies an approved future weather window becomes active
and triggers real route/diversion recomputation, then shuts workers down.

No paid model call, live collection, online event mutation or Render deployment
was performed. The local machine has no Docker runtime. The configured Docker
recreation workflow is a pending platform check until its job actually passes.
The remaining Vite large-chunk warning is unchanged; it does not fail the build.

## Simulation result boundaries

Both strategies use the same 44 directed shared-segment resources and fixed
population/OD distribution. Actual results:

| Simulated case | Baseline served | Guided served | Baseline delay (person·min) | Guided delay |
|---|---:|---:|---:|---:|
| Normal shared-segment input | 10000 | 10000 | 32103.4 | 32103.4 |
| Explicit 10% residual-capacity stress | 9690 | 9801 | 125121.6 | 123138.1 |

Normal input shows no claimed guided benefit. Stress input is a sensitivity test,
not measured real occupancy. Wheelchair unmet demand is zero in these specific
simulated cases; dedicated wheelchair berths and actual accessibility have not
been certified. The extra-route-delay constraint does not guarantee queue delay.
See [`data/sim/p3-shared-capacity-report.md`](../../data/sim/p3-shared-capacity-report.md)
and its full input/version/reproduction evidence.

## Handoff and online execution

- A: consume `/api/ai/chat`, `/api/persona/parse`, `/api/sources/status`,
  `/api/replanning/status` and new cached P3 simulation IDs; render factual
  fallback/source/simulation assumptions. Connect dashboard and comparison UI.
- B: verify live HKO/MTR categorical signals, provenance, service-calendar and
  weather policy data; obtain/verify a real load provider before enabling one.
- C/platform maintainer: configure the intended DeepSeek key and explicit live
  test; run the Render/public review and persistence procedure; record deployed
  frontend/backend SHA, retained IDs/revisions/audit/source/usage counts and timings.
  Enable and verify required GitHub checks after a successful run.

Setup/procedures: [`deploy/DEEPSEEK.md`](../../deploy/DEEPSEEK.md),
[`deploy/P3-ACCEPTANCE.md`](../../deploy/P3-ACCEPTANCE.md),
[`P3 runtime replan handoff`](../coordination/P3-C-runtime-replanning.md).
P3 as a whole remains open until these cross-team and live acceptance items pass.
