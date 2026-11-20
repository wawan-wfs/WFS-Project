#!/usr/bin/env python3
"""Operator-only snapshot packager. Never called from API/agent/worker.

Copies only exact delivered source files and two versioned trusted probes to a
bounded TAR. The TAR digest must be checked independently on the isolated host.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import config

MAX_FILES=110
MAX_BYTES=5_000_000


def package(project_id: str, output: Path) -> str:
    if not re.fullmatch(r'[a-f0-9]{20}',project_id):raise ValueError('Project ID must be 20 lowercase hex digits')
    project=config.PROJECTS/project_id
    if not project.is_dir() or project.is_symlink():raise ValueError('Project delivery directory missing or unsafe')
    files={}
    for path in sorted(project.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):raise ValueError('Delivery symlink or device rejected')
        if path.is_file():files['project/'+path.relative_to(project).as_posix()]=path
    for name in ('qa_probe.py','qa-node.js'):
        files['trusted/'+name]=ROOT/'scripts'/name
    if not 1<=len(files)<=MAX_FILES or sum(p.stat().st_size for p in files.values())>MAX_BYTES:
        raise ValueError('Snapshot exceeds bounded file count/size')
    manifest={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}
    output=output.resolve()
    with tarfile.open(output,'w:gz') as tf:
        for name,path in files.items():
            if not path.is_file() or path.is_symlink():raise ValueError('Unsafe probe or artifact')
            data=path.read_bytes()
            info=tarfile.TarInfo(name);info.mode=0o444;info.size=len(data);info.mtime=0
            tf.addfile(info,io.BytesIO(data))
        blob=json.dumps({'format':'wfs-sealed-snapshot-v28','project_id':project_id,'files':manifest},
                        sort_keys=True,separators=(',',':')).encode()
        info=tarfile.TarInfo('MANIFEST.json');info.mode=0o444;info.size=len(blob);info.mtime=0
        tf.addfile(info,io.BytesIO(blob))
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('project_id')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps({'archive':str(args.output),'sha256':package(args.project_id,args.output)}))
    except (OSError,ValueError,tarfile.TarError) as exc:
        parser.error(str(exc))
