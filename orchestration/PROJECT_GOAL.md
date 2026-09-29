# Project Goal

## Mission

建立一个简单、可靠、可学习的多 Agent 项目管理与编排系统，使用户只需与一个 Codex 总控沟通，由总控管理四个专门 Agent，并持续生成可审查的项目状态和 WorkBuddy prompt。

## Success Criteria

- 项目目标、当前状态、角色职责和历史运行记录各自有明确文件。
- 每轮都能生成四个边界清楚、格式一致的 Agent 任务。
- Codex 能在能力允许时调用 subagents，并如实说明未自动完成的部分。
- 每轮能形成四份报告、综合结论、状态更新、下一轮计划和 WorkBuddy prompt。
- Git 能显示每轮修改内容，并允许从历史 commit 恢复。
- 系统默认使用 Markdown 和少量 PowerShell，不依赖数据库、Web UI、Docker 或外部 Agent 框架。
- 初学者能够理解文件用途、运行方式和验证结果。

## Non-Goals

- 当前不构建通用 SaaS 平台。
- 当前不引入数据库、消息队列、容器编排或付费 API 自动循环。
- 当前不允许 Agent 自行改变项目总方向。
- 已完成并验证的项目文件应上传到 GitHub 对应里程碑分支，不只保存在本地。

## Constraints

- Windows + PowerShell 环境。
- 四个 Agent 的具体职责可以由用户随时替换。
- 并行写入必须避免文件重叠。
- 项目事实必须可从 Git 和仓库文件中审计。

## Definition of Done

系统拥有完整模板和首轮示例；四个 subagents 已完成一次真实审查；验证脚本通过；`PROJECT_STATE.md` 能准确说明当前状态和下一里程碑。
