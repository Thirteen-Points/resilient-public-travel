# FreddyP3 本地 debug · 2026-10-02

本轮在 FreddyP3 分支验证当前完整代码，公共浏览器测试使用真实 Edge、隔离临时 API/SQLite 和 Vite；管理员浏览器检查使用 FastAPI 提供的重建静态资源与独立临时 SQLite。未部署或写入线上服务，不调用付费模型或实际采集源。

## 修复

- M2 仿真文件 `data/sim/m2-simulation-result.json` 的场景 ID 为 `m2_six_station_directed_od_am_peak`，原缓存仅查找同名文件，导致真实请求 404。增加明确的旧文件映射，优先使用标准场景文件，仍校验场景身份与 assumptions；不扫描输入/manifest，不推断或修改仿真数值。缓存按实际文件路径区分，避免标准文件与旧文件同时间戳时混用结果。
- 仿真页面移除已解决的文件映射故障说明。浏览器验收新增真实 M2 成功响应和负改善/缺口缺字段检查，缺失场景用独立不存在的 ID 验证 404 与旧结果保留。
- `npm run build:admin` 暴露提交的管理员 bundle 与 P3 当前源码不一致；同步重建的 HTML/CSS/JS，满足仓库管理员 bundle 校验要求。
- P3 首次浏览器运行因本机缺少 Playwright ffmpeg 而失败；安装到被忽略的 `.cache/playwright/` 后重跑，不降低录屏要求。失败结果保留为 `.cache/p3-browser/p3-result-failed-missing-ffmpeg.json`。
- 临时管理员浏览器检查首次误设初始配置版本为 1；实际为 0，首次保存到 1。核对代码及真实 POST 响应后修正测试假设并完整重跑通过，失败证据保留为 `admin-debug-failed-revision-assumption.json`。

## 验证

| 检查 | 结果 |
| --- | --- |
| 前端 typecheck | 通过 |
| Vitest | 10 文件 / 88 测试通过 |
| 公共构建及管理员构建 | 通过；公共 JS 740.91 kB，仍有 >500 kB 提示 |
| 后端、引擎、tests 全量 pytest | 432 测试 + 264 子测试通过；1 项 Starlette/httpx 弃用警告 |
| 原后端 unittest | 修改前基线 212 测试通过；修改后由全量 pytest 覆盖 |
| M2 浏览器回归 | 通过；发布 188/261/173 ms，撤回 3446 ms，使用原 M2 计时方法 |
| P3 浏览器验收 | 通过；聊天实际 OD/时区响应、fallback、503/取消、偏好阻塞、双画像、M0/M2 仿真、缺失场景、来源失败、断网恢复、待审隔离、三次确认发布、撤回、移动端及 seed 演示 |
| 管理员重建资源浏览器检查 | 登录、概览、审核页、设置保存/重载、移动端无横向溢出、Activity、退出及无页面错误通过 |

P3 计时使用公开独立访客，未携带审核凭据；从确认按钮真实 click 到地图覆盖版本/像素及实际路线卡数字吻合后两帧结束。服务预检后为热状态，未限速，出发时间 `2026-10-02T12:47:00+08:00`。

| 轮次 | 点击时间（UTC） | 事件版本 | 地图 ms | 路线卡 ms | ≤5秒 |
| --- | --- | --- | --- | --- | --- |
| 1 | 04:37:29.454 | 4 | 1521 | 1360 | 通过 |
| 2 | 04:37:31.470 | 6 | 2483 | 2225 | 通过 |
| 3 | 04:37:34.421 | 8 | 2421 | 2291 | 通过 |

撤回 2886 ms，原路线 ID 完整恢复。本地结果不能代替 Pages→Render 线上或冷启动验收。

## 证据与复现

本轮日志和截图/录屏在仓库 `.cache/p3-browser/`，被 Git 忽略：`backend-regression.txt`、`typecheck.txt`、`vitest.txt`、`build.txt`、`build-admin.txt`、`p3-debug.txt`、`p3-result.json`、`m2-simulation-response.json`、`simulation-m2.png`、`local-publication-timings.json`、追加式 `local-publication-history.jsonl`、`local-withdrawal.json`、`admin-debug-result.json` 和 `admin-debug-*.png`。既有未跟踪 `runs/` 证据保持原样，不加入本次提交。

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
.\.venv\Scripts\python.exe -m pytest backend/tests backend/app/engine/tests tests -q
Set-Location frontend
npm run typecheck
npm run test
npm run build
npm run build:admin
Set-Location ..
# 设置 M2_PLAYWRIGHT 为本机已有 Playwright 包的绝对路径。
$env:M2_BROWSER_CHANNEL = 'msedge'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.cache/playwright'
# 首次录屏需依赖；也可使用本机已有的 PLAYWRIGHT_BROWSERS_PATH。
node (Join-Path $env:M2_PLAYWRIGHT 'cli.js') install ffmpeg
node tests/browser/m2.e2e.cjs
node tests/browser/p3.e2e.cjs
```

## 保留的未完成项

完整个性化聊天契约、每次路线查询的快照标识、公开采集来源状态/最后成功时间，以及正式 P3 仿真场景和分配口径仍待 B/C 确认。轮椅聊天等组合继续明确阻塞，对比仍是 unverified preview。M2 模拟总延误仍高于 baseline，不能宣称改善或正式 P3 验收完成。线上部署、三轮发布/撤回及恢复未在本轮执行。
