# online-surfing-bot 本地实施与验收报告

日期：2026-10-03，Asia/Shanghai。任务负责人：本任务用户。状态：**partial**。

代码、离线集成和回归已完成；港铁真实请求/解析通过三周期，真实 Signal 入库尚未验证。四个社媒来源受阻。没有上传分支、创建 PR、发布 Event 或执行 T2.6 真实模型验收。

## 基线、规则与分支

- 产品仓库：Thirteen-Points/resilient-public-travel，remote `upstream`。
- 远端 GitHub 和 fetch 一致：`main=d952216cd6360c73fc01b17e6e8b4de30865f045`，标题 `docs: rewrite project README`。
- [PR #100](https://github.com/Thirteen-Points/resilient-public-travel/pull/100) merged=true，合并 SHA `f0b4a9548270b3704772650226ab84be954bebfc`；[PR #103](https://github.com/Thirteen-Points/resilient-public-travel/pull/103) merged=true，SHA `e745701e7f030e597ee880dfd4854a65bbc01589`。两者均经 `git merge-base --is-ancestor` 验证属于同步后的 main 历史。
- #101 曾被 #102 撤回，因此以当前代码检查为准，不按旧 B 报告推定能力已合并。
- 创建 `online-surfing-bot`，工作树：`C:\Users\zyc\Documents\ChatGPT\Tecent X Hack4SDG\.verification\online-surfing-bot`。原 ZYC-M1 的未提交改动保留。
- 当前树未发现额外 AGENTS.md；已阅读 README、协作手册、契约、SignalStore、Signal API、审核与独立来源身份逻辑，以及现有 HKO/MTR/social_mock 和 P3 scheduler。
- 使用新增 `round-005`，没有覆盖 round-001 至 round-004。项目状态文档未改，由总控审核后决定更新。
- 本地实现提交包含本报告；精确提交可从该工作树 `git log -1 --format=%H` 查询。目标里程碑未指定，历史 PR 暂停要求继续遵守。

## 完成内容

独立 CLI 的 once/poll/status；来源协议；繁简中文及英文过滤；港铁公开网页 JSON 适配器；稳定内容版本 ID；官方匿名主体；内部恢复/转发关联；原文与发布时间分离；持久化来源状态、分页、租约、重试退避；Signal 和检查点原子写入。

默认 300 秒、24 小时、每来源每轮 100 条，HTTP 10 秒、最多额外重试两次。限速 Retry-After 持久化，单源失败隔离，离线禁止网络。没有使用网页配置中的密钥、私有 Mobile API、付费第三方采集商或登录绕过。

使用严格 Signal 现有字段，`received_at` 是采集时间；`real` 不代表内容已核实。SignalStore 只新增内部事务插入辅助方法，公共签名、用户上报 API 和 schema 不变。保留所有既有模拟、HKO/MTR ETA、Web 调度、审核和路线机制。新来源状态在 CLI 查看，未扩展原 `/api/sources/status`。

## 变更文件

| 分组 | 文件 |
|---|---|
| 配置 | `.env.example`、`backend/.env.example` |
| 内部存储服务 | `backend/app/services/signal_store.py`、`backend/app/services/ingest/online_store.py` |
| 采集实现 | `backend/app/services/ingest/online_models.py`、`online_http.py`、`mtr_mobile.py`、`online_runner.py`、`online_cli.py` |
| 离线测试 | `backend/tests/test_online_ingest.py` |
| 说明 | `docs/ONLINE-INGEST.md`、`docs/coordination/online-source-feasibility.md` |
| 本轮报告和证据 | 本文件及 `runs/round-005/evidence/`；没有提交 `.venv`、`.cache`、数据库或凭据 |

## 实际命令与结果

下列命令除 git fetch/worktree 外均在上述新工作树根目录执行。网络安装首次在沙箱内未完成，随后使用允许的网络执行安装成功；没有自动审批拒绝或待用户批准项。

| 实际执行 | 结果 / 证据 |
|---|---|
| `git -c http.sslBackend=openssl fetch upstream main` | 成功；从过时 6d112ca 同步到 d952216；没有推送 |
| `git worktree add -b online-surfing-bot <上述工作树> upstream/main` | 成功，HEAD=d952216，保留旧工作区 |
| Bundled Python `-m venv .venv`，`.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt` | 安装成功；具体版本见 `evidence/python-packages.txt` |
| `.\.venv\Scripts\python.exe -m unittest backend.tests.test_online_ingest -v` | 早期夹具 window 缺少 end_confidence 失败，修正测试夹具后 25 项通过；失败日志保留 `targeted-tests.txt`，随后 `targeted-tests-second.txt` |
| `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -q`，`PYTHONPATH=<root>;<root>/backend` | 当时 237 项通过，退出 0；`backend-regression.txt`。随后新增的测试由最终完整 pytest 验证 |
| `.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend/tests backend/app/engine/tests tests -q --junitxml=.cache/online-tests-delivery.xml`，`PYTHONPATH=<root>;<root>/backend`，OFFLINE_MODE=true，AI_ENABLED=false，AI_DISABLE_EXTERNAL=true | **519 passed，264 subtests passed，25.62 秒，退出 0**；`pytest-delivery.txt`。只有既有 Starlette/httpx 弃用警告 |
| 同一 pytest 命令首次未设置 PYTHONPATH | 两个历史 `app` 导入失败；日志 `pytest-first.txt` 保留，随后按仓库 CI 导入路径修正并通过 |
| `.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` | 四份 seed 的 JSON Schema / Pydantic / ID 校验通过，退出 0；`contracts.txt` |
| `.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli status` / `once`，OFFLINE_MODE=true | status 退出 0，once 显示 offline、退出 1；没有网络调用；`cli-status-offline.jsonl`、`cli-once-offline.jsonl` |
| `.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli poll --cycles 3`，OFFLINE_MODE=false，INGEST_ENABLED=true，INGEST_SOURCES=mtr_mobile,threads,instagram,facebook,xiaohongshu，绝对 DB_PATH 指向 `.cache/online-live/events.sqlite3` | 三次 MTR success，四个社媒各周期 blocked；总体退出 1 是已选择来源受阻，不是 MTR 请求失败；`live-three-cycles.jsonl` |
| 同一 live DB 的 CLI status，随后新进程 once | status 成功；once 的 MTR 为 waiting，保持 completed_rounds=3，没有重复请求/记录；`live-final-status.jsonl`、`live-restart-once.jsonl` |
| `git diff --check` | 通过；最终提交前再次检查 |

完整 pytest 包含新增 **30 项离线测试**，覆盖解析、时间、关键词、分页、上限、重复、重启、恢复关联、同作者证据身份、事务回滚、元数据补齐、429/超时/5xx/401/403、空结果、格式变化、robots、来源失败隔离及 CLI 信号处理。

## 真实来源证据

| 周期 | 请求开始（Asia/Shanghai） | 状态 | 处理 / 入库 / 跳过 |
|---|---|---|---|
| 1 | 2026-10-03 00:19:03.934314 +08:00 | success | 2 / 0 / 2 missing_publication_time |
| 2 | 2026-10-03 00:24:04.173225 +08:00 | success | 2 / 0 / 2 missing_publication_time |
| 3 | 2026-10-03 00:29:04.387816 +08:00 | success | 2 / 0 / 2 missing_publication_time |

实际周期间隔为 **300.238911 秒、300.214591 秒**。内部记录一直是两条，Signal 为零。内容摘要、原始 ID、来源链接、采集时间、跳过原因、游标及状态见 `evidence/live-summary.json`；公告 JSON 指纹各轮一致。线路全部 green。页面构建时间不冒充发布时间。

- [D_332：国庆黄金周加密东铁线班次](https://www.mtr.com.hk/alert/alert_simpletxt_title_tc.html#D_332)，首次采集 2026-10-03 00:19:04.147392 +08:00。发布时间为空，未创建 Signal。
- [D_328：启德东盟杯交通安排](https://www.mtr.com.hk/alert/alert_simpletxt_title_tc.html#D_328)，同一首轮采集；发布时间为空，未创建 Signal。

两条公告本身也不是当前默认延误/停运主题。按任务负责人确认的规则跳过。**真实请求和正文解析成功；真实内容入库尚未验证。** 实际三个周期没有出现新增公告，因此真实增量变化尚未实证；增量、重启去重和错误隔离通过明确标注的离线样本验证，不能替代真实增量证据。

当前没有可宣称“真实内容已进入审核收件箱”的来源。MTR 公开资源读取链可用；小红书、Threads、Instagram、Facebook 均 blocked，具体官方文档、权限、额度/费用未知项和阻塞见五来源表。

## 审核、停止和安全边界

- 隔离 SQLite 集成测试确认：合格的 simulated 测试项直接经内部服务入库，现有 reviewer GET 收件箱返回它；无权限访问被拒绝；重复与断点续采没有重复记录。
- 同一测试保留已发布 seed Event，采集前后公开 Event、图快照和成功的 route-query 完全相同。没有采集自动发布或设置置信度。不是线上发布验收。
- 三周期自然结束输出 stopped，释放租约。CLI 的 SIGINT 自动测试确认设置停止标记、关闭 HTTP、恢复原处理器；请求结束后检查停止标记并避免继续写入，也有测试覆盖。
- **Codex 托管 PTY 的 Ctrl+C 注入和向专用测试控制台发 Ctrl+C 均未完成实机退出验证。** 该离线测试进程已按已核实 PID 清理，没有留下采集后台循环。普通用户 PowerShell 键盘退出仍需现场确认；有界 `--cycles` 退出已实测。本报告不把单元信号测试称为实机 Ctrl+C 验收。
- 没有调用真实付费模型、线上审核写接口、Render 部署或 PR 操作。星标来源状态中的 success 只表示读取成功；provenance=real 不表示人工确认。

## 下一步

1. 总控审核本地实现与证据，决定是否更新项目状态；上传前由负责人确认里程碑和 PR 安排。
2. 港铁出现有可靠发布时间且匹配主题的新公告时，在同一数据库验证真实 Signal ID、reviewer 收件箱可见和重复运行幂等，补充新的不可覆盖轮次证据。
3. Threads/Instagram/Facebook 提供正式 token、批准权限和目标账号/主页配置后，再按现行官方文档实现对应适配器并逐来源真实验收；小红书先取得官方内容检索入口依据。
4. 在用户实际 PowerShell 终端确认 Ctrl+C 退出，完成剩余操作验收。T2.6 真实模型继续暂缓。
