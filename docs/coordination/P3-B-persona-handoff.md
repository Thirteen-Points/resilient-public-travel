# P3 B persona handoff to A and C

Status after P3 integration: the shared app registers the catalog and parser
routers. Local shared-app tests cover both URLs and the optional parser fallback.
Catalog defaults are simulated design assumptions.

## Exact route-query contract

The route API accepts a `profile` object, not a `profile_id` or a bare `preset`.
The same object should be sent by A and by any Agent route tool. Values below
are from `data/personas.json`.

```json
{"origin":"TAW","destination":"ADM","depart_at":"2026-10-06T08:20:00+08:00","profile":{"persona":"commuter","mobility":"standard","max_walk_m":800,"max_transfers":3,"preset":"fastest","hard_flags":[],"weights":{"time":0.45,"transfers":0.10,"walk":0.10,"price":0.10,"comfort":0.05,"reliability":0.10,"carbon":0.05,"freshness":0.05}}}
```

```json
{"origin":"TAW","destination":"ADM","depart_at":"2026-10-06T08:20:00+08:00","profile":{"persona":"wheelchair","mobility":"wheelchair","max_walk_m":400,"max_transfers":2,"preset":"most_stable","hard_flags":["no_stairs","no_minibus","no_non_lowfloor_bus"],"weights":{"time":0.20,"transfers":0.10,"walk":0.25,"price":0.05,"comfort":0.10,"reliability":0.25,"carbon":0.025,"freshness":0.025}}}
```

C should verify that the engine enforces the wheelchair hard limits on this
request shape and that Agent tools map `profile_id` to the same object. No
route is guaranteed for an OD without accessible candidates.

## B-owned API and configuration

- `GET /api/personas` returns five simulated defaults in contract order: `commuter`, `student`, `tourist`, `elderly`, `wheelchair`. No reviewer token is needed. `data/personas.json` is the source; preferences are design assumptions, not observed passenger profiles.
- `GET /api/personas/presets` returns normalized effective weights for `fastest`, `most_stable`, and `fewest_transfers`. `data/presets.json` records them. C's current raw score tuples for the latter two sum to 1.05 and are normalized by the engine. The returned values match the current effective scoring ratios.
- `POST /api/persona/parse` returns `{patch, explanation, method}`. The default is `rule_fallback`. The model path requires both `AI_ENABLED=true` and `PERSONA_PARSE_AI_ENABLED=true` plus a configured provider key. No model key belongs in frontend code. Model output is schema-validated; failure falls back to rules. Explicit and existing wheelchair restrictions cannot be relaxed.
- Shared-app tests exercised the model path with fake clients. No real provider was called, and T2.6 remains paused.

## A handoff

Use the public catalog for the profile selector and display the returned `explanation` and `method` near any free-text preference control. A currently sends only `{preset}` in its live route query and has no five-profile selector or comparison view. A owns those frontend files and must pass the selected profile to `/api/routes/query` without presenting simulated preferences as measured passenger behavior.

## C handoff and current acceptance gap

The local deterministic query at `TAW → ADM`, `2026-09-22T08:20:00+08:00` returned the same top route ID `r_d242fe3d797400df` for all three presets and for commuter, student, tourist and wheelchair. Elderly (`mobility=reduced`, `max_walk_m=400`, `no_stairs`) returned no feasible route. B did not change C's candidates, hard filters, or score code. C should investigate feasible accessible candidates and demonstrate at least two different top routes on a documented same-OD comparison if the data support it. Never relax wheelchair limits or invent a route to pass the demo threshold. A and C should align on the route-query profile shape before UI wiring.
