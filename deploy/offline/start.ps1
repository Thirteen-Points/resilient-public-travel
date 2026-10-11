param([string]$Python = $env:P4_PYTHON, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Python) { $Python = Join-Path $repo '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Set P4_PYTHON to your prepared Python executable; offline launch never installs dependencies.' }
Set-Location $repo
$arguments = @('scripts/offline_demo.py')
if ($CheckOnly) { $arguments += '--check-only' }
& $Python @arguments
exit $LASTEXITCODE
