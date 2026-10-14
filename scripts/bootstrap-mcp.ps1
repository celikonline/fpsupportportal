$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run scripts/bootstrap.ps1 first.' }
& $taskPython -m venv "$taskRoot/.runtime/mcp-venv"
if ($LASTEXITCODE -ne 0) { throw 'MCP environment creation failed.' }
& "$taskRoot/.runtime/mcp-venv/Scripts/python.exe" -m pip install -r "$taskRoot/apps/mcp/requirements.lock"
if ($LASTEXITCODE -ne 0) { throw 'MCP dependency installation failed.' }
