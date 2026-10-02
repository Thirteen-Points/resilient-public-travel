# B/P3 collection and persona report

Status: **partial** on 2026-10-02. B's local service, queue, source-status API and
persona contracts are implemented. Shared-app integration, A/C use and online
acceptance remain open. No GitHub push or PR was made.

## Baseline and changed files

GitHub `main` was read with `git ls-remote` as `c2934c1fee124b41227a30f70b8628feb0b109ff`.
The local product worktree `b-p3-main` was created from that commit on
`codex/b-p3-20261002`. Existing `b-p3-prep` and other worktrees were left
untouched. Earlier network-restricted checks could not reach GitHub; a
command-scoped elevated read and fetch succeeded. The product repository has
no root `AGENTS.md`; the outer orchestration repository's instructions apply.

B-owned changes: `backend/app/services/ingest/{hko,mtr_eta,collection}.py`,
`backend/app/api/{sources,persona}.py`, `backend/app/services/persona.py`,
`data/{personas,presets}.json`, B tests and coordination documents. The persona
catalog was selectively brought forward from local `codex/b-p3-prep`; its
shared `main.py` edits were not copied. C owns registration in `main.py`.

## Implemented behavior

- `SourceCollectionService.start()/stop()/status()` provides two independent
  scheduler loops. `SOURCE_COLLECTION_ENABLED` defaults false, and
  `OFFLINE_MODE=true` prevents source requests. Poll requests have the existing
  per-request 10-second timeout, with up to three source attempts and bounded
  1/2-second retry waits. A source failure does not stop the other loop.
- Poller detector state, Signal rows, processing queue and source status are
  committed in the same SQLite database. A failed write restores the in-memory
  detector state so that the next poll can re-emit the observation. On restart,
  the persisted detector state prevents duplicate HKO/MTR emission. Simulated
  replay forces stored Signal provenance to `simulated`.
- New Signals run through the existing rule extractor and Event aggregator.
  Unmatched drafts are durable `pending_review` queue entries; merge ambiguity
  and processing errors remain visible for reviewer action. This service does
  not create a complete Event card, approve one or change a route. The existing
  approved-event snapshot boundary remains under C's shared app.
- A's read-only status fields and C's exact lifecycle snippet are in
  `P3-B-source-collection-handoff.md`. B's commuter/wheelchair requests and
  current A/C gaps are in `P3-B-persona-handoff.md`.

## Commands actually run and results

- `git ls-remote https://github.com/Thirteen-Points/resilient-public-travel.git refs/heads/main refs/heads/XMQM3`: `main=c2934c1`, no `XMQM3` ref returned.
- `.venv\Scripts\python.exe -m unittest backend.tests.test_b_collection backend.tests.test_b_persona_catalog backend.tests.test_signal_api backend.tests.test_event_api_flow backend.tests.test_review_state backend.tests.test_aggregate backend.tests.test_hko backend.tests.test_mtr_eta -q`: **79 passed**.
- `$env:PYTHONPATH='.;backend'; .venv\Scripts\python.exe -m unittest discover -s backend/tests -q`: **225 passed**. The earlier full-suite attempt failed to import `pytest` and `app` because test dependencies and PYTHONPATH were missing; these were corrected in the ignored `.venv` and command environment. The first targeted attempt also failed because an old P3 persona test assumed C's shared `main.py` registration; it was changed to test the B router in an isolated app.
- `git diff --check`: passed; Git reported only LF-to-CRLF advisory messages.
- Simulated clients (unit tests): HKO timeout then success, exhausted failure with stale status while MTR still succeeds, MTR two consecutive anomalous rounds, process restart, failed SQLite write recovery, offline network guard, public status and protected review queue. Every stored replay Signal used `simulated`.
- Real one-shot HKO poll on 2026-10-02 05:47 UTC: live `WTS` thunderstorm warning, no fetch error, one `real` Signal. Real one-shot MTR poll at 05:47 UTC: six usable East Rail station observations, no failures or anomalous stations, **zero Signals**.
- Real collector MTR run at 05:48:49 UTC: `new_signals=0`, `result=no_new_signals`, `last_success` populated, `last_error=null`, `source_time=2026-10-02 13:48:52`, `stale=false`.
- Real HKO collector run at 05:49:18 UTC: one Signal and one `pending_review` draft. A subsequent fresh-process probe exposed duplicate emission because a newly added state method had been shadowed by the poller's existing `restore_state`. That defect was fixed by using the existing `export_state()/restore_state()` pair. A **new** probe database at 05:51 UTC yielded first run 1, fresh-process run 0, one Signal and one queue row; status recorded `result=no_new_signals`, `last_error=null` and a source timestamp. The earlier probe database is invalid as dedup evidence and is ignored by Git.

## Risks, gaps and next action

1. C must register the B router and collector in shared `main.py` and verify
   application startup/shutdown, route snapshot behavior and deployment
   configuration. Render's current blueprint sets `OFFLINE_MODE=true`, so live
   scheduled polling is disabled there by default.
2. A must consume the persona and source-status contracts. C must map Agent
   `profile_id` to the same route `profile` object and verify wheelchair
   constraints in the live route path. These cross-team semantics are **not yet
   verified**.
3. Real HKO and MTR source responses were sampled, but continuous live
   scheduling, reviewer UI workflow, C's approve/edit/reapprove/withdraw
   integration and Render redeployment persistence are **not yet verified**.
   No Render admin access or deployed API URL was provided. A static public
   Pages frontend does not prove the API or disk persistence.
4. Do not upload until B's local work, C integration and requested acceptance
   are complete. Then review status/diff, keep generated databases and `.venv`
   out of Git, push the milestone branch and open a PR to `main`.
