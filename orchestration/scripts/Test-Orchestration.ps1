$ErrorActionPreference = 'Stop'

$requiredFiles = @(
    'AGENTS.md',
    'README.md',
    'PROJECT_GOAL.md',
    'PROJECT_STATE.md',
    'agents/agent-a.md',
    'agents/agent-b.md',
    'agents/agent-c.md',
    'agents/agent-d.md',
    'workbuddy/WORKBUDDY.md',
    'prompts/orchestrator.md',
    'prompts/templates/task.md',
    'prompts/templates/report.md',
    'prompts/templates/synthesis.md',
    'prompts/templates/next-round.md',
    'prompts/templates/workbuddy-prompt.md',
    '.codex/config.toml',
    '.codex/agents/agent-a.toml',
    '.codex/agents/agent-b.toml',
    '.codex/agents/agent-c.toml',
    '.codex/agents/agent-d.toml'
)

$missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
$rounds = @(Get-ChildItem -LiteralPath 'runs' -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^round-\d{3}$' } |
    Sort-Object Name)

foreach ($round in $rounds) {
    $requiredRoundFiles = @(
        'task-a.md', 'task-b.md', 'task-c.md', 'task-d.md',
        'report-a.md', 'report-b.md', 'report-c.md', 'report-d.md',
        'synthesis.md', 'next-round.md', 'workbuddy-prompt.md'
    )
    foreach ($name in $requiredRoundFiles) {
        $path = Join-Path $round.FullName $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $missing += $path
        }
    }
}

if ($missing.Count -gt 0) {
    Write-Host 'Orchestration validation FAILED.' -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "Missing: $_" }
    exit 1
}

Write-Host 'Orchestration validation PASSED.' -ForegroundColor Green
Write-Host "Core files: $($requiredFiles.Count)"
Write-Host "Complete rounds: $($rounds.Count)"

