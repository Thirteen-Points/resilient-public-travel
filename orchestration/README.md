# Multi-Agent Project Orchestration

这是一个以 Markdown、Git 和 Codex 原生 subagents 为核心的轻量项目编排系统。

## 从哪里开始

1. 在 `PROJECT_GOAL.md` 写清项目目标。
2. 在 `PROJECT_STATE.md` 维护当前事实，不记录聊天流水账。
3. 在 `agents/` 调整四个 Agent 的职责。
4. 让 Codex 按 `prompts/orchestrator.md` 开启新一轮。
5. 每轮产物保存在唯一的 `runs/round-NNN/` 中。

## 自动化等级

- LEVEL 1：使用模板生成任务，人工发送与收集。
- LEVEL 2：Codex 使用 `.codex/agents/` 中的自定义 subagents 分配并收集工作。
- LEVEL 3：仅在出现明确瓶颈后，才考虑 API、MCP 或更复杂脚本。

当前状态：LEVEL 2 已配置；LEVEL 1 始终可作为可靠回退方案。

## 一轮工作的最短指令

在 Codex 中输入：

> 读取 AGENTS.md、PROJECT_GOAL.md、PROJECT_STATE.md、四个角色文件和最近一轮，严格按照 prompts/orchestrator.md 开始下一轮。使用四个 subagents；受并发限制时分批执行。完成报告、综合、状态更新、下一轮计划和 WorkBuddy prompt，并运行验证脚本。

## 安全边界

- 不把密钥写入仓库。
- 已完成并验证的文件上传到 GitHub：M0 用 `Mingquan-Xia`，M1 用 `XMQM1`，M2 用 `XMQM2`；通过合并申请进入 `main`。
- 不自动删除历史 round。
- 不让多个并行 Agent 修改同一文件。
