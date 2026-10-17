# ResilientRoute（韧性路线）

**阅读语言：[English](README.md) | [简体中文](README.zh-CN.md)**

ResilientRoute 是一个面向香港东铁线**大围 → 金钟走廊**的中断感知出行引导原型。当轨道区段中断时，它把多源信号变成经人工审核的可信事件，把事件应用到确定性多模式路线引擎上，再为每一位乘客——赶时间的上班族或轮椅用户——提供个性化的、如实标注的替代方案，覆盖地铁、巴士、渡轮与步行，并附带建模票价与官方巴士到站时间。

本项目由 Thirteen-Points 队为 Hack4SDG 2026 黑客松开发。

> **这是一个学术原型，不是官方交通服务。** 网络、运力、仿真与部分票价为建模或推导数据。本项目不提供实时时刻表，不构成无障碍保证，也不是出行建议。真实出行请以运营方公告为准。

## 线上演示

| 组件 | 地址 |
| --- | --- |
| 公众网页 | <https://resilient-public-travel.pages.dev> |
| REST API（Render） | <https://resilient-public-travel-api.onrender.com> |
| 交互式 API 文档 | <https://resilient-public-travel-api.onrender.com/docs> |

## 它做什么

**1 · 早发现，人工把关。** 任何人都可以提交未核实报告（"信号 Signal"）。审核员把文本结构化、合并证据、生成带置信度评分的事件卡。只有审核员点击发布后，受影响区段才会在地图上变红、所有路线才会重算。一份提交的报告是信号，永远不是已证实的事故。

**2 · 个性化多模式路线。** 引擎在轨道、导入自运输署 GTFS 的巴士图、渡轮与步行链路中搜索，再按出行画像过滤排序：同一场中断，赶时间的通勤者与轮椅用户看到的首选路线不同、解释也不同。无障碍硬约束是强制过滤，不是建议。

**3 · 如实的群体分流。** 预计算的 1 万人沙盒对比"无引导"与"有引导"两种需求分配。当替代运力耗尽时，剩余的未满足需求会如实显示——原型讲的是风险与缺口，不宣称"解决"拥堵。

**4 · 能真实的尽量真实。** 票价从官方港铁、运输署巴士与天星小轮数据源导入带版本号的 SQLite 票价库；查不到的票价保持缺失。巴士到站时间来自九巴/龙运与城巴的官方开放 API，无法核实的匹配明确显示为不可用，而不是猜测。

**5 · 离线兜底。** 预制的离线包在完全无网络的环境下运行完整演示——API、构建好的前端、冻结数据与媒体。演示断网也要能演完。

## 架构

```
信号（公众上报、可选采集器）
        │
        ▼
审核台（/admin/，会话登录）── 发布 / 编辑 / 撤回
        │
        ▼
已批准事件 ──► 图快照（运力降权 / 区段关闭）
        │
        ▼
确定性路线引擎（图 + 票价 + 无障碍过滤）
        │
        ▼
React + MapLibre 前端：地图、路线卡片、偏好、巴士到站
```

- **后端** —— Python 3.11+ / FastAPI / SQLite。路线引擎、图构建、票价库、仿真、信号管道与管理员控制台位于 `backend/app/`。
- **前端** —— React、TypeScript、Vite、MapLibre GL。公众页面与独立的 `/admin/` 审核台位于 `frontend/`。
- **AI 边界** —— 可选的 LLM（DeepSeek、Qwen 或 GLM）只读文本、写措辞：结构化报告文本、解析偏好、解释工具结果。路线编号、时间、置信度、运力等一切数字全部来自确定性引擎。`AI_ENABLED=false`（默认）时系统以确定性回退完全离线运行。
- **出处无处不在** —— 每个数据对象都标注 `real` / `real-derived` / `simulated`，并在界面上显示。

## 本地运行

环境要求：Python 3.11+、Node.js 20.19+ 或 22.12+、Git。以下为 PowerShell 命令；macOS/Linux 请使用 `python3`、`.venv/bin/python` 与 `export NAME=value`。

启动 API：

```powershell
git clone https://github.com/Thirteen-Points/resilient-public-travel.git
cd resilient-public-travel
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:AI_ENABLED = 'false'
$env:OFFLINE_MODE = 'true'
$env:AI_DISABLE_EXTERNAL = 'true'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

在第二个终端启动前端：

```powershell
cd resilient-public-travel\frontend
npm ci
npm run dev
```

打开 <http://localhost:5173>。API 位于 <http://127.0.0.1:8000>，交互式文档在 `/docs`；本地就绪检查用 `/api/health/deep`。仓库也提供一键启动脚本（`scripts/start.sh`、`scripts/start.bat`）与 Docker Compose 配置，详见[部署指南](deploy/DEPLOYMENT.md)。

要让 Vite 指向其他 API，在 `frontend/.env.local` 设置 `VITE_API_BASE_URL` 并重启 Vite。**绝不要**把 API 密钥、审核令牌或密码放进 `VITE_*` 变量——Vite 会把它们嵌入可下载的浏览器产物。

### 数据模式与审核入口

- **API 模式（默认）**：查询确定性引擎，并应用在所请求出发时刻生效的已批准事件；数据来自仓库文件与本地 SQLite 数据库，不是实时服务。
- **固定种子演示**：打开 `http://localhost:5173/?data=seed`，展示不会随出发时间重算的固定示例旅程。切换模式会重载页面。
- 公众查询、已发布事件读取与报告提交无需凭证。审核在独立的 `/admin/` 控制台进行，其服务端登录配置见[管理员指南](deploy/ADMIN.md)。公众端没有对比、仿真或审核页面，也不会请求审核凭证。
- 更新每 3 秒刷新、来源状态每 15 秒刷新；失败时保留现有结果并显示内联重试提示。
- 地图线路使用内置、已标注出处的几何快照，不做运行时几何请求；未核实的路径保持示意样式。见[几何来源与限制](frontend/src/map/GEOMETRY_SOURCES.md)。

## API 速查

| 方法 | 端点 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health`、`/api/health/deep`、`/api/meta` | 就绪检查、构建标识、元数据 |
| `GET` | `/api/graph/network`、`/api/graph/snapshot?at=<ISO>` | 建模网络与按时刻的影响 |
| `POST` | `/api/routes/query` | 确定性多模式候选路线 |
| `GET` | `/api/buses/status`、`/api/buses/services`、`/api/buses/eta` | 走廊巴士目录与经校验的官方到站 |
| `GET` | `/api/fares/status`、`/api/fares/lookup` | 票价库版本与按日期票价查询 |
| `POST` | `/api/signals` | 公众未核实报告提交 |
| `GET` | `/api/events/published?at=<ISO>` | 按时刻生效的最后批准事件 |
| `POST` | `/api/ai/chat`、`/api/persona/parse` | 工具支持的对话与保守偏好解析 |
| `POST`、`GET` | `/api/sim/load`、`/api/sim/result?scenario_id=...` | 建模分流方案与预计算场景 |
| `GET` | `/api/sources/status`、`/api/replanning/status` | 安全的来源与重规划状态 |
| `GET`、`POST` | `/api/events`、`/api/signals`、`/api/stream/events` | 审核队列、证据与带鉴权的事件流 |
| `POST` | `/api/events`、`/api/events/ingest`、`/api/events/{id}/review` | 审核员事件创建与审核操作 |

受保护的审核路由需要 `X-Review-Token`；`/api/admin` 下的管理员路由使用管理员会话。路线查询示例：

```json
{
  "origin": "TAW",
  "destination": "ADM",
  "depart_at": "2026-10-05T08:30:00+08:00",
  "profile": { "preset": "fastest" }
}
```

## 验证变更

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt "pytest-subtests>=0.14,<1"
$env:PYTHONPATH = '.;backend'
$env:AI_ENABLED = 'false'
$env:OFFLINE_MODE = 'true'
$env:AI_DISABLE_EXTERNAL = 'true'
.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py
.\.venv\Scripts\python.exe scripts/validate_data_layer.py
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend/tests backend/app/engine/tests tests -q
```

前端检查（在 `frontend` 下）：

```powershell
npm ci
npm run typecheck
npm run test
npm run build
npm run build:admin
```

浏览器回归套件（`tests/browser/`，基于 Playwright）覆盖真实后端请求、事件发布、路线刷新、故障恢复与移动端布局；GitHub Actions 另有一次性容器重建检查，验证数据库与加密设置的持久化。完整流程见 [P3 验收](deploy/P3-ACCEPTANCE.md)与 [P4 验收](deploy/P4-ACCEPTANCE.md)。

## 离线演示包

`deploy/offline/` 提供预置离线包：无需安装、无需网络即可启动 API 与构建好的前端，包含走廊五分钟演示脚本、冻结的仿真证据，以及作为故障兜底的录屏媒体。用 `scripts/package_offline.py` 构建，用 `python scripts/preflight.py --demo --require-media` 校验，用 `deploy/offline/start.ps1` / `start.sh` 启动。详见[离线包指南](deploy/offline/README.md)。

## C++ 沙盒模拟报告

`sim_cpp/` 是一个独立的 C++20 事件仿真沙盒：把同一批 1 万人合成人群放在东铁线（红磡–会展）一小时封闭场景下，对比三种策略——**A**（无故障基准）、**B**（预知计划封闭窗口的 protected-first bucket 预分配）与 **C**（只看即时信息的最快路线，被强制下车后才重规划）。核心发现：95% 每车物理上限全程未绑定，真正起作用的是 3,400/460 的规划 cap；bucket 用普通乘客的小幅绕行，换来 protected 群体的尾部保障（强制落车 0 对 633 人，最大延误 30 对 60 分钟）。全部报告、图表与验证记录可直接在 GitHub 上查看：

- **[模拟测试报告](sim_cpp/report/SIMULATION_REPORT.md)**（中文，图表内嵌） · **[分析结论](sim_cpp/report/CONCLUSIONS.md)** · **[Bucket 对比](sim_cpp/report/BUCKET_COMPARISON.md)** · **[验证记录](sim_cpp/report/VERIFICATION.md)** · **[单页摘要](sim_cpp/report/SIMULATION_ONE_SLIDE.pptx)**（PPTX）

## 部署

仓库内置 Render Blueprint（`render.yaml`）部署 API——为 `events.sqlite3`、管理员与 AI 用量数据库挂载持久磁盘——前端部署在 Cloudflare Pages。后端通过 `CORS_ALLOWED_ORIGINS` 只放行确切的线上 Pages 域名；审核 API 由 `REVIEW_API_TOKEN` 保护。依赖任何已部署实例之前，先核验 `/api/health/deep`、`/api/meta` 与已部署构建 SHA。完整手册见[部署指南](deploy/DEPLOYMENT.md)。

## 信任与数据边界

- 出处分为 `real` / `real-derived` / `simulated`。标注 `real` 的报告只说明其来源渠道，不核实报告内容本身。
- 事件只有经人工批准才影响路线计算；待审编辑不会替换当前生效的批准版本。
- 未知的无障碍信息保持未知——建模的轮椅约束不等于真实无障碍行程认证。
- AI 不产生任何数字或路线；所有数字来自确定性引擎。
- 离线模式与 `AI_DISABLE_EXTERNAL=true` 会阻断一切外部模型与采集器调用，包括管理员设置中已启用的调用。

解读种子数据前，请先阅读[数据出处台账](data/PROVENANCE.md)与[数据质量说明](data/DATA_QUALITY.md)。

## 仓库结构

```
backend/app/     FastAPI 应用：引擎、图、仿真、服务、AI、管理台
frontend/        React 公众端 + /admin/ 审核台
contracts/       契约 Schema、种子数据与接口契约
data/            网络、日历、票价、仿真、出处台账
deploy/          部署、管理台、票价、离线包指南
docs/            计划、验收记录、架构图
scripts/         校验、导入、打包与预检工具
tests/           浏览器（Playwright）与集成测试
```

## 文档索引

- [部署指南](deploy/DEPLOYMENT.md) · [管理员指南](deploy/ADMIN.md) · [DeepSeek 配置](deploy/DEEPSEEK.md)
- [巴士目录与到站](deploy/BUS-API.md) · [票价数据库](deploy/FARES.md)
- [离线演示包](deploy/offline/README.md) · [P3 验收](deploy/P3-ACCEPTANCE.md) · [P4 验收](deploy/P4-ACCEPTANCE.md)
- [仿真数据与假设](data/sim/README.md) · [出处台账](data/PROVENANCE.md)
- [地图几何来源](frontend/src/map/GEOMETRY_SOURCES.md) · [可编辑架构图](docs/architecture/resilient-public-travel.svg)
- [项目计划索引](docs/plan/00-INDEX.md)
