# ResilientRoute — 前端原型设计规范 v1

状态：设计方案已定义；Figma 已建封面和 token/style 基础。组件、页面和交互尚未绘制，原因是 Figma Starter MCP 额度耗尽。

[Figma 工作文件](https://www.figma.com/design/lVMpgmxkP6NQe5QuDRA80C)

## 依据与设计方向

功能依据：Thirteen-Points/resilient-public-travel 的 docs/plan/00–09，尤其是 03-contracts、04-workstreams、05-timeline 和 07-demo-acceptance。
视觉参考：[Arie](https://arie.guide/)，观察日期 2026-09-22。

已观察到的参考特征：大面积留白、无衬线大标题、手写强调、圆润按钮和卡片、深色沉浸首屏、#BEFF52 亮黄绿主按钮。参考网页实际字体为 ABC Diatype；当前 Figma 不提供该字体。本项目明确选用 DM Sans / Noto Sans TC / Caveat，属于品牌演绎而非逐像素复制。

产品视觉：深墨绿封面与入口、纸白工作区、低饱和地理底色，黄绿色只用于主行动。地图路线 A/B/C 与异常、来源状态保留契约中的颜色。

## 颜色系统

| Token | HEX | 用途 |
|---|---|---|
| bg/page | #F7F8F2 | 背景或语义填充 |
| bg/surface | #FFFFFF | 背景或语义填充 |
| bg/hero | #18221D | 背景或语义填充 |
| bg/brand | #BEFF52 | 背景或语义填充 |
| bg/hover | #ACEB40 | 背景或语义填充 |
| bg/subtle | #E8EFDE | 背景或语义填充 |
| bg/water | #DEE9E4 | 背景或语义填充 |
| text/primary | #18221D | 文字 |
| text/secondary | #5E6961 | 文字 |
| text/inverse | #FFFFFF | 文字 |
| text/brand | #243F31 | 文字 |
| border/default | #D9DFD5 | 边框 |
| status/affected | #C62828 | 状态标记，与文字并用 |
| status/degraded | #F9A825 | 状态标记，与文字并用 |
| status/normal | #2E7D32 | 状态标记，与文字并用 |
| route/A | #1565C0 | 路线身份，与 A/B/C 文字并用 |
| route/B | #6A1B9A | 路线身份，与 A/B/C 文字并用 |
| route/C | #00838F | 路线身份，与 A/B/C 文字并用 |
| source/simulated | #0288D1 | 背景或语义填充 |
| bg/danger | #FFF0EC | 背景或语义填充 |
| bg/warning | #FFF5DB | 背景或语义填充 |
| bg/info | #ECF3FA | 背景或语义填充 |

语义颜色引用 primitive 变量。所有变量具有用途作用域与 var(--rr-...) CSS 映射。当前 Starter 方案使用单模式集合；深色入口使用独立的 bg/hero 与 text/inverse 语义。

注意：amber #F9A825 用作色块或指示器，不作为白底正文；正文用 text/primary。任何状态都必须同时有文字、符号或路线字母。

## 页面与流程范围

| ID | 页面 / 状态 | 核心内容与操作 | 数据契约 |
|---|---|---|---|
| P01 | Welcome | 品牌首屏；香港走廊范围；Plan my journey；查看三亮点 | Meta |
| P02 | Journey planner | 起终点、出发时刻、五画像、三偏好；六站及替代线；800 m 圈；查询 | Network, UserProfile |
| P03 | Route results | 地图与候选列表；A/B/C 区分；ETA 区间、换乘、步行、票价；更新原因 | RouteCandidate[] |
| P04 | Route detail | 分段路线、至少三维打分、风险与偏好偏差、无障碍核实状态、来源 | legs, score_breakdown, warnings, notes, evidence |
| P05 | Preferences | 五画像与自由文本偏好；解析结果由用户确认；硬约束与软权重分开展示 | UserProfile, persona/parse |
| P06 | Compare | 同 OD 同事件下 commuter / wheelchair 并排；不同 top1、权重、原因；轮椅不得含小巴 | RouteCandidate, UserProfile |
| P07 | Event timeline | 原始信号、置信度 20/55/85/90%、来源与因子、冲突标记；未发布不改图 | Signal, Event.audit_log |
| P08 | Report disruption | 线路、位置、观察内容、来源；提交、缺字段错误、成功回执 | POST /api/signals |
| P09 | Review console | 队列、原文与结构化字段并排；编辑、拒绝、发布；审计记录 | Event, review |
| P10 | Publish confirmation | 明示受影响区段、影响类型与生效范围；确认 / 返回；成功后展示已发布与地图更新入口 | affected_segments, status |
| P11 | Simulation | 1 万人；无/有引导柱图；总延误、P95 等待、过载线路、服务率、运力缺口、公平保护 | SimResult, DiversionPlan |
| P12 | Sources & assumptions | 数据来源、更新时间、真实/推算/模拟；仿真假设；免责声明 | Meta, assumptions[] |
| P13 | Recovery states | loading、empty、圈外、网络失败、LLM 不可用、旧数据、重试 | error.code/message/fallback |
| P14 | Mobile journey | 390 px 单列；地图与底部结果卡；保留画像、路线与来源 | 同桌面 |
| P15 | Mobile route detail | 分段路线与风险；固定底部返回/选择动作；大字号下不裁切 | 同桌面 |

## 可点击原型连线计划

P01 主按钮 → P02；P02 查询 → P03；P03 路线卡 → P04；P04 返回 → P03。
P02/P03 偏好 → P05；P05 应用 → P03；P03 对比 → P06。
主导航：Journey → P02，Updates → P07，Compare → P06，Simulation → P11。
P07 上报 → P08；P08 提交 → 成功回执 → P07。
P07 Review → P09；P09 Publish → P10；P10 Cancel → P09；P10 Confirm → 已发布状态 → 更新后的 P03。
P09 Reject → rejected 状态（不影响地图）；Expire → expired 状态（移除影响并提示重算）。
P11 Assumptions → P12；每页 Sources 链接 → P12。
P13 Retry → 对应成功页；圈外 → 最近接入点；无结果 → P05 调整偏好。
移动流程：P14 查询结果 → P15 详情 → P14。

原型应预置 Passenger / Review / Simulation / Mobile 四个 flow starting points；所有关键入口有返回路径。Figma 演示数据按种子值固定，实际输入解析、地图计算与仿真在实现阶段接后端。

## 组件清单与变体

| 组件 | 变体与属性 |
|---|---|
| Button | Primary / Secondary / Ghost / Danger；Default / Hover / Focus / Pressed / Disabled / Loading；Label 文本；Icon swap；超 30 组合拆分 |
| Input | Empty / Filled / Focus / Error / Disabled；Label、Value、Helper、Required |
| Choice | Persona / Preset；Selected / Unselected / Disabled；保留文字说明 |
| Status badge | Draft / Pending / Published / Updated / Expired / Rejected |
| Provenance badge | Real / Derived / Simulated；附来源和更新时间 |
| Route card | A / B / C；Default / Selected / Unavailable；Route label、ETA、fare、walk、transfers；warnings 与来源不可丢失 |
| Event card | Low / Medium / Ready for review / Published / Conflict；confidence、source count、updated |
| Navigation | Journey / Updates / Compare / Simulation；Active / Default；desktop / mobile |
| Metric | Delay / Wait / Overload / Service / Gap；baseline 与 guided；单位、样例标识 |
| Drawer / Dialog | Preferences、Evidence、Publish；有明确标题、关闭与返回 |
| Recovery panel | Loading / Empty / Offline / Stale / Out of range / AI unavailable；解释与下一步 |

## 字体与排版原则

| 样式 | 字体 / 字重 | 字号 / 行高 | 用途 |
|---|---|---|---|
| RR/Display | DM Sans Medium | 72 / 76 px | 桌面品牌首屏，最多两行 |
| RR/H1 | DM Sans Medium | 48 / 54 px | 页面主标题 |
| RR/H2 | DM Sans Medium | 32 / 40 px | 区块标题、移动端页面标题 |
| RR/H3 | DM Sans Medium | 24 / 32 px | 卡片标题、指标 |
| RR/Body | DM Sans Regular | 16 / 24 px | 正文、解释、表单内容 |
| RR/Small | DM Sans Regular | 14 / 20 px | 辅助信息 |
| RR/Label | DM Sans Medium | 14 / 20 px | 按钮、标签、表单名称 |
| RR/Caption | DM Sans Regular | 12 / 18 px | 非关键来源补充说明 |
| RR/Accent | Caveat Regular | 72 / 80 px | 首屏一句短英文强调 |
| RR/Chinese | Noto Sans TC Regular | 16 / 26 px | 繁体中文正文 |

英文标题依字号使用 -2 / -1.5 / -0.6 / -0.3 px 字间距，正文不压缩字距。中文不继承英文的负字间距；同一组件混排时以中文高度确定最小高度。Caption 不用于警告、ETA、票价或必填表单信息。

正文每行约 65–75 个英文字符；说明段落以两到四行为宜。使用 sentence case。时间写成“31–38 min”，金额写“HK$12.50”，步行写“420 m”；置信度写“90%”，不暗示为准时到达概率。指标使用等宽数字特性，以便纵向比较。

手写字体只出现在品牌或情绪性短句，最多占一个首屏的一处。路线步骤、审核内容、风险、图例和数值一律用无衬线字体。中文主标题采用 Noto Sans TC，遵循相同层级尺寸；英文小标题不替代中文必要说明。

## 响应式布局与尺寸

| 布局 | 设计基准 | 页边距 | 结构 |
|---|---|---|---|
| 大桌面 | 1440 px | 64 px | 12 列，24 px 栏间距；内容宽 1312 px |
| 小桌面 / 平板横向 | 1024–1279 px | 32 px | 地图双栏；结果列约 360 px，地图弹性宽 |
| 平板竖向 | 768–1023 px | 24 px | 双栏内容可改为上下布局；审核原文与字段使用页签 |
| 手机 | 390 px 基准，最低检查 320 px | 20 px，窄屏 16 px | 单列；地图 / 列表切换；底部操作栏 |

桌面应用头部高 80 px；典型结果列宽 400 px，地图区占剩余宽度，中间间隔 24 px。桌面详情抽屉宽 480 px，确认弹窗宽 560 px；手机上变为全宽底部面板或独立页面，最大高度受可视区域限制，内容可以滚动。

所有结构容器使用 Auto Layout；卡片文字随内容增高。仅地图点位、连线和确需覆盖的浮层使用绝对定位。窗口变窄时先缩外边距，再改单列，不能缩小关键正文来硬塞内容。

间距只从 0 / 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 80 px 中选择。图标与文字间距 8 px；字段名称与内容 8 px；卡片内区块 16 px；卡片间 24 px；页面大区块 48–80 px。

圆角：小标记 8 px，输入框 16 px，卡片 24 px，大型首屏 32 px，按钮与选择标签使用胶囊。阴影：RR/Card 为 y=4、blur=20、opacity=6%；RR/Floating 为 y=16、blur=48、opacity=13%。普通证据表和数据表保持平面，依靠分隔线组织信息。

层级顺序为：底图 → 覆盖圈 → 网络线 → 候选路线 → 站点 → 地图控制 → 导航与提示 → 抽屉 → 遮罩 → 确认弹窗。固定底部控件不能遮住最后一项内容，必须预留等高底部空间。

## 色彩使用与对比检查

下表为按当前 HEX 值计算的相对亮度对比值，不代表尚未制作的完整界面已经通过无障碍验收。

| 前景 / 背景 | 对比值 | 设计使用 |
|---|---:|---|
| #18221D / #F7F8F2 | 15.30:1 | 主正文与纸白工作区 |
| #5E6961 / #FFFFFF | 5.72:1 | 白卡片上的次要正文 |
| #243F31 / #BEFF52 | 9.62:1 | 黄绿色主按钮文字 |
| #FFFFFF / #18221D | 16.34:1 | 深色品牌首屏文字 |
| #C62828 / #FFFFFF | 5.62:1 | 白底错误说明 |
| #F9A825 / #FFFFFF | 1.97:1 | 仅装饰或带深色文字的状态指示；不得作白底正文 |

项目验收目标：普通文本至少 4.5:1，大字号至少 3:1，必要的控件边界与聚焦提示至少 3:1。浅色 border/default 只用于装饰性分隔；输入框若依赖边界识别，应使用更深的 text/secondary 边线。聚焦环采用 route/A 蓝色，2 px 线宽与 2 px 外间隙。

品牌黄绿不会代替状态绿色：主行动与交通正常状态必须用文字区分。来源等级沿用 real=绿色、real-derived=琥珀色、simulated=蓝色；蓝色和琥珀色来源徽标正文统一使用深色，彩色只用于点、图标或底色。

## 地图、路线与图表规范

六站走廊、替代轨道与接入线路来自 Network 数据；800 m 圈是地理距离，不是固定像素圆。站点中英文名称使用数据中真实名称。示意地图必须标“Schematic”，不可配假比例尺来暗示真实导航精度。

网络背景线建议 2 px；路线 A/B/C 为 4 px，选中路线为 6 px。站点直径 10 px，换乘站 14 px；交互命中区至少 44 px。路线 A/B/C 的字母徽标跟随卡片与地图高亮，不能只靠蓝、紫、青辨认。关闭区段使用红色及闭合/中断符号；不可用候选以灰化和“Unavailable”文字说明，不显示为可选主推荐。

事件发布后，顶部用一句话说明“Route updated: cross-harbour service suspended”，同时刷新路线卡和地图。未发布事件只出现在事件观察或审核区域，不改变乘客可用路线。

分流图保持 baseline / guided 使用一致的两种颜色和相同轴范围，柱图从零开始；柱顶标绝对值，单位直接写在标题或轴标签。三种路线仍保留 A/B/C 色，不与策略配色混用。负载率用百分比并标 100% 参考线；目标满载率 85% 作为单独参考线。未知值显示“—”和原因，不显示 0。

展示总延误、人均或人·分钟、P95 等待、过载线路数、服务率时严格保留后端单位。运力缺口单独成卡，不能被“改善百分比”掩盖。所有种子仿真图加“Simulated · seed example”，附假设入口。

## 组件尺寸与交互规则

按钮默认高度 48 px；大按钮 56 px，小按钮 40 px但交互命中区仍至少 44 px。主按钮每个局部任务只出现一个。Hover 加深填充；Pressed 进一步强化；Focus 显示独立聚焦环；Disabled 使用不可用说明；Loading 保留按钮宽度、显示进行中的动词并阻止重复提交。

输入框默认高度 56 px；名称永远放在输入框上方，不只靠 placeholder。错误信息出现在字段下方，保留用户输入。起终点支持交换，交换后同时更新文字和地图点位。日期时间清楚标示香港时间。

路线卡内容顺序固定为：A/B/C 标识与路线名称 → ETA 区间及换乘/步行/票价 → 推荐解释 → 打分拆解 → 风险与偏好偏差 → 来源、更新时间和免责声明。至少展示三维评分。卡片折叠态不能隐藏“不可通行”“无障碍待核实”等会改变选择的重要警告。

事件卡内容顺序固定为：状态与置信度 → 事件标题 → 受影响区段及方向 → 来源数量与冲突提示 → 最近更新时间 → 查看证据。置信度不是严重度；严重度另用标明名称的字段展示。

审核台选择一条事件后，左侧看原文、右侧看结构化字段。发布前确认框显示区段、影响类型与生效范围；确认后不可让同一次点击重复发布。拒绝需要理由；更新保留版本与审计记录；过期操作说明会移除事件影响。审核入口与普通乘客导航分离。

抽屉和弹窗打开时焦点进入标题后的第一个可操作控件；Tab 在弹窗内循环；Escape 关闭非提交中的弹窗；关闭后焦点返回触发控件。没有提交的偏好修改，关闭时不自动应用。

## 动效、键盘与无障碍

页面切换使用 180 ms 淡入淡出；抽屉使用 240 ms；颜色和选择状态变化使用 120–180 ms。避免长时间阻挡信息的开场动画。

置信度演示可逐步展示 20% → 55% → 85% → 90%；官方证据可到 85%，审核完成后才到 90%。置信度动画不得自动触发发布。生产数据更新频率由事件流控制，不为视觉效果制造虚假更新。

中断脉冲应短暂、低频且不会妨碍读图；减少动态效果设置下改为静态描边。读屏只播报完整更新结果，避免逐帧播报数字。关键状态变化使用可读提示，但不抢走用户正在输入的焦点。

所有查询、查看路线、切换偏好、提交上报及审核流程应可用键盘完成。地图提供等价站点列表，用户无需精确点击地图才能查询。大字号模式以内容重排实现；不能裁掉来源、风险、确认动作或返回入口。

轮椅约束属于硬条件；不得通过降低评分来保留不满足条件的路线。电梯状态未知时明确说明“Access not verified”，不能标成“Fully accessible”。

## 中英文字与异常状态文案

产品默认英文界面，香港站名及用户原始上报保留繁体中文；设计说明文档使用简体中文。新增中英内容均使用短句，避免“保证可达”“实时准确”等超出数据证据的承诺。

| 状态 | 英文示例 | 中文含义 / 下一步 |
|---|---|---|
| 查询中 | Finding routes for your needs… | 正在按你的需要查找路线，保留原布局 |
| 没有匹配 | No route matches all your requirements. | 没有同时满足全部条件的路线；提供调整偏好 |
| 圈外 | This location is outside the 800 m access area. | 显示最近接入点，允许重新选择 |
| 数据较旧 | Showing saved routes. Last updated 08:20 HKT. | 明示旧数据时间，提供 Retry |
| 网络失败 | We couldn’t refresh the routes. Your saved results are still here. | 保留上次结果，不清空页面 |
| AI 不可用 | Preference parsing is unavailable. Choose a preset to continue. | 提供人工选择画像和偏好的入口 |
| 上报成功 | Report received. It will be reviewed before affecting routes. | 已收报，审核前不会影响路线 |
| 证据冲突 | Sources disagree. Review required. | 保留冲突双方证据，不以高置信度覆盖 |
| 已发布 | Published. Affected routes are being updated. | 显示审核人和更新时间 |
| 可达性未知 | Lift access has not been verified. | 不声称全程无障碍 |

每个页面页脚与每张路线卡保留 Sources、Updated、Academic demo。完整免责声明使用计划文本：“本平台为学术演示，非官方应急指引；路线与负载为推算/模拟结果，请以港铁及运输署官方公告为准。”英文对应文案：“Academic demonstration, not official emergency guidance. Routes and loads are estimated or simulated. Follow official MTR and Transport Department announcements.”

## 范围、优先级与开发交接

M0 应先实现地图骨架、六站/替代线/800 m 圈、三张事件卡，并用种子路线渲染简化路线卡。这里以 03-contracts §8 的冻结检查表为准；路线卡完整版可继续在 P1 完成。颜色枚举从冻结契约读取，不在各组件中复制不同版本。

完整设计后续按 P02/P03/P04/P07/P09 主链优先，随后是 P05/P06 个性化和 P11/P12 分流与出处。移动适配、可选 AI 对话面板等按计划取舍；设计规范中预留 AI 面板，但不让它成为完成查询的前置条件。

可选 AI 对话面板放在地图右下角的辅助入口，内容包括用户问题、从工具获取的路线解释、证据与更新时间、偏好补丁确认。失败时回到预设偏好与结构化数据，不生成猜测路线。这是 P3 可选扩展，不列入 M0。

| UI 模块 | 后端 / 数据 | 前端职责 |
|---|---|---|
| NetworkMap | GET /api/graph/network | 绘点、线与范围圈，不自行创造站点 |
| ImpactLayer | events/published + graph/snapshot | 仅应用有效已发布影响 |
| RouteCard / Compare | POST /api/routes/query | 展示 ETA、打分、warnings、notes、evidence |
| EventTimeline | stream/events + audit_log | 按事件版本更新，不倒退覆盖 |
| ReviewConsole | events/{id}/review | 展示状态机结果、审计与错误 |
| SimulationDashboard | sim/result + sim/load | 保留单位、假设、缺口与模拟标签 |
| Provenance / Footer | GET /api/meta | 来源、更新时间、免责声明 |
| RecoveryPanel | error.code / message / fallback | 保留上次成功状态并提供下一步 |

组件名称建议与前端保持一致，变量采用 rr 命名空间。地图几何属于数据，视觉颜色属于 token，页面文字属于文案配置，三者分开。Figma 文本属性用于可替换内容，布尔属性用于可选辅助说明，图标使用 instance swap；不要每换一个图标就复制一套组件。

## 数据诚实性与重要约束

计划内 SimResult 数字是占位示例。设计使用时必须显示“Simulated · seed example”；不可声称为实测改善。ETA、价格、距离保留推算标签。人工发布是唯一生效入口。轮椅路线中“无楼梯”“电梯可用”等事实未经核实时不能显示为已验证。

本规范新增的是视觉与交互设计决策，不修改后端契约。发现设计所需字段缺失时，先按现有字段解释或保留未知状态，再通过团队契约流程讨论；不能让前端静默猜字段。

## 验收清单与当前完成情况

规范文档已完成；以下是后续制作/实现的验收要求，尚未执行的检查不视为已通过。

- 每个画面具有一致的导航、来源、更新时间和学术演示免责声明。
- 组件使用实例，颜色/间距/圆角绑定变量，文本使用命名样式。
- 原型主路径可点击且有返回；未发布事件不影响地图。
- 1440 / 390 / 320 px 布局无溢出；英文/中文与 ETA 不裁切。
- 每张路线卡至少三维评分，ETA 区间、风险、备注、来源齐全。
- 对比视图显示不同 top1；轮椅用户不会得到小巴或未满足硬条件的路线。
- 分流看板明确模拟、假设与运力缺口；比较图轴范围和单位一致。
- 20%/55%/90% 演示可复现；发布到地图及卡片更新的实现目标为 5 秒内。
- 静态示例与实时状态不会混淆；异常状态有下一步。
- 键盘、聚焦、触摸目标、文字对比与减少动态效果均经过实际检查。
- 每个页面完成截图检查；交付原型前验证所有连接目标有效。

当前 Figma 中已验证的产物：封面、3 个变量集合、61 个变量、10 个文字样式、2 个阴影样式。变量别名未发现断链，CSS 映射齐全，封面已做截图检查。Components 与 Prototype 页面目前为空；规范画板、组件、产品页面及交互未完成。

按用户最新指示，本次工作到规范文档写作与检查为止，不继续生成本地原型或 Figma 页面。

