"""Only static checks here. User-generated software is NEVER executed by this service."""
from __future__ import annotations
import ast
import hashlib
import json
import os
import re
import shutil
import tempfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from .config import MAX_PROJECT_FILES, MAX_PROJECT_BYTES

_ALLOWED_EXT={'.html','.css','.js','.jsx','.ts','.tsx','.mjs','.cjs','.json','.md','.txt','.py','.toml','.yaml','.yml','.sql','.svg','.xml','.sh','.ps1','.bat','.env.example'}
_ALLOWED_BASE={'Dockerfile','Makefile','.gitignore','LICENSE','Procfile','requirements.txt','.env.example'}
_BAD_PARTS={'.git','.ssh','.aws','node_modules','__pycache__','.venv','venv','.github','.vscode','data','secrets','credentials'}
_BAD_NAMES={'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}
_SECRET_PATTERNS=[re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC |PRIVATE )?PRIVATE KEY-----'),re.compile(r'\bsk-(?:proj-|live-)[A-Za-z0-9_-]{15,}'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}')]


def clean_path(s):
    if not isinstance(s,str) or len(s)>180 or '\\' in s or '\x00' in s or s.startswith('/'):
        raise ValueError(f'Path ditolak: {str(s)[:80]}')
    p=PurePosixPath(s)
    if len(p.parts)>8 or any(v in ('..','.') or v.lower() in _BAD_PARTS or v.endswith((' ','.')) or v.split('.')[0].lower() in _BAD_NAMES for v in p.parts):
        raise ValueError(f'Path berbahaya: {s[:80]}')
    if p.as_posix()!=s or not re.fullmatch(r'[A-Za-z0-9_./-]+',s):
        raise ValueError(f'Path tidak didukung: {s[:80]}')
    if p.name not in _ALLOWED_BASE and p.suffix.lower() not in _ALLOWED_EXT:
        raise ValueError(f'Jenis file tidak diperbolehkan: {s[:80]}')
    if p.name in ('.env','.npmrc','.pypirc') or re.search(r'(?:secret|token|password|private)[._-]',p.name,re.I):
        raise ValueError(f'Nama file berpotensi menyimpan secret: {s[:80]}')
    return s


class _Parser(HTMLParser): pass


def check_files(files, stack='static'):
    if not isinstance(files,dict) or not files or len(files)>MAX_PROJECT_FILES:
        raise ValueError('Jumlah file tidak valid')
    total=0
    notes=[]
    folded=set()
    for name,body in files.items():
        clean_path(name)
        if name.casefold() in folded:
            raise ValueError(f'Benturan nama file tidak kompatibel Windows: {name}')
        folded.add(name.casefold())
        if not isinstance(body,str):raise ValueError(f'Konten bukan teks: {name}')
        blob=body.encode('utf-8')
        if len(blob)>240000:raise ValueError(f'File terlalu besar: {name}')
        total+=len(blob)
        for regex in _SECRET_PATTERNS:
            if regex.search(body):raise ValueError(f'Deteksi credential pada {name}; hentikan dan simpan secret di environment')
        ext=PurePosixPath(name).suffix
        if ext=='.json':
            try:json.loads(body)
            except json.JSONDecodeError as e:raise ValueError(f'JSON invalid {name}: {e.msg}') from None
        if ext=='.py':
            try: ast.parse(body,filename=name)
            except SyntaxError as e:raise ValueError(f'Python syntax error {name}: {e.msg}') from None
        if ext=='.html':
            try:_Parser().feed(body)
            except Exception:raise ValueError(f'HTML gagal diparse: {name}') from None
    if total>MAX_PROJECT_BYTES:raise ValueError('Total ukuran file melebihi batas')
    if stack=='static' and 'index.html' not in files:
        raise ValueError('Situs statis wajib memuat index.html')
    if stack=='node-web' and not ('server.js' in files and 'package.json' in files):
        raise ValueError('Node Web requires server.js and package.json')
    if stack=='node-web':
        pkg=json.loads(files['package.json'])
        if not isinstance(pkg,dict) or not isinstance(pkg.get('scripts',{}),dict):raise ValueError('Node Web package.json must contain scripts')
        if pkg.get('dependencies') or pkg.get('devDependencies'):
            raise ValueError('Node Web preview supports Node built-in libraries only; external dependencies are not permitted')
    if stack=='fastapi' and not any(name.endswith('.py') for name in files):
        raise ValueError('Proyek FastAPI wajib memuat kode Python')
    if stack=='react-vite':
        if 'package.json' not in files or 'index.html' not in files or not any(x in files for x in ('src/main.jsx','src/main.tsx','src/main.js','src/main.ts')):
            raise ValueError('React/Vite memerlukan package.json, index.html, dan src/main.jsx/tsx/js/ts')
        try:
            pkg=json.loads(files['package.json'])
            if not isinstance(pkg.get('scripts'),dict) or not isinstance(pkg['scripts'].get('build'),str):
                raise ValueError('React/Vite perlu scripts.build pada package.json')
        except (TypeError,AttributeError):raise ValueError('package.json wajib JSON object') from None
    notes.append(f'{len(files)} file, {total} byte, path dan format dasar lolos')
    notes.append('Python AST, JSON, HTML parser diperiksa bila relevan')
    notes.append('Tidak ada kode hasil AI yang dieksekusi saat validasi')
    return notes


def safe_write(root:Path,files:dict):
    for name,body in files.items():
        clean_path(name)
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(body.encode('utf-8'))


def deliver(root:Path,files:dict,stack='static'):
    notes=check_files(files,stack)
    root.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.wfs-stage-',dir=root.parent))
    try:
        safe_write(stage,files)
        # Avoid accidentally overwriting previously delivered files on retries.
        if root.exists():
            shutil.rmtree(root)
        os.replace(stage,root)
    finally:
        if stage.exists():shutil.rmtree(stage)
    manifests=[]
    for name in sorted(files):
        blob=files[name].encode()
        manifests.append((name,len(blob),hashlib.sha256(blob).hexdigest()))
    return notes,manifests
