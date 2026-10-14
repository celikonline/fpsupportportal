$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPythonCommand = Get-Command python -ErrorAction SilentlyContinue
$taskPython = if ($taskPythonCommand) { $taskPythonCommand.Source } else { Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' }
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Python 3.12 must be installed.' }
& $taskPython -m venv "$taskRoot/.venv"
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
& "$taskRoot/.venv/Scripts/python.exe" -m pip install -r "$taskRoot/apps/api/requirements.lock"
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& "$taskRoot/.venv/Scripts/python.exe" "$PSScriptRoot/configure_local.py"
Push-Location "$taskRoot/apps/web"
try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } }
finally { Pop-Location }
