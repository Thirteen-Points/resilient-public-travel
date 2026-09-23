# M0 C + A/B integration report

This report records the local integration on top of GitHub `main` after A and B
were merged. It covers M0 only; no M1 implementation is included.

## Merge and ownership decisions

- The integration branch starts from the current GitHub `main` and merges the
  existing GitHub `ZYC` branch, preserving both histories.
- The two real merge conflicts were `backend/app/main.py` and
  `backend/requirements.txt`. The app entry point now composes B's persisted
  signal-submission API with C's deterministic route, simulation, health, and
  optional AI-fallback endpoints. Dependencies from both branches are retained.
- A/B-owned signal schemas, API/store modules, frontend, and main-only files are
  retained. C's deletions of those files are intentionally not applied.
- C's previous local history had no common ancestor with GitHub. Its current
  M0 source files were therefore transplanted selectively; historical generated
  test-output snapshots were not treated as current evidence.

## Wheelchair M0 policy

- MTR and full-size BUS are assumed usable by default when accessibility fields
  are absent or unknown; MINIBUS is always excluded.
- Explicit `accessible=false` or `partial`, explicit non-low-floor BUS, and
  stairs remain blocking. WALK/FERRY still require affirmative accessibility
  data, and the wheelchair walking limit remains 400 m.
- Routes surface a warning that this is a demo policy assumption, not official
  accessibility verification. Seed wheelchair top picks are regenerated from
  the route engine under this policy.

## Verification

- Full A/B/C M0 suite: **312 tests passed** (two upstream Starlette/httpx
  deprecation warnings only), including B's event/signal JSON Schema checks,
  C route/simulation/AI tests, and the combined-app signal + wheelchair-route
  smoke test.
- `scripts/validate_data.py`: passed with one documented simulated-event
  warning. `scripts/preflight.py`: passed in offline mode with LLM optional.
- Targeted wheelchair/accessibility suite: 49 tests passed, including default
  MTR/BUS, minibus exclusion, explicit negative flags, and top-3 seed/API
  consistency.

## Remaining boundaries

This integration does not assert that every real station entrance, lift,
boarding point, or bus vehicle has been officially verified. Simulated values
remain labeled as simulated. M1 work is out of scope.
