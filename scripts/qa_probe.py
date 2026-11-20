"""Trusted probe executed INSIDE network-disabled, constrained Docker container.

The imported project is untrusted and must never be run outside Docker.
"""
from __future__ import annotations
import ast
import importlib
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path('/workspace')

def syntax():
    checked=0
    for path in ROOT.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('Symlink tidak diperbolehkan di project sandbox')
        if not path.is_file():continue
        if path.suffix.lower()=='.py':
            ast.parse(path.read_text(encoding='utf-8'),filename=str(path));checked+=1
        elif path.suffix.lower()=='.json':
            json.loads(path.read_text(encoding='utf-8'));checked+=1
    print(json.dumps({'check':'python_json_syntax','files_checked':checked,'status':'pass'}))

def smoke():
    sys.path.insert(0,str(ROOT))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    entrypoints=('app.main','main','src.main','server','api.main')
    errors=[]
    for module in entrypoints:
        try:
            loaded=importlib.import_module(module)
            application=getattr(loaded,'app',None)
            if not isinstance(application,FastAPI):
                errors.append(f'{module}: no FastAPI app')
                continue
            with TestClient(application,raise_server_exceptions=True) as client:
                response=client.get('/openapi.json',timeout=6)
                if response.status_code!=200:raise RuntimeError(f'OpenAPI status {response.status_code}')
                spec=response.json()
                if not isinstance(spec,dict) or 'paths' not in spec:raise RuntimeError('OpenAPI schema tidak valid')
            print(json.dumps({'check':'fastapi_asgi_smoke','module':module,'routes':len(spec['paths']),'status':'pass'}))
            break
        except Exception as e:
            errors.append(f'{module}: {type(e).__name__}: {str(e)[:180]}')
    else:
        raise RuntimeError('Tidak ada FastAPI entrypoint yang lolos smoke: '+'; '.join(errors))
    tests=ROOT/'tests'
    if tests.is_dir():
        proc=subprocess.run([sys.executable,'-B','-m','pytest','-q','tests'],cwd=ROOT,timeout=45)
        if proc.returncode:raise RuntimeError(f'Unit tests failed ({proc.returncode})')
        print(json.dumps({'check':'project_pytest','status':'pass'}))

if __name__=='__main__':
    syntax()
    if '--runtime-fastapi' in sys.argv:
        smoke()
