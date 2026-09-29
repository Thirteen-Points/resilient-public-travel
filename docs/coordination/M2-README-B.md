# M2 README contribution from B

Status: B's documentation and offline verification are complete; real-model and cross-team acceptance remain partial.
Historical baseline: `fe6cb4f` on `Mingquan-Xia`; rechecked after B commits `d7bfa18` and `e0b3ce6`. The 2026-09-29 local M2 recheck used `b344581` on `XMQM2` and passed 127 backend tests and the B contract-seed validator. README integration belongs to A; this file changes no shared README sections or API contracts. Remote `XMQM2` status was not verified because GitHub was unreachable during the recheck.

Upload review: the descriptions below are B's handoff at `b344581`, not a fresh description of the integrated application. The later `XMQM2` checkout at `a82e790` includes A/C frontend, route-engine and AI-adapter work. Consult the root README and revalidate integrated behavior before copying any section into current release materials. On that checkout, 179 backend tests passed with `PYTHONPATH=backend`, and the B seed validator passed; neither check exercised a real model or live source.

## English sections for A to merge into the root README

The paths below are repository-relative references. When copying these sections into the root README, they can be used directly as link targets.

### Event pipeline and human review

The backend stores raw `Signal` records in SQLite, including `signal_id`, `received_at`, `source_type`, `source_name`, `raw_text`, `raw_url`, `lang` and `provenance`. `POST /api/signals` accepts an unverified user report and returns a Signal ID with HTTP 202. Receipt does not confirm a disruption, create an Event or change a route. The endpoint accepts `raw_text` (1–2000 characters), optional `author_hint`, and `lang` (`zh-HK` or `en`); source metadata is assigned by the server. Reviewers can read originals through protected `GET /api/signals` and `GET /api/signals/{signal_id}`; `unlinked_only=true` filters records not linked to an Event without deleting their originals.

An authenticated reviewer calls `POST /api/events/ingest` with `signal_id`. The structurer produces a strict `StructuredEventDraft`: `event_type`, `title`, `summary`, `mode`, `line`, `direction` and categorical `affected_segments`. The current schema covers internal line `ERL` and six station codes (`TAW`, `KOT`, `MKK`, `HUH`, `EXC`, `ADM`). With an injected model client, invalid JSON, schema errors or client failures trigger one retry, then offline rule extraction. Without a client, rules run immediately. These rules extract explicit supported phrases and station spans conservatively; they do not verify truth or guarantee complete language understanding.

Ingestion merges evidence only into one matching active Event: event type, mode and line must agree, affected segments must overlap, direction must be compatible, and the observation must fall within the configured two-hour matching margin. No match returns `state=needs_review`, a `draft` and `event=null`; ambiguous matches require review (HTTP 409). A reviewer must create the first complete card through `POST /api/events`, supplying explicit severity, time-window and capacity facts. The server replaces submitted confidence with its own calculation. Repeated ingestion of the same Signal is idempotent; new evidence increments the Event version and adds an audit entry without silently changing disruption facts or publishing the card.

Confidence is a deterministic review aid, not a probability of truth. One source starts at 0.20; two independent agreeing sources yield 0.35; three yield 0.55. Independence is approximated by `(source_type, source_name, author_hint)`, so repeated or anonymous reports from the same channel do not inflate the score, and these identifiers are not proof of separate people. An explicitly verified, real official notice can set the service-level score to 0.85; human confirmation adds 0.05. Conflicting segment impacts deduct 0.15. The current HTTP ingestion path does not mark notices as verified, so it does not demonstrate the official 0.85/0.90 stage.

`POST /api/events/{id}/review` supports `approve`, `edit`, `reject` and `expire`. Approval requires a score of at least 0.60 after the human-confirmation bonus. Editing or adding evidence to a published card moves it to `updated` and requires approval again. `GET /api/events/published` exposes only currently published cards. Protected reviewer endpoints and `GET /api/stream/events` require `X-Review-Token`; SSE supports reconnecting with `Last-Event-ID` or `after_id`. Its payload contains the latest full `event` and the corresponding historical audit `change`, rather than a graph or route update.

### Run one offline backend event demonstration

Run from the repository root in PowerShell, using a Python 3.12 environment with the packages in `backend/requirements.txt` installed. In the verified Windows environment, Python was not on PATH; the bundled executable was used as follows. On another machine, replace only the executable path with your installed Python 3.12 path.

```powershell
$readmePython = 'C:\Users\xiami\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $readmePython -m venv .venv-readme-b
.\.venv-readme-b\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv-readme-b\Scripts\python.exe -m unittest backend.tests.test_event_api_flow.EventApiFlowTests.test_signal_merge_review_publish_and_sse_change -v
```

The checkpoint is `Ran 1 test` and `OK`. This executable demonstration uses FastAPI's in-process `TestClient` and a temporary SQLite database. It submits three scripted reports, obtains a rule-based draft, creates a review candidate with fixture numeric facts, merges evidence (0.20 → 0.35 → 0.55), approves it (0.60), checks the published list, and reads SSE publication and subsequent edit frames. It makes no model request and validates no live transport incident. The user-submission API labels its channel `real` even for these scripted reports; that label is not evidence that the scenario is real. The test supplies an isolated test authorization value internally; production authorization must be configured separately.

For a separate simulated social Signal playback:

```powershell
.\.venv-readme-b\Scripts\python.exe -m backend.app.services.ingest.social_mock --speed 100 --run-id readme-b-check
```

The checkpoint is three JSON Signal records followed by `completed=true`, `delivered=3` and no failures. This command prints simulated Signals; it does not insert them into the API, create cards or publish events.

### Data sources and provenance

| Source | Implemented label and meaning | Current limitation |
|---|---|---|
| HKO `warnsum` / `warningInfo` | `real`: official weather-warning responses when successfully fetched; activation/clearance Signals include a source URL | One-shot poller, in-memory last-good snapshot; no automatic scheduler or inbox wiring in the default app. Live fetches were not validated in this README check. |
| MTR East Rail ETA (`getSchedule.php`, source line `EAL`) | Raw ETA comes from an official endpoint; emitted suspected-delay Signals are `real-derived` | Project heuristic: nearest arrival greater than 10 minutes, or supported delay status, across at least two adjacent stations for two consecutive polls. This is not an official delay standard or verified disruption notice. Detection state is in memory; recovery resets it without emitting a recovery Signal. Live fetches were not validated here. |
| User submission | `real` denotes the input channel, not verified report content | Reports are untrusted; the public endpoint does not allow callers to set provenance. |
| Social playback | `simulated`, visibly marked in source names and text | Scripted posts; no real social-media feed. |
| Event seeds and model-acceptance samples | `simulated`, including the seed's official-style notice | Fixtures are not live incidents or real-model acceptance evidence. |
| Network, route and simulation seeds | Mixed field-level labels; route values are illustrative, simulation values are placeholders | `real` labels in static seeds do not establish current accuracy. Some entries explicitly say fares, capacity, accessibility or thresholds still need verification; no route-engine or simulation execution was verified on this branch. |

Read each record's `provenance`, source URL and timestamp alongside its notes. Event provenance is inherited from the first Signal at card creation; aggregation does not produce a full mixed-source provenance summary. Confidence and provenance describe different things. This is an academic demonstration; use official transport and weather announcements for actual travel decisions.

### AI responsibilities and current limits

AI is restricted to extracting supported text and categorical fields into an unverified draft. `StructuredEventDraft` rejects extra fields, including `severity`, `confidence` and `capacity_factor`. AI must not invent routes, stations, travel times, ETA ranges, delay minutes, fares, headways, capacity, passenger counts, load or diversion percentages. Numeric event facts come from explicit reviewer input and confidence from deterministic code; future traffic calculations must come from the deterministic engine and traceable data. Schema validation checks structure, not factual correctness, and does not constitute semantic verification of numbers embedded in free-text titles or summaries.

At the `b344581` B handoff, `create_app(llm_client=None)` used offline rules for event structuring. `LlmJsonClient.generate_json(...)` was an injection boundary, and fake-client tests demonstrated retry and fallback only. The ten-sample real-model acceptance target of at least 8/10 first-pass successes was not completed in that handoff. Later C work added an AI adapter and related features to the integrated branch; this B-only check has not certified their live behavior. The B event-structuring prompt omitted `author_hint` but passed raw report text; it was not a personal-data redaction system.

### Server-side configuration

At the B handoff, the event-review API read `REVIEW_API_TOKEN`. Supply it privately on the server; no secret value belongs in the README, Git, browser source or URLs. Protected endpoints return 503 when it is missing and 401 for missing/incorrect authorization. The shared-token mechanism is limited to a controlled demonstration; production identity and permissions require separate review. The integrated application now reads additional runtime and AI configuration variables; see its current root README and `backend/app/runtime_config.py`.

`create_app(db_path=..., review_token=..., llm_client=...)` provides Python-level configuration for B's event API. The default database is `backend/app/data/events.sqlite3`; these parameters are not environment-variable names. The pending T2.6 acceptance record mentions `OPENAI_API_KEY`, but setting it alone does not prove B's event-structuring acceptance. The integrated C adapter uses its own provider configuration.

## Evidence and validation record (for A; do not copy as product claims)

| README section | Exact implementation and test references |
|---|---|
| Signal receipt | `backend/app/services/signal_models.py:Signal`; `backend/app/api/signals.py:UserSignalSubmission`, `build_user_signal`, `submit_signal`; `backend/tests/test_signal_api.py` |
| Draft and fallback | `backend/app/services/structure/llm_structurer.py:StructuredEventDraft`, `LlmEventStructurer.structure`, `SYSTEM_PROMPT`, `_user_prompt`; `backend/app/services/structure/rule_extractor.py:RuleEventExtractor`; `backend/tests/test_llm_structurer.py`, `test_rule_extractor.py` |
| Merge and confidence | `backend/app/services/aggregate.py:EventAggregator._same_incident`, `merge`; `backend/app/services/confidence.py:score_confidence`, `_source_key`; `backend/tests/test_aggregate.py`, `test_confidence.py` |
| Review, persistence and SSE | `backend/app/api/events.py:IngestResult`, `create_review_candidate`, `ingest_signal`; `backend/app/services/review_state.py:EventReviewService`; `backend/app/services/event_store.py:EventStore`; `backend/app/api/stream.py:event_frames`; `backend/tests/test_event_api_flow.py`, `test_review_state.py`, `test_event_store.py` |
| Provenance | `backend/app/services/ingest/hko.py:HkoWarningPoller`; `mtr_eta.py:MtrEtaAnomalyPoller`, `parse_station_observation`; `social_mock.py:SocialMockPlayer`; `contracts/seed/*.json` metadata/notes; corresponding `test_hko.py`, `test_mtr_eta.py`, `test_social_mock.py` |
| Model/configuration limits | `backend/app/main.py:create_app`; `backend/app/services/structure/acceptance.py`; `backend/tests/test_structure_acceptance.py`; `docs/coordination/T2.6-real-model-acceptance.md` |

Historical commands actually run from the repository root on 2026-09-27:

- `git status --short --branch`, `git remote -v`, `git log -4 --oneline`: correct repository and branch; initially clean. An unrelated `.venv-b-evidence/` appeared during work and was preserved.
- `python --version` and `python -m unittest discover -s backend/tests -v`: failed because Python was not on PATH.
- Bundled Python `--version`: Python 3.12.14. Initial test discovery using the bundled interpreter failed on missing `fastapi` / `jsonschema`; no code failure was inferred from missing dependencies.
- Bundled Python `-m venv .venv-readme-b`: succeeded. Virtual-environment `-m pip install -r backend/requirements.txt`: sandbox network attempt failed; approved network execution succeeded.
- `.\.venv-readme-b\Scripts\python.exe -m unittest discover -s backend/tests`: **127 tests passed**. A Starlette TestClient deprecation warning was emitted.
- Single-test demonstration command above: **1 test passed**, including publication at 0.60 and SSE edit delivery in under the test's one-second limit. This is an in-process check, not an end-to-end UI latency benchmark.
- `.\.venv-readme-b\Scripts\python.exe scripts/validate_contract_seeds.py`: passed; four JSON files readable, three Events and five Signals satisfy B's contracts. This does not validate C's network/route/simulation schemas or numeric accuracy.
- Social playback command above: passed; three simulated Signals, no failures.
- `rg -n 'getenv|environ' backend`: found only `REVIEW_API_TOKEN` in `backend/app/main.py`.
- `rg -n 'provenance|simulated|real-derived' contracts/seed`: inspected actual labels and pending-verification notes. An earlier Windows wildcard-path form failed and was corrected to this directory form.
- GitHub access in the sandbox failed; remote synchronization uses separately approved Git commands. No real HKO/MTR/model calls were run.
- Concurrent B work added the protected Signal inbox and bilingual disclaimer (`backend/app/api/disclaimer.md`); both handoffs were read, and the complete 127-test suite was rerun successfully after their commits. Other staged evidence files were preserved and excluded. Git commit initially failed because no author identity was configured; the existing branch author's name/email are used only as command-scoped Git options, without changing repository or global configuration.

Local M2 recheck on 2026-09-29 from the repository root: `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v` passed 127 tests (exit 0), and `.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` passed (exit 0) with four readable seed files, three valid Events and five valid Signals under B's contracts. The pre-existing untracked `.venv-readme-b/` was left alone. This recheck made no live-source or model requests, and did not verify browser delivery or deployment. `git ls-remote --heads origin XMQM2` could not connect to GitHub, so remote upload is unconfirmed.

Historical 2026-09-27 manual verification: compared these paragraphs against handlers, service fields, tests and B handoff records. No runnable service, frontend, graph or model capability was inferred from plan text alone. That earlier task changed only this B-owned handoff document; the current local M2 check also updates the B evidence/report documents and adds a new round report.

## Items for A / orchestrator confirmation

1. Reconcile these historical B sections with A's now-expanded root README before reusing them in M2 materials.
2. Resolve plan drift explicitly: `03-contracts.md` lists `ERL_E` / `ERL_W`, while the implemented draft uses `ERL`; ingestion returns `IngestResult`, not a complete Event; FastAPI errors use `detail`, not the planned error envelope. Its generic Signal-injection description is also broader than the implemented user-only POST. Do not advertise every planned endpoint as shipped.
3. Confirm the demonstrated 0.60 publication path and how UI badges explain the unverified `real` user channel, simulated fixtures, mixed Event provenance, and approximate source independence. A's frontend and C's graph/route consumption are not verified here.
4. Resolve model-selection drift between `02-architecture.md` and the later T2.6 acceptance record together with C. The integrated branch now has C's adapter, but this B record does not establish a completed real-model acceptance result.
5. Confirm controlled-demo authorization delivery (trusted backend proxy or authorized streaming fetch), precise CORS origins, UI behavior while a published card is `updated`, and which future live-source/model checks must precede stronger README claims.

Recommended next action: A merges the approved sections; B/C separately complete live model acceptance and cross-team integration before changing the documented limitations.
