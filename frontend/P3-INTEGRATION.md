# FreddyP3 前端交接与验收

2026-10-02 本地 debug 更新：M2 场景 ID 查询已修复，真实浏览器已验证读取；管理员静态资源已重新构建并同步。完整复验见 [P3-LOCAL-DEBUG.md](P3-LOCAL-DEBUG.md)。下文原交接记录中的 M2 404/文件映射问题为修复前状态；其余接口确认和线上验收缺项仍然保留。

执行日期：2026-10-02（HKT）。从 GitHub main `c2934c1fee124b41227a30f70b8628feb0b109ff` 同步到现有 `FreddyP3`，执行开始时两者一致。修改仅在 `frontend/**` 与 `tests/browser/p3*.cjs`；不改后端、数据或部署配置。

本轮检查结果、原始计时摘要和截图/录屏索引见 [P3-ACCEPTANCE.md](P3-ACCEPTANCE.md)。

## 已实现及边界

| 必交付项 | 前端现状 | 尚未完成的验收条件 |
| --- | --- | --- |
| AgentPanel | API 模式真实调用 `/api/ai/chat`，冻结当前 OD 与时区时间；30 秒超时、取消、重试、HTTP/工具失败、后端 fallback、旧请求保护；返回路线直接呈现。固定模板仅在显式 seed 模式。 | B/C 当前适配器未解析完整画像/偏好，`profile_id` 也未解析为真实画像。因此只允许通勤＋最快的现有默认组合，其他组合明确阻塞；事件条件是后端当前事实，不能宣称已固定快照。完整个性化聊天未完成。 |
| 仿真 | 独立 Simulation 页面，scenario_id 可输入；真实 baseline/guided 延误、等待、过载、分配与缺口；保留旧结果、时间缺失可见、负改善不改写。 | 默认明确标记旧 M0 预计算演示。C 尚未确认 P3 场景、比例分母与缺口口径；M2 文件名与接口索引不一致导致 404。缺失字段显示未提供。 |
| 两画像 | 独立 Compare 页面；两份请求同一 OD、时间、事件 id，分别使用通勤 fastest、轮椅 most_stable；整对提交，不覆盖规划器；约束、首选、权重、解释与警告来自引擎。无路线/相同首选如实显示。 | 每份路线没有计算快照标识。前后 graph 读取仅能检测部分竞态，不能证明两份结果一致；界面明确标记 unverified preview，正式同条件验收未完成。B/C 需确认轮椅硬约束与数据假设。 |
| 来源 | 独立于主链刷新公开 `/api/meta`；保留旧元数据，读取失败单独提示。只显示响应中存在的 `last_ok`，无值显示未提供。 | 实际公开 meta 仅返回 seed 文件名，无分类、最后成功采集时间或失败/部分失败/禁用状态。界面显示 unknown／pending B；完整真实来源状态未完成。 |
| 刷新恢复 | 保留审核语义、SSE/3 秒公开轮询、请求版本保护；元数据失败不拖住主链；断网保留地图、路线、对比与仿真并标旧，恢复后重新查询。新增渲染计时标记、键盘焦点、大字/高对比、减少动画支持。 | 线上尚未发布本分支。管理员现有会话控制工具因本机 sandbox helper 启动失败，未执行线上发布或撤回。线上三轮 ≤5 秒验收未完成。 |

“前端诚实展示”和“模型是否改善”分别验收。真实旧 M0 `367770 → 400170` person-minutes、M2 文件 `15088.4 → 24682.4` 均为负改善；不作为实时客流或改善承诺。

## 10/6 前 B/C 接口需求

以下是对当前代码和公开响应的核对，**不是 B/C 的确认记录**。B/C 的书面确认、接口版本及真实成功/fallback/失败/缺字段响应仍待收集。不为缺失能力自拟响应字段。

| 责任人 | 当前已核对契约 | 必须补齐/确认 |
| --- | --- | --- |
| B/C：聊天 | `message, origin, destination, depart_at, profile_id?, event_id?, demand?`；`message, fallback, routes, tool_calls`。默认确定性 fallback 可读。 | 两画像、正式偏好与已发布事件条件如何传递并实际生效；返回结果/工具失败/fallback 的语义与来源。现有 `profile_id` 只进入包含 id 的字典，不会解析为轮椅约束。 |
| C/B：路线 | `profile` 中 `mobility,preset,max_walk_m,max_transfers,hard_flags`；公开返回路线数组。轮椅使用既有 no_stairs/no_minibus/no_non_lowfloor_bus、400 m、2 次换乘。 | 每份结果可验证的相同快照标识/固定条件方式；约束真实生效证据及数据假设。现有 `least_walking` 不被引擎接受，API UI 已禁用，不映射。 |
| C：仿真 | M0 id `scn_huh_exc_closed_am_peak` 可读；M2 文件 id `m2_six_station_directed_od_am_peak` 返回 404。两者字段不完全相同。 | 修复 M2 API 文件映射；提供 P3 场景 id、分配比例与分母、缺口字段/单位、生成与场景时间、假设。不得用 M2 `unmet_demand` 猜测旧 M0 `unstoppable_demand` 的同义性。 |
| B：来源 | 实际公开 `sources` 为字符串数组。原计划 meta 示例存在 `name,last_ok`，当前服务未输出。管理端 `SourceResult.at` 为尝试时间。 | 公开且无管理凭据的来源分类、最后成功时间、最近失败/部分失败/禁用/未知状态与失败信息；明确旧数据状态。不能将 `generated_at`、事件更新时间或采集尝试时间当最后成功时间。 |
| B/C：线上验收 | Pages `https://resilient-public-travel.pages.dev/`；Render `https://resilient-public-travel-api.onrender.com`，应用审核 `/admin/`。 | 部署本分支前端、确认后端版本；提供独立模拟 P3 测试事件、有效时间窗和应用审核会话。Render Dashboard 登录与应用审核登录是不同会话。访客独立上下文，不含任何审核凭据。 |

10/7 可用现有确认契约联调当前界面；新增契约只有在 B/C 提供确认响应后才接入。Vitest/故障注入中明确名为 contract-test 的控制响应仅用于测试，不能当线上结果或 B/C 确认样例。

## 证据与复现

输出目录：仓库根 `.cache/p3-browser/`（被 Git 忽略，不提交截图或凭据）。

- `typecheck.txt`、`vitest.txt`、`build.txt`：前端检查。
- `p3-result.json`：新增端到端断言及未完成项。
- `chat-response.json`、`comparison-requests.json`、`simulation-response.json`：实际本地后端响应与请求。
- `agent-api.png`、`agent-error.png`、`compare-desktop.png`、`compare-mobile.png`、`compare-accessibility.png`、`simulation-negative-improvement.png`、`sources-unknown.png`、`sources-refresh-failure.png`、`simulation-offline-retained.png`、`compare-offline-retained.png`、`recovered-comparison.png`，以及 `video/*.webm`。
- `local-publication-timings.json`、追加式 `local-publication-history.jsonl`、`local-withdrawal.json`、`local-publish-*.png`：**本地隔离服务**，不代替线上验收。计时从确认按钮真实 click 事件开始，到实际地图覆盖层版本或路线卡 id/数字吻合后两帧结束。
- 初始严格计时失败记录保存在 `local-publication-timings-failed-*.json` 及追加式 history。第一批同时有金额字符串校验错误；前两批地图失败是测试出发时间早于 `published_at`，按当前后端 `active(event, at)` 语义不应生效。第三批误用 SVG 检测实际 Canvas 地图。所有失败仍保留。修正采用有效未来出发条件，并检测覆盖层 Canvas 实际像素及渲染帧，不能挑选轮次冒充线上通过。
- `.cache/m2-browser/result.json`：保留原浏览器回归；原计时未区分实际地图和路线卡渲染，只作为既有回归证据。
- `online/acceptance.json`、`online/public-routes.png`、`online/video/*.webm`：真实线上**只读**检查。初始健康响应耗时单独记录，不据此断言冷启动。线上验收轮次为空。

```powershell
Set-Location frontend
npm run typecheck
npm run test
npm run build
Set-Location ..
# 使用已有 Playwright；可按本机设置 M2_PLAYWRIGHT/M2_BROWSER_CHANNEL。
node tests/browser/m2.e2e.cjs
node tests/browser/p3.e2e.cjs
node tests/browser/p3.online.cjs # 默认只读，保存公开查询证据
```

生产发布验收先由 C 部署本分支。B 准备 **simulated**、title 含 P3、confidence ≥.55、pending_review 的独立测试事件，有限时间窗覆盖当前到至少 20 分钟后。脚本将选择当前＋10 分钟出发，以满足 `published_at <= departure`；该条件应与 C 确认，不回溯修改生产事件时间。管理员浏览器不应有未保存编辑。

```powershell
$env:P3_ACCEPTANCE='1'
$env:P3_EVENT_ID='<B/C 准备的模拟事件 id>'
$env:P3_CDP_URL='<现有已登录应用管理员浏览器的本地 CDP 地址>'
# 不复制浏览器 cookie，不导出 storageState。
# B/C 也可改用本机 P3_ADMIN_USER / P3_ADMIN_PASSWORD 环境变量；不要发在聊天里。
node tests/browser/p3.online.cjs
```

三次均为实际 Confirm publication 点击。每轮保留地图和路线卡两项时间、事件版本、网络条件及失败原因；待审核修改保持上次已审核内容；撤回、断网可见旧图/路线、恢复重新查询随后执行。脚本写入完整证据后才判断达标，失败不能删掉重选。公开访客采用全新上下文，检查无审核 header、URL 凭据或存储。本地视频只录访客，新建审核上下文不录屏。线上脚本尚未在应用管理员会话下验证，是未完成项。

## 五分钟 Demo（10/8–10 真接口联调后复核，10/11 正式验收）

| 时间 | 操作与说明 |
| --- | --- |
| 0:00–0:40 | API 模式选择同一 OD/时区出发时间、通勤最快；键盘查询。说明后端 seed 输入仍是模拟资料。 |
| 0:40–1:25 | Agent 显示真实 fallback、路线及来源，与网络响应核对；取消/失败/重试。尝试轮椅会明确提示聊天接口阻塞，不冒充个性化。 |
| 1:25–2:15 | Compare 两画像同一请求条件；查看硬约束、解释、权重和警告。如果首选相同，如实说明；快照未确认时展示 unverified，不能称已验收。 |
| 2:15–3:00 | Simulation 读取 C 确认 id。现阶段可用明确标旧 M0，展示 guided 延误更高、剩余过载和缺口；请求 M2 显示 404 与旧结果。 |
| 3:00–3:35 | 来源页展示缺失最后成功时间/状态未知，模拟读取失败保留旧元数据；说明 B 的公开状态契约仍待接入。 |
| 3:35–4:30 | B/C 在审核端确认模拟发布，独立访客看实际图与卡；展示三轮原始计时。尚未线上完成时必须明确说未完成。 |
| 4:30–5:00 | 撤回、断网保留、恢复。展示免责声明和未完成清单，区分界面接入与模型改善效果。 |

## 未完成项与下一步

1. B/C：完整个性化聊天与固定事件条件契约；A 接收到真实确认响应后补接客户端与用例。
2. C/B：两画像查询快照标识、轮椅约束的真实数据有效性及 least_walking 的正式支持；A 取消 preview 阻塞前必须验证。
3. C：P3 仿真 id、M2 文件映射、比例分母/缺口单位/时间口径；A 按真实响应补字段，不能自行推断。
4. B：公开来源状态与最后成功时间；A 在确认契约后支持 failed/partial/disabled/unknown 展示。
5. C/B/A：部署 FreddyP3 前端并执行线上三轮发布、撤回及恢复。当前只读线上查询通过；CUA 管理员会话工具两次启动失败（`windows sandbox failed: helper_unknown_error: setup refresh had errors`），无线上发布计时或线上撤回结果。
6. A：收集 B/C 的确认记录与新响应，补充实际联调证据。当前接口文档是交接请求，不能标为双方已确认。
