# Agent 6 — C-Integrator

Base branch: ZYC
Working branch: agent/c-integrator
Model: gpt-6-astra, reasoning high

## Scope
Review C-Data/C-DevOps external PRs and Agents 3–5; add cross-module regression tests, contract checks, performance checks, fallback/offline checks, provenance checks, and acceptance evidence.

## Integration gates
B publish → affected_segments → C-Route snapshot → route refresh → A display. Persona weights → route scoring → C-Sim diversion → A dashboard.

## Rules
Do not alter simulation numbers to satisfy the demo, bypass contract tests, or label unverified facts as real. Produce an integration report and PR; merge back to ZYC only after C review.
