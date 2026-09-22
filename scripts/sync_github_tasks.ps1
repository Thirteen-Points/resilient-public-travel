param(
    [string]$Repository = "Thirteen-Points/resilient-public-travel",
    [int[]]$Workstreams = (1..10),
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $DryRun -and [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
    throw "GITHUB_TOKEN is required unless -DryRun is used."
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workstreamsPath = Join-Path $repositoryRoot "docs/plan/04-workstreams.md"
$apiBase = "https://api.github.com/repos/$Repository"
$headers = @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$optionalTasks = @("T2.12", "T5.8", "T7.4")
$shouldTasks = @(
    "T2.3", "T3.9", "T3.10", "T4.3", "T6.8",
    "T6.10", "T7.5", "T8.2", "T8.4", "T9.5"
)
$doneTasks = @("T2.1", "T2.3", "T2.4")
$inProgressTasks = @("T2.2", "T2.5", "T2.6")
$blockedTasks = @("T1.2", "T1.3")
$scopeNotes = @{
    "T1.2" = "当前阻塞：线路/Signal 来源枚举未冻结，A/C 验收证据及三方签字缺失。"
    "T1.3" = "当前阻塞：GitHub 凭据缺少组织 Project 权限；Issues 与标签已先建立。"
    "T2.5" = "M1 的用户上报链路属于阶段交付；如果减少事件源，只裁剪额外展示，不删除接口。"
    "T3.1" = "核心走廊与替代轨道网络为必做；渡轮和小巴子范围可按 06 §3 作为应做内容裁剪。"
    "T3.5" = "候选生成主能力为必做；渡轮和小巴候选可按 06 §3 作为应做内容裁剪。"
    "T4.2" = "最快和最稳两个预设属于必做；第三个少换乘预设可按 06 §3 作为可选内容裁剪。"
}

function Get-TaskRows {
    Get-Content $workstreamsPath |
        Where-Object { $_ -match '^\| T\d+\.\d+ \|' } |
        ForEach-Object {
            $parts = $_.Trim().Trim('|').Split('|') |
                ForEach-Object { $_.Trim() }
            $id = $parts[0]
            $workstream = [int](($id.Substring(1)).Split('.')[0])
            if ($Workstreams -notcontains $workstream) {
                return
            }

            [pscustomobject]@{
                Id = $id
                Workstream = $workstream
                Task = $parts[1]
                Owner = $parts[2]
                Backup = $parts[3]
                Deliverable = $parts[4]
                DefinitionOfDone = $parts[5]
                DifficultyText = $parts[6]
                Difficulty = ([regex]::Matches($parts[6], '⭐')).Count
                Hours = $parts[7]
                Stage = $parts[8]
            }
        }
}

function Get-Priority([string]$taskId) {
    if ($optionalTasks -contains $taskId) { return "可选" }
    if ($shouldTasks -contains $taskId) { return "应做" }
    return "必做"
}

function Get-Status([string]$taskId) {
    if ($doneTasks -contains $taskId) { return "已完成" }
    if ($inProgressTasks -contains $taskId) { return "进行中" }
    if ($blockedTasks -contains $taskId) { return "阻塞" }
    return "待办"
}

function Get-Labels($task) {
    $ownerLabel = if ($task.Owner -in @("A", "B", "C")) {
        $task.Owner
    } else {
        "Shared"
    }
    $backupLabel = if ($task.Backup -in @("A", "B", "C")) {
        $task.Backup
    } else {
        "All"
    }

    $labels = @()
    $labels += ("ws:{0:d2}" -f $task.Workstream)
    $labels += "owner:$ownerLabel"
    $labels += "backup:$backupLabel"
    $labels += "priority:$(Get-Priority $task.Id)"
    $labels += "difficulty:$($task.Difficulty)"
    $labels += "status:$(Get-Status $task.Id)"
    foreach ($stage in ($task.Stage -split '/')) {
        $labels += "stage:$stage"
    }
    return $labels
}

function Get-IssueBody($task) {
    $priority = Get-Priority $task.Id
    $notes = if ($scopeNotes.ContainsKey($task.Id)) {
        $scopeNotes[$task.Id]
    } else {
        "按 docs/plan/06-risks.md §3 的统一砍单纪律执行；任何裁剪都要同步看板、演示脚本和已知局限。"
    }
    $lines = @(
        "## 任务信息", "",
        "- **任务 ID**：$($task.Id)",
        "- **工作流**：WS$($task.Workstream)",
        "- **负责人**：$($task.Owner)",
        "- **备份人**：$($task.Backup)",
        "- **优先级**：$priority",
        "- **阶段**：$($task.Stage)",
        "- **难度**：$($task.DifficultyText)",
        "- **估时**：$($task.Hours) 小时", "",
        "## 产出", "", $task.Deliverable, "",
        "## 完成定义（DoD）", "",
        "- [ ] $($task.DefinitionOfDone)",
        "- [ ] 提供可复查的代码、文档、截图或测试证据",
        "- [ ] 不违反 ``docs/plan/03-contracts.md`` 的冻结契约与数据真实性规则", "",
        "## 依赖、裁剪范围与备注", "", $notes, "",
        "## 来源", "",
        "- ``docs/plan/04-workstreams.md``",
        "- ``docs/plan/06-risks.md`` §3"
    )
    return $lines -join [Environment]::NewLine
}

$tasks = @(Get-TaskRows)
if ($DryRun) {
    $tasks | ForEach-Object {
        [pscustomobject]@{
            Id = $_.Id
            Title = $_.Task
            Labels = (Get-Labels $_) -join ","
        }
    }
    return
}

$existingIssues = Invoke-RestMethod -Headers $headers -Uri "$apiBase/issues?state=all&per_page=100"
$issuesByTask = @{}
foreach ($issue in $existingIssues) {
    if (-not $issue.pull_request -and $issue.title -match '^\[(T\d+\.\d+)\]') {
        $issuesByTask[$matches[1]] = $issue.number
    }
}

$created = 0
$updated = 0
foreach ($task in $tasks) {
    $isDone = $doneTasks -contains $task.Id
    $payload = @{
        title = "[$($task.Id)] $($task.Task)"
        body = Get-IssueBody $task
        labels = @(Get-Labels $task)
        state = if ($isDone) { "closed" } else { "open" }
    }
    if ($isDone) {
        $payload.state_reason = "completed"
    }
    $json = $payload | ConvertTo-Json -Depth 6

    if ($issuesByTask.ContainsKey($task.Id)) {
        Invoke-RestMethod -Method Patch -Headers $headers -ContentType "application/json" `
            -Uri "$apiBase/issues/$($issuesByTask[$task.Id])" -Body $json | Out-Null
        $updated++
    } else {
        Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" `
            -Uri "$apiBase/issues" -Body $json | Out-Null
        $created++
    }
}

Write-Output "created=$created updated=$updated total=$($created + $updated)"
