param([ValidateRange(1,8)][int]$WorkerReplicas=3)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop tidak ditemukan di PATH. Instal Docker Desktop dengan WSL2/Linux containers.' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Engine belum berjalan. Jalankan Docker Desktop dan aktifkan Linux containers.' }
if (-not (Test-Path '.env')) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 scripts/bootstrap.py }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python scripts/bootstrap.py }
    else {
        Write-Warning 'Python Windows tidak ada; bootstrap menggunakan container resmi Python.'
        $root=(Get-Location).Path
        docker run --rm --mount "type=bind,source=$root,target=/setup" --workdir /setup python:3.12-slim python scripts/bootstrap.py
        if ($LASTEXITCODE -ne 0) { throw 'Bootstrap via Docker gagal.' }
    }
}
Write-Host "[1/3] Menjalankan API dan $WorkerReplicas worker replica(s)..." -ForegroundColor Cyan
docker compose up --build -d --scale worker=$WorkerReplicas
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose gagal. Periksa docker compose logs api worker.' }
Write-Host '[2/3] Memeriksa API readiness...' -ForegroundColor Cyan
$ready=$false
for ($i=0;$i -lt 30;$i++) {
    try {
        $r=Invoke-RestMethod 'http://127.0.0.1:8080/ready' -TimeoutSec 3
        if ($r.status -eq 'ready') { $ready=$true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    docker compose logs --tail 30 api
    throw 'API belum siap; periksa log di atas.'
}
Write-Host '[3/3] Memeriksa proses worker...' -ForegroundColor Cyan
$running=docker compose ps --status running --services
if ($LASTEXITCODE -ne 0 -or $running -notcontains 'worker') {
    docker compose logs --tail 30 worker
    throw 'Worker belum berjalan. Periksa log di atas.'
}
Write-Host 'WFS PROJECT v2.5 berhasil berjalan pada http://localhost:8080' -ForegroundColor Green
Write-Host 'Login menggunakan password dari bootstrap pertama. Jangan bagikan file .env.'
Write-Host 'Pemeriksaan browser dan model AI asli masih perlu dilakukan oleh operator.' -ForegroundColor Yellow
