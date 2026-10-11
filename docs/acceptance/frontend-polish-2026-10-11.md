# Frontend polish · local acceptance · 2026-10-11

Implemented on `codex/frontend-polish`, based on fetched `origin/main`
`7d658237e432d1a2a38ae95fc300b9331db216a4`, then synchronized with
`d07730d84df9f9db11b0a439680e4b503997781d` before opening the PR, and updated
through fare PR #108 at `e393fb3a3617ba12107b1f8c49e89fe7395ac3ca` before
the latest regression. This work was verified locally; the frontend has not
been deployed to production.

## Delivered behavior

- Public Journey, results/details, Report, Agent, Updates, How it works and
  preference editing remain. Public Compare, Simulation and Review screens,
  mounting/state/navigation and exclusive components/styles were removed.
  Shared administrator review components and backend APIs remain.
- Shared passenger/administrator tokens follow the original design specification:
  16/24 body, 14/20 supporting text, 48 px buttons, 56 px inputs and 44 px main
  hit targets. Route metrics scale in large-text mode; inverse badges remain
  readable in high contrast. How it works selectors no longer affect other pages.
- Desktop journey views use a separate map cell with 400 px results and 480 px
  details (360/440 px at smaller desktop widths). Below 1024 px, navigation
  folds, map/list tabs stay accessible while scrolling and long pages use document
  flow. Query/page/view changes reset mobile scroll. Updates does not overlap
  the map at 1024 px or clip on phones.
- OpenFreeMap Positron now loads successfully in development and production,
  using MapLibre 6's bundled worker. Irrelevant POI labels are suppressed; network
  paths are subdued and candidates use A/B/C blue/purple/teal. Selected routes
  use a 6 px stroke and white outline. The legend starts collapsed, zoom controls
  have 44 px targets, and catchment circles appear only during point selection.
  Mobile permanent station labels show traditional Chinese; full bilingual
  labels remain available through station tooltips and the form.
- Network, candidates and event overlays use one offline geometry resolver.
  Verified bends, directional bus variants, omitted intermediate rail stops and
  multipart boundaries are retained. Routing contracts, ranking, times, fares,
  walking distances and accessibility assumptions were not changed.
- The main-branch fare update is retained: official adult ticket amounts,
  per-step ticket charges and price explanations remain in results/details
  and Agent routes. Connecting MTR lines share one ticket; zero additional
  charges read "Included in ticket". Retired public pages remain removed.
- Healthy 3-second public polling stays quiet; source status polling remains
  15 seconds. Offline/failed/stale state retains results with an inline retry
  notice; recovery clears it. Actual route updates use a 4.2-second notification.
  Request cancellation and stale-response protection remain.

## Recorded validation

| Check | Result |
| --- | --- |
| TypeScript | Passed |
| Frontend unit suites | 12 files, 119 tests passed after fare-main sync; includes official seed fares and 15 geometry tests |
| Public production build | Passed; bundled worker emitted |
| Administrator production assets | Rebuilt into `backend/app/admin_static` |
| Geometry regeneration `--check` | Passed: 63 segments, 19 sources, 8,111 vertices, 3 missing directions |
| Browser integration | 13 groups passed with isolated backend/database and Edge; after fare-main sync, sequential M2 and P4 runs also passed in headless Chromium without page errors |
| Production browser smoke | Positron displayed, worker HTTP 200, resize/mobile labels passed; no page errors |
| Viewports | 320, 390, 768, 1024 and 1440 px checked |
| Accessibility | Station keyboard search, mobile navigation/Escape, map/list keyboard tabs, large text, high contrast and reduced motion checked |
| Git whitespace check | Passed |

The integration suite exercises all 30 directed corridor OD pairs for standard
and wheelchair profiles, preference preview/apply/cancel, delayed request
cancellation, failed chat/collection, offline/retry recovery, quiet polling,
short notification dismissal, mobile layout and `/admin/` review. It checks that
pending revisions do not replace approved public facts, a confirmed write is not
repeated after queue-refresh failure, withdrawal updates routes and public pages
do not send or store reviewer credentials.

After fare-main synchronization, the suite also verifies that every returned
ticket charge is finite and nonnegative, step charges reconcile with journey
totals, and displayed cards match API fares. The navigation helper waits for
CSS and React breakpoint state to agree before explicitly opening the mobile
menu, preventing the pending resize handler from closing a newly opened menu.

Three actual administrator approvals in the final regression produced the
following rendered-map / rendered-route-card timings: **2,943 / 2,611 ms**,
**3,104 / 2,961 ms**, and **2,965 / 2,977 ms**. All meet the 5-second local
acceptance budget. Measurements use a warm local backend, unthrottled browser
and real DOM/SVG paint, and do not establish hosted-network timing.

## Geometry limits

The capture covers 40 directional railway segments, 9 bus segments and 14
walking segments. Both Tsim Sha Tsui–Central ferry directions and the modeled
985B return direction remain explicitly schematic. The available OSM ferry
way was historical and was excluded. All shipped geometry derives from CSDI.

Official railway paths are generalized and can omit station areas. Model bus
points approximate boarding locations. Pedestrian geometry does not certify
exit selection, operating lifts or step-free continuity; the Central pier
endpoint has an unverified final approach of about 93 m, without an invented
connector. Full source URLs, captures/hashes, feature IDs, variants, offsets and
terms are recorded in [geometry sources](../../frontend/src/map/GEOMETRY_SOURCES.md)
and displayed in How it works.

Vite still reports large MapLibre/application chunks. This is a build warning;
the vector renderer loads as a separate chunk and its worker is bundled locally.

## Local visual evidence

Selected before/after screenshots and the production smoke record are committed
in `frontend-polish-evidence/` for PR review. The full local capture remains in
`.cache/frontend-polish/`, including all five viewport widths, map/list, large
text and high contrast variants. Baseline captures precede the service-hours
update in `d07730d`.

`after-routes-1440.png` and `after-planner-390.png` were refreshed after the
fare merge using code commit `d1167a3`. The desktop result now shows the
official seed rail fare **HK$17.10**; the timestamp and commits are recorded
in [fare-sync capture metadata](frontend-polish-evidence/fare-sync-capture.json).
All other screenshots and the original production smoke record were captured
before the fare merge. Older images may show **HK$12.50** and document the
visual baseline, rather than the current ticket calculation.

- [Before · desktop results](frontend-polish-evidence/before-routes-1440.png)
- [After · desktop results](frontend-polish-evidence/after-routes-1440.png)
- [Before · mobile planner](frontend-polish-evidence/before-planner-390.png)
- [After · mobile planner](frontend-polish-evidence/after-planner-390.png)
- [After · mobile map](frontend-polish-evidence/after-routes-map-390.png)
- [After · 1024 px Updates](frontend-polish-evidence/after-updates-1024.png)
- [Production smoke record](frontend-polish-evidence/production-smoke.json)

Reproduce with `npm run typecheck`, `npm test`, `npm run build`,
`npm run build:admin`, `python scripts/precompute_map_geometry.py --check`, and
`node tests/browser/p4.e2e.cjs` with the documented Python/Playwright environment.
