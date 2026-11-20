#Requires -Version 5.1
<# Non-destructive, operator-initiated Windows 10/11 acceptance preflight.
   Default: metadata only. -RunBrowser: interactive authenticated browser testing.
   Never captures passwords, MFA secrets, browser cookies or provider credentials. #>
[CmdletBinding()]
param(
  [string]$TargetURL = 'http://127.0.0.1:8080',
  [string]$EvidenceDirectory = (Join-Path $PSScriptRoot '..\data\acceptance-v34'),
  [switch]$RunBrowser
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$target = $null
try { $target = [uri]$TargetURL } catch { throw 'Invalid target URL' }
if ($target.Scheme -eq 'http' -and $target.Host -notin @('127.0.0.1','localhost')) {
  throw 'Remote plain HTTP is forbidden for authenticated acceptance'
}
if ($target.Scheme -notin @('http','https') -or $target.UserInfo -or $target.Fragment) {
  throw 'Accept only HTTP localhost or HTTPS URL without embedded credentials/fragments'
}
$record = [ordered]@{
  classification = 'OPERATOR HOST PREFLIGHT; NOT INDEPENDENT PRODUCTION ATTESTATION'
  measured_utc = (Get-Date).ToUniversalTime().ToString('o')
  target = $TargetURL
  os = [Environment]::OSVersion.VersionString
  powershell = $PSVersionTable.PSVersion.ToString()
  docker_cli = $false; docker_engine = $false
  docker_desktop_linux_engine = $false
  python_cli = $false
  chrome_installed = $false; edge_installed = $false
  browser_runs = @()
  nvda_manually_verified = $false
  mfa_recovery_manually_verified = $false
  rollback_manually_verified = $false
  production_admission = 'DENIED'
}
$record['docker_cli'] = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$record['python_cli'] = [bool](Get-Command python -ErrorAction SilentlyContinue)
if ($record['docker_cli']) {
  $info = & docker info --format '{{.OSType}}|{{.OperatingSystem}}' 2>$null
  if ($LASTEXITCODE -eq 0 -and $info) {
    $record['docker_engine'] = $true
    $record['docker_desktop_linux_engine'] = ($info -match '^linux\|.*Docker Desktop')
  }
}
$chrome = @("${env:ProgramFiles}\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")
$edge = @("${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe", "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe")
$record['chrome_installed'] = [bool](@($chrome | Where-Object { Test-Path $_ }).Count)
$record['edge_installed'] = [bool](@($edge | Where-Object { Test-Path $_ }).Count)
if ($RunBrowser) {
  if (-not $record['docker_desktop_linux_engine'] -or -not $record['python_cli'] -or
      -not $record['chrome_installed'] -or -not $record['edge_installed']) {
    throw 'Prerequisites missing; no authenticated browser run started'
  }
  $env:WFS_E2E_URL = $TargetURL
  $env:WFS_E2E_STABILITY_SECONDS = '600'
  foreach ($channel in @('chrome','msedge')) {
    $env:WFS_E2E_CHANNEL = $channel
    Write-Host "Launching $channel acceptance; enter test credentials interactively."
    & python (Join-Path $PSScriptRoot 'acceptance_v25_windows.py')
    $record['browser_runs'] += @{ channel = $channel; exit_code = $LASTEXITCODE; evidence_type = 'OPERATOR_LOCAL_BROWSER' }
  }
}
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$path = Join-Path $EvidenceDirectory ('PREFLIGHT_V34_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
if (Test-Path $path) { throw 'Evidence file already exists; no overwrite allowed' }
$record | ConvertTo-Json -Depth 5 | Set-Content -Path $path -Encoding UTF8 -NoNewline
Write-Host "Evidence written (no secrets): $path"
if (-not $record['docker_desktop_linux_engine']) { exit 2 }
if ($RunBrowser -and @($record['browser_runs'] | Where-Object { $_.exit_code -ne 0 }).Count -gt 0) { exit 1 }
exit 0
