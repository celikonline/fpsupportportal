$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPidFile = Join-Path $taskRoot '.runtime/processes.json'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Output 'No launcher process record found.'; exit }
$taskRecords = Get-Content -LiteralPath $taskPidFile -Raw | ConvertFrom-Json
function Stop-PortalChildren([int]$taskParent) {
    foreach ($taskChild in Get-CimInstance Win32_Process -Filter "ParentProcessId = $taskParent") {
        Stop-PortalChildren $taskChild.ProcessId
        Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue
    }
}
foreach ($taskRecord in $taskRecords) {
    $taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($taskRecord.pid)"
    $taskExpectedScript = Join-Path $PSScriptRoot "start-$($taskRecord.service).ps1"
    if ($taskProcess -and $taskProcess.CommandLine.Contains($taskExpectedScript)) {
        Stop-PortalChildren $taskRecord.pid
        Stop-Process -Id $taskRecord.pid -ErrorAction SilentlyContinue
    }
}
Write-Output 'Owned portal processes stopped. Docker volumes are preserved.'
