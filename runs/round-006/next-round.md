# Next Round Plan — Round 006

## Primary Objective

Close the remaining real-model and deployment acceptance gates after PR review.

## Entry Conditions

- M1 PR #95 and the M2 Round 006 PR have review decisions.
- Team provides ten approved real text samples outside Git and names the provider/model.
- A deployed test URL and reviewer access are available for online checks.

## Dependencies

- Real provider credentials in a trusted environment; no keys or raw texts committed.
- Team semantic review of each model result.

## Proposed Agent Assignments

- A: verify final bilingual wording and page/card visibility in deployment.
- B: run T2.6 real-model metrics, record sample IDs and categories, coordinate semantic review.
- C: fix any proven API or expiry regression in the appropriate milestone branch.
- D: audit final evidence and main merge/deployment status.

## Expected Deliverables

- Safe T2.6 result record, semantic review summary, deployed smoke-test evidence, and updated project state.

## Success Criteria

- Ten approved real samples; at least 8 first-pass valid outputs; retries/fallbacks and model recorded; semantic review passes.
- PRs merged to `main` by an authorized reviewer, then deployed API and browser checks pass.
