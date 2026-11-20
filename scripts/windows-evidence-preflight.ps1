# Read-only Windows capability snapshot. Does not start Docker or use credentials.
param([Parameter(Mandatory=$true)][string]$OutputJson)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Run this preflight on Windows.' }
$target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputJson)
if (Test-Path -LiteralPath $target) { throw 'Choose a new output file.' }
$os = Get-CimInstance Win32_OperatingSystem
$gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  [ordered]@{ name=$_.Name; driver=$_.DriverVersion }
})
$docker = Get-Command docker -ErrorAction SilentlyContinue
$compose = $null
if ($docker) {
  $versionText = & docker compose version --short 2>$null
  if ($LASTEXITCODE -eq 0) { $compose = [string]$versionText }
}
$result = [ordered]@{
  classification='PREFLIGHT_ONLY'
  utc=[DateTime]::UtcNow.ToString('o')
  windows=[ordered]@{ version=$os.Version; build=$os.BuildNumber }
  display_adapters=$gpu
  docker_cli_present=[bool]$docker
  compose_cli_version=$compose
  not_verified=@('Docker daemon and container isolation','hardware WebGL/VRAM','Chrome and Edge 600s',
    'native browser zoom and keyboard','NVDA','MFA recovery','matched restore')
}
$json = ConvertTo-Json -InputObject $result -Depth 5
$stream = [IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try {
  $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
  $stream.Write($bytes,0,$bytes.Length)
} finally { $stream.Dispose() }
Write-Host "Preflight saved. Capability inventory is not acceptance evidence."
