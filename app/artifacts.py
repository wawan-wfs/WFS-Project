"""Immutable delivery evidence: verify each exported/read file against its DB manifest.

A changed generated file must not be silently served or previewed. Works on Windows/Linux.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from . import config, store, validation

class ArtifactChanged(ValueError):
    pass


def verified(pid: str) -> dict[str, Path]:
    root=config.PROJECTS/pid
    if root.is_symlink() or not root.is_dir():
        raise ArtifactChanged('Folder hasil hilang atau tidak aman')
    output={}
    for item in store.list_artifacts(pid):
        name=validation.clean_path(item['name'])
        target=root/name
        if any(p.is_symlink() for p in [target,*target.parents] if p!=root.parent and p!=config.PROJECTS):
            raise ArtifactChanged(f'Symlink pada artefak: {name}')
        if not target.is_file():
            raise ArtifactChanged(f'File hasil tidak ditemukan: {name}')
        binary=target.read_bytes()
        if len(binary)!=item['bytes'] or hashlib.sha256(binary).hexdigest()!=item['sha256']:
            raise ArtifactChanged(f'Integritas file berubah sejak delivery: {name}')
        output[name]=target
    return output


def source_files(pid: str) -> dict[str, str]:
    output={}
    for name,target in verified(pid).items():
        if name == 'WFS_DELIVERY.md':
            continue
        output[name]=target.read_text(encoding='utf-8')
    return output
