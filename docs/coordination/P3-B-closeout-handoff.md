# P3 B 收口：画像、来源、事件交接

日期：2026-10-05。基线：`fde1c1f` 的本地收口分支；不代表 PR #104 已并入 `main`。本文件只交接 B 所有的接口和复验证据，不替 A/C 宣告 M3 验收通过。

## 给 A：可直接接入的公开契约

- `GET /api/personas` 返回 `commuter/student/tourist/elderly/wheelchair` 五个完整路线 `profile`。默认值来自 `data/personas.json`，是**模拟设计假设**，不是观察到的乘客行为。前端选择画像后，应把整份对象作为 `POST /api/routes/query` 的 `profile` 传入；只传 `profile_id` 不会自动解析。
- `GET /api/personas/presets` 返回 `fastest/most_stable/fewest_transfers` 八维归一化权重；数据同样是模拟默认值。不得把目录存在等同于“五画像首选路线不同”。
- `POST /api/persona/parse` 仍返回 `{patch, explanation, method}`。当前规则为默认，真实模型解析未验收；失败时 `method=rule_fallback`。合并 patch 时保留原有更严格的步行上限和硬约束；轮椅至少保留 `no_stairs/no_minibus/no_non_lowfloor_bus` 与 ≤400 米。
- `GET /api/sources/status` 返回 HKO 警告、MTR ETA 和独立 MTR 公开公告采集的 `classification/status/last_attempt/last_success/stale`；不返回密钥、原始异常或 URL 参数。`success` 只表示本来源采集步骤成功，不表示已产生合格 Signal，更不表示人工确认。`partial_failure/failed/disabled/offline/waiting/unconfigured` 须在界面区别显示。现有前端仍主要读取 `/api/meta`，需 A 接入新公开状态。
- `GET /api/replanning/status` 已有 `reason/trigger/elapsed_ms/within_five_second_budget` 与快照摘要；横幅应显示审核批准后的重规划原因和实际计时，不能把本机结果叫线上 ≤5 秒。见 `docs/coordination/P3-C-runtime-replanning.md`。

完整画像示例（可作为同一 OD 对照，勿改硬限制）：

```json
{"persona":"commuter","mobility":"standard","max_walk_m":800,"max_transfers":3,"preset":"fastest","hard_flags":[],"weights":{"time":0.45,"transfers":0.10,"walk":0.10,"price":0.10,"comfort":0.05,"reliability":0.10,"carbon":0.05,"freshness":0.05}}
{"persona":"wheelchair","mobility":"wheelchair","max_walk_m":400,"max_transfers":2,"preset":"most_stable","hard_flags":["no_stairs","no_minibus","no_non_lowfloor_bus"],"weights":{"time":0.20,"transfers":0.10,"walk":0.25,"price":0.05,"comfort":0.10,"reliability":0.25,"carbon":0.025,"freshness":0.025}}
```

## 给 C：固定场景与当前阻塞

用大围 `TAW` → 金钟 `ADM`、`2026-09-22T08:20:00+08:00`，先在无事件基线下用上述完整画像比较；然后用 `tests/browser/b-p3-no-ai.cjs` 中的 `evt_b_p3_browser`（东铁 `HUH`→`EXC` 关闭、三条模拟 Signal、人工批准）重复同一 OD/时间。不要为了得到画像差异而放宽无障碍约束。C 应提交同一图快照下两份路线响应、首选 ID/时间、轮椅每腿可达性及步行总长，并解释为何不同或不可行。

本轮实测无事件基线：上班族、学生、游客和轮椅的 top1 都是 `r_d242fe3d797400df`；长者为空。三个预设 top1 也相同。因此 B 目录/API 已就位，但“五画像首选不同”、长者可行路线均**未达标**，仍由 C 查候选路线和底层数据。轮椅浏览器查询有 5 条候选，均未用小巴、各腿标记可达、步行 ≤400 米；这只证明当前样例请求，不证明全网无障碍数据已核实。

审核链的后端测试覆盖创建→批准→编辑→重新批准→过期/撤回的审计、SSE、图快照与恢复；浏览器只覆盖批准、刷新和撤回后的公开事件消失。已批准天气事件可触发重规划，待审信号不改变路线。MTR 公告真实请求曾成功，但没有产生合格 Signal；这条现实链仍为 partial。

## 给 A/C 的验收分界

本地 Edge 无 AI 测试原始产物在忽略目录 `.cache/b-p3-no-ai/`：`result.json`、`history.jsonl`、请求/响应、截图、录屏。雨天与无路线画面由受控 API 响应验证 UI 状态；真实获批雨天事件的路线影响由后端测试覆盖，尚缺完整浏览器录像。A 负责页面、横幅与最终画面，C 负责路线差异、长者可行性、仿真改善；双方给出同版本证据后才可标记 P3 完成。
