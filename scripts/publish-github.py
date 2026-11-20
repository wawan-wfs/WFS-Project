"""Operator-only GitHub PR publisher. Never called by API or autonomous agent.

Uses user's existing local git/gh authentication; no secrets are exposed to WFS workers.
Default is dry-run. Actual remote changes require --publish and typed confirmation.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data/wfs.sqlite3'


def checked_files(project_id):
    if not re.fullmatch('[a-f0-9]{20}',project_id):raise ValueError('Project ID invalid')
    with closing(sqlite3.connect(DB)) as db:
        row=db.execute('SELECT status,title FROM projects WHERE id=?',(project_id,)).fetchone()
        if not row or row[0]!='completed':raise ValueError('Only completed projects may be published')
        manifest=db.execute('SELECT name,bytes,sha256 FROM artifacts WHERE project_id=?',(project_id,)).fetchall()
    if not manifest:raise ValueError('No delivered artifacts')
    project=ROOT/'data/projects'/project_id
    if project.is_symlink():raise ValueError('Unsafe project path')
    files=[]
    for rel,size,digest in manifest:
        name=Path(rel)
        source=project/name
        if name.is_absolute() or '..' in name.parts or not source.is_file() or source.is_symlink():
            raise ValueError('Unsafe artifact: '+rel)
        if any(p.is_symlink() for p in source.parents if p != project.parent):
            raise ValueError('Symlink path: '+rel)
        blob=source.read_bytes()
        if len(blob)!=size or hashlib.sha256(blob).hexdigest()!=digest:
            raise ValueError('Artifact modified since delivery: '+rel)
        files.append((rel,source))
    return row[1],files


def run(args,cwd=None):
    proc=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if proc.returncode:raise RuntimeError('Command failed: '+args[0]+' '+args[1]+' ('+proc.stderr[-300:]+')')
    return proc.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description='Prepare or publish WFS project to a GitHub PR (explicit opt-in).')
    parser.add_argument('project_id')
    parser.add_argument('--repo',required=True,help='owner/repo')
    parser.add_argument('--publish',action='store_true',help='Push new branch and open DRAFT PR')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}/[A-Za-z0-9_.-]{1,100}',args.repo):
        parser.error('--repo must be owner/repo')
    title,files=checked_files(args.project_id)
    destination=f'wfs-deliveries/{args.project_id}'
    print(json.dumps({'project':title,'project_id':args.project_id,'repo':args.repo,
         'destination':destination,'files':[rel for rel,_ in files],
         'mode':'publish' if args.publish else 'dry_run'},ensure_ascii=False,indent=2))
    if not args.publish:
        print('DRY-RUN ONLY. Nothing was pushed. Add --publish for manual approval and a draft PR.')
        return 0
    if not shutil.which('gh') or not shutil.which('git'):
        raise RuntimeError('Git and GitHub CLI (gh) must be installed and authenticated on Windows')
    print('GitHub account:',run(['gh','api','user','--jq','.login']))
    repo=run(['gh','repo','view',args.repo,'--json','nameWithOwner','--jq','.nameWithOwner'])
    if repo.lower()!=args.repo.lower():raise RuntimeError('GitHub repository mismatch')
    confirm=input(f'Type exactly PUBLISH {args.repo} to push a NEW branch and create a DRAFT PR: ').strip()
    if confirm!=f'PUBLISH {args.repo}':raise RuntimeError('Cancelled by operator')
    branch=f'wfs/{args.project_id}-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
    with tempfile.TemporaryDirectory(prefix='wfs-gh-export-') as tmp:
        target=Path(tmp)/'repository'
        run(['gh','repo','clone',args.repo,str(target),'--','--depth','1'])
        if not run(['git','-C',str(target),'config','user.name']):raise RuntimeError('Set local git user.name first')
        if not run(['git','-C',str(target),'config','user.email']):raise RuntimeError('Set local git user.email first')
        if (target/destination).exists():raise RuntimeError('Destination exists; do not overwrite prior release')
        run(['git','-C',str(target),'switch','-c',branch])
        for relative,source in files:
            dest=target/destination/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
        run(['git','-C',str(target),'add','--',destination])
        run(['git','-C',str(target),'commit','-m',f'feat: deliver WFS PROJECT {args.project_id}'])
        run(['git','-C',str(target),'push','--set-upstream','origin',branch])
        url=run(['gh','pr','create','--repo',args.repo,'--head',branch,'--draft',
                 '--title',f'WFS delivery: {title[:70]}','--body',
                 f'AI-generated source from WFS PROJECT. Review all files, execute QA in CI, and audit secrets/security before merge.\n\nProject: `{args.project_id}`.'])
        print('Draft PR created:',url)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,ValueError,sqlite3.Error,subprocess.TimeoutExpired) as err:
        print('Publish failed:',err,file=sys.stderr);sys.exit(2)
