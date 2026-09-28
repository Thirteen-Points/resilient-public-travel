# M0 QA Checklist — ResilientRoute Frontend

Scope: the M0 seed-driven demo (Tai Wai → Admiralty corridor, fixed snapshot
`2026-09-22T08:20:00+08:00`). This checklist is written for the integrated app
after the parallel modules (`api/`, `map/`, `lib/`) are wired into the pages.
It verifies behaviour and honest-data rules only — visual polish is judged
against the Figma spec separately, never by screenshot comparison here.

Related modules:

- Data boundary: `frontend/src/api/seedDataSource.ts`, `frontend/src/api/normalizers.ts`
- Map data: `frontend/src/map/transformers.ts` (`buildMapModel`, `buildImpactModel`, `buildRouteLayers`)
- Display + recovery: `frontend/src/lib/formatters.ts`, `frontend/src/lib/recovery.ts`, `frontend/src/lib/provenance.ts`

## 0. Build health

- [ ] `npm install` then `npm run dev` starts the Vite dev server with no console errors
- [ ] `npm test` passes (unit suites for api / map / lib)
- [ ] `npm run typecheck` reports no errors
- [ ] `npm run build` completes

## 1. Map renders from seed data

- [ ] Six corridor stations render (Tai Wai, Kowloon Tong, Mong Kok East, Hung Hom, Exhibition Centre, Admiralty) with bilingual labels (`Tai Wai · 大圍` style)
- [ ] All 22 seed nodes are transformable; nothing beyond the seed appears on the map
- [ ] Alternative lines render: TML detour, KTL, TWL crossing, plus bus / ferry / minibus services
- [ ] 800 m catchment circles render for the six corridor stations; radius comes from `catchment_m` in the seed (node override, network default `800` as fallback) and is a ground-distance circle, not a fixed pixel circle
- [ ] The unmodelled minibus terminus `BS_TW` is absent and no geometry is invented for it (`stopIdsWithoutStation` stays `['BS_TW']`)

## 2. Events — three cards, one gate

- [ ] Three event cards are visible on the Updates screen: pending (0.20 confidence), pending multi-source (0.55), published (0.90)
- [ ] Pending events do **not** change the map: with only `evt_seed_001` / `evt_seed_002` the impact overlay is empty
- [ ] The published event `evt_seed_003` alone changes the map: HUH→EXC and EXC→ADM render as closed (not passable), TAW→KOT renders as crowded (passable)
- [ ] Expired-window behaviour: querying past `2026-09-22T12:00+08:00` yields no active published event (`getPublishedEvents` returns `[]`)

## 3. Simplified route cards

- [ ] Three candidates (A/B/C) render for Tai Wai → Admiralty with stable layer identities (`route-A`, `route-B`, `route-C`)
- [ ] ETA range uses an en dash (`31–38 min`), never a hyphen
- [ ] Fare renders as `HK$12.50`; a missing fare renders `—` with its reason, never `HK$0`
- [ ] Walk distance renders in metres (`420 m`), never miles
- [ ] Provenance badge on every card: `Real` / `Estimated / Derived` / `Simulated`; unknown values show `Unknown`
- [ ] Warnings and at least one human-readable explanation (`explain`) are visible

## 4. Compliance trio — on every screen

- [ ] Source (which seed / which line record) is stated
- [ ] Update time is shown in HKT (`… HKT` suffix) and matches the snapshot
- [ ] The disclaimer text from `getMeta().disclaimer` is visible (academic demo, follow official announcements)

## 5. Responsive layout

- [ ] 1440 px: two-column, map plus side panel, no overflow
- [ ] 1024 px: map and results coexist; results column ≥ 360 px
- [ ] 390 px: single column; map/list switch works
- [ ] 320 px: no horizontal overflow; ETA ranges and bilingual station names are not clipped

## 6. Accessibility

- [ ] Keyboard: Tab reaches every interactive element (station combobox, presets, route select, nav) in a logical order; ArrowUp/ArrowDown move the station list; Enter selects; Escape cancels
- [ ] A visible focus ring is present on every focusable element
- [ ] `prefers-reduced-motion: reduce` disables pulsing/animated effects (map pulse, confidence animations)
- [ ] Map pick and status messages are announced (`role="alert"` / live regions)

## 7. Degraded and recovery states (P13)

States are modelled in `frontend/src/lib/recovery.ts`; each must show a message, a fallback, the previous-result policy and a next action — never a blank page.

- [ ] Loading: previous data stays visible while a refresh is in flight
- [ ] Empty: no route for an unmodelled OD pair shows honest emptiness with a way back to the corridor
- [ ] Stale: old data keeps rendering with a stale indication, not an error
- [ ] Offline: network failure keeps the last successful result on screen (seed snapshot keeps the demo alive)
- [ ] Out of range: picking a point > 800 m from any access point names the nearest access point and suggests station search
- [ ] AI unavailable: preset preferences still produce deterministic seed routes
- [ ] Error: API error envelope `{error:{code,message,fallback}}` maps to a readable state; unknown values render `—`, never `0`

## 8. Honest-data audit

- [ ] Spot-check 10 visible numbers (ETA, fare, walk, load, confidence): each is traceable to a seed file or explicitly labelled `Simulated`
- [ ] No `simulated` record is ever labelled `Real` (`worstProvenance` decides merges)
- [ ] `seedIssues` from the DataSource boundary is empty for the shipped seeds (any non-empty entry is a field conflict to report, not to hide)

## 9. Negative tests

- [ ] Unmodelled OD (e.g. Tai Wai → Hung Hom) returns no fabricated routes
- [ ] Unpublished / expired events never colour segments (`buildImpactModel` excludes them with a recorded reason)
- [ ] Missing coordinates stay missing: no station, circle or segment is drawn from invented positions
