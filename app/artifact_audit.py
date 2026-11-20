"""Read-only crash-boundary audit for delivery folders and SQLite manifests.

Never deletes, repairs, or exposes source contents. Operators must inspect
suspect folders and restore from a matching backup before resuming a worker.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from . import store,validation


def audit():
    issues=[]
    project_root=store.PROJECTS
    with store.connect() as cx:
        rows=cx.execute('SELECT id,status,worker_id FROM projects ORDER BY id').fetchall()
        manifests={r['id']:cx.execute(
            'SELECT name,bytes,sha256 FROM artifacts WHERE project_id=? ORDER BY name',(r['id'],)
        ).fetchall() for r in rows}
    ids={r['id'] for r in rows}
    if project_root.exists():
        for path in sorted(project_root.iterdir()):
            if path.is_symlink():
                issues.append({'code':'UNSAFE_SYMLINK','entry':path.name})
            elif path.name.startswith(('.wfs-stage-','.wfs-previous-')):
                issues.append({'code':'UNRESOLVED_STAGING_OR_BACKUP','entry':path.name})
            elif path.name not in ids and path.is_dir():
                issues.append({'code':'UNOWNED_DELIVERY_DIRECTORY','entry':path.name})
    for project in rows:
        pid=project['id'];root=project_root/pid
        manifest=manifests[pid]
        if not manifest:
            if root.exists():
                issues.append({'code':'DELIVERY_WITHOUT_MANIFEST','project_id':pid})
            continue
        if root.is_symlink() or not root.is_dir():
            issues.append({'code':'MANIFEST_WITHOUT_SAFE_DELIVERY','project_id':pid})
            continue
        listed=set()
        for file in manifest:
            name=file['name']
            try: clean=validation.clean_path(name)
            except ValueError:
                issues.append({'code':'INVALID_MANIFEST_PATH','project_id':pid});continue
            listed.add(clean)
            target=root/clean
            if any(p.is_symlink() for p in [target,*target.parents] if p!=root.parent and p!=project_root):
                issues.append({'code':'UNSAFE_DELIVERY_FILE','project_id':pid,'name':clean});continue
            if not target.is_file():
                issues.append({'code':'MISSING_MANIFEST_FILE','project_id':pid,'name':clean});continue
            # Streaming digest keeps memory bounded for large outputs.
            digest=hashlib.sha256();size=0
            with target.open('rb') as handle:
                for data in iter(lambda:handle.read(1024*1024),b''):
                    digest.update(data);size+=len(data)
            if size!=file['bytes'] or digest.hexdigest()!=file['sha256']:
                issues.append({'code':'DIGEST_MISMATCH','project_id':pid,'name':clean})
        for f in root.rglob('*'):
            if f.is_symlink():
                issues.append({'code':'UNSAFE_DELIVERY_FILE','project_id':pid,'name':f.relative_to(root).as_posix()})
                continue
            if f.is_file() and f.relative_to(root).as_posix() not in listed:
                issues.append({'code':'UNMANIFESTED_FILE','project_id':pid,'name':f.relative_to(root).as_posix()})
    return {'status':'INVESTIGATE' if issues else 'CLEAN_LOCAL','read_only':True,
            'projects_examined':len(rows),'issues':issues,
            'note':'SQLite/FS are not crash-atomic; CLEAN_LOCAL is not power-loss or host attestation.'}
