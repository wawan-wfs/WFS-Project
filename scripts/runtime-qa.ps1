# Run safe syntax/format checks in disposable, network-disabled Docker containers.
# No AI-generated code is executed by this default command.
param([Parameter(Mandatory=$true)][string]$ProjectId)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($ProjectId -notmatch '^[a-f0-9]{20}$') { throw 'Project ID harus berupa 20 karakter hex dari dashboard WFS.' }
$source = Join-Path (Join-Path $root 'data/projects') $ProjectId
if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Folder proyek belum ada: $source" }
$projectDir = (Resolve-Path -LiteralPath $source).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI tidak ditemukan.' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop belum berjalan.' }
$common = @('run','--rm','--network','none','--read-only','--cap-drop','ALL',
    '--security-opt','no-new-privileges','--pids-limit','64','--memory','384m','--cpus','1',
    '--user','10001:10001','--tmpfs','/tmp:rw,noexec,nosuid,size=32m',
    '--mount',"type=bind,source=$projectDir,target=/workspace,readonly",'--workdir','/workspace')
$python = @'
import ast, json, pathlib, sys
root=pathlib.Path('/workspace')
seen=0
for path in sorted(root.rglob('*')):
    if not path.is_file(): continue
    suffix=path.suffix.lower()
    if suffix == '.py':
        ast.parse(path.read_text(encoding='utf-8'),filename=str(path)); seen+=1
    elif suffix == '.json':
        json.loads(path.read_text(encoding='utf-8')); seen+=1
print(f'Python AST / JSON: PASS ({seen} file(s))')
'@
Write-Host '[1/2] Python AST + JSON (isolated/no network)...' -ForegroundColor Cyan
& docker @common 'python:3.12-alpine' 'python' '-B' '-c' $python
if ($LASTEXITCODE -ne 0) { throw 'Python/JSON validation gagal.' }
$node = @'
const fs=require('fs'),path=require('path'),cp=require('child_process');
let total=0;
function scan(d){for(const name of fs.readdirSync(d)){const p=path.join(d,name);const st=fs.lstatSync(p);
 if(st.isSymbolicLink()) continue;
 if(st.isDirectory()){scan(p);continue;}
 if(/\.(js|mjs|cjs)$/.test(p)) {const r=cp.spawnSync(process.execPath,['--check',p],{encoding:'utf8',timeout:12000});
 if(r.status!==0){process.stderr.write(r.stderr||`Invalid: ${p}\n`);process.exit(1);} total++;}
}}
scan('/workspace');console.log(`JavaScript syntax: PASS (${total} file(s)); JSX/TSX not compiled here.`);
'@
Write-Host '[2/2] JavaScript syntax (isolated/no network)...' -ForegroundColor Cyan
& docker @common 'node:22-alpine' 'node' '-e' $node
if ($LASTEXITCODE -ne 0) { throw 'JavaScript validation gagal.' }
Write-Host 'PASS: Pemeriksaan dasar pada sandbox Docker tanpa network.' -ForegroundColor Green
Write-Warning 'Bukan bukti aplikasi berjalan, lulus unit test atau aman untuk production. JSX/TSX, paket npm dan dependencies perlu CI/build terpisah.'
