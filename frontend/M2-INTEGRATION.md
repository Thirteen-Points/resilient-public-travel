# Role A · M2 integration

This supersedes the endpoint/configuration assumptions in M1-INTEGRATION.md. The combined backend includes events, review, signals, streaming, routes, simulation and deterministic AI replies.

## Approved event semantics

SQLite stores the last approved payload independently of the pending reviewer revision, in the same write transaction. Public `/api/events/published` and the graph sync consume that payload. Editing or merging a published card sets reviewer status `updated`; the last approved facts remain active until reapproval or reject/expire. The graph never consumes unapproved edits. Reviewer audit history is separate from public approved payloads.

Public event reads and `/api/graph/snapshot` accept a timezone-aware `at`; the frontend uses the current query's departure time, or server current time before a query. Status, window.start, published_at, window.end and expires_at jointly gate effects. An old updated card with no saved approved payload must be reviewed again; historical numeric facts are not reconstructed from an audit action.

## API and authorization

Review requests use `action`, `actor` and optional `edits`; no server-side rejection reason field exists. UI supports updated-card reapproval and withdrawal. The inbox structures/merges Signals and creates complete pending cards using explicit reviewer severity/capacity/time fields.

Public reads never depend on the protected queue. Reviewer credentials are temporary, memory-only inputs. Streaming fetch sends `X-Review-Token`, parses incremental SSE frames, resumes with `Last-Event-ID`, aborts on cleanup and reconnects after three seconds. Polling remains active. URL token authentication was removed. CORS origins are configured server-side through `CORS_ORIGINS`.

Private requests/evidence have their own warning. Public refresh failure retains the previous map/cards with a stale notice. Route requests use a latest-request guard. Successful writes are not reported as failed because a subsequent read failed.

## Current limits

No production reviewer identity/session setup or external deployment was verified. Shared credentials remain controlled-demo access. Raw reports are stored for review; user-channel provenance does not verify their contents. Live source polling/model acceptance is separate. Agent chat is local templates, persona comparison and a simulation dashboard are later frontend work. Offline retention requires a previously loaded page; the app is not an installed offline PWA.

## Reproducible checks

- `npm run typecheck`, `npm run test`, `npm run build` from frontend.
- Backend unittest discovery with `PYTHONPATH=backend`.
- Engine tests and cross-module pytest suite.
- `tests/browser/m2.e2e.cjs` launches an isolated database/API and a real browser, exercises public/report/review paths, and stores local screenshots/timing results under `.cache/m2-browser/`.

See the root README for exact commands and prerequisites. These checks do not claim live HKO/MTR/model or production validation.
