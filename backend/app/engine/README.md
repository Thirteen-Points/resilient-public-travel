# C-Route：T3.3–T3.10 / ZYC 前置交付

直接在 **ZYC** 工作。所有实现、fixture 和测试均在 `backend/app/graph/` 与 `backend/app/engine/`；没有修改公共契约、main、B 事件管道或 C-Sim 的 load/queue/fairness 模块。

## 本次已完成

- headway 时序有向多重图、沿线相位偏移、连续乘车只计一次候车；服务日历/假期/时间窗、午夜与班距切换。
- 不可变事件快照与原子发布/落盘；按线路、模式、区段、方向和事件有效期关闭或降权；旧版本增量不回退快照。
- 有界无环候选搜索，严格执行步行、换乘和无障碍限制；中间节点 Jaccard <0.7，每个换乘点至多两条路线，可行时覆盖两种乘车模式；不足数量如实告警。
- 可复算八维评分、ETA 区间、中文规则解释、来源/新鲜度、软偏好备注、步行距离矩阵、模拟碳排放与舒适度模型、按快照/时刻/画像隔离的 LRU。
- **数据适配器**隔离 seed 和最终数据：线路、容量、班距、票价均从输入读取；核心不内置具体线路或车辆容量。核验后替换适配器及其输入即可。
- **契约 HTTP 适配器**提供 `/api/graph/network`、`/api/graph/snapshot`、`POST /api/routes/query`，路线响应为 `RouteCandidate[]`，包含 `load_estimate`，错误为 `{error:{code,message,fallback}}`。
- 负载是注入接口，不在本模块重复实现 C-Sim 算法。仅 seed 明确采用模拟零需求 fixture；其他数据源未提供负载时返回 503，不猜客流。路线缓存命中后仍重新调用负载提供方。

## 使用的 fixture 与真实性

1. `contracts/seed/network.seed.json`、`event.seed.json`：只读；SeedDataAdapter 对内存副本的 meta、节点、线路、步行边及事件统一标记 **simulated**。原文件保持原样。
2. `engine/fixtures/seed_policy.json`：模拟票价基线、缺省票价、轨道票制分组、零需求场景以及 CLI 示例 OD/时刻。核心没有 12.5 港元或具体 OD 的隐藏默认值。
3. `engine/fixtures/network.synthetic.json`：O→D 的十条独立人工线路、两种模式；全部 simulated。用于证明算法不依赖香港种子线路名、车辆容量或班距。
4. `engine/fixtures/events.synthetic.json`：关闭其中一条人工线路的模拟事件，验证快照及契约返回九条剩余路线。
5. 单元测试内的小型图、事件和步行边都明确标记 simulated。碳排/座位概率/方差系数属于模拟模型，不声称实测；路线总体仍标 simulated。

## 运行与 API 接入

Python 3.10+。图和算法只用标准库；HTTP 层及契约测试用 FastAPI/httpx，当前测试版本记录在 `requirements-test.txt`。

```bash
python -m pip install -r backend/app/engine/requirements-test.txt
python -B -m unittest discover -s backend/app/engine/tests -v
python -B -m backend.app.engine --events contracts/seed/event.seed.json
```

```python
from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app, create_router

engine = RouteEngine.from_seed(events_path="contracts/seed/event.seed.json")
app = create_app(engine)  # 可单独部署；已有 FastAPI app 可 include_router(create_router(engine))
routes = engine.query("TAW", "ADM", "2026-09-22T08:20:00+08:00", {"preset": "fastest"})
top3 = routes[:3]

# B 的发布/更新/撤销回调；全量仓库同步使用 replace_events(events)。
engine.snapshots.update_event(event_dict)
```

`create_app()` 为独立 HTTP 验证入口，包含统一 4xx/5xx 处理。仅复用 router 时，集成方继续使用主应用的统一异常处理。请求 origin/destination 当前使用节点 ID；地名/坐标解析由 C-Data/C-AI 的接入层负责。发布钩子同步构建新快照，不依赖 LLM。

## 最终数据接入，只换适配层

```python
from backend.app.graph.adapter import MappingDataAdapter

adapter = MappingDataAdapter(
    normalized_network,        # 现有 network seed 结构；带来源与更新时间
    baseline_fare=verified_baseline_fare,
    fares=normalized_fares,    # 内部票制配置；不增加公共契约字段
    events=published_events,
    holidays=verified_holidays,
)
engine = RouteEngine.from_adapter(adapter, load_provider=sim_load_provider)
```

也可实现 `DataAdapter.load() -> RoutingData` 对接最终 C-Data 文件格式。适配层对缺失容量、班距、票价和来源报错，不自动填入模拟值。`fares` 按 line_id 映射 `{fare_hkd, group, provenance, note}`；只有明确配置相同非空 group 才连续计价一次，和交通模式无关。种子票价区间取上界及基线假设全部局限在 SeedDataAdapter。

## 需要其他 Agent 提供的接口

| 提供方 | 接口 / 输入 | 本模块消费点 |
|---|---|---|
| C-Data | 已核验节点/边/线路、班距日历、容量、票价、票制分组、无障碍属性、来源/更新时间、公众假期 | `MappingDataAdapter` / `DataAdapter.load()` |
| B | 现有 Event、版本、状态、affected_segments、window 和发布/撤销回调 | `SnapshotStore.update_event()` / `replace_events()` |
| B/契约负责人 | 正式 `contracts/schemas/*.json` | 已有文档驱动的消费者测试；拿到正式 schema 后补验证，不修改字段 |
| C-Sim | 已有 `RouteSupply`、`estimate_queue`、`build_diversion_plan`；显式客流快照由 `MappingDemandAdapter` 提供 | `engine/sim_adapter.py` 已桥接；每次查询返回前更新负载 |
| C-Integrator | 注册 router、主应用统一异常处理、端到端事件传播与 API 验收 | `create_router(engine)` / `create_app(engine)` |
| C-AI | 注入 `RouteHandlers.handlers()`；会话级实例隔离 | 六个确定性 handler 已实现路线 ID 解析、画像读取和静态地名解析 |

内部 `query_details()` 返回 routes、graph_snapshot、diagnostics、route_parameters 和 expanded；它不是 REST 返回包装结构。每个 `route_parameters[route_id]` 含 capacity_per_hour（已乘 **一次 0.85**）、service_capacity_per_hour（未乘 0.85）、headway_s（最保守有效班距）、provenance。供 C-Sim 的 `RouteSupply.from_route_output` 适配时加上 route_id 即可；不要重复乘 0.85。没有公共 RouteCandidate 新字段。路径 ID 由边序列计算，快照版本独立。

## 测试结果与当前阻塞

- 单元/消费者契约测试覆盖候车、时段切换、无障碍、关闭/降权/过期、不可变快照、持久化、多样性、评分复算、缓存、负载刷新、HTTP 成功/错误形状、全链模拟来源与只换适配器的集成行为。
- 香港 seed 场景普通画像 10 条；轮椅 top-3 按 M0 默认无障碍策略由动态引擎生成并与 seed picks 对齐。人工网络正常 10 条、关闭后 9 条。硬约束优先，不凑数。
- 测试打印 25 次冷查询（含每次建图）的 P95，并检查 <1.5s；同步发布/落盘测试检查 <2s。最终次数和耗时见提交报告。
- **fixture 前置开发无阻塞**。正式 JSON Schema 尚未落盘，当前测试直接从 `03-contracts.md` 读取 RouteCandidate 示例并独立断言字段/类型/数值；不把它宣称为正式 schema 验收。
- 实际交通准确度、步行误差 <30%、容量/票价/峰期方向、电梯/低地台可达性、公众假期及全链路发布延迟，仍待 C-Data 和集成验收；不影响当前算法与接口测试。seed 缺失 BS_TW 被明确跳过，未伪造节点。

## 提交范围与报告

本次将已有 C-Route 核心带入 ZYC 并完成适配与契约前置工作，测试迁入自有目录；不改 main 或其他 Agent 的文件。每次提交报告列出完成内容、fixture、测试结果、阻塞、所需接口和实际提交 SHA。


## 接口稳定版：字段来源、单位与位置

**保持公共 RouteCandidate 结构**。`headway_s`、`capacity_per_hour`、`freshness_s` 不重复添加到公共路线根对象：分别使用 `legs[].headway_s`、`load_estimate.capacity_per_hour`、`total.freshness_s`。内部稳定的 C-Sim 输入是 `query_details()["route_parameters"][route_id]`，这三个键在那里是同名平铺字段，同时提供 `route_id`、`service_capacity_per_hour` 与 `provenance`。

| 字段 | 来源 / 计算方式 | 类型与单位 |
|---|---|---|
| `route_id` | 有序、有向边 ID 序列的 SHA-256 前 16 位加 `r_`；同一物理路径跨画像/时刻保持一致，快照版本另存 | string，无单位 |
| `total.time_s` | 最后一段抵达时刻 − 查询出发时刻；包括每次登车候车、运行及步行 | number，秒 |
| `total.transfers` | `max(0, 登车次数 − 1)`；同线路连续区段只计一次登车，步行打断乘坐后重新登车 | integer，次 |
| `total.walk_m` | 路径中 WALK 边输入 `walk_m` 的总和 | number，米 |
| `total.fare_hkd` | 适配器 `fares[line_id].fare_hkd` 按登车收费，相同显式非空票制 group 的连续换乘不重复收费；等于各 leg 票价之和 | number，港元 |
| `total.reliability` | `max(0, 1 − sigma_s / time_s)`；同一连续乘车段的模式模拟 sigma 累加，不同 leg 按方差合并；受天气事件影响的巴士/渡轮加惩罚 | number，0–1 无量纲；模拟估计 |
| `legs[].mode` | 标准化网络 `lines[].mode`；步行连接为 WALK | enum：MTR/BUS/MINIBUS/WALK/FERRY |
| `legs[].accessible` | 一般画像按边与沿途节点数据计算；轮椅 M0 将 MTR/大巴默认视为可用，明确 false/partial、阶梯仍阻断，且始终排除小巴；WALK/FERRY 仍需明确可达，累计步行 ≤400m | boolean；轮椅默认规则在结果 warning 中说明，不代表官方核验 |
| `legs[].headway_s` | 登车时段名义班距 / 当时运力系数；由 adapter 网络和当前事件快照计算；WALK 省略此字段（无车辆班距） | number，秒/班 |
| 内部 `headway_s` | 路径各乘车区段有效班距的最大值，含登车后区段降权；用于保守负载估算 | number，秒/班；仅 WALK 为 0 |
| `load_estimate.capacity_per_hour` / 内部 `capacity_per_hour` | 各乘车区段 `3600 / 名义班距 × capacity_per_vehicle × capacity_factor × 0.85` 的最小值。0.85 已应用一次；内部供给保持完整精度，C-Sim 卡片可四舍五入到三位小数 | number，人/小时 |
| 内部 `service_capacity_per_hour` | 上述运力在乘 0.85 之前的物理服务吞吐；排队 rho 用此值作分母 | number，人/小时 |
| `provenance` | 当前 seed、合成 fixture、模拟碳排/舒适度/可靠度/队列结果均 simulated；读取 adapter 不会将未核验值升级为 real | enum：real / real-derived / simulated；当前演示输出 simulated |
| `total.freshness_s` / 内部 `freshness_s` | 各段出发时刻减该段 `updated_at` 或 `network.meta.built_at` 的非负最大值；只有无时间戳时才使用显式 freshness_s / 已告警的 24h 模拟下界 | number，秒 |

地名/接入点工具的 `freshness_s` 使用会话 `observed_at` 与输入数据更新时间的差；传入 observed_at 可完全复现。负载工具使用供给和客流快照的新鲜度最大值。公共 `DiversionPlan` 保持 C-Sim 原有字段，数据新鲜度可追溯到当前搜索上下文及其 supply rows，不给公共计划新增字段。

## 六个确定性 handler 的实际位置与调用

六个实现均为 **`backend/app/engine/handlers.py::RouteHandlers` 的同名方法**。`engine/sim_adapter.py` 只桥接 C-Sim 的现有算法，不重复实现队列/分流规则；`graph/adapter.py` 读取交通数据和画像，AI 层不存交通事实。

| Handler | 输入 | 返回与边界 |
|---|---|---|
| `geocode_place` | query | 精确匹配节点 id、中文/英文名或输入 aliases；返回 node_id/lat/lng/label/provenance/freshness_s。坐标为 WGS84 十进制度；未知或重名报错，不猜地点 |
| `find_access_points` | lat/lng，radius_m 默认及上限 800（仅起终点接入半径） | 返回半径内**已建模网络节点**，含 kind、accessible、distance_m、来源和新鲜度，按距离和 ID 排序；距离为 Haversine 米数，不宣称存在未建模入口或步行连接 |
| `search_transit_routes` | from/to、depart_at、可选 modes/profile_id | 返回现有 `RouteCandidate[]`；profile_id 来自 adapter.profiles；保留本会话最新完整候选集和快照。Python 通过 `**{"from": ..., "to": ...}` 传入保留字字段 |
| `score_routes` | route_ids、可选 weights | 返回 RouteScore 列表：route_id/score/score_breakdown/provenance/freshness_s；始终以该次完整候选集归一化，避免只传一条就虚假变满分 |
| `estimate_load` | route_ids、正整数 horizon_min | C-Sim LoadEstimate 列表加工具元数据 provenance/freshness_s；users_on_route 是窗口内人数，capacity_per_hour 仍为人/小时，expected_wait_s 为秒，load_factor/refusal 为无量纲 |
| `get_diversion_plan` | event_id、非负整数 demand | 原有 DiversionPlan；窗口固定 60 分钟，demand/分配/缺口均为该窗口人数。事件须在最近查询出发时已发布且有效。由 C-Sim 的聚合算法计算，无逐人画像的限制保留在 fairness.note |

后三个 route-id/context 工具需要先搜索。未知 ID、重复 ID、过期快照、未配置客流均明确报错；图变化后必须重新搜索。一个 RouteHandlers 实例对应一个会话，不在多个用户之间共享最近查询。

```python
from backend.app.graph.adapter import SeedDataAdapter, JsonDataAdapter
from backend.app.engine.handlers import RouteHandlers
from backend.app.engine.sim_adapter import MappingDemandAdapter
from backend.app.ai.tools import build_default_registry

handlers = RouteHandlers(
    SeedDataAdapter(events_path="contracts/seed/event.seed.json"),
    observed_at="2026-09-22T08:20:00+08:00",
)
registry = build_default_registry(handlers.handlers())
# await registry.call("search_transit_routes", {
#     "from": "TAW", "to": "ADM", "depart_at": "2026-09-22T08:20:00+08:00",
#     "profile_id": "wheelchair",
# })

# 标准化文件入口：网络结构与公开 seed 的 nodes/lines/walk_links 一致。
# routing policy 是内部适配器配置，含 baseline_fare / fares / holidays / profiles。
adapter = JsonDataAdapter(
    "backend/app/engine/fixtures/network.synthetic.json",
    "backend/app/engine/fixtures/routing.synthetic.json",
    "backend/app/engine/fixtures/events.synthetic.json",
)
demand = MappingDemandAdapter({}, source="explicit_demo_demand", provenance="simulated",
                              freshness_s=0, default_rate_per_hour=0)
handlers = RouteHandlers(adapter, demand_adapter=demand, observed_at="2026-09-22T08:20:00+08:00")
```

`MappingDemandAdapter` 的 rates_per_hour 单位为人/小时，窗口人数按 `floor(rate × horizon_min / 60)` 计算。默认客流必须显式提供；seed 的零需求由已有 fixture 声明。队列/分流仍是模拟模型，所以即使输入观测已核验，计算输出也不标 real。

## 本阶段验证与剩余接口事项

- 当前 ZYC 的原单行评分断言已无括号错误；本次进一步拆成 `rescored = score_routes(...)` 和独立断言，并运行整个 `backend/app` 的 compileall。
- **42 项 C-Route 测试通过**，新增 12 项覆盖六个 handler 的最小契约及真实 AI 注册器/CSim 调用。合成关闭场景正反向均排除关闭线路；轮椅排除非低地台、小巴、阶梯、partial 和不可访问节点；快照变化拒绝旧结果。
- 标准化文件适配测试实际读取 simulated JSON，并仅更换线路 ID/班距/容量/票价/坐标后验证输出变化；`candidates.py` 字节保持不变，证明无需重写核心。
- **C-Route 的六个 handler 无待实现接口阻塞**。最终 C-Data 标准化实包尚未出现在仓库，因此当前确认的是约定结构/模拟包可读；实包到位后仍需验证字段映射和数据准确度。正式 JSON Schema 与实际入口/电梯信息仍待对应负责人交付。
- 上述接口稳定阶段的 C-AI trace 限制已由后续 C-AI 提交修正；最新 M0 测试确认 trace 保留 simulated 和数据新鲜度。本模块不修改 AI 层或公共契约。


## M0 最新交接

以 [reports/M0_HANDOFF.md](reports/M0_HANDOFF.md) 为最新状态：C-Route 54 项、相关消费者契约 17 项、Route→AI 专项 1 项全部通过，compileall 通过。四份 seed 的哈希、旧字段/引用差异及实际计算的基础演示响应见 [reports/m0-evidence.json](reports/m0-evidence.json)。正式 Schema 与完整 M0 验收未被冒充为通过。

`RouteHandlers` 的直接方法仍返回前文所列结果；`handlers.handlers()` 是 AI 注册器专用包装：search → `{routes, graph_snapshot, provenance, freshness_s}`，access → `{access_points, provenance, freshness_s}`，score → `{scores, provenance, freshness_s}`，load → `{loads, provenance, freshness_s}`；geocode 已有元数据，diversion 仅在工具包装中补 freshness_s。公开 REST 路线数组和直接 DiversionPlan 均不变。

整体声明为 simulated 的输入会覆盖矛盾的 real 子标签，且只改副本。工具包装的新鲜度取自身数字及 evidence 数据的最大年龄，旧负载不会被新网络时间覆盖。每个 handler 的成功/错误路径与此防误标行为均有自有测试。


### M0 人工规则修正：接入半径与累计步行

800 m 仅为 `find_access_points` 的起终点接入搜索半径上限；不限制整条路线累计步行。普通用户未提供 `max_walk_m` 时没有隐含的累计上限；显式用户画像的累计限制仍生效，行动受限/轮椅现有 400 m 限制保留。无累计限额时，步行评分按本次候选的最大累计距离归一化。累计 >500 m 输出较长步行警告。

每条步行边必须引用已建模节点，搜索只能沿连续边行进；不会凭坐标邻近补造入口或缺失连接。r_seed_007 的 900 m 本身不构成排除理由，但参考 seed 不直接作为算法输出。GMB_481B 仍因缺失 BS_TW、unverified/demo_only 排除；官方确认完整起终点/方向/站序且模型解析步行接入前不能恢复运营资格。

轮椅 M0 规则：MTR 和大型巴士默认可用，因此缺少 accessible/low_floor 字段不阻断候选；明确不可达、partial、楼梯或明确非低地台仍阻断；小巴始终排除。WALK/FERRY 仍要求边和端点明确 accessible=true，累计步行上限仍为 400m。该模式默认是演示策略假设，不代表官方设施核验；返回路线会带说明 warning。


### 六节点 30 有向 OD

`python -B -m backend.app.engine.coverage --depart-at 2026-09-22T08:20:00+08:00` 使用真实 RouteEngine 输出逐 OD 计数与缺口，不保存路线清单。`--wheelchair` 和 `--events PATH` 分别验证画像与事件快照；公开 RouteCandidate 契约不变。目标为每 OD 10 条，不足 10 明确诊断，不能用重复路线补齐。

当前结果及 C-Data 接入阻塞见 [M0_CORRIDOR_OD_RESULTS.md](reports/M0_CORRIDOR_OD_RESULTS.md)。`corridor_access.simulated.json` 仅供测试证明适配器替换，不由默认 seed 适配器加载。


### 原定 M0 T3.3 / T3.4 与路线 seed 修复

显式 `headway_s: null`（或当日时段 null）表示停运；缺失 headway_s 字段仍报数据错误。WALK 无候车且公开 leg 省略 headway_s，内部零等待不变。公众假期由适配器显式提供，测试中的日期仅为 simulated 日历，非官方假日表。

`tests/test_m0_timing.py` 覆盖工作日高峰/非高峰、周六、周日/公众假期、ceil 与 offset、WALK/null，以及 published 事件在 2 秒内切换不可变快照、双向闭边阻断、缓存失效和降权恢复。测量范围为 update_event 到进程内快照切换，不冒称上游网络/SSE 全链路时限。

routes.seed 采用当前引擎生成的新稳定 route_id，不将旧 r_seed_006/008 改义后复用。参考卡片均标记 simulated；轮椅 top-3 使用动态引擎按用户指定的 MTR/大巴默认策略重新生成，旧卡及替换关系见 reports/route-seed-repair-review.json。C-Sim 必须以新卡重新计算，不能沿用旧卡份额。


### M0 最终收尾状态

最新整合状态见 [M0 integration report](../../../docs/acceptance/m0-integration-report.md)。轮椅 MTR/大巴默认规则只用于 M0 demo，explicit false/partial、阶梯、小巴与步行约束仍生效；默认假设不冒充真实无障碍证据。

轮椅不足3时可局部回退换乘点复用和Jaccard两项软多样性规则，结果警告高度重合；所有安全硬约束和普通画像全局规则不变。该回退不能绕过明确不可达、阶梯、小巴或步行上限等硬约束。

## Transport selection

The route query accepts `modes` (allowed transit modes) and `required_modes` (each must occur in the journey). Required modes filter feasible paths before diversity and scoring and form part of cache identity. Walking and other transit modes can provide connections. Supported transit values are MTR, BUS, MINIBUS and FERRY; the curated network currently has no verified minibus service.
