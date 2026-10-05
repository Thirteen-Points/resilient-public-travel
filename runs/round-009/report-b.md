# B P3/P4 收口报告

日期：2026-10-05。**状态：partial**（B 的本地代码、问答和交接已具备；真实天气浏览器全链路、A/C 差异与最终媒体、线上验收未完成）。基线：`fde1c1f`；本地分支 `codex/b-p3-p4-closeout`。草稿 PR #104 尚未并入 `main`，本轮没有推送、合并或线上写操作。

## 完成工作与文件

| 范围 | 文件与事实 |
|---|---|
| 画像/偏好 | `data/personas.json`、`data/presets.json`、`backend/app/services/persona.py`、`backend/app/api/persona.py`、`backend/app/main.py`：五画像、三预设、`GET /api/personas[/presets]`、现有 parse 规则默认/模型显式 opt-in；失败保留硬约束。完整 profile 必须由调用方传路线 API。 |
| 来源/天气 | `backend/app/admin/collect.py`、`backend/app/admin/scheduler.py`、`data/weather_impact.json`：成功时间只在成功时推进；安全公开分类、状态、尝试/成功时间与 stale；天气系数统一 simulated。HKO 官方警告不证明系数真实。 |
| AI 守门 | `backend/app/ai/llm_client.py`、`backend/app/ai/schemas.py`、`backend/app/ai/prompts/discipline.md`：工具数字/路线/线路约束、模拟客流表述、失败兜底纪律。 |
| 测试/材料 | `backend/tests/test_b_p3_closeout.py`、`tests/browser/b-p3-no-ai.cjs`、`docs/plan/07-demo-acceptance.md` §4、`docs/coordination/P3-B-closeout-handoff.md`、`P4-B-material-review.md`、本轮任务/报告/证据。问答 16 条，每答不超过三句；未改 A 的 §1/§2 脚本。 |

## 实际命令与结果

工作目录为本工作树根目录，Shell 为 PowerShell。以下均实际执行；`PYTHONPATH` 设为工作树根与 `backend` 目录。浏览器脚本自身以干净临时库启动后端，并设置 `OFFLINE_MODE=true AI_ENABLED=false AI_DISABLE_EXTERNAL=true`。

| 命令/检查 | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend/tests backend/app/engine/tests tests -q` | **526 passed、264 subtests passed、1 Starlette/httpx 弃用警告**，37.39 s，退出 0。此前强行给全套测试设置 `AI_DISABLE_EXTERNAL=true` 导致两个模拟真模型测试失败；改为按测试自身环境运行后全部通过，不能把第一次叫代码回归。 |
| B 相关 `test_b_p3_closeout.py`、`test_b_replan_handoff.py`、`test_runtime_replanning.py`、`test_source_scheduler.py` | 修改前轮次 **29 passed**；最终修改已包含在上面完整 526 通过中。覆盖审核审计/SSE、自动过期、撤回恢复、待审天气不生效、批准天气重规划与来源状态。 |
| `.\.venv\Scripts\python.exe scripts/validate_data_layer.py` | 20 JSON 结构一致；1 条既有来源真实性人工核查警告，退出 0。 |
| `.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` | 四份 seed 的 Schema/Pydantic/ID 检查通过，退出 0。 |
| `node node_modules/typescript/bin/tsc --noEmit`（frontend） | 退出 0。 |
| `node node_modules/vite/bin/vite.js build --configLoader runner`（frontend） | 退出 0；89 modules，JS chunk 偏大警告。默认 Vite config loader 在本机 Windows 沙箱读取失败，runner 模式通过。 |
| `node tests/browser/b-p3-no-ai.cjs`，设置 `M2_PLAYWRIGHT`、`M2_BROWSER_CHANNEL=msedge`、`M2_EVIDENCE_DIR=runs/round-009/evidence/browser` | **passed=true**，退出 0；真实 Edge 查询、五条轮椅候选检查、受控无路线/模拟雨天 UI、来源失败、未审不发布、批准/撤回、断网保留/恢复。见 `evidence/browser/`。 |
| `git diff --check` | 退出 0；仅 LF/CRLF 未来转换提示。 |

早期浏览器试跑因缺 ffmpeg、读取旧异步响应和天气夹具不合批准条件而失败；旧脚本覆盖 `result.json`，未完整保留这些原始堆栈。已改为追加 `history.jsonl`，最终可交付运行及录屏是完整留存的，但“保存所有原始失败记录”这一条**未达标**。

## 数据十项抽查

`data/personas.json` 中五个画像（1–5）和 `data/presets.json` 中三个预设（6–8）均有文件级 `simulated` 声明；轮椅 hard_flags/400 米另由单测锁定。`data/weather_impact.json` 的各天气条件、可靠性 CV 与渡轮阈值（9）均标 `simulated`；`contracts/seed/sim.seed.json` 的仿真人群（10）由 `data/PROVENANCE.md` S4/seed 表声明为 simulated。此抽查是**标签与出处定位**，不是逐条外部来源真实性复核；官方网络/警告资料不能证明模拟系数或乘客负载。

## 角色互测和未完成项

- B 走了 A 的浏览器路径：雨天警告与无路线为受控响应，来源失败、LLM 关闭、事件批准/撤回、离线保留与恢复已执行；真实批准天气事件的浏览器重规划画面尚缺。后端测试覆盖天气触发，但不能代替完整录像。
- 固定大围→金钟同一 OD 的上班族、学生、游客、轮椅 top1 仍相同，长者为空；因此 T4.1/T4.2 目录/API 完成不等于 M3“懂个人”通过。交 C 排查候选/数据；不可放宽轮椅硬约束。
- A 需接五画像/来源状态/解析说明和重规划横幅，更新最终 PPT/视频/README/Data-AI 说明；旧 07 §1/§2 的“4 辆低地台小巴”“6,140 人/小时”、固定时间/收益数字不可照读。B 已给可复制修订文案，未找到可审的最终 PPT/视频文件。
- MTR 公开公告真实请求成功但未产生合格 Signal，真人审核链仍 partial；受限社媒、T2.6 真模型、真实载客量、线上部署/计时仍暂缓。P3/P4 项目整体不得标完成。

## 建议下一步

请总控先确认 PR #104 的处理，再从当时最新 `main` 建正式分支，逐项移植本轮小提交并开 PR，不整合旧 `XMQM3`。A/C 按 `docs/coordination/P3-B-closeout-handoff.md` 各交同版本证据；A 将 `P4-B-material-review.md` 的事实修订带入最终媒体。B 再补真实天气浏览器全链路和失败记录保全，最后才复核 P3/P4 完成状态。
