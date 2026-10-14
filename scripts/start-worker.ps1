. "$PSScriptRoot/env.ps1"
$env:POSTGRES_OWNER_PASSWORD = $null
Push-Location "$taskRoot/apps/api"
try { & "$taskRoot/.venv/Scripts/python.exe" -m celery -A config worker --pool=solo --loglevel=warning }
finally { Pop-Location }
