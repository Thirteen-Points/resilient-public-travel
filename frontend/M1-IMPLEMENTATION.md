# M1 frontend handoff

> This records the original seed implementation. The subsequent API integration,
> current modes and remaining B/C dependencies are documented in [M1-INTEGRATION.md](./M1-INTEGRATION.md).

## Implemented

- Route cards: ETA range, original score factors, risks, preference notes,
  source/provenance, snapshot freshness, disclaimer, and carrier colour chips.
- Review: searchable/filterable stage queue, keyboard navigation, original
  evidence beside editable fields, draft save/cancel, rejection reasons,
  publication confirmation, local action history, and replay.
- Agent: prominent planner entry, GSAP spring entrance, original SVG companion,
  green idle / red traffic triangle, independent loading ring, template replies
  from the existing data source, and a focus-only green BorderBeam.
- Shared GSAP page/card/confidence/success motion, with media-query cleanup and
  reduced-motion branches. Avatar loops and BorderBeam stop for reduced motion.
- Map: carrier colours, two-colour joint buses, stable fallback palette,
  selected-path casing, permanent bilingual station labels, pointer-anchored
  wheel zoom, keyboard/buttons/touch zoom, fit button, and colour legend.
- Departure: HKT calendar, known Sep–Oct 2026 holidays, time rail and shortcuts.
  `RouteQuery.departAt` receives the selected ISO value with `+08:00`.

## Data boundaries

The three event records are stages of one incident. Publishing supersedes the
previous published stage. `activePublishedEvents` evaluates changes at the seed
snapshot, not the current wall clock or the chosen journey time. A pending or
rejected stage cannot activate a map alert. The existing 60% publication threshold
is retained; editing text does not manufacture a higher confidence score.

Replay restores the original fields and confidence values, placing every stage
back in pending review. Local decisions and history reset on refresh. The latest
90% stage is immediately reviewable in this replay. A missing referenced signal
is explicitly identified; no original text is fabricated.

Route candidates remain fixed. Review decisions do not recalculate them. Agent
answers are delayed local templates, not API responses. Backend, shared contracts,
and seed JSON are unchanged. No five-minute demo script was made. Automated
tests were not run; the Bloub engine characterization suite is present in the
frontend tree but was not part of the browser walkthrough.

Default basemap is OSM raster: the previous vector default rendered a blank
background in the preview environment. The configured CARTO → OpenFreeMap → OSM
fallback remains available. Failed or stalled basemaps fall back to the independent
schematic overlays. Brand metadata lives in `src/lib/lineColors.ts`.

## Checks performed

- `npm run typecheck` — passed.
- `npm run build` — passed; Vite still reports a >500 kB main bundle advisory.
- Browser walkthrough: planner/date/time query; results/details; Updates and
  How it works; review replay/edit/save/cancel publication/confirm publication;
  arrow-key queue navigation/reject/filter; green Agent for pending records;
  red triangle plus loading ring after publication; reply error and recovery;
  carrier legend; pointer wheel zoom and zoom buttons.
- Desktop 1440px and narrow 390px/320px layouts inspected; narrow horizontal
  overflow corrected and rechecked. OSM basemap rendered in the final preview.
- Reduced-motion code paths were inspected; OS-level preference switching and
  physical touch pinch were not exercised by the available browser controls.

Dependencies and visual references are documented in `THIRD_PARTY_NOTICES.md`.
