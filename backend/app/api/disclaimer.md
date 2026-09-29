# T2.14 — 中英文免责声明与出处文案（B → A）

状态：文案交付，待 A 接入 interim 界面。本文不表示 UI 已上线。
范围：B 的事件后端说明与文案；不新增 API 字段、不修改契约、种子或前端。
依据：`docs/plan/01-product-scope.md` §8–9、`03-contracts.md` §3/5/7、
`04-workstreams.md` T2.14、`06-risks.md` §4，以及当前 Event / Signal 模型与 API。
中文采用简体，与计划文档一致；`zh` / `en` 是下表的文案语言标识，不改变 Signal.lang。

## 1. 可直接复用的固定文案

每个 ID 的中英文表达同一边界。显示位置是接入要求，不是现有 UI 描述。

| ID | 中文（zh） | English (en) | 适用位置及字段映射 |
|---|---|---|---|
| footer.disclaimer | 本平台为学术演示，非官方应急指引。路线、服务影响及运力可能为推算或模拟结果。出行请以港铁、运输署等官方公告为准。 | This platform is an academic demonstration, not official emergency guidance. Routes, service impacts and capacity may be estimated or simulated. For travel decisions, follow official announcements from MTR, the Transport Department and other relevant authorities. | 每页底部；静态文案。未来 C 的 Meta.disclaimer 可使用此中文值，英文由 A 的语言资源复用；当前未实现 /api/meta。 |
| card.disclaimer | 学术演示，非官方指引；影响、路线及运力可能为推算或模拟，请以官方公告为准。 | Academic demo, not official guidance. Impacts, routes and capacity may be estimated or simulated. Follow official announcements. | 每张事件、路线、仿真卡底部；静态文案，与来源和等级同时可见。 |
| ai.boundary | AI 只协助整理文字或出行偏好，不决定行程时间、票价、班次或运力数字，也不替代人工审核。 | AI only helps organise text or travel preferences. It does not determine journey times, fares, service frequency or capacity figures, and does not replace human review. | 事件审核原文旁；有偏好输入或 AI 解释时也显示。对应结构化草稿与 Event 的人工审核流程；不是 AI 返回字段。 |
| demo.seed | 演示样例：事件及数字用于展示界面，不代表当前交通情况。 | Demo sample: events and figures illustrate the interface and do not represent current transport conditions. | 使用 contracts/seed 数据的页面及卡片；由 A 的种子加载模式触发，不按置信度判断。 |
| sim.placeholder | 示意数字，尚未由仿真计算验证。 | Illustrative figures, not yet validated by a simulation run. | sim.seed.json 的 meta.placeholder=true 时紧邻图表数字；不可称为已测得的分流收益。 |
| event.confidence_help | 置信度是本系统对现有信息的评分，不是事实正确的概率，也不代表官方确认。 | Confidence is this system's score for the available information. It is not the probability that an event is true or a sign of official confirmation. | Event.confidence 旁的说明；可展示 confidence_factors，但不要把评分转成“准确率”。 |
| event.review_help | 人工审核表示本项目审核员已检查此版本，不等于官方确认。 | Human review means a project reviewer has checked this version. It does not mean official confirmation. | 仅在当前版本满足下述已审核规则时，放在审核状态说明中。 |
| source.mtr_inference | 基于港铁到站数据推算的疑似延误，不是港铁官方延误公告。 | A suspected delay inferred from MTR arrival data, not an official MTR disruption notice. | mtr_eta.py 检测器产生的 Signal；provenance=real-derived，保留实际 source_name 与 raw_url。不能仅凭 source_type=official 认作公告。 |
| source.user_unverified | 用户上报，内容尚未核实。 | User report; the content has not been verified. | source_type=user 的原始 Signal 旁；real 只说明输入真实，不证明内容。 |
| source.mock | 模拟来源，仅供演示。 | Simulated source, for demonstration only. | Signal.provenance=simulated 旁；包括模拟官方公告，不能去掉“模拟”限定。 |
| data.cached | 当前显示上次取得的数据，请留意记录时间并查看官方公告。 | Showing previously retrieved data. Check the recorded time and official announcements. | A 明确知道请求失败、正在显示缓存时；不根据固定秒数自行宣称过期。 |

## 2. 来源、时间、真实性等级的模板

花括号是 A 从实际字段填入的值，不是新增后端字段。
来源、事件更新时间、等级须在每条事件上可见；多来源逐条列出，不用最高等级掩盖其他来源。

| ID | 中文（zh） | English (en) | 字段 / 缺失行为 |
|---|---|---|---|
| event.updated | 事件更新时间：{time} | Event updated: {time} | Event.updated_at；不是官方公告更新时间。 |
| source.name | 来源：{name} | Source: {name} | 经 Event.signals[] 的 ID 找到 Signal.source_name；保留来源原名，避免翻译成未获证实的机构名称。 |
| source.received | 信号接收时间：{time} | Signal received: {time} | Signal.received_at；不是信号发布或发生时间。 |
| source.link | 查看来源 | View source | Signal.raw_url 有有效 http/https URL 才显示链接；URL 为空时显示 source.no_link。 |
| source.no_link | 未提供来源链接 | No source link provided | Signal.raw_url=null、空或不可用；不要补一个官方首页充当该事件的证据。 |
| source.unavailable | 来源详情暂不可用（信号编号：{ids}） | Source details unavailable (signal IDs: {ids}) | 只有 Event.signals[]、没有对应 Signal 时；保留 ID，不从 title、summary 或 confidence_factors.note 猜出处。空列表用 source.none。 |
| source.none | 未提供来源详情 | No source details provided | 没有 Signal ID 或来源记录。 |
| time.unavailable | 时间暂不可用 | Time unavailable | 时间缺失、无时区或不可解析；不能填当前时间代替。 |
| event.level | 事件数据等级：{level} | Event data type: {level} | Event.provenance；每条 Signal 另显示 source.level，不推断继承。 |
| source.level | 来源数据等级：{level} | Source data type: {level} | Signal.provenance；未识别值使用 level.unknown。 |
| meta.generated | 结果生成时间：{time} | Result generated: {time} | 仅未来实际 Meta.generated_at 可用时；不替代事件更新时间。 |
| meta.last_ok | 来源最近成功获取时间：{time} | Source last retrieved successfully: {time} | 仅未来实际 Meta.sources[].last_ok 可用时；不表示官方更新时间。 |

时间统一显示完整日期、时分及明确时区（例如香港时间 UTC+08:00），从原时间转换。
历史种子的时间保留历史日期；`meta.built_at` 只能称为“样例构建日期 / Sample build date”。
`window.start/end` 是影响时段，`published_at` 是本项目发布时间，`expires_at` 是事件到期时间，均不能替代 `updated_at`。
不承诺“实时”“每分钟更新”或某个轮询频率：采集器配置不证明线上运行频率。

| 原始 provenance | level 文案（zh / en） | 解释（zh / en） | 契约颜色 |
|---|---|---|---|
| real | 真实来源 / Real source | 来自实际数据或输入渠道，内容仍需核实。 / From an actual data or input channel; the content still requires verification. | #2E7D32 |
| real-derived | 推算 / Estimated | 基于数据或规则推算，并非直接观测。 / Estimated from data or rules, not directly observed. | #F9A825 |
| simulated | 模拟 / Simulated | 为演示构造，不代表实际交通情况。 / Constructed for the demo; does not represent actual transport conditions. | #0288D1 |
| 缺失或未知（level.unknown） | 等级未提供 / Type unavailable | 尚无足够信息判断数据性质。 / There is not enough information to identify the data type. | 不冒用上述等级颜色 |

等级描述数据性质，不是可靠程度的排序；绿色不代表已核实。
保留原始枚举 `real-derived`，不要发送颜色别名 `derived` 作为 API 值。

## 3. 当前事件 API 的接入边界

- 公开 `GET /api/events/published` 返回 `Event[]`，每张卡可直接取得 `updated_at`、`provenance`、`status`、`confidence`、`signals`。
- `Event.signals` 是 ID 列表，**不是来源对象**；当前没有公开的 Signal 详情查询端点。
  种子模式可按 ID 关联 `event.seed.json.signals[]`。真实 API 模式在来源详情未交接前使用 `source.unavailable` / `source.none`；完整来源展示仍需后续联调。
- `POST /api/signals` 仅返回 `signal_id`，提交成功不等于事件已确认或发布。
  不向浏览器暴露 `REVIEW_API_TOKEN`，不为取得来源调用受限审核端点或展示 author_hint。
- `source_type=official` 描述渠道。HKO 信号来自气象警告，不自动证明交通中断；
  MTR 检测器从到站异常推算疑似延误；模拟“官方公告”仍然是 simulated。
- Event.provenance 与关联 Signal.provenance 分别展示。当前聚合更新不重新计算 Event.provenance，
  因而不能仅凭事件等级替代逐条来源等级，也不能把所有混合来源显示为“官方”。
- 当前版本显示“已人工审核 / Human-reviewed”须同时有 `status=published`、非空 `reviewed_by`，
  且最新 `audit_log` 动作为 `review_approved`（当前 API）或 `published`（历史种子）。`draft` / `pending_review` 用“待人工审核 / Awaiting human review”；
  `updated` 用“有新信息，待重新审核 / New information; awaiting another review”；
  `expired` 用“已过期 / Expired”，`rejected` 用“未通过审核 / Rejected”。
  其他或缺失证据用“审核状态待核实 / Review status unverified”。这些状态不覆盖模拟徽标。
  聚合新信号会使 published 转为 updated，历史 reviewed_by 不能证明当前版本已审。
- 种子 evt_seed_003 即使 published、置信度 0.90，也仍显示“模拟”及 `demo.seed`，不能称为港铁已确认。

## 4. 路线与仿真交接（已有契约，当前未实现）

当前 `backend/app/main.py` 只注册 signals / events / review / stream；
本次不实现 C 的 `/api/meta`、路线、仿真接口，也不声称偏好 API 已可用。

| 适用位置 | 已有契约映射 | interim 注意事项 |
|---|---|---|
| 路线卡数据等级 | RouteCandidate.provenance、legs[].provenance | 顶层与每段分别显示，不因一段 real 将整条路线称为真实。 |
| 路线出处 | evidence[].event_id / evidence[].source | 契约样例有 evidence，但当前 routes.seed.json 路线没有 evidence；缺失显示 source.none，不能杜撰 URL。 |
| 路线新鲜度 | total.freshness_s / evidence[].freshness_s | 这是年龄秒数，不是绝对更新时间；种子数值不是当前数据年龄。未取得真实时间时用 time.unavailable。 |
| 路线、运力和影响数字 | total、load_estimate、Event.affected_segments[].capacity_factor | 使用 card.disclaimer，不把推算值包装成实测人数、保证能上车或官方停运结论。 |
| 仿真看板 | SimResult.provenance、assumptions[] | 显示模拟及假设；种子额外显示 sim.placeholder；禁止把占位收益称为真实仿真结果。 |
| 页脚出处列表 | Meta.sources[].name / url / provenance / last_ok | 仅在实际响应具备字段后接入；Meta 是计划契约，当前无端点。 |

种子核对发现：routes.seed.json 的 meta.purpose 称数值为示意，个别路线/腿却标 real；
network.seed.json 部分 real 项仍注明票价或停航门槛待核实。A 应保留各字段原等级并明确显示样例提示和待核实说明，
不能用 real 徽标暗示这些数字已经核实。此冲突交 A/C 数据负责人处理，本任务不修改 C 的数据。

## 5. A 的接入检查点

1. 两种语言下，每页底部及每张卡片都能看到免责声明；来源、事件更新时间、等级不只藏在弹窗中。
2. 种子三态均显示模拟；模拟官方公告保留模拟限定。真实用户输入仍显示未经核实。
3. 多来源分别显示名称、接收时间、等级和实际链接；无链接、未交接详情及未知等级均有明确兜底。
4. 已发布模拟事件不变成“官方确认”；updated 不沿用旧审核状态。置信度不标成准确率。
5. 种子和缓存不使用浏览器当前时间伪造更新时间；仿真占位数字有紧邻提示。
6. AI 边界文案可见；未实现的接口使用固定文案与缺失态，不伪造已上线功能。

本清单供 A 实现后验收；B 本次仅核对文案与字段，未执行浏览器 UI 验收。

## 6. B 完成报告（2026-09-27）

- status: completed（文案与字段说明交付；UI 接入由 A 完成）。
- 完成：双语免责声明、AI 边界、出处/时间模板、三种等级、审核状态、缺失与种子兜底、A 接入检查点。
- 修改文件：仅 `backend/app/api/disclaimer.md`；没有修改运行代码、契约或种子。
- 手工验证：逐项对照 Event / Signal 模型、events / signals / review API、review_state、aggregate、main 的路由注册及四份种子；
  核对中英含义、字段拼写、时间语义、API 的 review_approved 与历史种子的 published 动作差异。
- 实际检查（仓库根目录，以仓库外独立环境 `../t214-check-env` 的 Python 运行）：
  - 初次用桌面内置 Python 执行种子验证与单测，因缺少 jsonschema / fastapi 失败；没有计为通过。
  - 安装 `backend/requirements.txt` 后，`python scripts/validate_contract_seeds.py` 通过：4 份 JSON 可读，3 个 Event、5 个 Signal 符合 B 契约。
  - `python -m unittest backend.tests.test_contract_seeds backend.tests.test_event_api_flow backend.tests.test_review_state backend.tests.test_aggregate backend.tests.test_signal_api`：49 项通过；有 Starlette/httpx 弃用提示，无失败。
  - 未为纯文案新增镜像实现的单测；现有回归测试用于核实映射依赖的事件、审核及上报行为。
  - `git diff --cached --check` 通过；已逐行审阅暂存 diff，范围仅此文案文件。
- 风险/未决：来源详情未公开；路线/网络种子存在等级与待核实说明冲突；Meta、路线与仿真端点在本分支未实现。见 §3–4，不宣称已完成 UI 验收。
- 工作区保护：目标仓库克隆时干净；检查期间出现其他 signals.py、事件测试、T2.5 交接及报告/环境文件修改，保留且不纳入本任务提交。
- 推荐下一步：A 按 §5 接入并检查双语界面；A/C 处理种子出处和等级冲突，并协调真实事件来源详情的安全交接。
