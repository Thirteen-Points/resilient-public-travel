# P3 C 日历、天气与运行重规划接线

默认 `SeedDataAdapter` 读取 `data/calendar.json` 中 `verified=true` 且 `schedule_type=sunday_ph` 的日期，并读取 `data/weather_impact.json`。当前日历是交付窗口内的三条已核验 2026 假期，不能当作完整年度日历。图快照散列和 JSON 持久化包含天气政策，恢复后仍可计算相同结果。归一化数据可通过 `MappingDataAdapter(weather_policy=...)` 或 `JsonDataAdapter` 的政策输入显式提供天气政策。

天气计算只接受 `published`、`reviewed_by` 非空、置信度至少 0.6 的 Event；运行协调器的数据入口必须使用 `EventStore.approved_events()`，这样待复审编辑仍保留上次批准的事实。未审核 Signals 和取消/解除文本不会启用天气影响。已批准标题/摘要中的 HKO 代码或明确中文警告名称映射到政策；没有明确代码/名称的事件不猜测条件。

区域天气对整个演示网络应用估计系数，这是模拟假设。公交/渡轮时长乘 `mode_penalties`，步行时长同时乘 WALK penalty 并除以 `walk_speed_factor`；多个警告取最不利系数，不连乘。T8+ 的政策零值在模型中排除相应模式；这不是对实时运输服务是否停运的认证。`reliability_cv` 用于 ETA 方差。路线警告明确显示天气模拟模型。

应用启动时创建 `RuntimeReplanningCoordinator(engine, event_store.approved_events)`，在启动、审核存储提交后，以及周期性的生效/过期检查中调用 `sync_approved_events()`。公开的 `build_router(coordinator)` 提供 `/api/replanning/status` 原因、快照和计时摘要；`POST /api/replanning/load-observations` 使用已有 `x-review-token` 审核鉴权。未经鉴权的请求不能改变监视器或快照。

内部订阅使用 `register_query(query_id, context)`；需要分流结果时使用 `register_simulation(query_id, context, demand)`。context 是 `RouteEngine.query_details()` 的明确参数，demand 为明确的非负整数模拟人数。每次重算复用同一次 query_details 的 route_parameters 和 graph_snapshot；步行运力未建模，因此不会塞入虚构步行容量。可注入 `diversion_replanner(decision, route_details)` 计算其他已明确的场景。

默认可信负载来源只有 `manual_simulation/simulated`，不会将人工观察标记为真实。真实来源必须由部署方显式安装可信适配器并配置 `trusted_load_sources={source: {provenance}}`。负载观察必须时间递增，连续观测间隔不超过 2 分钟；超过 95% 持续至少 5 分钟触发一次，下降或采样断档后重新计时。观察只是重算触发器，不会凭载客率虚构乘客人数、改变运力或自动改路线权重。真实负载影响排序还需要真实 LoadProvider 的明确接线，当前未制造此来源。

分流观察可额外传 `context` 与 `demand` 获取即时模拟结果。缺省不假设需求，未提供需求时不生成默认分流人数。结果记录 reason、trigger、elapsed_ms、within_five_second_budget；天气/审核事件计时包含批准事实读取、快照替换和订阅重算。超过预算如实报告。

验证：`backend/tests/test_runtime_replanning.py` 覆盖默认节假日班距、待审天气无影响、批准后重算、编辑保留批准版、撤销恢复、雨天步行、T8 渡轮排除、持久化恢复、连续负载、断档/旧观察/来源限制，以及鉴权拒绝。
