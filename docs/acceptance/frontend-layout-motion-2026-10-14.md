# Shared passenger layout and page motion · 2026-10-14

Implemented on `codex/frontend-layout-motion`, based on `origin/main`
`ff96bd56bb10c6a8bd89171ee74ca1eee1a05693`. This change retains the latest
East Rail station selector, English interface, official fares, preference
editing, request cancellation and stale-response protection.

## Delivered behavior

- The initial Journey map, Report and Agent draw station markers with subdued
  outlines and readable hover/focus states. Background network paths are not
  generated. Candidate paths appear after a route query; approved disruptions
  remain visible on Updates and queried journeys. Existing verified geometry
  and explicit schematic/walking paths are retained.
- Plan journey, Report and Agent share the same grid, sidebar dimensions,
  padding, title size, map position and high-contrast borders. Desktop sidebars
  are 400 px at 1440 px and 360 px at 1024 px, with a 24 px map gap. Below
  1024 px, their content uses normal document flow and the existing map/list
  switch; mobile station labels remain visible in English.
- Transitions between these three pages and Updates/How it works use a 260 ms
  fade and small vertical movement. Browsers with element-scoped View
  Transitions capture the main content while the header remains interactive.
  Other browsers use the existing GSAP panel animation. Reduced motion skips
  both. Repeated navigation keeps the latest selection, and the mounted Agent
  preserves its unsent draft.

The scoped transition follows the [CSS View Transitions Level 2 element API](https://drafts.csswg.org/css-view-transitions-2/).
There are no changes to backend contracts, ranking, journey time, ticket prices,
accessibility decisions, public polling intervals or administrator review.

## Validation

| Check | Result |
| --- | --- |
| Frontend unit regression | 20 files, 151 tests passed |
| TypeScript and public production build | Passed |
| Administrator production bundle | Rebuilt and unchanged |
| P4 browser regression | 18 groups passed, including publication within 5 seconds, offline recovery, preferences and accessibility |
| Targeted browser regression | 13 groups passed with scoped transitions; 12 passed with the capability disabled, including actual animation frames, input availability, navigation cancellation and reduced motion |
| Rapid pointer navigation | 20 rounds with scoped snapshots and 20 with the capability disabled; all five header clicks delivered and the last page selected |
| Responsive layout | All five retained pages fit 320 and 390 px; all three sidebars and maps match at 1024 and 1440 px |

The targeted suite uses its own API/database and dynamic ports. Route queries,
approved event coverage, Agent draft preservation, keyboard-reachable forms,
station labels and computed marker contrast are checked through the rendered
interface. It is included in the existing GitHub regression workflow and
adapts to the browser's scoped-transition capability.

At a 1440 × 1000 viewport, all three sidebars occupy `x=64, y=148, w=400,
h=828`, and the map starts at `x=488`. At 1024 × 1000 they occupy `x=32,
y=148, w=360, h=828`, and the map starts at `x=416`. The previous Report and
Agent panels were 480 px wide and overlapped the map. Default station outlines
have approximately 1.33:1 contrast against their white fill; focus, hover,
point selection and high contrast provide stronger visual feedback.

## Captured evidence

Screenshots and measurements were captured from the local working tree using
the baseline above. They demonstrate the change before merging; deployment
checks are performed separately against the resulting main commit.

- [Previous Report layout](frontend-layout-motion-evidence/before-report-1440.png)
- [Plan journey, 1440 px](frontend-layout-motion-evidence/plan-journey-1440.png)
- [Report, 1440 px](frontend-layout-motion-evidence/report-1440.png)
- [Agent, 1440 px](frontend-layout-motion-evidence/agent-1440.png)
- [Report, 390 px](frontend-layout-motion-evidence/report-390.png)
- [Updates transition frame](frontend-layout-motion-evidence/transition-updates-1440.png)
- [Scoped browser measurements](frontend-layout-motion-evidence/scoped-layout-evidence.json)
- [Fallback browser measurements](frontend-layout-motion-evidence/fallback-layout-evidence.json)
- [Rapid pointer navigation](frontend-layout-motion-evidence/rapid-pointer-evidence.json)
- [Stable basemap capture metadata](frontend-layout-motion-evidence/final-capture.json)

The full before/after captures and isolated runtime logs are available locally
under `.cache/frontend-layout-motion/`; CI uploads the current regression
evidence as a workflow artifact.
