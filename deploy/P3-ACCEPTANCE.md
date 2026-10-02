# P3 deployment and regression acceptance

The repository changes automate local regression and Docker recreation checks.
GitHub CI execution, protected-branch settings and Render redeployment must still
be checked after the changes are pushed by an authorized maintainer. No live
event publication, real provider request or redeployment was performed here.

## Startup flags

`scripts/start.sh --offline --no-llm` and the Windows equivalent now set
`OFFLINE_MODE=true`, `AI_ENABLED=false` and `AI_DISABLE_EXTERNAL=true` before the
backend starts. Explicit flags override inherited environment values and prevent
saved administrator AI configuration from enabling external requests.
`LLM_ENABLED` remains a legacy alias when `AI_ENABLED` is unset.

Add `--check-config` to inspect argument parsing without installing dependencies
or starting the server. This prints only these nonsecret environment flags and
the port; unset values show runtime defaults. It does not load dotenv files.
Without explicit flags the backend still loads its configured environment.

## Durable Docker storage

Compose mounts `app_data` at `/app/backend/app/data`, which contains
`events.sqlite3`, its audit records, `admin.sqlite3` with encrypted settings and
source collection state, `ai_usage.sqlite3` with durable model budget reservations,
caches and snapshots. Keep `ADMIN_ENCRYPTION_KEY` stable
across recreation. Supply production credentials via the server environment;
never use frontend `VITE_*` variables for credentials.

Before replacing an existing container, make a consistent SQLite backup of both
databases and preserve the encryption key. The previous Compose configuration
only mounted cache/snapshot subdirectories; its event databases may exist only
in the old container. Restore that backup into the new parent volume before
removing the old container. Existing cache/snapshot volumes are not deleted by
this change. Do not remove `app_data` when restarting or upgrading.

Use a full 40-character commit SHA as `APP_BUILD_SHA` when building/running
Compose. `/api/meta` and health expose the deployment-supplied build identity;
missing or malformed identity is explicitly unknown. Render's
`RENDER_GIT_COMMIT` provides the identity on that platform. A public API response
cannot be assumed to run the latest GitHub main without checking this identity.

## Automated GitHub checks

`P3 regression` runs contract/data validators, all backend and integration tests,
frontend tests, typecheck/production build, and the existing browser publication,
polling recovery and mobile regression. It stores JUnit results and browser
screenshots/results even on failure. Its second job builds Docker, seeds a
simulated event with audit history plus encrypted administrator settings, forces
container recreation, then verifies those same records and a reserved model budget
entry survive. The budget probe makes no provider request.

After the first successful CI run, configure required checks for
`Backend, frontend and browser`, `Container recreation persistence`, and the
existing administrator bundle check `verify` in the GitHub main protection rule.
Confirm the exact check names shown on the run. This requires repository settings
permission; the workflow file itself cannot enforce protected-branch rules.

The container probe is guarded by `P3_PERSISTENCE_FIXTURE=true` and belongs only
in a disposable Compose project. It must not be run on a production database.
Local probe tests verify application storage behavior; a machine without Docker
does not provide evidence that a real container mount passed.

## Render and public frontend acceptance

1. Confirm the Render persistent disk is mounted at
   `/opt/render/project/src/backend/app/data`, the service uses one instance, and
   a stable administrator encryption key is configured. Confirm `/api/meta`
   reports the intended merged commit SHA and `/api/health/deep` succeeds.
2. In the controlled acceptance environment, submit a clearly simulated report,
   merge independent evidence, confirm fields and approve it through the review
   console. Capture the approval response, public event revision, graph snapshot
   and front-end route/map changes. Measure each refresh and verify <= 5 seconds.
   Repeat an edit/reapproval and withdrawal, including disconnected SSE polling.
3. Save an administrator source configuration with collection disabled and record
   its revision. Record the event ID, audit count, approved revision, and source
   collection state. Redeploy the same service without replacing its disk/key.
4. Verify the saved event, audit history, approved facts, encrypted configuration
   and source state remain readable. Record the new build SHA and screenshots.
   Keep fixture events clearly marked and withdraw them after acceptance.
5. Attach CI run links, measurements and screenshots to M3 evidence. If platform
   access is unavailable, mark these online checks pending instead of claiming
   that local tests establish deployment persistence or online latency.
