#!/usr/bin/env python3
"""Operator-only immutable *per-attempt* source snapshot for v2.9.

No Docker, network, app worker or API use. Archive SHA must be compared on an
independent channel. This does not provision a remote staging host.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import re
import secrets
import sys
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import config


def package(project_id: str, output: Path, attempt_id: str) -> dict:
    if not re.fullmatch(r'[a-f0-9]{20}',project_id):raise ValueError('Invalid project ID')
    if not re.fullmatch(r'[a-f0-9]{32}',attempt_id):raise ValueError('Invalid attempt ID')
    root=config.PROJECTS/project_id
    if not root.is_dir() or root.is_symlink():raise ValueError('Project source missing')
    files={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Source symlinks/special files denied')
        if path.is_file():files['project/'+path.relative_to(root).as_posix()]=path
    for name in ('qa_probe.py','qa-node.js'):
        files['trusted/'+name]=ROOT/'scripts'/name
    if not 2<len(files)<=110 or sum(f.stat().st_size for f in files.values())>5_000_000:
        raise ValueError('Source bounds violated')
    output=output.resolve()
    if output.exists() or output.is_symlink():raise ValueError('Refusing to overwrite previous attempt archive')
    output.parent.mkdir(parents=True,exist_ok=True)
    hashes={}
    try:
        with tarfile.open(output,'x:gz') as archive:
            for name,path in files.items():
                data=path.read_bytes()
                if len(data)!=path.stat().st_size or path.is_symlink():raise ValueError('Source changed during snapshot')
                hashes[name]=hashlib.sha256(data).hexdigest()
                info=tarfile.TarInfo(name)
                info.mode=0o444; info.size=len(data); info.mtime=0
                archive.addfile(info,io.BytesIO(data))
            manifest={'format':'wfs-sealed-snapshot-v29','project_id':project_id,
                      'attempt_id':attempt_id,'files':hashes}
            data=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
            info=tarfile.TarInfo('MANIFEST.json');info.mode=0o444;info.size=len(data);info.mtime=0
            archive.addfile(info,io.BytesIO(data))
        return {'project_id':project_id,'attempt_id':attempt_id,'archive':str(output),
                'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':len(hashes),
                'remote_path':f'/srv/wfs-runner/staging/{project_id}/{attempt_id}'}
    except Exception:
        output.unlink(missing_ok=True)
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('project_id')
    p.add_argument('--attempt-id',default=None,help='32-character hex identifier; generated if omitted')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(package(a.project_id,a.output,a.attempt_id or secrets.token_hex(16))))
    except (OSError,ValueError,tarfile.TarError) as exc:p.error(str(exc))
