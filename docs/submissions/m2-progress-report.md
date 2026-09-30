# Interim Progress Report

**Project:** Resilient Public Travel (Thirteen Points)
**Reporting date:** 30 September 2026
**Interim window:** 2–4 October 2026

## Project status

Resilient Public Travel is a Hong Kong East Rail Line corridor prototype for
disruption-aware, accessibility-conscious journey planning. It combines an
event pipeline, deterministic route and simulation services, and a map-based
frontend. This report describes checked-in implementation and acceptance
evidence; it does not treat planned work as completed.

As of this reporting date, the scheduled M2 window has not started; the items
below are preparation status against the 2–4 October interim milestone.

## Completed

- **M0 integration:** The checked-in integration report records 312 passing
  A/B/C tests, successful data validation, and a successful offline preflight.
  It also documents remaining limits on official verification of accessibility
  and operational data. See
  [`m0-integration-report.md`](../acceptance/m0-integration-report.md).
- **M1 route-engine receipt:** The C-side baseline records that a published
  event delivered to the route engine changes its graph snapshot and causes
  routes to be recomputed. The report explicitly limits this evidence to the C
  receipt boundary; it does not certify the complete B-to-C-to-A workflow. See
  [`m1-c-baseline.md`](../acceptance/m1-c-baseline.md).
- **M1 demo preparation:** `scripts/demo_m1_story.py` contains a happy-path
  demonstration for signal intake, event review, publication, and rerouting.
  This report does not claim the script has been run successfully. A checked-in
  successful run log or independent end-to-end acceptance record was not found.
- **Data and reproducibility groundwork:** The repository includes seed data,
  provenance and data-quality records, deterministic offline startup, and
  validation/preflight scripts. The data ledger distinguishes official-source
  observations, derived estimates, and simulated fixtures.

## In progress

- **M1 end-to-end confirmation:** Run and record the demo against the current
  integrated application, including the frontend map and route-card refresh.
  The checked-in C baseline does not establish those UI behaviors.
- **Interim packaging:** Refresh the English README to match current endpoints
  and functionality; export a PNG architecture diagram; prepare the concise
  submission materials, board snapshot, and the P3/P4 plan.
- **Deployment and demo readiness:** Confirm a public URL or document the local
  run/video fallback, then record a cold-start and accessibility check. No
  deployment URL or deployment verification evidence is included here.
- **Recorded video:** The repository contains a demo script and a video
  outline, but no checked-in MP4 with bilingual subtitles was found.

## Next steps

1. Close or clearly disclose the M1 frontend and integration acceptance gaps.
2. Freeze an interim build and verify the current run instructions against it.
3. Complete and review the English architecture, provenance/AI statement,
   progress report, contribution summary, and board snapshot.
4. Record and review the three-minute bilingual-subtitled demo, or provide the
   planned local-run fallback if deployment is unavailable.

## Blockers and scope notes

- The M1 acceptance report records that automatic B-to-C event delivery and
  frontend refresh were outside its verified boundary. The demo script is
  preparation, not proof that this full chain passed.
- The coordination handoff records that the organization Project board had not
  been created and the 77 Issues had not been added. This status should be
  rechecked before submission.
- The 10,000-person sandbox belongs to **P3 (5–11 October)** in the project
  timeline, not M2 interim acceptance. Any sandbox output must be presented as
  simulation, not observed passenger data.
- Public deployment, a successful full end-to-end run, and a final video remain
  unverified in the checked-in evidence reviewed for this report.

## Evidence

- [`docs/acceptance/m0-integration-report.md`](../acceptance/m0-integration-report.md)
- [`docs/acceptance/m1-c-baseline.md`](../acceptance/m1-c-baseline.md)
- [`scripts/demo_m1_story.py`](../../scripts/demo_m1_story.py)
- [`docs/plan/05-timeline.md`](../plan/05-timeline.md)
- [`docs/coordination/T1.3-board.md`](../coordination/T1.3-board.md)
