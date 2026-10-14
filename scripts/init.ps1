. "$PSScriptRoot/env.ps1"
docker compose --env-file "$taskRoot/.env" -f "$taskRoot/infra/compose.yaml" up -d --wait --wait-timeout 300 db redis clamav
if ($LASTEXITCODE -ne 0) { throw 'Infrastructure startup failed.' }
$taskRuntimeUser = $env:POSTGRES_USER
$taskRuntimePassword = $env:POSTGRES_PASSWORD
try {
    $env:POSTGRES_USER = 'support_owner'
    $env:POSTGRES_PASSWORD = $env:POSTGRES_OWNER_PASSWORD
    & "$taskRoot/.venv/Scripts/python.exe" "$taskRoot/apps/api/manage.py" migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migrations failed.' }
    & "$taskRoot/.venv/Scripts/python.exe" "$taskRoot/apps/api/manage.py" seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
} finally {
    $env:POSTGRES_USER = $taskRuntimeUser
    $env:POSTGRES_PASSWORD = $taskRuntimePassword
}
