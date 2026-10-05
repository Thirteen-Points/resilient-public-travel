# B prompt discipline

1. Route IDs, line names, times, fares, capacity, delay and load figures must come from a successful deterministic tool result. A model may explain the result, not create or alter it.
2. Identify simulated, estimated and derived data accurately. Never describe simulated demand or weather coefficients as measured passenger or service data.
3. If a tool or model fails, expose the failure and use the deterministic fallback. Human review is still required before a Signal affects the published network.

`backend/app/ai/llm_client.py` contains the runtime prompt; `backend/app/ai/schemas.py` enforces the output boundary. This file records the policy for reviewers and tests.
