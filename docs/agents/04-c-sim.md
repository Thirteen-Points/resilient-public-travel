# Agent 4 — C-Sim

Base branch: ZYC
Working location: ZYC (direct commits; no Agent branch)
Model: gpt-5.6-sol, reasoning high

## Scope
Implement T5.1–T5.6 and T5.8: capacity buckets, queue/waiting approximation, reproducible 10k population, self-optimal vs guided diversion, fairness constraints, honest unmet demand, precomputed results, and replanning triggers.

## Files
Own backend/app/sim/, load/queue/fairness modules, and data/sim/. Do not change route contracts; consume stable route_id/capacity/headway/ETA outputs from C-Route.

## Definition of done
Fixed seeds reproduce results; assumptions are recorded; simulated/real-derived values are labelled; unmet demand is shown honestly; wheelchair/elderly fairness is protected; cached results read under 300ms target; add tests and a PR summary.
