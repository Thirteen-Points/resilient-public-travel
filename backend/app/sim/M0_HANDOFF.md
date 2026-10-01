# C-Sim M0 handoff

## Acceptance

Run from the repository root with the project Python runtime:

```text
python scripts/verify_sim_m0.py
python scripts/verify_sim_multi_od_m0.py
```

The command is offline, deterministic, and uses only explicitly simulated
fixtures. It rewrites `data/sim/m0-verification.json` and exits non-zero if any
route-field, provenance, reproducibility, capacity-conservation, fairness,
unmet-demand, replanning, precompute, or cache check fails.

The guided allocator limits standard users to the target capacity. Protected
users without a fair alternative may use the remaining physical capacity;
target overload is reported, and physical capacity is still a hard limit.
Protected users are first assigned to their accessible personal-best route
when that route still has physical capacity. Before this fix, capacity-first
route ordering could place them on a slower route even when their best route
had room. The M0 report now checks this case explicitly while retaining fixed
seed reproducibility, accessibility, conservation, and overload reporting.

This is algorithm and adapter evidence only. It is not evidence that transport
data is real, current, complete, or operationally safe.

## Multi-OD M0 prework

The original population model generated several origins but fixed every
destination to ADM, then ranked one shared route pool for every passenger.
The new internal path accepts a separate C-Route `query_details` result for
each directed `(origin, destination)` pair. It filters and allocates each
passenger only inside that OD's candidate set while reusing the existing
capacity, accessibility, fairness, and personal-best logic. The frozen public
`SimResult` is unchanged.

`multi_od_routes.simulated.json` compactly covers all 30 directed pairs among
TAW, KOT, MKK, HUH, EXC, and ADM with 59 distinct synthetic candidates. It
does not copy candidates to reach ten. The machine-readable report records
the exact candidate shortage and unmet demand for every OD, including one
explicit zero-candidate OD. MTR and BUS
profiles enter wheelchair rankings only when `accessible=true`; inaccessible
MTR and MINIBUS profiles remain in the fixture specifically to prove that the
hard filter rejects them.

## Current adapter boundary

C-Route `query_details` supplies `routes[]` plus
`route_parameters[route_id]`. C-Sim consumes stable `route_id`, ETA,
transfers, walk, fare, reliability, `freshness_s`, leg mode/accessibility,
headway, capacity, and provenance. A runtime compatibility test calls the
current C-Route engine directly. C-Sim does not add these private fields to
the public route contract.

The private `route_parameters` map is now described by
`backend/app/sim/route_parameters.schema.json`. Each map key and its value's
`route_id` identify the same candidate. The current C-Route producer emits
`headway_s` (seconds), `capacity_per_hour` and
`service_capacity_per_hour` (passengers/hour), `freshness_s` (seconds), and
`provenance`; `comfort` and `freshness_score` are optional internal metrics.
The two capacity fields have different meanings: the first is the target
allocatable capacity, and the second is service capacity before the target-load
factor. C-Sim's standard `query_details` path requires positive headway and
target capacity; missing or non-positive values are rejected rather than
silently replaced. Every value retains its own provenance classification.

For multi-OD use, the private wrapper is
`{"provenance": ..., "od_route_sets": [...]}`. Each item contains
`origin`, `destination`, `demand_weight`, `provenance`, `routes`, and
`route_parameters`, with the latter two retaining the ordinary per-query
shape. Empty candidate sets are represented by empty `routes` and an empty
`route_parameters` object. OD pairs must be unique; every non-empty candidate
`route_id` must also be globally unique across the wrapper, because the current
allocator keys supply/capacity records by `route_id`. If route identity should
represent a shared physical service across OD pairs, that requires a separate
shared-capacity model and is not implied by this adapter contract.

The schema documents the current engine's producer contract; it does not claim
that its capacity or provenance values are verified transportation facts.
Route identifiers are currently generated from the route edge sequence. The
multi-OD uniqueness requirement therefore remains a runtime check and must be
addressed explicitly if identical paths can occur in different OD sets.

For multi-OD simulation, `od_route_sets_from_contract` consumes a private
array whose items add only `origin`, `destination`, demand weight, and
provenance around the unchanged per-query `routes` and `route_parameters`
objects. The compact profile expander is fixture-only and rejects duplicated
candidate references or any attempted provenance upgrade.

B updates are validated as one of event, route-load, or weather updates and are
then passed to the deterministic replanning monitor.

## Dependencies and blockers

- **C-Data:** verified headway, capacity, residual capacity, demand, and source
  timestamps are not connected. All current values remain `simulated`.
- **C-Route:** keep `query_details.routes[]` and
  `query_details.route_parameters[route_id]` stable, including positive
  `headway_s` and `capacity_per_hour`. A formal private integration schema is
  still missing. Multi-OD live integration also needs one result per requested
  OD and globally unique candidate `route_id` values, or an explicit shared
  capacity identity/model if ids are intentionally reused across ODs.
- **B:** provide a live delivery mechanism for `event_id`, `version`, `status`,
  `confidence`, `route_id`, `load_factor`, `observed_at`, and
  `weather_warning_code`. C-Sim currently validates simulated messages but does
  not subscribe to B's event store or SSE stream.
- **C-Integrator:** may use `python scripts/verify_sim_m0.py` as the simulated
  single-pool gate and `python scripts/verify_sim_multi_od_m0.py` as the
  multi-OD gate. The latter writes
  `data/sim/m0-multi-od-verification.json`.

No additional C-Sim code failure is known after this fix. The unresolved items
above remain integration/data blockers and do not change the simulated result
into verified transport data.

## M0 simulation seed boundary

`contracts/seed/sim.seed.json` is an explicitly `simulated` placeholder for
M0 contract/UI wiring. Its root `scenario_id`, route references, overload
counts, assigned demand, unmet demand, shares, and deltas must be internally
consistent, but `meta.placeholder=true` is intentionally retained. The seed
must not be promoted to measured evidence or a formal computed `SimResult`.

Agent6 should keep the `PLACEHOLDER` finding as a hard failure whenever a
formal simulation result is being accepted. For M0 seed wiring, run a separate
shape/reference/aggregation check; for computed-result acceptance, point the
gate at `data/sim/scn_huh_exc_closed_am_peak.json`. Do not add an
`allow-placeholder` switch or weaken the formal result-quality check. M3 still
owns result-quality acceptance.
