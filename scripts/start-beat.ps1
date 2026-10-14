. "$PSScriptRoot/env.ps1"
$env:POSTGRES_OWNER_PASSWORD = $null
New-Item -ItemType Directory -Force "$taskRoot/.runtime" | Out-Null
Push-Location "$taskRoot/apps/api"
try { & "$taskRoot/.venv/Scripts/python.exe" -m celery -A config beat --loglevel=warning --schedule "$taskRoot/.runtime/celerybeat" }
finally { Pop-Location }
