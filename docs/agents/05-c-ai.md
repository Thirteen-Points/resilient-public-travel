# Agent 5 — C-AI

Base branch: ZYC
Working location: ZYC (direct commits; no Agent branch)
Model: gpt-5.6-terra, reasoning medium

## Scope
Implement T8.1, T8.2, T8.4 and T8.5: OpenAI-compatible LLM client, DeepSeek→Qwen→GLM fallback, tool layer, call/cost logging, schema validation, retry/timeout/cache, and deterministic no-LLM fallback.

## Files
Own backend/app/ai/. Do not make the LLM generate routes, times, capacities, or simulation numbers; those must come from deterministic engine tools.

## Tools
geocode_place, find_access_points, search_transit_routes, score_routes, estimate_load, get_diversion_plan.

## Definition of done
LLM failure never blocks the main route flow; schema failure retries once then falls back; full query works with LLM disabled; every tool call is traceable; add tests and a PR summary.
