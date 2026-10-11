# P4-C deployment and online acceptance runbook

This runbook prepares deployment and acceptance work from local `ZYC-P4`.
It does not authorize deployment, publication, changes to `main`, or repository
settings. The production revision, reviewer/platform access, production
performance and persistence have **not been verified** by this local work.
See [the C acceptance report](../docs/acceptance/p4-c-acceptance.md) for executed
local checks and C technical media; the team's final PPT still needs its owners'
review and sign-off. Use the [online record template](../docs/acceptance/evidence/p4/c/online-template.json)
for a separate, later run by the responsible operators.

## 1. Prepare a versioned deployment

1. The release operator records the approved full 40-character commit SHA, branch,
   backend/frontend origins, UTC start time, platform service IDs, Python/Node
   versions and release owner. Until a deployment exists, leave these fields null
   and its status `not_run`. This C implementation stays on `ZYC-P4`; the existing
   Render Blueprint names `main` and is not evidence this branch was deployed.
2. Prepare dependencies while network access is available. Install the backend
   requirements and use `npm ci` in `frontend`. Build the public frontend with
   `VITE_API_BASE_URL` set to the intended backend origin and `VITE_BUILD_SHA` set
   to the approved full SHA. Save the build log and artifact hashes. Set
   `APP_BUILD_SHA` for Docker; Render supplies `RENDER_GIT_COMMIT`. Do not infer
   the running version from the repository's newest commit.
3. Run `python scripts/preflight.py` against the release checkout. It validates
   data and both fixed-input P3 cached results without contacting a server.
   A nonzero exit blocks rehearsal. Preserve JSON output, including scenario,
   input hashes, units, assumptions and provenance. Do not regenerate route
   inputs or change weights merely to obtain a passing result.
4. Confirm persistent storage and stable `ADMIN_ENCRYPTION_KEY` with the platform
   operator. Compose mounts `app_data` at `/app/backend/app/data`; the Render
   Blueprint mounts its disk at `/opt/render/project/src/backend/app/data`.
   `DB_PATH`, when set, must point to the intended persistent `events.sqlite3`;
   `admin.sqlite3` and `ai_usage.sqlite3` are created beside it. Preserve the
   cache/snapshot directories on that disk.
5. Before replacement, make SQLite-native backups of **all three** databases,
   record backup time and SHA-256, and check each with `PRAGMA integrity_check`.
   Use SQLite's backup API or `.backup`, rather than copying only a live database
   while its WAL may contain committed changes. Pause writers for a consistent
   backup set. Keep the existing encryption key in the platform operator's secure
   recovery store; exclude keys, tokens, sensitive reports and databases from
   Git/CI evidence.
6. The authorized operator deploys the approved backend artifact, then the matching
   frontend artifact. Preserve the existing disk/volume and key; do not use
   `docker compose down --volumes`. Verify the exact frontend origin in
   `CORS_ALLOWED_ORIGINS`. Reviewer access uses the private authenticated
   administrator path or a server-managed credential; do not put tokens into
   frontend `VITE_*` variables.
7. Against the actual service, run this opt-in check from the matching checkout,
   replacing placeholders with the recorded origin and approved SHA:

   ```bash
   python scripts/preflight.py --api-base-url "https://<backend-origin>" --expected-build-sha "<full-approved-sha>"
   ```

   Save the exit code and JSON. Check `/api/health`, `/api/health/deep`,
   `/api/meta`, both cached simulation responses and the public frontend's
   `/build-info.json`. Compare backend `build.commit_sha` and frontend
   `commit_sha` to the approved SHA. Null/unknown identity or differing SHAs
   remain a failed version check. Check `/docs`, an actual route query, exact
   frontend CORS preflight and deterministic AI fallback. Preflight does not
   establish frontend deployment, reviewer authorization or disk persistence.

The final offline preparation and five-minute sequence are in
[deploy/offline/README.md](offline/README.md). A prepared local bundle uses
`python scripts/preflight.py --demo --require-media`; a running offline demo also
adds `--api-base-url http://127.0.0.1:8000 --require-offline` and, when known,
`--expected-build-sha <full-sha>`. `--demo` checks the local offline build
inventory, not a production frontend. The C backup uses a real local WebM
recording (`media/demo.webm`, open in Edge/Chromium) and `media/slides.pdf` based
on C data/screenshots. It is a technical demonstration; replacing/signing off
the team's final PPT remains a separate handoff. Treat absent or unchecked
media as pending rather than as a completed five-minute fallback.

## 2. Publication and revision isolation

Run writes only in an explicitly approved acceptance environment. B/reviewer owns
review decisions; C records versions/timing; A verifies map/cards/routes. Missing
reviewer access makes dependent steps `blocked` with the required reviewer role.

1. Save `/api/events/published`, `/api/graph/snapshot` and a fixed route query
   before writing. Choose a departure inside the event's active HKT service
   window; preserve the same query payload within each measured round.
2. Submit a clearly simulated report using `POST /api/signals` or the Report UI.
   Save its Signal ID and read the stored Signal with reviewer-authenticated
   `GET /api/signals/{signal_id}`. Record provenance and a redacted evidence
   hash. Submission alone must not alter public events or routes.
3. Extract/merge using `POST /api/events/ingest` or the Review UI. If its state
   is `needs_review`, the reviewer confirms segment, direction, capacity factor,
   severity and time window, then creates a pending card using `POST /api/events`
   or Create pending card. All fixture sources stay explicitly simulated.
   Follow the existing confidence/publication rules. Retain a rejected approval;
   do not overwrite confidence or route weights to make it pass.
4. Approve through the private UI or `POST /api/events/{event_id}/review` with
   `action: "approve"`, a reviewer actor and the current `expected_version`.
   Record HTTP status, approved Event/version, `review_approved` audit entry,
   public version and snapshot. For an ERL HUH-to-EXC closure fixture, verify
   route legs avoid that closed directed segment during its active window.
5. Edit the published card with `action: "edit"`. Verify its protected current
   state is `updated`, while the public card and routes/map retain the last
   approved facts until explicit reapproval. Refresh on HTTP 409. If a write
   succeeded but UI refresh failed, re-read Event/audit before retrying to avoid
   treating a confirmed write as unconfirmed.
6. Repeat edit/reapproval for **three measured rounds** in total. Each round
   saves the write response, public read, snapshot, refreshed route response
   and screenshot with Event revision. Record action-to-write-response and
   action-to-visible-public/map/route times separately in milliseconds. The
   P3 visible-refresh target is <= 5,000 ms per update; leave missing timings
   null. Screenshots without timestamps are not latency measurements. Verify
   public reads in a visitor session and refusal of private reports/publication
   with wrong reviewer credentials.

## 3. Withdrawal, natural expiry and network recovery

Use separate Events for withdrawal and natural expiry: the current state machine
does not reapprove an expired Event.

| Case | Operator steps | Required evidence |
|---|---|---|
| Withdrawal | Review the approved fixture with `action: "expire"` and current `expected_version`. This is the supported withdrawal action. | Protected state `expired`, audit `review_expired`, public removal, restored affected edge and fresh routes. Preserve the Signal/audit rather than deleting them. |
| Natural expiry | Before approval give a second fixture a short timezone-aware `window.end`. Wait past the real clock deadline without sending `action: "expire"`; then read public/protected events. | Reads/stream reconcile through `expire_due`: state `expired`, audit `auto_expired`, public impact removed. Repeated reads add no duplicate expiry. Record clock times; the public `at` query parameter does not prove real-time expiry. |
| Stream loss | Disconnect the reviewer stream but keep HTTP available; withdraw a fixture from a connected authorized client. | Public HTTP polling removes its card and restores map/routes. Record surface timings and network evidence showing HTTP stayed available. |
| Network loss and recovery | After successful route cards appear, block the browser's backend access, then restore it and use Refresh. A separate connected reviewer may change the fixture during disconnection. | Retained cards/stale notice screenshot; disconnect/reconnect times; refreshed revisions, snapshot and route response; stale notice clears after success. The disconnected browser must not be claimed to have received live updates. |

Record each visible withdrawal/expiry/recovery surface separately. Preserve
timeouts/failures instead of filling values. Withdraw any remaining simulated
public fixtures after acceptance; retain stored evidence and audit.

## 4. Redeployment and rollback retention

The platform operator owns storage operations; B/reviewer owns protected reads
and fixture cleanup. Before redeployment, record each fixture Signal ID/hash,
Event ID/current version/status, last approved version if active, and ordered
audit history/count. Record administrator settings revision, disabled collection
state and AI-usage/budget snapshot when platform access allows it. Expired events'
absence from the public feed is not deletion; verify them through protected reads.

1. Save backend/frontend SHAs, `/api/meta`, Signal/Event reads, linked Signal IDs
   and ordered audit in the approved private evidence store. The disposable
   container probe covers Event/audit/settings/budget recreation, not this
   production Signal-retention check.
2. Redeploy the approved service retaining its disk/volume/key. Save job ID,
   start/end UTC times, health downtime and new SHAs. Read the same records after
   recovery. Immutable Signal hashes/IDs and prior ordered audit must match.
   Versions/status/approved facts must match unless documented actions or
   natural expiry added explained audit entries. An expired fixture need not
   reappear publicly.
3. Verify encrypted settings remain readable with the same revision and collection
   disabled, and prior AI usage remains readable. Run preflight for the new SHA
   and verify the frontend identity. A matching database path alone is insufficient.
4. If health, identity or acceptance fails, the authorized platform operator
   restores the previous backend/frontend artifacts, preserving disk/key, and
   rechecks health, SHAs, records and routes. Do not restore an old database merely
   for a code rollback because later reports could be lost. If data restoration
   is necessary, pause writers, preserve the failed state, agree the recovery
   point, restore the consistent three-database backup set with its matching key,
   and record the lost interval. Rehearse restoration in an isolated environment.

No production redeployment or rollback was performed by this local C task.

## 5. Performance, CI and required checks

| Scope | Record | Limit of the evidence |
|---|---|---|
| Local | C report, preflight JSON, `.cache/p4-c/performance.json`, rehearsal artifacts; runtime/machine, base SHA and dirty status | Simulation <= 30 s and route P95 <= 1,500 ms under the recorded local workload only. |
| CI | Actions URL, tested SHA, job conclusion, artifact names/hashes | Checks executed on that runner; local passes do not establish a CI pass. |
| Production | Deployment ID, backend/frontend SHAs, origins, UTC time, workload/concurrency and raw durations | Service behavior, latency and persistence only in that measured environment. |

For production route P95, preserve at least 60 query durations, payloads,
successes/errors, warm/cold behavior and concurrency. State the percentile
method (nearest rank: `sorted_ms[ceil(0.95*n)-1]`). Preserve failures/timeouts;
do not discard them to claim a pass. Precomputed-result download time is not
10,000-person simulation execution time. Run the execution benchmark on the
release checkout/runner and label that scope.

Confirm these required-check names from an actual PR run:

- `Backend, frontend and browser` — workflow `P3 regression`.
- `Container recreation persistence` — workflow `P3 regression`.
- `verify` — workflow `Administrator bundle`.

The repository administrator confirms checks on the intended commit, configures
them as required in the intended branch protection/ruleset, decides review/bypass
policies and records verification time. Protection configuration remains
**pending administrator confirmation**. This C task does not change settings;
workflow files alone do not enforce protection. Failures must keep their failing
status and uploaded evidence. Record artifact expiry for final acceptance links.

## 6. Owners and unverified work

Copy the online template into a dated private evidence record; do not overwrite
the unexecuted template. Use `not_run` for untouched steps, `blocked` with a
specific missing permission for dependent steps, and `passed` only after all
assertions execute. Unknown measurements stay null. Redact credentials/sensitive
raw Signals from shareable records and keep originals in the approved private
store. Local, CI and production records need separate scopes and identities.

| Pending item | Responsible role | Next action |
|---|---|---|
| Approved release, disk/service access, rollback artifacts | Deployment/platform operator | Record approved SHA/origins; verify disk/key and three backups before deployment. |
| Review fixtures and private reads | B / authorized reviewer | Execute publication, expiry and protected Signal/Event/audit retention. |
| Public identity and visible map/routes | A / frontend operator; C timing | Capture three timed rounds and disconnect/recovery on the deployed frontend. |
| Required checks/protection | Repository administrator | Verify actual check names/run and record protection settings. |
| Team final PPT/media approval | A / demo owner + reviewer | Review C technical WebM/PDF; replace/sign off team presentation if needed. |
| Online C record | C with those operators | Fill observations/evidence and preserve unresolved items with owner/next step. |

After the weight conclusion is approved, the team reruns relevant route/UI/
simulation regression and records new input/version identities. This runbook
does not modify scoring weights or preference presets.
