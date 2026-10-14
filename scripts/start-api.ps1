. "$PSScriptRoot/env.ps1"
$env:POSTGRES_OWNER_PASSWORD = $null
& "$taskRoot/.venv/Scripts/python.exe" "$taskRoot/apps/api/manage.py" runserver 127.0.0.1:8000 --noreload
