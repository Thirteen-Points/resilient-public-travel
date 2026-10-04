# B：真实交通采集交接核查与本机验收

日期：2026-10-04（Asia/Shanghai）。任务负责人：用户。**状态：partial**。

## 基线与范围

- 先检查了现有产品工作树：`XMQM2` 有未跟踪的 `.venv-readme-b/`；旧 `social-media-ingest` 工作树有未提交改动。均未覆盖。
- 从 GitHub `origin` 抓取 `online-surfing-bot`，在独立工作树 `online-surfing-bot-acceptance` 检出本地同名分支。检出前远端 HEAD 与交接提交均为 `46e871a865a9f4030b6f6f7d1bed7619b27f6efe`，没有后续提交；`d952216cd6360c73fc01b17e6e8b4de30865f045` 是其祖先。检出后分支、HEAD、干净工作区均核实。
- 已阅读本分支 `docs/ONLINE-INGEST.md`、五来源可行性表、round-005 报告和证据，及 Signal 契约、SignalStore、来源实现、审核 API/列表和 Web lifespan。新采集器仍只由独立 CLI 启动；Signal 走内部存储事务，未调用用户上报 POST `/api/signals`。现有审核 GET 收件箱需 reviewer 授权，只有人工批准的 Event 才影响发布链。
- 交接证据中的 `519 passed` 是旧轮次结果；以下为本机重新运行。项目状态文件未改，交由总控审核。验收执行阶段没有 PR、推送、合并或 T2.6 真实模型调用；随后负责人已另行授权推送及创建 PR。

## 本轮变更文件

- `backend/app/services/ingest/online_cli.py`：Windows 上同时注册 `SIGBREAK` 停止处理器，并在退出时恢复原处理器。此变更提供 Ctrl+Break 备用停止路径；不把托管终端信号注入当作实机键盘验收。
- `backend/tests/test_online_ingest.py`：增加 Windows `SIGBREAK` 停止与处理器恢复测试。
- `docs/ONLINE-INGEST.md`：说明 Ctrl+Break 监听和现场键盘验证仍待完成。
- 本报告及 `runs/round-008/evidence/`：保存本次测试与真实采集证据；不含数据库、虚拟环境或凭据。未覆盖 round-005。

## 实际命令与结果

除 `git fetch`、`git worktree add` 从原产品仓库执行外，下列命令均在独立工作树根目录的 PowerShell 执行。测试设 `OFFLINE_MODE=true`、`AI_ENABLED=false`、`AI_DISABLE_EXTERNAL=true`、`DB_PATH=.cache/online-acceptance/tests.sqlite3`，并按教程设置 `PYTHONPATH=<root>;<root>/backend`；真实请求使用独立的 `live-authorized.sqlite3`。

| 命令或操作 | 实际结果 |
|---|---|
| `git fetch origin online-surfing-bot`；`git worktree add -b online-surfing-bot <独立目录> 46e871a...`；`git rev-parse HEAD`、`git status --short --branch` | fetch、检出成功；HEAD 为完整交接 SHA；初始工作区干净。 |
| `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt` | 沙箱网络失败，退出 1；按网络权限重试成功，退出 0。依赖仅装入本工作树忽略的 `.venv`。 |
| `.\.venv\Scripts\python.exe -m unittest backend.tests.test_online_ingest -v` | 修改前 30 项通过、退出 0；修改后 **31 项通过、退出 0**，见 `evidence/targeted-tests.txt`。 |
| `.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend/tests backend/app/engine/tests tests -q --junitxml=.cache/online-acceptance/pytest-after-fix.xml` | 修改前 519 passed、264 subtests passed、退出 0；修改后 **520 passed、264 subtests passed、退出 0**。只有既有 Starlette/httpx 弃用警告，见 `evidence/pytest-complete.txt`。 |
| `.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` | 四份 seed 的 JSON Schema、Pydantic、ID 检查通过，退出 0；见 `evidence/contracts.txt`。 |
| `.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli once`，真实来源 MTR | 沙箱内网络受限，`network_error`、退出 1；换用新隔离 DB 并允许网络后，实际请求成功、退出 0。没有把失败 DB 的退避当作来源故障。 |
| 同一真实 DB 中再次执行 `once` | 第二次请求成功、退出 0，`completed_rounds=2`；内部记录仍 1、Signal 仍 0，见两份 live 日志和 DB 摘要。 |
| PowerShell PTY 中 `poll`，两次发送 Ctrl+C | 首轮为 `waiting`；托管终端没有交付可验证的正常退出。随后按已核实的专属 PID 停止该测试进程，进程返回 -1；不能记作 Ctrl+C 验收。 |
| Windows 进程组控制事件探测 | `CTRL_C_EVENT` 和 `CTRL_BREAK_EVENT` 在该托管环境都未得到 CLI 的 `stopped` 输出；探测超时后结束进程。新增处理器的单元测试通过，但实体键盘验证仍未完成，见 `evidence/windows-signal-probe.txt`。 |
| `git diff --check` | 通过；只有 Git 对未来 LF/CRLF 转换的提示。 |
| `git commit -m "Verify online traffic ingest handoff and Windows stop handling"` | 首次尝试退出 128：当前仓库没有配置 Git 作者姓名和邮箱。随后使用仓库历史中已有的 `Codex <codex@users.noreply.github.com>` 身份，仅通过本次提交命令的 `-c` 参数指定作者；未修改用户 Git 配置。 |

## 真实来源与入库

- 来源：[港铁公开公告 JSON](https://www.mtr.com.hk/alert/alert.json)，可追溯公告 [D_332：国庆黄金周加强列车服务](https://www.mtr.com.hk/alert/alert_simpletxt_title_tc.html#D_332)。这是官网公开资源，不称作已验证的 MTR Mobile 官方 API。
- 第一次请求开始：2026-10-04 12:25:39.675156 +08:00；公告写入内部记录：12:25:42.184694 +08:00。第二次请求开始：12:33:36.566899 +08:00。两轮各处理 1 条，`issuedTime` / `published_at` 均为空，均按已确认规则记为 `missing_publication_time`；每轮新增 Signal 为 0。
- 第二轮后隔离库：内部记录 1、Signal 0、租约 0、成功轮次 2。未出现发布时间明确且匹配默认交通主题的新公告，因此**真实内容入库、真实增量入库、真实审核列表可见及真实内容不影响已发布 Event/图/路线均尚未验收**。离线集成测试验证了这些路径的模拟数据行为，不能代替真实证据。
- 与交接时的两条公告相比，本次公开快照只剩 D_332；这证明来源内容有变化，不证明出现过合格内容或真实增量 Signal。

## 来源状态、问题与下一步

- MTR：公开资源请求和解析成功；真实 Signal 入库未验证。小红书、Threads、Instagram、Facebook：仍为 **blocked**，未取得团队正式凭据、已批准权限或已验证的内容入口；不因配置占位 token 宣称接通。先前官方资料核查中 Meta 文档返回 429，不能据此推定 API 配额；小红书尚无已验证的公开笔记检索入口。
- Windows 实际 PowerShell **键盘** Ctrl+C 正常退出、当时的租约释放及随后续采仍需现场操作验收。当前测试仅证明：独立 `once` 自然退出后租约为 0；被托管终端强制停止后，同一 DB 可重启读取检查点，未产生额外记录。强制停止不是优雅退出证据。
- 建议负责人在可交互的本机 PowerShell 按教程运行 `poll`，待出现一轮 `source_result` 后亲自按 Ctrl+C，记录 `type:"stopped", requested:true`、退出码、`status`、租约数与再次启动结果。如键盘信号确实送达而 CLI 未停止，再针对代码修复。
- 出现带可靠发布时间、符合默认交通主题的真实公告时，继续在隔离 DB 验证 Signal、授权审核 GET 列表、重跑幂等及未审核前 Event/图/路线不变；无内容时继续保留 partial，不放宽时间规则。社媒凭据/审批到位后再逐来源核实现行官方接口、配额、范围和费用。
