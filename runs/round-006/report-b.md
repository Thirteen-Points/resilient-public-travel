# Agent B Report — Round 006

## Status

`partial`: automatic expiry integration passed; T2.6 real-model acceptance remains blocked on an approved corpus and model choice.

## Work Completed

- Added a synchronous JSON provider adapter compatible with the existing structurer and configured DeepSeek/Qwen/GLM providers, plus a CLI that requires exactly ten unique samples marked real and emits only safe result categories.
- Added provenance to acceptance sample records. The bundled simulated fixture is refused by the real-acceptance CLI.
- Added shared-app integration coverage for automatic expiry, single audit entry, SSE `auto_expired`, graph recovery and route ID restoration.
- Updated `docs/coordination/T2.6-real-model-acceptance.md` to state what is and is not accepted.

## Files Changed

- `backend/app/services/structure/acceptance.py`, `backend/app/services/structure/provider_client.py`, `backend/tests/test_structure_provider.py`, `backend/tests/test_b_replan_handoff.py`, `scripts/run_t2_6_acceptance.py`, `docs/coordination/T2.6-real-model-acceptance.md`.

## Findings and Evidence

- GitHub `main`, `XMQM2`, `FreddyM2` and `ZYC-M2` were checked; only the ten anonymized/rewritten `simulated` fixture texts were found. Existing handoff reports also say real model acceptance was not performed. No team-approved ten-real-text corpus was found.
- No real provider request was made. First-pass, retry and fallback counts for ten real texts are **unmeasured**, not zero.
- In a local API and browser run, an event with a 45-second window was published; after its deadline it became `expired` with final audit action `auto_expired`, graph snapshot had zero affected edges, and the connected browser banner changed to “No active published disruption.” That short-window run queried a next-day journey, so it did **not** demonstrate route ID change in that browser run. The integrated backend test does verify route ID change and restoration for a departure within the event window.

## Validation Performed

- `python -m unittest backend.tests.test_structure_provider backend.tests.test_structure_acceptance -v`: 5 passed.
- `python scripts/run_t2_6_acceptance.py --provider deepseek --samples backend/tests/fixtures/t2_6_acceptance_samples.json`: exited 1 with the expected simulated-corpus rejection, before provider selection or network call.
- `python -m unittest backend.tests.test_b_replan_handoff -v`: 3 passed, including automatic expiry across the shared app.
- `python -m unittest discover -s backend/tests`: 193 passed.
- A later repeat with the lightweight `.venv-readme-b` Python failed with six import errors because that environment lacks the declared `python-dotenv` dependency; rerunning discovery with the project's `.venv` Python passed all 193 tests. The failed environment run is not counted as a code failure or a pass.
- Local HTTP `GET /api/events`, `/api/events/published`, `/api/graph/snapshot` after expiry: event `expired`, final action `auto_expired`, no affected edges. Browser observation as above.

## Problems, Risks, or Unresolved Questions

- Team must identify and approve ten real texts, their use rights and the selected provider/model; actual provider calls and semantic fidelity review remain undone.
- The acceptance metric checks schema-valid first-pass rate, not factual extraction accuracy. Team review must check missing or invented facts before calling T2.6 complete.

## Recommended Next Action

- Run the documented CLI with the approved private corpus, record model/first-pass/retry/fallback per sample ID, then perform a human semantic review.
