# Round 005 — M1/M2 post-merge closeout

Started: 2026-10-01. Orchestrator: Codex. Baseline: GitHub `main` at `4e95f25`.

## Tasks, ownership, and boundaries

| Task | Owner | Allowed files | Acceptance |
|---|---|---|---|
| M1 full chain | Orchestrator with A/B/C review | `scripts/demo_m1_story.py`, `runs/round-005/M1-report.md` | Actual local HTTP report/review/reroute run, relevant tests, browser route and map inspection. Upload to `XMQM1`. |
| M2 T2.6 | B with C adapter review | `backend/app/services/structure/`, `backend/tests/`, `docs/coordination/T2.6-real-model-acceptance.md`, round report | Ten team-approved real texts, at least eight first-pass schema-valid outputs, real provider record and safe fallback; otherwise explicitly partial. Upload validated work to `XMQM2`. |
| M2 expiry and reroute | B backend, C route engine, A browser; orchestrator owns shared entrypoint | `backend/app/api/`, `backend/app/services/review_state.py`, `backend/tests/`, `frontend/src/`, round report | Automatic expiry yields one audit update, SSE notice, graph restoration and route recomputation, with browser evidence. Upload to `XMQM2`. |
| M2 persona and disclaimer | B API, A UI; orchestrator owns `backend/app/main.py` | `backend/app/main.py`, `backend/app/api/persona.py`, `backend/tests/`, `frontend/src/`, `backend/app/api/disclaimer.md`, round report | Shared app exposes persona parse; bilingual disclaimers are visible in pages and cards; browser check. Upload to `XMQM2`. |

Tasks sharing `backend/app/main.py`, `backend/tests/`, or `frontend/src/` execute sequentially. Reports state actual commands and separate code, local tests, browser observations, and GitHub merge state.
