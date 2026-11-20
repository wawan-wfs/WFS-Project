#!/usr/bin/env python3
"""Privileged OPERATOR host-only importer for fs-immutable rootless staging.

Run on an isolated Linux runner with an ext4 filesystem supporting chattr +i.
Never place this script on the public API or an AI agent code-execution host.
An authenticated operator must verify archive SHA-256 via an independent channel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT=Path('/srv/wfs-runner')
MAX_TOTAL=5_000_000
MAX_FILES=110


def _seal_tree(path:Path):
    for entry in sorted(path.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if entry.is_symlink():raise ValueError('Symlink not allowed during sealing')
        entry.chmod(0o555 if entry.is_dir() else 0o444)
        subprocess.run(['chattr','+i',str(entry)],check=True,capture_output=True)
    path.chmod(0o555)
    subprocess.run(['chattr','+i',str(path)],check=True,capture_output=True)


def import_snapshot(archive:Path,project_id:str,expected_sha256:str,root:Path=ROOT):
    if os.name!='posix' or (hasattr(os,'geteuid') and os.geteuid()!=0):
        raise ValueError('Must run as root on dedicated Linux staging host')
    if not re.fullmatch('[a-f0-9]{20}',project_id):raise ValueError('Invalid project ID')
    if not re.fullmatch('[a-f0-9]{64}',expected_sha256):raise ValueError('Full expected archive SHA-256 required')
    if root!=ROOT:raise ValueError('Staging root must be /srv/wfs-runner')
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_size>8_000_000 or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Archive SHA-256 mismatch')
    stage_root=root/'staging'; trusted_root=root/'trusted'
    for d in (root,stage_root,trusted_root):
        if d.is_symlink() or not d.is_dir() or d.stat().st_uid!=0 or d.stat().st_mode&0o022:
            raise ValueError('Staging dirs must be root-owned, non-writable by non-root, non-symlinks')
    dest=stage_root/project_id
    if dest.exists() or dest.is_symlink():raise ValueError('Refusing to overwrite existing immutable project snapshot')
    with tempfile.TemporaryDirectory(prefix='.wfs-import-',dir=str(stage_root)) as d:
        tmp=Path(d)
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers()
            if len(members)>MAX_FILES+1 or sum(m.size for m in members)>MAX_TOTAL:
                raise ValueError('Snapshot exceeds limits')
            if not all(m.isfile() and m.name and not m.issym() and not m.islnk() for m in members):
                raise ValueError('Non-regular TAR content refused')
            names=[m.name for m in members]
            if len(names)!=len(set(names)) or 'MANIFEST.json' not in names:
                raise ValueError('Duplicate names/missing manifest')
            for m in members:
                parts=PurePosixPath(m.name).parts
                if any(part in ('.','..','') for part in parts) or m.name.startswith('/') or len(parts)<2 and m.name!='MANIFEST.json':
                    raise ValueError('Unsafe archive path')
                if m.name!='MANIFEST.json' and parts[0] not in ('project','trusted'):
                    raise ValueError('Unexpected archive prefix')
            meta=json.load(tar.extractfile('MANIFEST.json'))
            if meta.get('project_id')!=project_id or meta.get('format')!='wfs-sealed-snapshot-v28':
                raise ValueError('Manifest project/version mismatch')
            manifest=meta.get('files')
            if not isinstance(manifest,dict) or set(manifest)!=set(names)-{'MANIFEST.json'}:
                raise ValueError('Manifest does not list all files')
            if set(k for k in manifest if k.startswith('trusted/'))!={'trusted/qa_probe.py','trusted/qa-node.js'}:
                raise ValueError('Trusted probes must be exactly the approved filenames')
            for m in members:
                if m.name=='MANIFEST.json':continue
                content=tar.extractfile(m).read()
                if hashlib.sha256(content).hexdigest()!=manifest[m.name]:
                    raise ValueError('Archive entry checksum mismatch')
                target=tmp/m.name
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as handle:handle.write(content)
        trusted=tmp/'trusted'
        approved=trusted_root/'v28'
        # Shared trusted probes must also be unmodifiable from the runner UID.
        if approved.exists():
            if approved.is_symlink() or not approved.is_dir():raise ValueError('Trusted probe root invalid')
            observed={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in approved.iterdir() if p.is_file() and not p.is_symlink()}
            expected={k.split('/')[1]:v for k,v in manifest.items() if k.startswith('trusted/')}
            if observed!=expected:raise ValueError('Approved trusted probes do not match immutable release')
        else:
            _seal_tree(trusted)
            os.rename(trusted,approved)
        project=tmp/'project'
        if not project.is_dir():raise ValueError('No source files')
        _seal_tree(project)
        os.rename(project,dest)  # atomic publication within one filesystem
    return str(dest)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('archive',type=Path)
    p.add_argument('--project-id',required=True)
    p.add_argument('--expected-sha256',required=True)
    args=p.parse_args()
    try:print(import_snapshot(args.archive,args.project_id,args.expected_sha256))
    except Exception as exc:p.error(str(exc))
