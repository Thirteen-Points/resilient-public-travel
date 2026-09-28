# M0 C-AI handoff

## Boundary

`ToolRegistry` is the sole AI tool boundary.  It records each call with the
handler-returned `provenance` and `freshness_s`; it never upgrades simulated
data to a stronger label.  `NoLLMQueryService` orchestrates deterministic
route, load and diversion tools and returns a public string `message`.

An unavailable, timed-out or invalid handler becomes a traceable safe tool
result.  It never causes the route flow to invent a replacement value.

## C-Data replacement point

Keep the AI package unchanged.  C-Data should instantiate the C-Route
`RouteHandlers` with its normalized, verified data adapter and demand/simulation
adapters, then pass `handlers.handlers()` to `build_default_registry(...)`.
The six stable names are:

- `geocode_place`
- `find_access_points`
- `search_transit_routes`
- `score_routes`
- `estimate_load`
- `get_diversion_plan`

Each handler result must retain `provenance` and `freshness_s`; the registry
propagates those fields into its audit trace.  No C-Data facts belong in this
package or its fixtures.

## Fixtures

`fixtures/chat_tool_results.simulated.json` remains an AI-only fixture and is
explicitly `simulated`.  It is not a transport source.

## Multi-OD boundary

`search_transit_routes` receives the caller's `from`, `to`, and `depart_at`
unchanged.  It has no corridor-specific OD constant.  If C-Route returns fewer
than its candidate target, `NoLLMQueryService` explicitly says that only the
computed candidates are displayed; it never pads the result with an invented
route.

## T8.1 LLM client verification

`LLMClient` uses the OpenAI-compatible `/chat/completions` JSON endpoint and
tries configured providers in this order: DeepSeek, Qwen, then GLM.  A bounded
outer timeout, provider failure, or schema failure advances to the next
provider; every attempt is recorded in `call_log`.  The verification tests use
only mocked requests and intentionally contain no provider keys or network
calls.  When AI is disabled, the deterministic fallback remains the result.
