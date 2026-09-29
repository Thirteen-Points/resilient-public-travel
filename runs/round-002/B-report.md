# B M2 收件箱与事件链路验证

- 状态：partial。
- 完成：补齐审核方 Signal 收件箱、未关联过滤与原文详情，添加 API 回归测试。
- 修改文件：`backend/app/api/signals.py`、`backend/tests/test_event_api_flow.py`、`docs/coordination/T2.5-api-handoff.md`、`docs/coordination/B-M2-event-pipeline-report.md`、本文件。
- 验证：在仓库根目录执行 `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v`，127 项通过，退出码 0；`git diff --check` 通过；fetch 后 HEAD 与 origin/Mingquan-Xia 为 0/0。
- 证据：API 链路覆盖上报、规则草稿、人工成卡、合并、0.20→0.35→0.55、审核发布至 0.60，以及 SQLite 审计驱动 SSE 重连和实时帧生成。
- 未解决：T2.6 缺真实客户端和 OPENAI_API_KEY，未运行真实模型验收；官方核实 API、0.90 API 演示、A 界面与 C 图/路线联调待完成。
- 下一步：A 接入受信审核代理与原文视图；C 注入真实模型并消费已发布区段。详细实际命令、环境失败记录、契约冲突和交接说明见 `docs/coordination/B-M2-event-pipeline-report.md`。
- 保留：非本轮创建的 `.venv-readme-b/`、`backend/app/api/disclaimer.md`、`runs/round-001/`，不纳入本轮提交。
