$taskRoot = Split-Path $PSScriptRoot -Parent
Push-Location "$taskRoot/apps/web"
try { npm run dev } finally { Pop-Location }
