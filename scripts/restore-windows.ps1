# Offline restore requires an explicit ZIP backup and confirmation.
param([Parameter(Mandatory=$true)][string]$BackupZip)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath $BackupZip -PathType Leaf)) { throw 'Backup ZIP tidak ditemukan.' }
$backup=(Resolve-Path -LiteralPath $BackupZip).Path
Write-Warning 'Restore menimpa folder data/ dan seluruh proyek. Simpan backup sebelum melanjutkan.'
$confirmation=Read-Host 'Ketik RESTORE untuk melanjutkan'
if ($confirmation -cne 'RESTORE') { throw 'Dibatalkan.' }
docker compose stop api worker
try {
  if (Test-Path 'data') {
    $name='data-before-restore-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item -LiteralPath 'data' -Destination $name
    Write-Host "Folder data lama disimpan sebagai $name"
  }
  $staging=Join-Path $PWD ('wfs-restore-'+[guid]::NewGuid().ToString('N'))
  try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Expand-Archive -LiteralPath $backup -DestinationPath $staging
    if (-not (Test-Path (Join-Path $staging 'data/wfs.sqlite3'))) { throw 'ZIP bukan backup WFS yang valid.' }
    Move-Item -LiteralPath (Join-Path $staging 'data') -Destination (Join-Path $PWD 'data')
    Write-Host 'Data berhasil direstore.' -ForegroundColor Green
  } finally { if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force } }
} finally { docker compose start api worker }
