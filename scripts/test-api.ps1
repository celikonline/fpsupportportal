. "$PSScriptRoot/env.ps1"
# Owner creates only the isolated test DB; security tests switch to the runtime role.
$env:POSTGRES_USER = 'support_owner'
$env:POSTGRES_PASSWORD = $env:POSTGRES_OWNER_PASSWORD
& "$taskRoot/.venv/Scripts/python.exe" "$taskRoot/apps/api/manage.py" test portal --noinput --verbosity 2
exit $LASTEXITCODE
