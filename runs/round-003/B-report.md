# B M2 材料本地复核与收尾（2026-09-29）

## 状态

**partial**：B 的 M2 英文交接材料与离线验证已整理；真实模型、线上来源、A/C 全链联调和团队 interim 提交仍未由本报告验收。下文记录 2026-09-29 原始本地复核；随后用户要求上传，上传前续查见文末。

## 完成工作

- 在本地 `XMQM2` 分支、起始提交 `b344581` 上复核 B 的 README 素材、进度证据、事件链路报告、当前 API 与双语免责声明。
- 将 2026-09-27 的 `Mingquan-Xia` 记录明确标为历史基线，补入 2026-09-29 当前分支的验证结果。英文进度段落使用当前的 127 项测试结果，同时保留旧基线 126 项的来历。
- 明确 `XMQM2` 远端状态未经核实、T2.6 真实模型验收未运行、A/C 界面和路线全链未验证。T8.3 独立提示词交付不属于本轮 M2 材料收尾。
- 对照 `backend/app/main.py`、`backend/app/api/signals.py`、`backend/app/api/events.py` 和结构化器，未发现双语免责声明需要修改的具体错误；保留该文件原样。

## 修改文件

- `docs/coordination/M2-README-B.md`
- `docs/coordination/B-M2-progress-evidence.md`
- `docs/coordination/B-M2-event-pipeline-report.md`
- 新增本报告；未覆盖 `round-001` 或 `round-002`。

## 实际检查与结果

以下命令均在仓库根目录运行：

| 命令或检查 | 结果 |
|---|---|
| `git status --short --branch`、`git log --oneline --decorate -15`、`Get-ChildItem runs -Directory` | 确认当前为 `XMQM2`、HEAD `b344581`；开始时只有原有未跟踪 `.venv-readme-b/`；`round-003` 未使用。 |
| `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v` | 127 项通过，退出码 0；有 Starlette/httpx 的弃用警告。测试使用本地模拟/替身，不证明真实模型或浏览器效果。 |
| `.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` | 通过，退出码 0；四份种子 JSON 可读，三张 Event 与五条 Signal 符合 B 的契约。 |
| `git ls-remote --heads origin XMQM2` | 未成功：无法连接 `github.com:443`。不能据此判断远端分支存在与否。 |
| `git diff --check`、`git diff` | 文档修改后检查通过，无空白错误；Git 仅提示本机未来可能作 LF/CRLF 转换。逐项检查了改动范围。 |

## 发现、风险与下一步

- 当前 API 有审核方 Signal 收件箱、人工成卡、事件审核和 SSE；后端离线测试不能替代 A 的真实界面操作或 C 的图快照及路线重算验收。
- T2.6 仍缺 C 的真实模型适配器和受信环境中的真实请求记录；脚本化十样本测试不等于真实文本的首次通过率。此次未检查任何凭证值，也未调用模型。
- 共享契约仍有 `ERL_E`/`ERL_W` 与实现 `ERL`、ingest 返回形状、错误外壳及 `updated` 期间公开事件行为等差异，需 A/B/C 决定，不在 B 文档收尾时擅自修改。
- A 可采用更新后的英文段落和免责声明，随后记录界面、路线、真实来源及真实模型的单独验收证据。`.venv-readme-b/` 保持原状，不纳入交付。

## 上传前续查

- `git ls-remote --heads origin XMQM2 main` 成功，两个远端分支当时均指向 `a82e790`；`git fetch origin refs/heads/XMQM2:refs/remotes/origin/XMQM2` 成功。本地 `b344581` 是远端的祖先，远端领先 40 个提交。目标 B 文档及本报告在这些提交中未被修改。
- `git merge --ff-only origin/XMQM2` 成功，将本地分支快进至 `a82e790`，保留了本地 B 文档改动及原有未跟踪 `.venv-readme-b/`。新基线包含 A/C 的前端、路线和 AI 适配器，因此同步前有关“当前没有这些模块”的说法已限定为历史快照。
- 在新基线上，`.\.venv\Scripts\python.exe -m unittest discover -s backend/tests` 因新测试导入 `app` 而出现一个导入错误；设置仓库的 backend 导入路径后，`$env:PYTHONPATH = (Get-Location).Path + '\backend'; .\.venv\Scripts\python.exe -m unittest discover -s backend/tests` 通过 179 项（退出码 0）。`.\.venv\Scripts\python.exe scripts/validate_contract_seeds.py` 也通过（退出码 0）。这些是离线检查，未调用真实模型或线上来源。
- 本次仅准备上传 B 的三份交接文档和本报告；`.venv-readme-b/` 不纳入提交。整个 M2 的团队验收仍需单独核实。
