# B M2 事件管道收尾报告

- 日期：2026-09-27
- 状态：partial。B 的离线事件 API 演示链及收件箱补齐已通过测试；真实模型验收和 A/C 全链联调尚未完成。
- 仓库根目录：`C:/Users/xiami/Documents/ChatGPT/GenAI Hackathon 2/resilient-public-travel`
- remote：`https://github.com/Thirteen-Points/resilient-public-travel.git`
- 分支：`Mingquan-Xia`；检查基线：`fe6cb4f`。开始时工作树干净。
- 父目录是另一个没有 remote、尚无提交的 orchestration 仓库；其已有暂存文件未改动。本仓库没有额外 AGENTS.md，遵守父目录规则及用户指定 B 范围。

## 完成工作及修改文件

审核台原先只能提交 Signal 和凭 ID ingest，没有接口发现未处理上报或查看原文。这阻断“上报进入待审队列”和原文对照。

- `backend/app/api/signals.py`：增加受审核令牌保护的收件箱列表、未关联过滤和 Signal 详情。使用现有存储与 Signal 契约，不增加状态字段。
- `backend/tests/test_event_api_flow.py`：增加 API 回归测试，验证授权、顺序、草稿仍在队列、创建/合并后退出未关联视图、原文保留、404 和未配置令牌的 503。
- `docs/coordination/T2.5-api-handoff.md`：补充 A 的收件箱接入约定。
- `docs/coordination/B-M2-event-pipeline-report.md`：本报告。
- `runs/round-002/B-report.md`：本轮不可覆盖的执行记录。

未改 A 前端、C 图/路线/AI 客户端、共享 Schema、main 或父仓库文件。

提交前发现非本轮创建的未跟踪 `.venv-readme-b/`、`backend/app/api/disclaimer.md`、`runs/round-001/`，均保留且不纳入本轮提交。不覆盖 round-001，另建 round-002。

## 链路检查与证据

| 环节 | 实际证据与限制 |
|---|---|
| 用户上报 | POST 返回 202；同步保存后才返回；原文与服务端生成来源保留。测试验证 1 秒内完成。 |
| 结构化草稿 | 未注入 LLM 时走规则抽取；没有匹配返回 needs_review，不猜严重度和运力。真实 LLM 错误/非法响应的重试与降级由 fake-client 测试覆盖。 |
| 第一张 Event | 审核方显式提交完整 pending_review Event，服务器将请求伪造的 0.90 重算为 0.20。仍需人工补齐交通数字。 |
| 合并与置信度 | API 测试三名不同 author_hint 的报告得到 0.20、0.35、0.55；同源不加分、矛盾降分、模糊匹配拒绝、幂等重试均有服务层测试。author_hint 只是演示来源提示，不是已验证的独立身份。 |
| 人工审核发布 | API 测试 0.55 加审核 0.05 后以 0.60 发布；低分和非法状态拒绝；published 编辑/新增证据进入 updated，需复审。 |
| SSE | 现有集成测试读取真实 SQLite 审计序号生成的帧，验证 published、置信度、重连游标及新修改在 1 秒内被生成器读到。未验证浏览器、线上代理或公网延迟。重放帧的 event 为最新完整卡片，历史置信度应读取 change.confidence_after。 |

## 实际命令和结果

命令均在上述仓库根目录运行，除最初定位命令在父目录运行。

- `git rev-parse --show-toplevel`、`git remote -v`、`git status --short --branch`：确认目标仓库、remote、分支及干净基线。
- `rg --files --hidden -g AGENTS.md -g '!**/.git/**' -g '!**/.venv/**'`：目标仓库内没有额外 AGENTS.md。读取了 03-contracts、04-workstreams、05-timeline 及 B 相关 coordination 文件。
- `python -m unittest discover -s backend/tests -v`：失败，PATH 没有 python。
- 用 bundled Python 运行同一命令：101 项，3 个模块导入错误，缺 fastapi/jsonschema；不是代码验收通过。
- `& 'C:\Users\xiami\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv`：成功创建隔离环境。
- `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt`：成功；.venv 已由现有 gitignore 忽略。
- `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v`：127 项全部通过，2.085 秒，退出码 0。Starlette 对 httpx TestClient 发弃用警告，不影响本次结果。
- `git diff --check`：通过；Git 提示 LF/CRLF 自动转换，无空白错误。
- `git fetch origin Mingquan-Xia`：成功；`git rev-list --left-right --count HEAD...origin/Mingquan-Xia` 为 0/0。

## 未解决问题及 A/C 接口交接

1. **T2.6 blocker**：`backend/app/ai/llm_client.py` 不存在，`OPENAI_API_KEY` 未配置（仅检查存在性）。未调用真实模型，真实样本首次通过率未运行，不能把 fake-client 结果当正式验收。C 需提供 `LlmJsonClient.generate_json(...)` 适配器和受信环境凭证，再通过 `create_app(llm_client=...)` 注入并运行现有 10 样本验收器。
2. **0.90 演示差距**：服务层支持“核实真实官方来源 + 审核”得到 0.90，但当前 API ingest 未提供官方核实操作。此次实际 API 证据为最高 0.60 的用户报告链。不得通过请求分数或模拟官方文本伪造 0.90；官方渠道核实路径需团队明确后由 B/C 对接。
3. **A**：接入新收件箱、原文详情、现有 ingest/create/review；首张完整 Event 需人工确认字段。SSE 走受信代理或带头流式 fetch，置信度动画读取审计 change。前后端精确 CORS origin 尚待确认。
4. **C**：消费 `/api/events/published` 的 `affected_segments`、version、window，并在发布/复审/expire 后联调图快照和路线重算。当前分支没有 graph/engine/frontend，因此没有“地图变色/真实路线”验收证据。
5. **契约冲突**：03 的线路枚举 ERL_E/ERL_W 与 Event/规则的 ERL、外部 EAL 映射仍待团队决定；不擅自改变共享字段。M0 建议 updated 期间保留旧发布版本，但现有 `/published` 仅返回 status=published，updated 会暂时退出集合。A/C 需明确并联调此行为，不能假定旧版仍由 API 提供。
6. **统一错误外壳**：03 要求 error.code/message/fallback，但现有 API 使用 FastAPI detail；需 A 确认 interim 错误适配。此次未改全局错误处理或跨区应用入口。

## 推荐下一步

A 用受信审核代理完成一次真实界面操作，C 消费实际已发布 Event 联调区段与路线；随后补真实模型与官方核实路径的独立验收。B API 测试通过不等于全团队 M2 已完成。
