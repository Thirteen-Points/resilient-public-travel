param(
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "$repo;$repo\backend"
$env:AI_ENABLED = if ($env:AI_ENABLED) { $env:AI_ENABLED } else { "false" }
$env:OFFLINE_MODE = if ($env:OFFLINE_MODE) { $env:OFFLINE_MODE } else { "true" }
$pythonCommand = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonCommand) {
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundled) { $pythonCommand = (Resolve-Path $bundled).Path }
}
if (-not $pythonCommand) { throw "Python 3.10+ was not found. Install Python or set PATH before starting." }
& $pythonCommand -m scripts.preflight
if ($LASTEXITCODE -ne 0) { throw "Preflight failed; service was not started." }
& $pythonCommand -m uvicorn backend.app.main:app --host $ListenHost --port $Port
