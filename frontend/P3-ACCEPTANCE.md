# P3 执行记录 · 2026-10-02

后续本地 debug 已修复 M2 场景 API 文件映射，并同步管理员构建产物；最新完整回归见 [P3-LOCAL-DEBUG.md](P3-LOCAL-DEBUG.md)。下文保留首次交付时的历史记录，原 M2 404 已不再是当前本地阻塞项。

本轮交付是可联调前端与证据，**不是 P3 全部验收完成**。接口依赖、责任人与五分钟 Demo 见 [P3-INTEGRATION.md](P3-INTEGRATION.md)。代码基于最新 main `c2934c1`，保留已有报告/审核/地图/路线链路。

## 检查结果

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run test` | 10 文件、88 测试通过 |
| `npm run build` | 通过；89 modules；JS 740.93 kB（gzip 214.26 kB）；仍有 >500 kB chunk 提示 |
| 原 `m2.e2e.cjs` | 通过；原三轮 190/154/184 ms、公开轮询撤回 3447 ms。原计时方法不是本轮严格双渲染口径。 |
| 新 `p3.e2e.cjs` | 通过；聊天真响应、显式 fallback、HTTP 失败/取消、偏好阻塞、两画像条件/约束、旧数据/负改善、来源读取失败、断网恢复、待审隔离、独立访客三轮/撤回、移动端和显式 seed 演示 |
| 线上只读探测 | Pages 路线卡实际渲染；无页面错误、无审核 header、无浏览器存储；health/meta/M0/chat 为 200，M2 为 404 |
| 线上三轮发布/撤回/断网恢复 | 未执行、未验收：新前端尚未部署，已登录管理员会话控制工具启动失败 |

## 最后完整本地运行的原始计时

环境为隔离临时数据库＋真实 Edge 浏览器、未限速、公开访客无审核凭据；服务预检后为热状态，未测量冷启动。出发时间 2026-10-02 11:35 HKT，有效测试窗口包含该出发时间。确认按钮 click 事件是起点，地图 Canvas 像素/覆盖版本与路线卡 DOM/后端数字一致并经过渲染帧才结束。

| 轮次 | 确认点击（UTC） | 已发布版本 | 地图 ms | 路线卡 ms | ≤5秒 |
| --- | --- | --- | --- | --- | --- |
| 1 | 03:25:11.282 | 4 | 1508 | 1376 | 通过 |
| 2 | 03:25:13.331 | 6 | 2540 | 2243 | 通过 |
| 3 | 03:25:16.349 | 8 | 2438 | 2224 | 通过 |

本地撤回 2900 ms；原先的路线 id 完整恢复。这些时间**不能替代 Pages→Render 线上计时**。

首三批严格计时测试的失败均保留：前两批使用早于 published_at 的出发时间，第三批误用 SVG 检查 Canvas；第一批另有金额字符串检测错误。修正后重新执行完整三轮。追加式 history 和失败 JSON 均在缓存，不删除失败后挑选三次。不存在已通过或已失败的生产发布轮次。

## 本地证据位置

全部位于仓库根 `.cache/p3-browser/`，没有提交凭据或浏览器会话。源代码与这份摘要在 GitHub 分支；截图/响应/录屏/详细日志被 Git 忽略，留在本机。

- 检查日志：`typecheck.txt`、`vitest.txt`、`build.txt`。
- 新浏览器结果：`p3-result.json`；真实响应：`chat-response.json`、`simulation-response.json`；双画像请求：`comparison-requests.json`。
- 计时：`local-publication-timings.json`、`local-publication-history.jsonl`、`local-publication-timings-failed-*.json`、`local-withdrawal.json`。
- 截图：`agent-api.png`、`agent-error.png`、`compare-desktop.png`、`compare-mobile.png`、`compare-accessibility.png`、`simulation-negative-improvement.png`、`simulation-allocation.png`、`simulation-assumptions.png`、`sources-unknown.png`、`sources-refresh-failure.png`、`simulation-offline-retained.png`、`compare-offline-retained.png`、`recovered-comparison.png`、`local-publish-{1,2,3}.png`。
- 本地完整访客录屏：`video/page@3f9974c26757314f06be1d637a752e09.webm`；seed 录屏另存。审核上下文不录屏。
- 线上只读记录：`online/acceptance.json` 及按运行时间保存的 `online/acceptance-*.json`、`online/public-routes.png`、`online/video/page@0d8d85b3983f178731b43614a1995b9d.webm`。2026-10-02T03:25:04Z 初始 health 315 ms，不能据此判断冷启动。
- 管理员会话工具故障：`cua-status.json`；两次 `cua.getState` 均报 `windows sandbox failed: helper_unknown_error: setup refresh had errors`，没有执行线上写操作。

## 未完成与责任人

- B/C：完整画像/偏好/事件条件聊天契约及真实确认样例。当前非默认组合明确阻塞。
- C/B：每份路线的计算快照标识、轮椅约束实际生效证据；当前对比明确是 unverified preview；less_walking 不可用。
- C：P3 仿真场景、M2 文件映射、比例分母/缺口单位/时间口径；缺失值均不猜测。
- B：公开来源分类、最后成功时间、失败/部分失败/未启用/未知状态契约。
- C/B/A：部署 FreddyP3 前端，在可用应用管理员会话上运行 `p3.online.cjs`，完成三轮发布、撤回与离线恢复，保存全量生产失败记录和录屏。脚本已交付，生产写入路径尚未验证。
- A：收到 B/C 确认响应后补接/测试并更新此记录；当前没有双方接口确认签收，不能将交接需求标成已确认。
