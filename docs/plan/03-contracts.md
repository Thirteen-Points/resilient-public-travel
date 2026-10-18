# 03 数据与接口契约（Contracts v1.0）

> **状态：待冻结（9/24 22:00 冻结为 v1.0）。** 冻结后任何字段变更走 §9 流程。
> 契约的作用只有一个：**让 A / B / C 三个人能同时开工，谁都不用等谁。**
> 配套种子数据文件：`contracts/seed/*.json`（A 立刻可用、C 用来校验解析器、B 用来演示事件卡）。

---

## 1. 目录骨架（9/24 前建好）

```
Hackathon2026SepOct/
├── docs/plan/                 # 本计划文档集（中文，内部用）
│   └── 00-INDEX.md ... 08-data-appendix.md
├── contracts/
│   ├── README.md              # 契约速查（谁消费哪个字段）
│   ├── schemas/*.json         # JSON Schema（校验用）
│   └── seed/                  # 种子数据：network / event / routes / sim
├── frontend/                  # Vite + React + TS + Leaflet        （A）
│   └── src/{pages,components,api,map,styles}
├── backend/                   # FastAPI + SQLite                   （B + C）
│   └── app/
│       ├── api/               # routers: signals events review routes sim graph meta
│       ├── services/          # ingest structure confidence persona   （B）
│       ├── graph/  engine/  sim/                                      （C）
│       ├── ai/                # tools.py  llm_client.py  prompts/     （B+C）
│       └── data/              # sqlite db + 生成的网络图快照
├── data/                      # 原始与处理后的静态数据 + 出处说明
├── scripts/                   # build_graph.py  fetch_weather.py  run_sim.py  export_demo.py
├── deploy/                    # 部署配置 + 保活脚本
└── README.md                  # 英文，对外（含一键运行与演示链接）
```

**文件级分工（避免冲突）**：A 只改 `frontend/`；B 只改 `backend/app/services/`、`backend/app/api/`（除 `routes.py`/`sim.py`）、`contracts/schemas/`；C 只改 `backend/app/graph|engine|sim|ai/`、`data/`、`scripts/`、`deploy/`。**跨区改文件必须提前在群里说。**

---

## 2. 枚举与常量（先定死，避免各写一套）

```jsonc
// 模式
"mode": ["MTR", "BUS", "MINIBUS", "WALK", "FERRY"]

// 线路 id（走廊 + 替代网络，真实线路，出处见 08）
"MTR":  ["ERL_E", "ERL_W", "TML", "KTL", "TWL", "ISL", "SIL"]
"BUS":  ["170", "182", "182P", "182X", "N182", "982X", "985", "985A", "985B", "81C", "87B", "80X", "82X", "83X", "280X"]
"MINIBUS": ["481B"]
"FERRY": ["TST_CEN"]

// 事件类型
"event_type": ["signal_failure", "train_failure", "door_fault", "power_failure", "weather", "crowd", "road_incident", "other"]

// 事件状态机（B 实现）
"status": ["draft", "pending_review", "published", "updated", "expired", "rejected"]

// 影响类型
"impact": ["closed", "reduced_capacity", "slow", "crowded"]

// 数据真实性
"provenance": ["real", "real-derived", "simulated"]

// 画像
"persona": ["commuter", "student", "tourist", "elderly", "wheelchair"]
"mobility": ["standard", "reduced", "wheelchair"]
"preset":   ["fastest", "most_stable", "fewest_transfers"]

// 分流参数
"eta_max_factor": 0.85        // 目标满载率上限
"diversion_fairness_max_extra_min": 15
"confidence_thresholds": {"publish_min": 0.6, "auto_expire_hours": 6}

// 颜色规范（A 用，全局统一）
"colors": {
  "normal": "#2E7D32", "affected": "#C62828", "degraded": "#F9A825",
  "route_A": "#1565C0", "route_B": "#6A1B9A", "route_C": "#00838F",
  "simulated": "#0288D1", "real": "#2E7D32", "derived": "#F9A825"
}
```

---

## 3. 数据对象（JSON Schema 要点 + 样例）

### 3.1 `Signal` — 原始信号（未结构化）

```json
{
  "signal_id": "sig_20260922_0007",
  "received_at": "2026-09-22T08:03:11+08:00",
  "source_type": "social",
  "source_name": "demo-social-stream",
  "author_hint": "anonymised",
  "raw_text": "大围站广播话东铁过海段信号故障，全部人落车，金钟方向停开",
  "raw_url": null,
  "lang": "zh-HK",
  "provenance": "simulated"
}
```

### 3.2 `Event` — 事件卡（**全系统最重要的对象**）

```json
{
  "event_id": "evt_20260922_001",
  "version": 3,
  "status": "published",
  "created_at": "2026-09-22T08:03:20+08:00",
  "updated_at": "2026-09-22T08:12:40+08:00",
  "published_at": "2026-09-22T08:12:40+08:00",
  "expires_at": "2026-09-22T14:12:40+08:00",

  "event_type": "signal_failure",
  "title": "东铁线红磡—会展过海段信号故障，过海服务暂停",
  "summary": "港铁公布红磡至会展站之间信号故障，东铁线过海段暂停服务，预计影响至中午。",

  "mode": "MTR",
  "line": "ERL",
  "direction": "both",
  "affected_segments": [
    {"from_node": "HUH", "to_node": "EXC", "impact": "closed", "capacity_factor": 0.0},
    {"from_node": "EXC", "to_node": "ADM", "impact": "closed", "capacity_factor": 0.0}
  ],
  "window": {"start": "2026-09-22T08:00:00+08:00", "end": null, "end_confidence": "unknown"},
  "severity": 4,

  "confidence": 0.9,
  "confidence_factors": [
    {"factor": "source_authority", "weight": 0.35, "score": 1.0, "note": "港铁官方新闻稿"},
    {"factor": "multi_source_agreement", "weight": 0.25, "score": 0.8, "note": "3 条社媒 + 1 条用户上报一致"},
    {"factor": "physical_consistency", "weight": 0.20, "score": 1.0, "note": "与天文台警告无关，与站序一致"},
    {"factor": "admin_confirmation", "weight": 0.20, "score": 1.0, "note": "审核员已确认"}
  ],

  "signals": ["sig_20260922_0005", "sig_20260922_0006", "sig_20260922_0007"],
  "reviewed_by": "admin_demo",
  "audit_log": [
    {"at": "2026-09-22T08:03:20+08:00", "actor": "system", "action": "created", "confidence_after": 0.20},
    {"at": "2026-09-22T08:05:02+08:00", "actor": "system", "action": "merged_signal", "confidence_after": 0.55},
    {"at": "2026-09-22T08:12:40+08:00", "actor": "admin_demo", "action": "published", "confidence_after": 0.90}
  ],
  "provenance": "real-derived"
}
```

**置信度阶梯规则（B 与 A 共同实现，Demo 的核心动画）**

| 阶段 | 起始 | 加分规则 | 上限 |
|---|---|---|---|
| 单条社媒 / 单条用户上报 | 0.20 | — | 0.35 |
| 第二条独立来源一致 | +0.15 | 多源一致 +0.2 | 0.55 |
| 官方 / 权威来源 | +0.35 | 官方公告直接 0.85 | 0.85 |
| 审核员确认 | +0.05 | — | **1.00** |
| 来源互相矛盾 | −0.15 | 记录冲突 | 触发"待核实"标记 |

### 3.3 `UserProfile` — 画像

```json
{
  "user_id": "u_demo_002",
  "persona": "wheelchair",
  "mobility": "wheelchair",
  "walking_speed_mps": 0.7,
  "max_walk_m": 400,
  "max_transfers": 2,
  "price_sensitive": 0.6,
  "has_discount_card": true,
  "urgency": "normal",
  "preset": "most_stable",
  "weights": {"time":0.25,"transfers":0.10,"walk":0.15,"price":0.05,"comfort":0.10,"reliability":0.25,"carbon":0.05,"freshness":0.05},
  "hard_flags": ["no_stairs", "no_minibus", "no_non_lowfloor_bus"],
  "note": "自由文本解析结果：'不要有楼梯，最好一程地铁'"
}
```

### 3.4 `RouteCandidate` — 路线候选（引擎输出给前端的主对象）

```json
{
  "route_id": "r_20260922_003",
  "label": "TML + 步行 + TWL",
  "legs": [
    {"mode":"MTR","line":"TML","from":"TAW","to":"ETS","depart":"08:20","arrive":"08:37","headway_s":180,"in_vehicle_s":1020,"walk_m":0,"fare_hkd":0,"accessible":true,"provenance":"real-derived"},
    {"mode":"WALK","from":"ETS","to":"TST","in_vehicle_s":300,"walk_m":420,"accessible":true,"provenance":"real-derived","note":"站内步行通道，有无电梯待核"},
    {"mode":"MTR","line":"TWL","from":"TST","to":"ADM","headway_s":120,"in_vehicle_s":300,"walk_m":0,"fare_hkd":12.5,"accessible":true,"provenance":"real-derived"}
  ],
  "total": {
    "time_s": 1900,
    "time_range_s": [1700, 2100],
    "queue_delay_s": 0,
    "transfers": 1,
    "walk_m": 420,
    "fare_hkd": 12.5,
    "co2_g": 820,
    "reliability": 0.86,
    "freshness_s": 45
  },
  "score": 0.78,
  "score_breakdown": [
    {"criterion":"time","raw":1900,"normalized":0.62,"weight":0.45,"contribution":0.279},
    {"criterion":"transfers","raw":1,"normalized":0.50,"weight":0.10,"contribution":0.050},
    {"criterion":"walk","raw":420,"normalized":0.48,"weight":0.10,"contribution":0.048},
    {"criterion":"reliability","raw":0.86,"normalized":0.86,"weight":0.35,"contribution":0.301}
  ],
  "load_estimate": {"users_on_route": 3120, "capacity_per_hour": 42500, "load_factor": 0.07, "expected_wait_s": 95, "board_refusal_prob": 0.0},
  "warnings": ["含 420 米站内步行通道，轮椅使用者请预留更多时间"],
  "notes": ["步行比你的偏好多 220 米"],
  "explain": "这是目前最稳的选择：全程轨道，不依赖已经九成满的过海巴士，但需要走一段站内通道。",
  "evidence": [{"event_id":"evt_20260922_001","used":true},{"source":"mtr_network_v1","freshness_s":86400}],
  "provenance": "real-derived"
}
```

`total.queue_delay_s` 是已计入 `time_s` 和 `time_range_s` 两端的额外排队等待秒数。
计算为 `max(0, load_estimate.expected_wait_s - route_parameters.headway_s / 2)`：
路径时间已有按班次计算的常规候车，排队模型的零需求基线（半班距）不重复累加。
路线级模型使用瓶颈班距，不按途经站点或换乘次数重复累加；纯步行为 0。
评分及解释在排队接入后计算，缓存仅保存未加排队的路径，每次命中仍重新读取负载并评分。
区间沿用行程模型的方差并整体平移，不表示已校准的排队等待置信区间。
缺少此字段的旧版本 seed 不得标成已计入排队；模拟需求仍标注 simulated。

### 3.5 `LoadEstimate` / `DiversionPlan` / `SimResult`

```jsonc
// LoadEstimate
{"route_id":"r_...","users_on_route":3120,"capacity_per_hour":42500,"load_factor":0.073,"expected_wait_s":95,"board_refusal_prob":0.0,"overloaded":false}

// DiversionPlan
{
  "plan_id":"dp_20260922_001","event_id":"evt_20260922_001","demand":10000,"window_min":60,
  "shares":[{"route_id":"r_001","share":0.42,"users":4200,"capacity_per_hour":42500,"load_factor":0.10},
            {"route_id":"r_002","share":0.31,"users":3100,"capacity_per_hour":466,"load_factor":7.2},
            {"route_id":"r_003","share":0.27,"users":2700,"capacity_per_hour":233,"load_factor":11.6}],
  "unstoppable_demand": 6140,
  "advice":["运力缺口 6,140 人/小时，建议提前 20 分钟出发或改用轨道替代","巴士路线已满，等待预计 2–3 班"],
  "fairness":{"max_extra_delay_min":15,"protected_users":412,"note":"轮椅与长者的个人最优被保留"},
  "provenance":"simulated"
}

// SimResult（预计算落盘，演示读取）
{
  "scenario_id":"scn_huh_exc_closed_am_peak",
  "population":10000,"time_range":["07:00","09:00"],
  "baseline":{"policy":"selfish","total_delay_person_min":184300,"p95_wait_min":37,"overloaded_routes":2,"served_rate":0.83},
  "guided": {"policy":"bucket","total_delay_person_min":112500,"p95_wait_min":14,"overloaded_routes":0,"served_rate":0.91,
             "unstoppable_demand":6140,"wheelchair_served_rate":0.94},
  "delta":{"delay_reduction_pct":38.9,"p95_wait_reduction_pct":62.2},
  "assumptions":["OD 权重模拟","画像比例模拟","巴士班次为推算值"],
  "provenance":"simulated"
}
```

> ⚠️ 上面 `SimResult` 里的数字是**占位示例**，必须由 `backend/app/sim/` 真实跑出来覆盖；**禁止手填**（见 `01` §9 反面标准）。

### 3.6 `Meta` — 新鲜度与来源（每屏必带）

```json
{
  "generated_at": "2026-09-22T08:20:00+08:00",
  "graph_snapshot": "g_20260922T081240Z_v3",
  "sources": [
    {"name":"HKO warnsum","last_ok":"2026-09-22T08:19:10+08:00","provenance":"real","url":"https://data.weather.gov.hk/..."},
    {"name":"MTR getSchedule","last_ok":"2026-09-22T08:19:40+08:00","provenance":"real"},
    {"name":"social-stream-mock","last_ok":"2026-09-22T08:18:00+08:00","provenance":"simulated"}
  ],
  "disclaimer": "本平台为学术演示，非官方应急指引；路线与负载为推算/模拟结果，请以港铁及运输署官方公告为准。"
}
```

---

## 4. REST API

| 方法 | 路径 | 说明 | 负责 | 关键返回 |
|---|---|---|---|---|
| POST | `/api/signals` | 用户上报 / 社媒模拟流注入 | B | `signal_id` |
| POST | `/api/events/ingest` | 文本 → 结构化事件卡草稿（调用 AI） | B | `Event(status=draft/pending_review)` |
| GET | `/api/events?status=` | 事件列表（审核台用） | B | `Event[]` |
| GET | `/api/events/published` | 已发布事件（地图与引擎消费） | B | `Event[]` |
| POST | `/api/events/{id}/review` | 审核：`approve` / `edit` / `reject` / `expire` | B | `Event`（含 `audit_log`） |
| GET | `/api/stream/events` | SSE：事件与置信度实时推送（**Demo 动画靠它**） | B | `Event` 增量 |
| GET | `/api/graph/network` | 地图图层数据（节点/边/线路/800m 圈） | C | `Network` |
| GET | `/api/graph/snapshot` | 当前图快照版本与受影响边 | C | `{snapshot_id, affected_edges[]}` |
| POST | `/api/routes/query` | `{origin, destination, depart_at, profile, event_ids}` → 10 候选 + 3–5 个性化 | C | `RouteCandidate[]` |
| POST | `/api/sim/load` | 给定需求与候选路线 → 负载与分流比例 | C | `DiversionPlan` |
| GET | `/api/sim/result?scenario_id=` | 读预计算的 1 万人仿真结果 | C | `SimResult` |
| POST | `/api/persona/parse` | 自由文本 → `UserProfile` 补丁（调用 AI） | B | `{patch, explanation}` |
| GET | `/api/personas` | 预设画像列表（前端切换用） | B | `UserProfile[]` |
| POST | `/api/ai/chat` | AI 对话（内部走 §5 工具调用） | B+C | `{message, tool_calls[], routes?}` |
| GET | `/api/meta` | 新鲜度、来源、免责声明 | C | `Meta` |
| GET | `/api/health` | 保活 + 演示前自检 | C | `{ok, sources[]}` |

**统一错误约定**：所有 4xx/5xx 返回 `{"error":{"code":"...","message":"...","fallback":"..."}}`；前端遇到错误时展示上一次成功数据 + "数据较旧"徽标，**不允许白屏**。

---

## 5. AI 工具（function calling schema 摘要）

```jsonc
// 工具定义示例：search_transit_routes（其余 8 个同构，见 02 §6）
{
  "name": "search_transit_routes",
  "description": "在受影响网络快照上搜索候选替代路线。只返回引擎计算的结构化结果，不产生新路线。",
  "parameters": {
    "type": "object",
    "properties": {
      "from": {"type": "string", "description": "节点 id 或地名"},
      "to": {"type": "string"},
      "depart_at": {"type": "string", "format": "date-time"},
      "modes": {"type": "array", "items": {"type": "string"}},
      "profile_id": {"type": "string"}
    },
    "required": ["from", "to", "depart_at"]
  }
}
```

**给 AI 的系统提示词必须包含的三条纪律**（B 维护 `backend/app/ai/prompts/`）：
1. 你**不可以**编造线路、站点、时间、票价、班次；所有数字必须来自工具返回；
2. 你必须**引用** `evidence` 与 `freshness`，并对模拟数据明确说明；
3. 工具调用失败时，直接告诉用户"暂时取不到数据"，**不要猜测**。

---

## 6. 种子数据（`contracts/seed/`）

| 文件 | 内容 | 谁用 | 用途 |
|---|---|---|---|
| `network.seed.json` | 走廊六站 + 替代轨道节点 + 巴士/小巴/渡轮线路（含班距、载客量、站序、坐标） | A（画图）、C（建图） | 让 A 第一天就能画地图，不必等 C 的图构建器 |
| `event.seed.json` | 3 张事件卡：低置信（单条社媒 0.2）、中置信（多源 0.55）、已发布（官方+审核 0.9） | A（卡片与时间线）、B（审核台） | 演示"置信度阶梯"的三态；审核台可空转 |
| `routes.seed.json` | 同一 OD、同一事件下 10 条候选 + 2 个画像各自的 top3 | A（卡片/对比视图）、C（对照自研引擎输出） | A 不等 C 就能做完整个前端 |
| `sim.seed.json` | 1 万人有/无引导的 `SimResult` 结构（数字为占位，需 C 用真实仿真覆盖） | A（看板） | A 先做图表，C 后填数字 |

**种子数据的硬要求**：所有坐标、班距、票价若未经核实，必须写 `"provenance": "real-derived"` 或 `"simulated"` 并在 `note` 里写明"待核实"。**禁止把猜测值标成 `real`**。

---

## 7. 前端消费约定（A 最该看的一节）

| 界面元素 | 数据来源 | 必填字段 |
|---|---|---|
| 地图线路与 800 m 圈 | `/api/graph/network` | `nodes[].kind`, `lines[].stops`, `catchment_m=800` |
| 受影响区段样式 | `/api/events/published` + `/api/graph/snapshot` | `affected_segments[].impact` |
| 路线着色（A/B/C 三色） | `/api/routes/query` 或 `/api/sim/load` | `route_id`, `total.time_range_s`, `score` |
| 路线卡片 | `/api/routes/query` | `score_breakdown`, `warnings`, `notes`, `evidence`, `provenance` |
| 置信度阶梯动画 | `/api/stream/events` + `Event.audit_log` | `confidence_after` 序列 |
| 分流看板 | `/api/sim/result` | `baseline` vs `guided`, `delta`, `unstoppable_demand` |
| 页脚/卡片底部 | `/api/meta` | `sources[]`, `disclaimer` |

**三个必须出现在 UI 上的字**（验收硬指标）：**来源、更新时间、免责声明**。

---

## 8. 契约冻结检查表（9/24 22:00 前逐项打勾）

- [ ] `contracts/schemas/*.json` 全部通过 `jsonschema` 校验种子数据
- [ ] 四个种子文件齐全，且 A 已能用它们渲染出地图 + 3 张事件卡 + 路线卡片
- [ ] `GET /api/health` 返回数据库与种子文件状态
- [ ] 前后端各有一个"假数据可跑"的分支被合并进 `main`
- [ ] 所有枚举与颜色写进 `contracts/README.md`，三方各留一份本地副本

## 9. 变更流程（冻结后）

1. 在群里发一条：改什么字段、为什么、影响谁；
2. 提 PR 同时改 `contracts/schemas/` + 种子数据 + 受影响代码；
3. 至少 1 人（非提出者）approve 才能合并；
4. **禁止直接改 `main`**；**冻结后新增字段只能"可选"**，不能把已有字段改类型或改语义。
