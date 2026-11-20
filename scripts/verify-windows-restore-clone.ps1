# Read-only validation against an already-restored, stopped Windows test clone.
param(
  [Parameter(Mandatory=$true)][string]$CloneRoot,
  [ValidatePattern('^[a-f0-9]{20}$')][string]$ProjectId,
  [ValidatePattern('^[a-f0-9]{20}$')][string[]]$ExpectedProjectIds,
  [string]$Python='python',
  [switch]$ExactInventory,
  [string]$InventoryFile,
  [ValidatePattern('^[a-fA-F0-9]{64}$')][string]$InventorySha256,
  [switch]$SummaryOnly
)
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Run this preflight on Windows.' }
if ($ProjectId -and $ExpectedProjectIds) { throw 'ExpectedProjectIds applies only to batch mode.' }
if ($ExactInventory -and (-not $ExpectedProjectIds -or $ProjectId)) { throw 'ExactInventory requires an expected project list in batch mode.' }
if ($InventoryFile -and ($ProjectId -or $ExpectedProjectIds -or $ExactInventory)) { throw 'InventoryFile is a separate batch mode.' }
if ($InventorySha256 -and -not $InventoryFile) { throw 'InventorySha256 requires InventoryFile.' }
if ($SummaryOnly -and $ProjectId) { throw 'SummaryOnly applies only to batch mode.' }
if ($InventoryFile) { $InventoryFile = (Resolve-Path -LiteralPath $InventoryFile).Path }
$sourceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$clone = (Resolve-Path -LiteralPath $CloneRoot).Path
if ($clone.TrimEnd('\') -ieq $sourceRoot.TrimEnd('\')) { throw 'Select a separate restored test clone.' }
$db = Join-Path $clone 'data\wfs.sqlite3'
$project = $null
if ($ProjectId) { $project = Join-Path (Join-Path $clone 'data\projects') $ProjectId }
$savedPythonPath = $env:PYTHONPATH
Push-Location -LiteralPath $sourceRoot
try {
  $env:PYTHONPATH = $sourceRoot
  $verify = Join-Path $PSScriptRoot 'verify-artifact-generation.py'
  if ($ProjectId) {
    & $Python $verify --db $db --project $ProjectId --candidate $project
  } else {
    $verifyArgs = @('--clone-root', $clone)
    foreach ($id in $ExpectedProjectIds) { $verifyArgs += @('--require-project', $id) }
    if ($ExactInventory) { $verifyArgs += '--exact-inventory' }
    if ($InventoryFile) { $verifyArgs += @('--inventory-file', $InventoryFile) }
    if ($InventorySha256) { $verifyArgs += @('--inventory-sha256', $InventorySha256) }
    if ($SummaryOnly) { $verifyArgs += '--summary-only' }
    & $Python $verify @verifyArgs
  }
  if ($LASTEXITCODE -ne 0) {
    if ($SummaryOnly) { exit $LASTEXITCODE }
    throw 'Artifact and SQLite snapshot verification failed.'
  }
} finally {
  $env:PYTHONPATH = $savedPythonPath
  Pop-Location
}
if (-not $SummaryOnly) { Write-Host 'Artifact match only. Docker, login, MFA and hardware require separate checks.' }
