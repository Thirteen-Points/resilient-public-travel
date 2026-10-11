# 给 Render 所有者的执行 prompt

复制以下内容到拥有此项目 Render 和 GitHub 权限的协作者聊天：

---

请部署 resilient-public-travel 的票价数据库修复，并完成完整官方票价库导入和线上验证。
仓库为 https://github.com/Thirteen-Points/resilient-public-travel，发布分支为 `codex/fare-database`，请查看对应 PR。
先阅读该分支的 `deploy/FARE-DEPLOYMENT-HANDOFF.zh-CN.md` 和 `deploy/FARES.md`，按交接文档执行。

现有前端是 https://resilient-public-travel.pages.dev，后端是 https://resilient-public-travel-api.onrender.com。
这次授权你核实现有 Render 服务和持久磁盘，备份现有 SQLite 数据库，合并本次票价 PR 到最新 main，部署该提交，
并在 Render Shell 从仓库根目录运行 `python -m scripts.refresh_fares --download`。
随后验证前后端实际版本、健康、票价 SQL 状态、网页价格及重启后的持久性。
如果 main 已有新提交，保留其他更新，解决冲突并重新验证。

修复代码和本地测试已经完成；之前所有地铁方案固定为 HK$12.50，现在应按真实站对票价。
运行时 SQL 数据库为 `fares.sqlite3`，默认在 DB_PATH 的 events 数据库同目录，FARE_DB_PATH 可覆盖。
JSON 仅用于空库首次初始化，完整导入必须另外在 Render 的运行时 Shell 执行，不能只上线启动图中的几个价格。
不要用这个协作者机器的旧 ZYC-P4 整个目录覆盖 main；这次发布分支已经基于最新线上 main 单独合入票价改动。

保留现有 events/admin/ai_usage 数据库、磁盘、管理员配置和 ADMIN_ENCRYPTION_KEY。
如实际没有持久存储或需要付费扩容，先把实际方案与费用提交所有者决定。
无需创建新 Render 服务或更换凭据。不要将任何密钥放进 VITE_* 前端变量。
若出错，先保留错误证据，修复或按交接文档回滚代码；代码回滚不要覆盖新业务数据。

上线验收至少包括：
1. `/api/meta` 与 Render 部署提交一致，`/api/health/deep` 成功。
2. `/api/fares/status` 为真实 SQLite 完整库，来源含 URL、SHA-256、导入时间。
   本地快照为 9,216 条港铁 OD、777,319 条公交分段、1,622 条公交全程、4 条中环↔尖沙咀渡轮费率；
   官方数据变化以本次成功导入日志为准。
3. 成人八达通港铁 TAW→ADM=HK$17.10；182 红隧→金钟分段=HK$12.20；平日渡轮上层=HK$5.00。
   再查 CHW→TUC=HK$27.90，确认图外站对也在数据库。
4. 真实路线查询和网页不再全部显示 HK$12.50；票段累计正确，站内港铁换线不重复收费。
   既有 X-Route-Snapshot 响应头及 Compare 等页面继续可用。
5. 重启或再次部署后，未额外更新的票价 revision、数量、来源校验值保持，已有业务功能健康。

请实际执行到完成，不要只给部署建议。缺少账号权限、持久磁盘或官方来源访问时，说明具体阻塞，保留已完成工作。
最终交付部署 ID、后端/前端提交与 URL、导入数量和日志、线上价格/网页证据，以及持久性验证结果。
在所有线上步骤真正通过前，不要宣称“完整票价数据库已上线”。
