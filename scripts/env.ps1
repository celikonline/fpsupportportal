$taskRoot = Split-Path $PSScriptRoot -Parent
$taskEnvFile = Join-Path $taskRoot '.env'
if (-not (Test-Path -LiteralPath $taskEnvFile)) { throw 'Run scripts/configure_local.py first.' }
foreach ($taskLine in Get-Content -LiteralPath $taskEnvFile) {
    if ($taskLine -match '^([A-Z][A-Z0-9_]*)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
}
