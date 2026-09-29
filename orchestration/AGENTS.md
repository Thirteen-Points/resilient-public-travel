# Repository Instructions

## Purpose

This repository is a simple, file-based system for project orchestration.
The orchestrator coordinates four specialist agents and prepares a prompt for WorkBuddy.

## Source of Truth

- `PROJECT_GOAL.md` defines the stable project goal and success criteria.
- `PROJECT_STATE.md` contains the latest concise project facts and current status.
- `agents/` defines the responsibilities and boundaries of specialist agents.
- `workbuddy/WORKBUDDY.md` defines WorkBuddy's role and boundaries.
- `runs/` contains round-specific tasks, reports, synthesis, and next-round plans.
- If files disagree, do not silently choose one. Report the conflict to the orchestrator.

## Working Rules

- Read the relevant project files before proposing or making changes.
- Keep the solution simple. Prefer Markdown and small scripts over new services or frameworks.
- Make only changes required by the assigned task.
- Respect each task's allowed-file list and do not edit files outside it.
- Do not change the overall project direction without an explicit orchestrator decision.
- Never claim that a command, test, or agent task succeeded unless it was actually run and verified.
- Preserve user work and unrelated changes.
- Ask before destructive actions, credential changes, or other hard-to-reverse operations.
- Upload completed, validated project files to GitHub instead of leaving them only locally. Use `Mingquan-Xia` for M0, `XMQM1` for M1, and `XMQM2` for M2. Keep generated environments, caches, and secrets out of Git.
- If a file's milestone or destination is unclear, clarify it before uploading. Use pull requests to merge milestone work into `main`.
- Use clear language suitable for a university student who is still learning Git and Codex.

## Orchestration Rules

- The orchestrator owns cross-agent decisions, conflict resolution, and updates to `PROJECT_STATE.md`.
- Specialist agents own only their assigned objectives and permitted files.
- Parallel work is allowed only when tasks are independent and their writable files do not overlap.
- Each agent report must state:
  - status: completed, partial, or blocked
  - work completed
  - files changed
  - findings and evidence
  - problems, risks, or unresolved questions
  - recommended next action
- Treat agent reports as evidence to review, not automatically as project truth.
- Record each orchestration round under one immutable `runs/round-NNN/` directory.

## Validation

- Run checks appropriate to the files changed.
- Record commands actually run and their results in the relevant report.
- When no automated check exists, describe the manual verification performed.

## Git Rules

- Keep commits small and focused on one understandable change.
- Review `git status` and the diff before committing.
- Do not rewrite history, force-push, delete branches, or discard changes without explicit user approval.
- Do not commit secrets, API keys, passwords, or personal access tokens.

## Tutor Mode

- Work in one reasonably sized learning step at a time.
- Explain what is being done, why it matters, where a command runs, and what success looks like.
- Explain a new command or concept briefly when it first appears.
- End each learning step with a concrete checkpoint before moving on.
