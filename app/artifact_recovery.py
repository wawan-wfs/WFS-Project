"""Read-only exact-match check of one offline delivery against a WFS SQLite snapshot."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from . import validation

PROJECT_ID = re.compile(r'[a-f0-9]{20}')


MAX_DELIVERED_PROJECTS = 1000
INVENTORY_SCHEMA = 'wfs-delivery-fingerprints-v1'


def _is_link(path):
    return path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction())


def _plain_path(path, *, directory=False):
    path=Path(path).absolute()
    if not (path.is_dir() if directory else path.is_file()) or any(_is_link(p) for p in (path,*path.parents)):
        raise ValueError('Expected existing plain file or directory, without symbolic parents')
    return path


def _rows(cx, project_id):
    return cx.execute('SELECT name,bytes,sha256 FROM artifacts WHERE project_id=? ORDER BY name LIMIT ?',
                      (project_id,validation.MAX_PROJECT_FILES+1)).fetchall()


def verify_generation(database, project_id, candidate):
    """Never restore or execute candidate content. Use offline snapshots only."""
    if not isinstance(project_id,str) or not PROJECT_ID.fullmatch(project_id):
        raise ValueError('Invalid project identifier')
    db=_plain_path(database)
    root=_plain_path(candidate,directory=True)
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=2)) as cx:
        cx.execute('BEGIN')
        state=cx.execute('SELECT status FROM projects WHERE id=?',(project_id,)).fetchone()
        return _verify(project_id,root,state,_rows(cx,project_id))


def validate_delivery_inventory(inventory):
    if (not isinstance(inventory,dict) or set(inventory)!={'schema','projects'}
            or inventory['schema']!=INVENTORY_SCHEMA):
        raise ValueError('Unsupported delivery inventory format')
    projects=inventory['projects']
    if (not isinstance(projects,dict) or not 1<=len(projects)<=MAX_DELIVERED_PROJECTS
            or any(not isinstance(pid,str) or not PROJECT_ID.fullmatch(pid)
                   or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest)
                   for pid,digest in projects.items())):
        raise ValueError('Invalid delivery inventory')
    return projects


def verify_delivered_clone(clone, *, expected_projects=(), exact_inventory=False,
                           expected_inventory=None, include_inventory=False):
    """Check every completed or review-required manifest in one stopped clone."""
    fingerprints=None
    if expected_inventory is not None:
        if expected_projects or exact_inventory or include_inventory:
            raise ValueError('Delivery inventory cannot be combined with other inventory options')
        fingerprints=validate_delivery_inventory(expected_inventory)
        expected_projects=list(fingerprints)
        exact_inventory=True
    if (not isinstance(expected_projects,(list,tuple)) or len(expected_projects)>MAX_DELIVERED_PROJECTS
            or any(not isinstance(p,str) or not PROJECT_ID.fullmatch(p) for p in expected_projects)):
        raise ValueError('Invalid expected project inventory')
    expected=set(expected_projects)
    if type(exact_inventory) is not bool or (exact_inventory and (not expected or len(expected)!=len(expected_projects))):
        raise ValueError('Exact inventory requires unique expected project IDs')
    root=_plain_path(clone,directory=True)
    db=_plain_path(root/'data'/'wfs.sqlite3')
    projects=_plain_path(root/'data'/'projects',directory=True)
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=2)) as cx:
        cx.execute('BEGIN')
        checks=cx.execute('PRAGMA quick_check(1)').fetchall()
        if checks!=[('ok',)]:
            return {'status':'DATABASE_CHECK_FAILED','checked':0,'results':[]}
        records=cx.execute("""SELECT id,status FROM projects WHERE status IN ('completed','review_required')
                            ORDER BY id LIMIT ?""",(MAX_DELIVERED_PROJECTS+1,)).fetchall()
        if len(records)>MAX_DELIVERED_PROJECTS:
            return {'status':'PROJECT_SCAN_LIMIT','checked':0,'results':[]}
        if not records and not expected:
            return {'status':'NO_DELIVERED_PROJECTS','checked':0,'results':[]}
        observed={project_id for project_id,_ in records if isinstance(project_id,str)}
        missing=sorted(expected-observed)
        unexpected=sorted(observed-expected) if exact_inventory else []
        reports=[]
        for project_id,status in records:
            if not isinstance(project_id,str) or not PROJECT_ID.fullmatch(project_id):
                report={'status':'INVALID_PROJECT_ID','matches':0,'issues':[]}
            else:
                try:path=_plain_path(projects/project_id,directory=True)
                except ValueError:report={'status':'MISSING_OR_UNSAFE_DIRECTORY','matches':0,'issues':[]}
                else:report=_verify(project_id,path,(status,),_rows(cx,project_id),
                                    include_fingerprint=include_inventory or fingerprints is not None)
                report['project_id']=project_id
            reports.append(report)
    result={'status':'DELIVERED_MATCH' if not missing and not unexpected and all(r['status']=='EXACT_MATCH' for r in reports)
            else 'DELIVERED_MISMATCH','checked':len(reports),'results':reports}
    if expected:
        result['expected_projects']=len(expected)
        result['missing_expected_projects']=missing
    if exact_inventory:
        result['unexpected_delivered_projects']=[p for p in unexpected if PROJECT_ID.fullmatch(p)]
        result['unexpected_delivered_count']=len(unexpected)
    if fingerprints is not None:
        mismatched=sorted(r['project_id'] for r in reports
                          if r.get('project_id') in fingerprints and 'fingerprint' in r
                          and fingerprints[r['project_id']]!=r['fingerprint'])
        result['mismatched_project_fingerprints']=mismatched
        if mismatched:
            result['status']='DELIVERED_MISMATCH'
    if include_inventory and result['status']=='DELIVERED_MATCH':
        result['inventory']={'schema':INVENTORY_SCHEMA,
                             'projects':{r['project_id']:r['fingerprint'] for r in reports}}
    return result


def _verify(project_id, root, state, rows, *, include_fingerprint=False):
    if not state or not rows or len(rows)>validation.MAX_PROJECT_FILES:
        return {'status':'NO_VERIFIABLE_MANIFEST','project_id':project_id,'matches':0,'issues':[]}
    expected={}
    expected_dirs=set()
    total=0
    for name,size,digest in rows:
        try:validation.clean_path(name)
        except ValueError:return {'status':'INVALID_MANIFEST','project_id':project_id,'matches':0,'issues':[]}
        if type(size) is not int or not 0<=size<=240000 or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):
            return {'status':'INVALID_MANIFEST','project_id':project_id,'matches':0,'issues':[]}
        expected[name]=(size,digest)
        total+=size
        expected_dirs.update(x.as_posix() for x in Path(name).parents if x!=Path('.'))
    if total>validation.MAX_PROJECT_BYTES or len({name.casefold() for name in expected})!=len(expected):
        return {'status':'INVALID_MANIFEST','project_id':project_id,'matches':0,'issues':[]}

    issues=[]
    seen=set()
    scanned=0
    matches=0

    def inspect(path):
        nonlocal scanned,matches
        for entry in path.iterdir():
            scanned+=1
            if scanned>validation.MAX_PROJECT_FILES*9+1:
                issues.append({'code':'CANDIDATE_SCAN_LIMIT'})
                return False
            name=entry.relative_to(root).as_posix()
            if _is_link(entry):
                issues.append({'code':'UNSAFE_ENTRY','name':name})
            elif entry.is_dir():
                if name not in expected_dirs:
                    issues.append({'code':'UNEXPECTED_DIRECTORY','name':name})
                elif not inspect(entry):
                    return False
            elif not entry.is_file():
                issues.append({'code':'UNSAFE_ENTRY','name':name})
            elif name not in expected:
                issues.append({'code':'UNEXPECTED_FILE','name':name})
            else:
                seen.add(name)
                size,digest=expected[name]
                with entry.open('rb') as stream:
                    content=stream.read(size+1)
                if len(content)!=size or hashlib.sha256(content).hexdigest()!=digest:
                    issues.append({'code':'DIGEST_MISMATCH','name':name})
                else:matches+=1
        return True

    inspect(root)
    issues.extend({'code':'MISSING_FILE','name':name} for name in sorted(expected.keys()-seen))
    report={'status':'EXACT_MATCH' if not issues else 'MISMATCH','project_id':project_id,
            'snapshot_project_status':state[0],'matches':matches,'issues':issues}
    if include_fingerprint and not issues:
        canonical=[INVENTORY_SCHEMA,project_id,state[0],sorted(rows)]
        report['fingerprint']=hashlib.sha256(json.dumps(
            canonical,ensure_ascii=True,separators=(',',':')).encode('ascii')).hexdigest()
    return report
