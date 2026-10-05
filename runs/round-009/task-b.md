# round-009：B 的 P3/P4 收口任务

基线为 `fde1c1f`，在本地 `codex/b-p3-p4-closeout` 工作；等待草稿 PR #104 处理后，再从当时最新 `main` 建正式分支逐提交移植。旧 `XMQM3` 只参考适用的画像/预设行为，不整分支合并。

允许文件：`backend/app/services/persona.py`、`backend/app/api/persona.py`、`backend/app/main.py`、`backend/app/admin/{collect,scheduler}.py`、`backend/app/ai/{llm_client,schemas}.py` 及新提示词纪律、对应 B 测试、`data/{personas,presets,weather_impact}.json`、B 浏览器测试、问答库 §4、B 交接/报告与本轮证据。不修改 A 前端、C 算路/仿真核心及最终媒体。

交付：五画像/三预设公开目录和保守解析；来源状态脱敏/新鲜度；天气模拟标签；AI 事实守门；P3 审核与无 AI 本地浏览器证据；≥15 条准确问答和 A/C 交接。跨团队差异、页面、线上计时和最终媒体如实列为待验收。

暂缓：T2.6 真模型、Render/Pages 写操作、受限社媒凭据、真实负载提供方，不作为本轮通过条件。
