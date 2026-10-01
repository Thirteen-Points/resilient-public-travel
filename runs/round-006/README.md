# Round 006 — M2 post-merge closeout

Started: 2026-10-01. Orchestrator: Codex. Baseline: GitHub `main` `4e95f25`, already containing the earlier M1/M2 merges. Milestone branch: `XMQM2`; work used an isolated checkout and never edited `main` directly.

This round follows M1 Round 005 and records four bounded tasks. Files shared by tasks were changed sequentially. All local demonstrations use modelled transport data and a temporary database.

| Task | Owner | Allowed files | Acceptance |
|---|---|---|---|
| A: requirements and page disclosure | A / UI implementer | `frontend/src/**`, `report-a.md` | Check the required bilingual text and source metadata in the actual browser. |
| B: T2.6 and expiry contracts | B / backend implementer | `backend/app/services/structure/**`, `backend/tests/test_structure_provider.py`, `backend/tests/test_b_replan_handoff.py`, `docs/coordination/T2.6-real-model-acceptance.md`, `scripts/run_t2_6_acceptance.py`, `report-b.md` | Real-model claim only with approved ten real samples; otherwise report partial. Automatic expiry must reconcile once and reach graph, routes, and SSE. |
| C: shared app integration | C / backend implementer | `backend/app/main.py`, `backend/tests/test_persona_preparse.py`, `report-c.md` | Persona parse route responds through the shared application. |
| D: independent verification | D / reviewer, read-only except `report-d.md` | `report-d.md` | Check status, tests, browser evidence, and remaining risks without upgrading partial work to completed. |

The orchestrator owns this README, synthesis, next-round plan, WorkBuddy prompt, Git review, commits, and the outer `PROJECT_STATE.md`.
