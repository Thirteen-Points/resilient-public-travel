# Project State

Last updated: 2026-10-02. Orchestrator: Codex.

## Current Objective

完成 `Thirteen-Points/resilient-public-travel` 的 M1/M2 合并后收尾，审查 PR 证据，并在真实数据与部署条件到位后完成剩余验收。本目录是编排源；产品代码和 `runs/round-005`、`runs/round-006` 在相邻的产品仓库工作树中。

## Current Architecture

- Markdown 保存目标、状态、角色、任务和报告；Git 保存可追踪历史。
- `AGENTS.md` 和 `.codex/agents/` 定义长期规则及四个专门 Agent；`runs/round-NNN/` 保存不可覆盖的本轮记录。
- PowerShell 脚本仅验证文件结构，不代替总控判断。外层编排目录是独立本地仓库，GitHub 副本在产品仓库的 `orchestration/` 目录。

## Verified GitHub State

2026-10-02 核对：`main` 为 `a37707d`，包含 M2 集成 PR #98；`XMQM2` 为 `8963552`。后者已合并最新 `main` 并保留 B 收尾改动，但其提交尚未包含在 `main`，仍需审查 [PR #96](https://github.com/Thirteen-Points/resilient-public-travel/pull/96)。2026-10-01 最后核对 `XMQM1` `013b0f7` 的 [PR #95](https://github.com/Thirteen-Points/resilient-public-travel/pull/95) 和编排 [PR #97](https://github.com/Thirteen-Points/resilient-public-travel/pull/97) 均未合并；本次未重新取得这两个 PR 的状态。

## Completed and Evidence

- M1：修正全链路演示的路线判断；本地 HTTP 演示、20 个跨模块测试、189 个后端测试通过，浏览器看到审核发布后的路线/卡片变化及人工过期恢复。见产品 `runs/round-005/M1-report.md` 和 PR #95。这里的“完成”仅指本地链路验收，未代表线上部署或合入 `main`。
- M2 自动过期：共享应用集成测试覆盖单次审计、SSE、图恢复和路线 ID 恢复；本地浏览器确认短时事件自动过期后的地图/公告恢复。见产品 `runs/round-006/report-b.md`。
- M2 画像路由：现有解析器接入共享应用，目标 API 在测试和本地 HTTP 中可用。
- M2 免责声明：中英说明和来源/时间信息在本地浏览器的页面、事件卡与路线卡可见；前端类型检查和生产构建通过。
- M2 组合验证：原收尾提交有 193 个后端测试通过；2026-10-02 与新 `main` 合并并解决 `UpdatesPage.tsx` 冲突后，216 个后端测试、前端类型检查及生产构建通过。工作树干净，兼容性合并提交 `8963552` 已推送 `XMQM2`，更新 PR #96。

## In Progress / Pending

- T2.6 真模型结构化验收仍为 **partial**：GitHub 已检查的分支仅找到十条标记 `simulated` 的匿名改写样本，未找到团队确认的十条真实文本。真实模型调用、首次通过/重试/规则兜底计数和语义复核都未进行。可运行接入与离线守卫已上传 PR #96。
- M2 集成 PR #98 已合并，但 B 收尾 PR #96 尚未进入 `main`。M1 PR #95 与编排 PR #97 的当前状态需在下一次审查时重新核对。B 收尾合并后还需要部署环境 API 与浏览器复验。
- M1 七项路线卡内容及五分钟演示还需独立完整清单；当前证据覆盖核心链路，不能当作所有产品验收均通过。

## Blockers Requiring User/Team Input

- 提供十条获团队批准的真实文本文件路径或安全存放位置，并确定 T2.6 使用的供应商/模型。旧计划指定 OpenAI `gpt-5.6-sol`，现有 C 配置为 DeepSeek/Qwen/GLM，存在待决冲突。原文和凭证不得提交 Git。
- 提供部署测试环境和相应访问条件，供合并后线上复验。PR 审查/合并由有权限的维护者决定。

## Decisions and Constraints

- 保留文件驱动的简单编排方案与已有四 Agent 角色；并行写入仅在文件不重叠时使用。
- M1 使用 `XMQM1`，M2 使用 `XMQM2`，通过 PR 指向 `main`；不直接改 `main`，不重写历史或强推。
- 严格区分“已实现”“本地测试”“浏览器/线上验证”“已合入 main”。已确认 B 收尾提交未进入 `main`，部署后的线上验证尚未完成；其他 PR 状态以各自最近一次核对时间为准。
- 按新证据更新本状态，保留旧 round 和用户现有工作；本轮编排记录为 `runs/round-001/`。

## Next Milestone

优先审查并合并已与最新 `main` 同步的 PR #96；取得 T2.6 真实样本与模型选择后运行真实验收；部署后复验 API、SSE、地图、路线卡与免责声明。再核对 PR #95/#97 状态。
