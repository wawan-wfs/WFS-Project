param([Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{20}$')][string]$ProjectId)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$folder = (Resolve-Path (Join-Path 'data/projects' $ProjectId)).Path
if (-not (Test-Path (Join-Path $folder 'index.html'))) { throw 'Script QA ini khusus proyek static dengan index.html' }
# This is an optional explicit, isolated syntax check. No Docker socket is in the app/worker.
docker run --rm --network none --read-only --security-opt no-new-privileges --cap-drop ALL --pids-limit 64 --memory 256m --cpus 1 --user 65534:65534 --mount "type=bind,source=$folder,target=/src,readonly" --tmpfs /tmp:rw,noexec,nosuid,size=32m node:22-alpine sh -c 'for file in /src/*.js; do if [ -f "$file" ]; then node --check "$file" || exit 1; fi; done; echo "JavaScript syntax checks passed (runtime test NOT performed)"'
if ($LASTEXITCODE -ne 0) { throw 'QA syntax check gagal' }
