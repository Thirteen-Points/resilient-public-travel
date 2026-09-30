# Data and AI Usage Statement

**Project:** Resilient Public Travel
**Evidence reviewed:** checked-in repository files on 30 September 2026

## Data sources and confidence labels

The project uses three provenance labels. They describe the status of each
value, not the quality of the overall system:

- **`real`**: a value explicitly verified against an official source for the
  stated field and scope.
- **`real-derived`**: an estimate or calculation based on a named source or
  documented assumption. It is not an official operational measurement.
- **`simulated`**: synthetic or project-generated data used for tests,
  demonstrations, or model scenarios; it must not be presented as observed
  passenger or service data.

The checked-in ledger records MTR network references, Hong Kong Transport
Department data, Hong Kong Observatory sources, and project-owned fixtures.
It also records the dates, fields, access limitations, and verification scope
for those checks. A listed source does not mean every value in the application
has been verified against that source. In particular, the ledger states that
some route, fare, headway, accessibility, and capacity fields require further
field-level verification. Bus capacity is estimated from vehicle assumptions
and service frequency; public feeds cited by the project do not provide vehicle
passenger capacity.

The canonical detail is in [`data/PROVENANCE.md`](../../data/PROVENANCE.md),
with quality limitations in [`data/DATA_QUALITY.md`](../../data/DATA_QUALITY.md)
and calculation assumptions in
[`data/capacity_method.md`](../../data/capacity_method.md). Seed fixtures and
synthetic events or demand remain labelled as simulated. No live API response
or deployed service state is claimed by this statement.

## AI use and limits

The architecture assigns optional language-model assistance to text
structuring, preference interpretation, and human-readable explanations. The
deterministic route and simulation components are the source of transport
facts. The checked-in LLM system prompt explicitly prohibits generating routes,
stations, times, fares, headways, capacities, loads, delays, or simulation
figures; tool results are used to ground factual answers. See
[`docs/plan/02-architecture.md`](../plan/02-architecture.md) and
[`backend/app/ai/llm_client.py`](../../backend/app/ai/llm_client.py).

The client defaults to AI disabled, uses configured providers only when keys
are supplied, validates the response schema, applies a timeout and configured
budget, and falls back to deterministic wording on disabled/unavailable or
invalid model responses. The test/handoff record describes mocked provider
tests; it does not establish successful live-provider use. See
[`backend/app/ai/M0_HANDOFF.md`](../../backend/app/ai/M0_HANDOFF.md).

The project policy says not to send user identity or precise location to a
model; only structured, de-identified preference fields should be used. This is
a documented design rule, not an independently verified privacy audit.

## Reporting boundaries

- Model output is not an official transport notice or operational decision.
- Human review is required before an event is treated as published operational
  state, as described in the project architecture.
- Simulated passenger demand and simulation results are not real-time ridership
  measurements. A 10,000-person sandbox is scheduled under P3 in
  [`docs/plan/05-timeline.md`](../plan/05-timeline.md); it is not M2 acceptance
  evidence.
- The M1 C-side acceptance report records deterministic routing with LLM
  disabled. Live model-provider behavior and public deployment are not verified
  by that report.
