param([ValidateSet('Project','User')][string]$Scope = 'Project')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root '.agents\skills'
if (!(Test-Path $source)) { throw "Project design skills folder not found: $source" }
if ($Scope -eq 'Project') {
  Write-Host 'Project-local design skills are already included at .agents\skills.' -ForegroundColor Green
  Write-Host 'Agents instructed by AGENTS.md can use them within this repository.'
  exit 0
}
$target = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Path $target -Force | Out-Null
Get-ChildItem -Path $source -Directory | ForEach-Object {
  $dest=Join-Path $target $_.Name
  if (Test-Path $dest) { Write-Warning "Skipping installed skill: $($_.Name)" }
  else { Copy-Item -Path $_.FullName -Destination $dest -Recurse; Write-Host "Installed local skill: $dest" -ForegroundColor Green }
}
Write-Host 'Skills are local instruction files. They do not install a ChatGPT plugin or a model.'
