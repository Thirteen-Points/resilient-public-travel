# B task and acceptance

Owner: B. Status scope: local P3 preparation plus M2 closeout verification. Permitted writes: `backend/app/services/persona.py`, `backend/app/api/persona.py`, `backend/app/main.py` during this exclusive local worktree session, B-owned `backend/tests/test_b_*.py`, `data/personas.json`, `data/presets.json`, `data/weather_impact.json`, `backend/app/ai/prompts/*.md`, B coordination documents, this round's B report. No A frontend or C engine/simulation edits.

Acceptance: five schema-valid profiles including wheelchair hard limits; three effective preset weight tables; public catalog and shared parser API; disabled/failed/invalid model falls back without weakening limits; weather coefficients are labelled simulated; prompt-injection numeric fabrication is rejected; one actual local browser query succeeds with AI disabled; event expiry and audit/SSE restoration tests pass. Record limitations and commands. Do not run T2.6 real-model sample acceptance.
