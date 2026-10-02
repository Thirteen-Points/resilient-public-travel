# DeepSeek V4.1 Flash integration

Verified on 2026-10-02 against the official [model announcement](https://api-docs.deepseek.com/zh-cn/news/news260910/), [API quick start](https://api-docs.deepseek.com/quick_start/) and [pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
Use API model ID `deepseek-flash` and base URL `https://api.deepseek.com`.
The product name `DeepSeek V4.1 Flash` is not the API identifier. Existing saved
administrator models are preserved; explicitly update an old `deepseek-chat`
selection in the console.

## Configure the server

For direct local startup, copy `backend/.env.example` to `backend/.env`, or set
the corresponding environment variables. CLI flags override dotenv settings.
For Compose use an explicit root env file, for example
`docker compose --env-file .env -f deploy/docker-compose.yml up --build -d`.
Keep real credentials outside Git and frontend variables.

```dotenv
OFFLINE_MODE=false
AI_ENABLED=true
AI_DISABLE_EXTERNAL=false
DEEPSEEK_API_KEY=<server-side key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
AI_BUDGET_CNY=50
AI_MAX_OUTPUT_TOKENS=2048
AI_CACHE_TTL_S=900
```

Alternatively, configure a DeepSeek connection/key in the same-origin admin
console and explicitly enable it. Saved admin settings take precedence when the
console is configured. Its enable switch is separate from the environment-key
enable switch. Offline mode and `--no-llm` still block both.

Requests use OpenAI-compatible JSON output and disable DeepSeek thinking for
bounded categorical extraction/wording. Routing, quantities, confidence and
capacity are computed by deterministic services. Invalid JSON/schema, invented
numeric wording, empty wording, attempted new tool calls, timeouts and budget
exhaustion preserve rule/template fallback. The chat endpoint always obtains
routes and simulation facts before optional wording. Its request must include
`message`, `origin`, `destination` and timezone-aware `depart_at`; `profile_id`
or an explicit `profile` can specify accessibility requirements.

## Usage and budget

`ai_usage.sqlite3`, beside the event/admin databases, records token counts,
provider cache-hit tokens, local cache hits, status and cost estimates without
keys, prompts or responses. `/api/admin/overview` includes `model_usage`.
All production model paths share this ledger: event ingestion, admin connection/
extraction tests and chat wording. Each request has independent diagnostics.

Before each paid attempt the ledger atomically reserves input/output cost.
Known returned usage replaces that reserve even if content validation fails.
Timeouts, malformed/missing usage and interrupted processes retain a conservative
estimate; restart does not reset the budget. Successful validated results use
a bounded in-memory TTL cache keyed by connection, model, key hash, schema and
input. Connection tests deliberately bypass that cache. Cached results do not
consume additional provider budget.

DeepSeek defaults use the verified peak CNY rates per million tokens: input 2,
provider cache-hit input 0.04, output 8. Off-peak invoices may be lower. Override
`DEEPSEEK_INPUT_COST_PER_MILLION`, `DEEPSEEK_CACHE_HIT_COST_PER_MILLION` and
`DEEPSEEK_OUTPUT_COST_PER_MILLION` when prices change. Custom providers need their
own equivalent `<PROVIDER>_*` rates. Without them each attempt retains
`AI_UNKNOWN_REQUEST_RESERVE_CNY` (default 1) as an explicitly unknown estimate.
That amount cannot establish a strict provider billing ceiling. Reconcile the
local ledger with provider billing; it is not an invoice. Do not delete the
ledger as a routine restart or to bypass a depleted budget.

## Remaining live acceptance

No real key was used and no paid API request was sent during this implementation.
After provisioning the intended key, use the console's explicit connection test
and a clearly simulated extraction sample. Verify the used model, token usage,
provider cache statistics and fallback with the public route flow. A must still
connect the visible Agent panel to `/api/ai/chat`. `--offline --no-llm` remains a
complete route/demo fallback without an external model.
