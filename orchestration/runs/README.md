# Runs

这里保存每一轮的完整审计记录。

## Naming

真实第一轮使用 `round-001`，之后依次为 `round-002`、`round-003`。不要重复使用或覆盖旧编号。

## Required Files Per Round

```text
round-NNN/
├── task-a.md
├── task-b.md
├── task-c.md
├── task-d.md
├── report-a.md
├── report-b.md
├── report-c.md
├── report-d.md
├── synthesis.md
├── next-round.md
└── workbuddy-prompt.md
```

在用户提供真实任务之前，不创建 `round-001`，避免把部署检查误当成项目运行记录。

