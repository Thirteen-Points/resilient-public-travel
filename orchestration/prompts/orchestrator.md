# Orchestrator Procedure

每轮严格执行以下流程。不要跳过读取、验证或状态更新。

## 1. READ

读取：

- `AGENTS.md`
- `PROJECT_GOAL.md`
- `PROJECT_STATE.md`
- `agents/agent-a.md` 到 `agents/agent-d.md`
- `workbuddy/WORKBUDDY.md`
- 最近一个 `runs/round-NNN/`（如果存在）

先核对目标、事实、角色和最近结论是否冲突。

## 2. PLAN

确定当前阶段、最大 blocker、依赖关系、可以并行的任务，以及本轮唯一主要目标。任务写入新的、从未使用过的 `runs/round-NNN/`。

## 3. DISPATCH

分别生成 `task-a.md`、`task-b.md`、`task-c.md`、`task-d.md`。每个任务必须包含：Context、Objective、Inputs、Files allowed to modify、Tasks、Deliverables、Acceptance criteria、Do not do、Report format。

## 4. EXECUTE

- LEVEL 1：把四个 task 交给用户，由用户发送并把结果保存为 report。
- LEVEL 2：调用四个 Codex subagents；任务独立时并行，写入范围重叠时串行。
- 受并发上限影响时分批运行，并如实记录。
- 无法自动完成的外部操作必须明确标为人工步骤。

## 5. COLLECT

确保四份报告存在且符合统一格式。缺失报告标为 `blocked`，不得编造。

## 6. SYNTHESIZE

创建 `synthesis.md`，包括四方 findings、agreements、conflicts、unresolved questions、risks、important discoveries、recommended next actions。结论必须区分事实、推断和建议。

## 7. UPDATE STATE

根据已验证事实更新 `PROJECT_STATE.md`。保持精炼，只保留 Current objective、Current architecture、Completed、In progress、Pending、Blockers、Decisions、Assumptions、Known issues、Next milestone。

## 8. NEXT ROUND

创建 `next-round.md`，说明下一轮主要目标、依赖、分工和进入条件；它是计划，不代表任务已完成。

## 9. WORKBUDDY

创建 `workbuddy-prompt.md`。它必须是可直接复制的完整 prompt，包含背景、当前事实、目标、输入、边界、交付物和验收标准。

## 10. VALIDATE

运行：

```powershell
pwsh -NoProfile -File .\scripts\Test-Orchestration.ps1
```

查看 `git status` 和 diff。只有实际验证通过后才可标记本轮完成。

