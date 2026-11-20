# Explicit opt-in build of AI-generated React/Vite in disposable Docker containers.
# Never mount .env, database, Docker socket or original generated source writable.
param([Parameter(Mandatory=$true)][string]$ProjectId)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($ProjectId -notmatch '^[a-f0-9]{20}$') { throw 'Project ID tidak valid' }
$project=Join-Path (Join-Path $root 'data/projects') $ProjectId
if (-not (Test-Path (Join-Path $project 'package.json'))) { throw 'Bukan proyek React/Vite, atau file belum tersedia' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop belum tersedia' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Engine tidak berjalan' }
Write-Host 'Build React/Vite membaca dependency npm dari internet. Pastikan Anda mempercayai proyek ini.' -ForegroundColor Yellow
$confirmed=Read-Host 'Ketik BUILD untuk melanjutkan'
if ($confirmed -cne 'BUILD') { throw 'Dibatalkan.' }
$tmp=Join-Path $root ('data/build-temp-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  Copy-Item -Path (Join-Path $project '*') -Destination $tmp -Recurse -Force
  $bind="type=bind,source=$tmp,target=/work"
  # Install dependency packages with lifecycle scripts DISABLED. Only npm registry requests are expected.
  Write-Host '[1/2] Install deps (ignore-scripts)...' -ForegroundColor Cyan
  docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 1024m --cpus 2 `
    --tmpfs /tmp:rw,nosuid,size=64m --env npm_config_cache=/work/.npm-cache `
    --mount $bind --workdir /work node:22-alpine npm install --ignore-scripts --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw 'npm install gagal; periksa package.json/dependencies.' }
  # Run untrusted Vite build with network COMPLETELY DISABLED and only temp copy writable.
  Write-Host '[2/2] Build (network none, no secrets)...' -ForegroundColor Cyan
  docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 1024m --cpus 2 `
    --tmpfs /tmp:rw,nosuid,size=64m --env npm_config_cache=/tmp/npm-cache --mount $bind --workdir /work node:22-alpine `
    npm run build -- --base ./
  if ($LASTEXITCODE -ne 0) { throw 'Build React gagal; periksa konfigurasi Vite dan kode AI.' }
  if (-not (Test-Path (Join-Path $tmp 'dist/index.html'))) { throw 'Vite tidak menghasilkan dist/index.html' }
  $preview=Join-Path (Join-Path $root 'data/previews') $ProjectId
  if (Test-Path $preview) { Remove-Item -LiteralPath $preview -Recurse -Force }
  New-Item -ItemType Directory -Path $preview -Force | Out-Null
  Copy-Item -Path (Join-Path $tmp 'dist/*') -Destination $preview -Recurse -Force
  Write-Host "Preview ready. Reload dashboard WFS dan klik Open Preview pada proyek $ProjectId" -ForegroundColor Green
} finally {
  if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
