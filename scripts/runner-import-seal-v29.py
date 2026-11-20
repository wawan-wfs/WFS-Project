#!/usr/bin/env python3
"""Privileged offline snapshot admission on a separate dedicated Linux runner.

Requires supporting chattr +i filesystem and root-owned /srv/wfs-runner. This
is intentionally NOT callable via the WFS dashboard/worker/API.
"""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT=Path('/srv/wfs-runner')


def validate_snapshot(archive:Path, project_id:str, attempt_id:str, expected_sha256:str):
    if not re.fullmatch('[a-f0-9]{20}',project_id) or not re.fullmatch('[a-f0-9]{32}',attempt_id):
        raise ValueError('Invalid project/attempt identity')
    if not re.fullmatch('[a-f0-9]{64}',expected_sha256):raise ValueError('Expected independent SHA-256 missing')
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_size>8_000_000:
        raise ValueError('Invalid archive')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Archive digest mismatch')
    with tarfile.open(archive,'r:gz') as tar:
        entries=tar.getmembers()
        if len(entries)>111 or sum(e.size for e in entries)>5_000_000:
            raise ValueError('Snapshot exceeds size limits')
        names=[e.name for e in entries]
        if len(names)!=len(set(names)) or 'MANIFEST.json' not in names:
            raise ValueError('Duplicate/missing archive entries')
        if not all(e.isfile() and not e.issym() and not e.islnk() for e in entries):
            raise ValueError('Nonregular member denied')
        for name in names:
            p=PurePosixPath(name)
            if name.startswith('/') or '\\' in name or p.as_posix()!=name or any(part in ('..','.','') for part in name.split('/')):
                raise ValueError('Unsafe archive path')
            if name!='MANIFEST.json' and (len(p.parts)<2 or p.parts[0] not in ('project','trusted')):
                raise ValueError('Unapproved archive prefix')
        manifest=json.load(tar.extractfile('MANIFEST.json'))
        if manifest.get('format')!='wfs-sealed-snapshot-v29' or manifest.get('project_id')!=project_id or manifest.get('attempt_id')!=attempt_id:
            raise ValueError('Snapshot attempt identity mismatch')
        checks=manifest.get('files')
        if not isinstance(checks,dict) or set(checks)!=set(names)-{'MANIFEST.json'}:
            raise ValueError('Manifest contents mismatch')
        if {k for k in checks if k.startswith('trusted/')}!={'trusted/qa_probe.py','trusted/qa-node.js'}:
            raise ValueError('Unexpected trusted probes')
        payload={}
        for entry in entries:
            if entry.name=='MANIFEST.json':continue
            blob=tar.extractfile(entry).read()
            if not isinstance(checks[entry.name],str) or hashlib.sha256(blob).hexdigest()!=checks[entry.name]:
                raise ValueError('Entry hash mismatch')
            payload[entry.name]=blob
        return payload


def _seal(folder:Path):
    for path in sorted(folder.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if path.is_symlink():raise ValueError('Symlink not allowed')
        path.chmod(0o555 if path.is_dir() else 0o444)
        subprocess.run(['chattr','+i',str(path)],check=True,capture_output=True)
    folder.chmod(0o555)
    subprocess.run(['chattr','+i',str(folder)],check=True,capture_output=True)


@contextlib.contextmanager
def operator_admission_lock():
    """Serialize imports with v3.5 operator GC; honor the pause marker."""
    root=ROOT
    if not root.is_dir() or root.is_symlink() or root.stat().st_uid!=0 or root.stat().st_mode&0o022:
        raise ValueError('Runner root is untrusted')
    lock=root/'.operator-maintenance.lock'
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077:
            raise ValueError('Unsafe operator maintenance lock')
        fcntl.flock(fd,fcntl.LOCK_EX)
        # GC requires manual maintenance window and denies new imports.
        if (root/'.admissions-paused').exists() or (root/'.admissions-paused').is_symlink():
            raise ValueError('Runner admissions are paused for operator maintenance')
        yield
    finally:
        os.close(fd)


def admit(archive:Path,project_id:str,attempt_id:str,expected_sha256:str):
    if os.name!='posix' or os.geteuid()!=0:raise ValueError('Root-owned offline staging required')
    payload=validate_snapshot(archive,project_id,attempt_id,expected_sha256)
    with operator_admission_lock():
        return _admit_locked(payload,project_id,attempt_id)


def _admit_locked(payload:dict,project_id:str,attempt_id:str):
    root=ROOT;stage=root/'staging';trusted=root/'trusted';namespace=stage/project_id
    for d in (root,stage,trusted):
        if not d.is_dir() or d.is_symlink() or d.stat().st_uid!=0 or d.stat().st_mode&0o022:
            raise ValueError('Untrusted staging root permissions')
    namespace.mkdir(mode=0o755,exist_ok=True)
    if namespace.is_symlink() or namespace.stat().st_uid!=0 or namespace.stat().st_mode&0o022:
        raise ValueError('Untrusted project namespace')
    target=namespace/attempt_id
    if target.exists() or target.is_symlink():raise ValueError('Attempt already admitted')
    with tempfile.TemporaryDirectory(prefix='.wfs-v29-',dir=str(namespace)) as d:
        tmp=Path(d);src=tmp/'project';src.mkdir()
        for name,data in payload.items():
            if name.startswith('project/'):
                p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(data)
        approved=trusted/'v28'
        expected={k.split('/')[1]:v for k,v in payload.items() if k.startswith('trusted/')}
        # Versioned trusted probes must have been separately installed and sealed
        # by a root administrator. The project snapshot can NEVER publish probes.
        if not approved.is_dir() or approved.is_symlink() or {
            f.name:f.read_bytes() for f in approved.iterdir() if f.is_file() and not f.is_symlink()
        }!=expected:
            raise ValueError('Trusted probes not pre-admitted or mismatch')
        _seal(src)
        os.rename(src,target)
    return str(target)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('archive',type=Path)
    p.add_argument('--project-id',required=True)
    p.add_argument('--attempt-id',required=True)
    p.add_argument('--expected-sha256',required=True)
    a=p.parse_args()
    try:print(admit(a.archive,a.project_id,a.attempt_id,a.expected_sha256))
    except (OSError,ValueError,tarfile.TarError,subprocess.CalledProcessError) as exc:p.error(str(exc))
