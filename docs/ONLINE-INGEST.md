# Windows PowerShell：真实交通信息采集

本模块把原始内容送到人工审核收件箱。它不会发布事件或改变路线。首版能请求港铁交通消息网页的公开 JSON；四个社媒来源仍受阻。详情见 [五来源表](coordination/online-source-feasibility.md)。

## 1. 找到正确目录

本次实现位于这个独立工作树，旧 ZYC-M1 的文件没有迁移过来。在 PowerShell 执行：

```powershell
Set-Location 'C:\Users\zyc\Documents\ChatGPT\Tecent X Hack4SDG\.verification\online-surfing-bot'
git branch --show-current
```

成功应显示 `online-surfing-bot`。下文的“项目根目录”都指这里。以后克隆此分支时，改成你自己的仓库目录即可。

## 2. 准备 Python

在项目根目录执行（本次交付已有 `.venv`，可跳过创建）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

成功会显示依赖安装完成。若 `python` 找不到，先安装 Python 3.11+；此机器也可用 `C:\Users\zyc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` 创建环境。无需激活虚拟环境，后续命令直接指定其 Python。

## 3. 配置同一个数据库

在项目根目录执行：

```powershell
$env:DB_PATH = Join-Path (Get-Location).Path 'backend\app\data\events.sqlite3'
$env:OFFLINE_MODE = 'false'
$env:INGEST_ENABLED = 'true'
$env:INGEST_SOURCES = 'mtr_mobile'
$env:AI_ENABLED = 'false'
$env:AI_DISABLE_EXTERNAL = 'true'
```

这让真实采集联网，但保持 AI 外部调用关闭。`DB_PATH` 必须与后端一致，建议用绝对路径；历史后端把相对 DB_PATH 按 backend 目录解析，CLI 保持相同语义。

临时变量只对这个窗口有效。长期保存可复制 `backend/.env.example` 为 `backend/.env` 再填写；已有 `.env` 时编辑它，不覆盖原配置。后端和 CLI 都读取 `backend/.env`，系统环境变量优先。仓库根的 `.env` 不由此 CLI 自动读取。

可调整的变量：

| 变量 | 默认值 / 作用 |
|---|---|
| INGEST_ENABLED | false；必须 true 才请求 |
| OFFLINE_MODE | true；true 时禁止请求 |
| INGEST_SOURCES | mtr_mobile；多个来源用逗号分隔 |
| INGEST_INTERVAL_SECONDS | 300；至少 300，遵循更慢的来源刷新提示 |
| INGEST_LOOKBACK_HOURS | 24；初次窗口，续采批次保存窗口，新的完整轮次滚动回看 |
| INGEST_MAX_ITEMS | 100；每来源每轮处理上限 |
| INGEST_PAGE_SIZE | 25；分页大小，范围 1–100 |
| INGEST_TIMEOUT_SECONDS | 10；范围大于 0 且不超过 30 秒 |
| INGEST_RETRIES | 2；最多额外重试两次，仅暂时故障重试 |
| INGEST_MTR_LANG | zh-HK；可选 en，正文保持原语言 |
| INGEST_EXTRA_KEYWORDS | 空；可添加逗号分隔主题关键词，仍要求香港交通背景和有效发布时间 |

缺少发布时间始终跳过，没有放宽时间的开关。当前公开源没有历史查询；24 小时只是过滤窗口，不能保证找回网站已经撤下的公告。

## 4. 先执行一次

仍在项目根目录：

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli once
$LASTEXITCODE
```

每行是 JSON。成功请求应出现 `status:"success"` 和 processed/added/duplicate/skipped 计数。`added:0` 不等于失败：可能没有符合条件的公告。`missing_publication_time` 表示已读到正文，但不能证实其发表于窗口内。

输出使用 ASCII JSON 转义，避免 PowerShell 中文编码问题；审核界面仍显示正常中文。

## 5. 持续采集、停止和重启

在同一个目录和配置窗口：

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli poll
```

先采一轮，之后默认每五分钟执行。按 **Ctrl+C** 停止；Windows 控制台也监听 **Ctrl+Break**。正常收到停止信号后会输出 `type:"stopped"`。已发出的请求受超时限制，退出可能需要等当前请求结束。再次执行同一命令会读取数据库检查点和退避时间；不删除数据库，不用重新导入 Signal。

要有界验证三轮：

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli poll --cycles 3
```

正常约十分钟完成，查看 `completed_rounds` 确认真正完成三次采集；busy/waiting 不代表成功周期。首次运行 once 后立即 poll，可能先显示 waiting，不能把 waiting 当作真实验收。

交接时已验证三周期自然退出和 SIGINT 处理器的自动测试。本轮新增 Windows SIGBREAK 处理器测试；Codex 托管终端的 Ctrl+C / 控制事件注入仍未完成实机退出验证，测试进程已清理。你自己 PowerShell 窗口的键盘退出尚待现场确认。需要有界运行时使用 `--cycles`，无需依赖终端按键。

## 6. 查看状态和失败原因

新 PowerShell 窗口先进入同一项目根目录，并设置相同 DB_PATH，然后执行：

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.ingest.online_cli status
```

会列出数据库、选中来源、阻塞原因、最近计数、last_success、next_attempt、cursor 等。日志不输出服务器错误正文、认证头或 token。`next_attempt` 是 UTC Unix 秒数。

| 状态 / 错误 | 应怎样理解 |
|---|---|
| offline / disabled | 检查 OFFLINE_MODE、INGEST_ENABLED |
| blocked | 当前无可用权限或入口；社媒 token 占位符不会自动启用新适配器 |
| waiting | 还没到下一次执行时间，包括上次失败后的退避 |
| busy | 同一来源已有进程占用；不要重复启动，异常退出后租约约 180 秒释放 |
| rate_limited | 429；按 Retry-After 延后，不连续轰炸接口 |
| timeout / server_error / network_error | 本次网络失败；有限重试和持久化退避，其他来源继续 |
| access_denied / robots_disallowed | 访问不允许；不要绕过登录、验证码或 robots，先停该来源并核查 |
| source_format_changed | 页面/JSON 格式变化；停止把异常正文当作 Signal，修复解析器后再验收 |
| storage_or_runner_unavailable | 检查数据库路径、磁盘和其他进程锁；不要删除生产数据库 |

退出码：0 为所选来源无失败，1 表示有 blocked/offline/disabled/error（可能同时有成功来源），2 为配置错误。status 成功读取返回 0。只读查看状态不会发网络请求。

## 7. 从现有审核入口检查 Signal

在后端窗口设置相同绝对 DB_PATH，并在项目根目录启动：

```powershell
$env:REVIEW_API_TOKEN = Read-Host '输入你已有的本地审核令牌'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

成功会显示服务监听 8000。原有管理员控制台也可继续使用既有登录配置；此任务不修改管理员设置。

另一窗口在同一根目录使用相同已有审核令牌：

```powershell
$reviewToken = Read-Host '输入同一个本地审核令牌'
$reviewHeaders = @{ 'x-review-token' = $reviewToken }
Invoke-RestMethod 'http://127.0.0.1:8000/api/signals?unlinked_only=true' -Headers $reviewHeaders
Remove-Variable reviewToken, reviewHeaders
```

符合条件的采集项会带 `online-mtr_mobile-` 前缀、正文及官方链接。它们只有 Signal 身份，需继续走已有人工成卡/审核/发布流程。空列表不能用模拟数据冒充真实采集成功。网页审核台或已有 `/admin/` 也可看到同一收件箱；新采集来源状态目前从 CLI 查看，旧 `/api/sources/status` 仍只包含原有 HKO/MTR ETA。

不要把社媒正文提交到 `POST /api/signals`，那是用户上报入口。

## 8. 运行离线测试

在项目根目录执行：

```powershell
$env:OFFLINE_MODE = 'true'
$env:AI_ENABLED = 'false'
$env:PYTHONPATH = (Get-Location).Path + ';' + (Join-Path (Get-Location).Path 'backend')
.\.venv\Scripts\python.exe -m unittest backend.tests.test_online_ingest -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -q
```

成功出现 `OK`。测试使用临时数据库和标为 OFFLINE TEST DATA 的内容，不调用真实平台、不验证真实模型。

## 数据与隐私边界

`signals` 保持原契约；`ingest_records` 保存公告发布时间、首个采集时间、原始 HTML、跳过原因、修订及恢复关联；`ingest_source_state` 保存续采状态；`ingest_leases` 防止重复进程。没有新 Event 表写入。作者是稳定匿名标识，港铁统一为同一官方主体。未来社媒作者可用环境中的 INGEST_AUTHOR_SALT 生成 HMAC 标识，不能把原始账号 ID 写入日志。

不上传数据库、`.env` 或任何凭据。上传分支和 PR 前，由任务负责人确认目标里程碑与历史暂停要求。
