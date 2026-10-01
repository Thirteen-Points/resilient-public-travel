# ResilientRoute administration

Open `/admin/` on the Render API origin. The console uses same-origin API requests,
server-side sessions, and English labels. Cloudflare's public frontend remains
compatible with the existing public and reviewer-token APIs.

## Initial access

Run `python scripts/create_admin_credentials.py` from the repository root using
an environment with backend requirements installed. It writes login credentials
to `runs/admin-credentials.local` and Render values to `.cache/admin-env.local`.
Both paths are ignored by Git. Add `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and
`ADMIN_ENCRYPTION_KEY` to the Render service environment; never put these values
in frontend build variables. New Blueprint instances prompt for these values.
The username/password login does not use or expose `REVIEW_API_TOKEN`.

Keep `ADMIN_ENCRYPTION_KEY` stable across deploys. It protects settings in
`backend/app/data/admin.sqlite3`, alongside the separate `events.sqlite3` on the
existing persistent disk. Missing/invalid credentials or an unavailable encryption
key disable administrator access while public APIs continue running. Password
hash rotation revokes existing administrator sessions. Sessions expire after
eight hours; logout revokes the session immediately. The cookie is HttpOnly,
Secure, SameSite=Strict, scoped to `/api/admin`; writes also require Origin and
CSRF validation. Only for local HTTP development, set `ADMIN_COOKIE_SECURE=false`.

To choose a new password, obtain a PBKDF2 hash with `password_hash` in
`backend.app.admin.store` using a secure local input method. Update only
`ADMIN_PASSWORD_HASH` in Render; keep the encryption key unchanged. There is no
public registration, password-reset endpoint or default production password.

## Review and configuration

Reports stay unverified. Extract/merge evidence, create a pending card, confirm
numeric facts, and save edits before publishing. Publication uses the existing
confidence threshold and state machine. Stale event/config revisions return 409;
reload before retrying. Review identity comes from the administrator session.
Rejection reasons are stored in administrator Activity; event audit records
continue using the existing contract.

Saved AI settings immediately affect new report-structuring calls only. Chat and
route calculations remain deterministic. Providers are DeepSeek, Qwen and GLM,
with fixed official HTTPS endpoints and configurable model, key, enable flag and
timeout. Keys are encrypted at rest and cannot be retrieved by the browser;
blank inputs retain a saved key, while Clear key deletes the active value.
Connection testing requires explicit confirmation and can incur provider charges.
Tests send a synthetic prompt, never a user's report. Production starts with AI off.

MTR East Rail and HKO use the existing adapters. Save and enable a source before
manual collection. Tests may run while a source is disabled, but never mutate
reports or detection state. Collection persists adapter state and signals in one
SQLite transaction, obeys the minimum observation interval, and does not publish
events. MTR reports require the configured consecutive observations; unchanged
HKO warning sets do not produce more reports. Added, duplicate, failure and
no-change results are displayed. There are no scheduled jobs. KMB remains
Not connected. Only explicit administrator Test/Collect actions make external
source requests; offline seed routes do not become live transit data.

## Building and deployment

Run `npm ci` then `npm run build:admin` in `frontend`. Commit the generated
`backend/app/admin_static` assets together with their source changes. CI checks
that the committed bundle matches its source. FastAPI serves the bundle so the
existing Render commands remain exactly:

- Build: `pip install -r backend/requirements.txt`
- Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

Do not remove or remount the disk. The console exposes neither Render credentials
nor filesystem/environment configuration. For recovery, back up both SQLite
databases using SQLite's backup API and preserve the encryption key separately.

## Verification

Run `PYTHONPATH=.:backend python -m pytest backend/tests tests -q` (use `;` between
paths on Windows), frontend tests, and `npm run build:admin`. Administrator tests
mock only external calls; they cover authorization, CSRF, rate limits, encrypted
settings, model timeout fallback, event conflicts, publication/withdrawal,
source intervals and state persistence across app recreation.

On Render check `/admin/`, login, `/api/admin/session`, `/api/admin/overview`,
`/api/health/deep`, `/docs`, the public Pages CORS preflight and an explicitly
labelled acceptance report. Redeploy and read that same report, administrator
configuration and session to verify real disk persistence. Avoid real AI tests
unless an administrator explicitly triggers the paid request.
