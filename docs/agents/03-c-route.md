# Agent 3 — C-Route

Base branch: ZYC
Working location: ZYC (direct commits; no Agent branch)
Model: gpt-6-astra, reasoning high

## Scope
Implement T3.3–T3.10: headway graph, graph snapshots, affected-segment closure/degradation, diverse candidate routes, hard constraints, scoring/explanations, walking estimates, caching, and eco/comfort estimates.

## Files
Own backend/app/graph/ and backend/app/engine/. Do not modify frontend, B event pipeline, or public contract fields without a contract note.

## Inputs
Use 03-contracts.md, C-Data network/access data, B's affected_segments, and persona weights.

## Definition of done
Published events switch snapshots within 2 seconds; affected edges are excluded; at least 8 candidates are returned; wheelchair routes exclude minibuses/stairs; score_breakdown is reproducible; cold-query P95 target is under 1.5s; route queries work with LLM disabled. Add tests and a PR summary.
