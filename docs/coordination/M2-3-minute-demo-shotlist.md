# M2 Interim 3-Minute Demo Shot List

Status: script draft for the planned 2026-10-03 recording. The video has not been recorded, and no externally accessible production deployment is evidenced in this repository. This document is not evidence that either is complete.

## Recording outline

| Time | Screen and action | Suggested narration | Evidence and guardrail |
|---|---|---|---|
| 0:00-0:20 | Open the ResilientRoute map. Point out the East Rail corridor and the disruption scenario used in the demo. | "ResilientRoute explores how people can make more informed choices when a transport disruption affects a route." | Use the current app or a clearly labeled local capture. Do not imply that this is a live incident. |
| 0:20-0:55 | Submit or load a sample report. Show its source text beside the structured event draft and confidence/evidence fields. | "Reports are treated as evidence to review, not as confirmed facts. The system organizes the information so a reviewer can inspect it." | Use a fixture or scripted report only if it is visibly labeled as a demo scenario. Do not describe simulated text as a real public report or claim automatic verification. |
| 0:55-1:30 | In the review screen, inspect the affected segment and publish the sample event. Return to the map and show the changed segment and refreshed route results, if the integrated API run succeeds. | "A human reviewer decides whether the event should take effect. Once published, the route view can respond to the changed network." | Capture this as a live chain only after verifying the backend response, graph snapshot and route refresh in the recording session. Otherwise use a labeled prepared capture and say it is a scripted local demonstration. |
| 1:30-2:05 | Show one route result and open its details: time range, risks, source/provenance and disclaimer. If supported by the verified build, compare two preference profiles. | "The route view exposes the reasons and data boundaries behind a suggestion. Different preferences can change what matters in a route." | Do not claim two profiles produce different operational routes unless that behavior is verified on the recorded build. Current seed-mode routes are fixed fixtures. |
| 2:05-2:35 | Show the provenance/source view and briefly distinguish official-source inputs, derived heuristics and simulated fixtures. | "Some inputs come from public sources, some are derived, and some are simulated. The interface and records should make that distinction visible." | Do not imply a source poller is continuously running. A one-shot API integration or a fixture is not continuous live monitoring. |
| 2:35-3:00 | End on the system boundary/architecture view or a concise slide: current scope, known limits, next milestone. | "This interim version demonstrates the current workflow and its limits. Any crowd-simulation figures are model outputs, not observed ridership; we will show the inputs and report the comparison as it is." | Show a simulation comparison only after verifying the exact run, input manifest and both strategies. Report an unfavorable result as-is; do not imply measured real-world impact. |

## Capture checklist

- Planned recording date: 2026-10-03; owner in the project plan: A. Actual recording: **not completed as of this draft**.
- External deployment: **not evidenced as complete**. The project plan assigns deployment to C; add and verify the public URL before describing the app as online.
- Run the integrated event-to-route flow on the exact build being recorded. Keep the run output and note whether the screen is API mode, seed mode or a prepared capture.
- Add Chinese and English subtitles during production, then verify the final runtime is at most 3:00.
- Replace every conditional shot above only after checking the actual build. Keep demo fixtures and simulated data visibly identified.

## Interim package checklist

- [x] Demo script and shot list drafted in this document; video production remains separate.
- [ ] Architecture diagram PNG: pending output from C, as assigned in `docs/plan/05-timeline.md`.
- [ ] Public deployment: not verified; do not publish a URL claim until an external check succeeds.
- [ ] 3-minute MP4 with Chinese and English subtitles: not produced.
- [ ] GitHub Project board snapshot: pending confirmation of the actual board and capture. This checklist does not claim that a board was created or screenshotted.
- [ ] Interim package submission: planned for 2026-10-04; confirm each artifact before marking complete.

## Next milestones

- **P3, 2026-10-05 to 2026-10-11:** develop and validate the three differentiators; the plan schedules the first 10,000-person simulation run for 2026-10-07 and comparison work for 2026-10-08 to 2026-10-09. Treat these as planned milestones until run evidence is recorded.
- **P4, 2026-10-12 to 2026-10-18:** calibrate data, run bug bash and freeze features on 2026-10-14; deploy the final version, stress-test, prepare the offline fallback, record the final video and presentation, rehearse, then deliver on 2026-10-18.
