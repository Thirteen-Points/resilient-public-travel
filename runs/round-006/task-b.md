# Agent B Task — Round 006

## Context

T2.6 requires ten team-approved real texts. The bundled ten samples are simulated. Expiry must propagate through audit, SSE, graph and route recomputation.

## Objective

Prepare a safe real-provider acceptance path and verify automatic expiry across the shared backend.

## Inputs

- `docs/coordination/T2.6-real-model-acceptance.md`
- `backend/app/services/structure/**`
- `backend/tests/test_b_replan_handoff.py`

## Files Allowed to Modify

- `backend/app/services/structure/**`
- `backend/tests/test_structure_provider.py`
- `backend/tests/test_b_replan_handoff.py`
- `docs/coordination/T2.6-real-model-acceptance.md`
- `scripts/run_t2_6_acceptance.py`
- `runs/round-006/report-b.md`

## Tasks

1. Identify whether GitHub contains approved real samples and run only evidence-backed acceptance.
2. Verify timed expiry, one audit action, SSE, graph recovery and route IDs.

## Deliverables

- `runs/round-006/report-b.md`

## Acceptance Criteria

- Partial T2.6 is labelled partial until a real model and ten approved real samples are run; expiry integration passes.
