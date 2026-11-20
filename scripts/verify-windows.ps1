$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
Write-Host '[1/4] Docker Compose configuration' -ForegroundColor Yellow
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Konfigurasi Docker Compose invalid' }
Write-Host '[2/4] Services status' -ForegroundColor Yellow
docker compose ps
if ($LASTEXITCODE -ne 0) { throw 'Gagal memeriksa Docker Compose' }
Write-Host '[3/4] API health' -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri 'http://localhost:8080/health' -TimeoutSec 10
if ($health.status -ne 'ok') { throw 'API health gagal' }
Write-Host '[4/4] Database readiness' -ForegroundColor Yellow
$ready = Invoke-RestMethod -Uri 'http://localhost:8080/ready' -TimeoutSec 10
if ($ready.status -ne 'ready') { throw 'DB readiness gagal' }
Write-Host 'Basic service checks passed. Lanjutkan smoke test login/demo lewat browser.' -ForegroundColor Green
