# P3/P4 precomputed simulation response

`GET /api/sim/result?scenario_id=ID` continues to return the stored object
verbatim. P4 adds metadata to the two P3 shared-capacity result files; it does
not remove/rename existing metrics or change older M0/M2 responses. Consumers
must tolerate extra fields and show missing information as unavailable.
`schemas/sim.schema.json` remains the legacy seed schema, not this API response.

Use the complete checked-in examples:

- [Normal](../data/sim/m2_six_station_directed_od_am_peak_p3_shared_segments.json)
- [10% capacity sensitivity](../data/sim/m2_six_station_directed_od_am_peak_p3_shared_segments_residual_10pct.json)

| Field | Meaning |
|---|---|
| `scenario_id`, `input_version`, `model_version` | Scenario identity, frozen route-input version, directed shared-segment model version. |
| `input_file`, `input_sha256`, `input_hash_semantics` | Input path and SHA-256 with CRLF converted to LF; JSON values are never rewritten for hashing. |
| `data_version` | Frozen network/policy paths and historical hashes. Legacy hashes can use CRLF; validation accepts LF/CRLF representations of the same source text, never changed values. |
| `source_revision`, `source_dirty`, `generator_sha256` | Generator checkout HEAD, tracked-change flag at generation, LF-normalized generator hash. A dirty HEAD is a base identifier, not proof of a clean deployed artifact. |
| `generated_at`, `query_time` | Actual generation instant and frozen route query departure, both with timezone. Runtime benchmarks are measured separately. |
| `metric_units`, `assumptions`, `provenance` | Explicit metric units, modelling boundaries and `simulated`. No observed passenger measurement is implied. |

`baseline` and `guided` retain their existing fields. `total_delay_person_min`
is summed person-minutes; `avg_delay_min` is minutes/person; `p95_wait_min` is
minutes. `served_demand`, `unmet_demand`, `unassigned_demand` and
`unstoppable_demand` are people in the stated window. Served + unmet equals the
population. `unassigned_demand` is allocation without a feasible assignment;
`unmet_demand` also includes assigned passengers that cannot be boarded.
`unstoppable_demand` is the reported model capacity gap; use its recorded value,
not a sum inferred from other indicators. Route shares use the full population
as denominator; their sum can be below one and must not be renormalized.

`service_capacity_per_hour` is people/hour; physical/target capacity in a
`resource_load` row is people/window. `overloaded_routes` counts route buckets;
`overloaded_shared_resources` counts directed segment resources. They are
different indicators, so a stress baseline can have 0 overloaded route buckets
and 6 overloaded shared resources. Resource IDs are unique, shared across
overlapping route IDs; opposite directions have independent budgets.

Fixed seed reproduces simulation output, excluding generation metadata.
`scripts/verify_p4.py` checks three runs of each case against every recorded core
field; it does not tune the frozen policy. Normal delay improvement is 0%, and
older negative-benefit results remain available. The 10% capacity factor is
invented for stress testing, not measured residual capacity.

The frozen M2 route input references `data/sim/frozen-network.seed.json`.
This snapshot preserves the network bytes used to build the historical route
candidates, independently of later operational seed updates such as first/last
boarding windows. Both preflight and the generator validate the manifest's
network path and hash. Moving the reference changes the input manifest hash;
route candidates, policy weights and simulation metrics remain unchanged.
