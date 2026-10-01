# contracts · 契约速查（谁消费什么）

> 完整定义见 `docs/plan/03-contracts.md`。**本文件是每天开工要查的那一页。**
> 冻结时间：**9/24 22:00（v1.0）**。冻结后改字段 = 群里先说 + PR + 至少 1 人 review。

---

## 1. 谁给谁什么

| 提供方 | 契约对象 | 消费方 | 用途 |
|---|---|---|---|
| C | `network.seed.json` → `/api/graph/network` | A | 画六站、替代线路、800 m 步行圈 |
| B | `event.seed.json` → `/api/events/*`、`/api/stream/events` | A / C | 事件卡三态、置信度阶梯动画；C 用于关闭受影响区段 |
| C | `/api/routes/query` → `RouteCandidate[]` | A | 路线卡片、地图三色着色 |
| C | `/api/sim/load`、`/api/sim/result` → `LoadEstimate[]`、`DiversionPlan`、`SimResult` | A | 分流看板、比例条、运力缺口 |
| B | `/api/persona/parse`、`/api/personas` | A / C | 画像切换、自由文本 → 权重 |
| C | `/api/meta` | A | 来源、更新时间、免责声明（**每页必显示**） |

---

## 2. 枚举（先抄成常量，别各写一套）

- `mode`: `MTR | BUS | MINIBUS | WALK | FERRY`
- `event_type`: `signal_failure | train_failure | door_fault | power_failure | weather | crowd | road_incident | other`
- `status`: `draft | pending_review | published | updated | expired | rejected`
- `impact`: `closed | reduced_capacity | slow | crowded`
- `provenance`: `real | real-derived | simulated`
- `persona`: `commuter | student | tourist | elderly | wheelchair`
- `preset`: `fastest | most_stable | fewest_transfers`
- `mobility`: `standard | reduced | wheelchair`

## 3. 全局常量

```
catchment_m = 800                 // 走廊站点步行圈半径
max_walk_m  = 800（默认）/ 400（reduced & wheelchair）
max_transfers = 3（默认）
eta_max_factor = 0.85             // 目标满载率上限
diversion_fairness_max_extra_min = 15
confidence_thresholds = { publish_min: 0.6, auto_expire_hours: 6 }
```

## 4. 颜色（UI 全局统一，不要各自挑色）

| 用途 | 色值 |
|---|---|
| 正常线路 | `#2E7D32` |
| 受影响（关闭） | `#C62828` |
| 降权（运力下降） | `#F9A825` |
| 路线 A / B / C | `#1565C0` / `#6A1B9A` / `#00838F` |
| 真实 / 推算 / 模拟徽标 | `#2E7D32` / `#F9A825` / `#0288D1` |

## 5. 接口清单

```
POST /api/signals                 用户上报 / 社媒模拟流注入
POST /api/events/ingest           文本 → 事件卡草稿（AI 结构化）
GET  /api/events?status=          事件列表（审核台）
GET  /api/events/published        已发布事件（地图与引擎）
POST /api/events/{id}/review      approve | edit | reject | expire
GET  /api/stream/events           SSE：事件与置信度实时推送
GET  /api/graph/network           地图图层数据
GET  /api/graph/snapshot          当前图快照与受影响边
POST /api/routes/query            → 10 候选 + 3–5 条个性化
POST /api/sim/load                → 分流比例与负载
GET  /api/sim/result              预计算的 1 万人仿真结果
POST /api/persona/parse           自由文本 → 画像补丁
GET  /api/personas                预设画像
POST /api/ai/chat                 AI 对话（内部走工具层）
GET  /api/meta                    来源 / 新鲜度 / 免责声明
GET  /api/health                  保活 + 演示前自检
```

## 6. 种子数据加载（A 的最短路径）

```
contracts/seed/network.seed.json   → 地图图层（六站 + 12 条线路 + 7 条步行链）
contracts/seed/event.seed.json     → 三态事件卡（0.20 / 0.55 / 0.90）+ 5 条原始信号
contracts/seed/routes.seed.json    → 8 条候选路线 + 2 个画像的 top3（TAW→ADM，过海段关闭）
contracts/seed/sim.seed.json       → 1 万人有/无引导对比（占位数字，待 C 覆盖）
```

前端可以**先把这些 JSON 当作静态 fixture 导入**，接口就绪后改成 fetch。这样 A 从今天起就能做完整 UI。
从仓库根目录校验：

```powershell
python scripts/generate_contract_schemas.py
python scripts/validate_contract_seeds.py
```

第二条命令会用 JSON Schema 校验四个种子文件，并对 B 负责的 Event / Signal 继续执行 Pydantic 双重验证。校验器也会核对网络声明数量、线路与站点引用、路线端点与线路引用，以及仿真结果引用的路线 ID。Network、Route、Simulation 和 event seed 外壳 schema 按当前冻结字段手工维护；单条 Event / Signal schema 则由 Pydantic 模型生成。

## 7. 三条不可违反的约定

1. **未核实的数值不得标 `real`** —— 只能用 `real-derived` 或 `simulated`（见 `08` §9 待核实清单）。
2. **每个面向用户的数字都要能追溯到 `provenance` 与 `freshness_s`**；路线卡片与页脚必须有**来源 / 更新时间 / 免责声明**。
3. **AI 不产生任何数字与路线** —— 只能调用 `02` §6 的 9 个工具读取引擎结果。
