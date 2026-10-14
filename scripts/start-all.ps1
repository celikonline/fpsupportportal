$taskRoot = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force "$taskRoot/.runtime" | Out-Null
$taskProcessList = @()
foreach ($taskService in @('api','worker','beat','web')) {
    $taskServiceScript = Join-Path $PSScriptRoot "start-$taskService.ps1"
    $taskProcess = Start-Process pwsh -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile','-File', ('"' + $taskServiceScript + '"')) -WorkingDirectory $taskRoot -RedirectStandardOutput "$taskRoot/.runtime/$taskService.log" -RedirectStandardError "$taskRoot/.runtime/$taskService.error.log"
    $taskProcessList += @{ service = $taskService; pid = $taskProcess.Id }
}
$taskProcessList | ConvertTo-Json | Set-Content -LiteralPath "$taskRoot/.runtime/processes.json"
Write-Output 'Portal starting at http://127.0.0.1:5173. Logs: .runtime/'
