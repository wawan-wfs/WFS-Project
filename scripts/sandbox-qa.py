"""Operator-controlled Docker QA for delivered projects.

Requires Python on host plus Docker Desktop. Does not grant Docker socket to AI.
Run `python scripts/sandbox-qa.py --help` for usage.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runner_policy import validate_image, remote_docker_prefix, check_daemon, inspect_container, remote_staging_path, validate_attempt_path, local_snapshot, staging_check_command, RunnerPolicyError

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'
BASE_IMAGE='python:3.12-slim'
NODE_IMAGE='node:22-alpine'
QA_IMAGE='wfs-project-qa-python:1.2'


def check_project(pid):
    if not re.fullmatch('[a-f0-9]{20}',pid):raise RuntimeError('Project ID harus 20 digit hex')
    root=DATA/'projects'/pid
    if root.is_symlink() or not root.is_dir():raise RuntimeError('Project folder tidak valid')
    with closing(sqlite3.connect(DATA/'wfs.sqlite3')) as cx:
        row=cx.execute('SELECT status,stack FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or row[0] not in ('completed','review_required'):
            raise RuntimeError('Proyek harus selesai di worker terlebih dahulu')
        manifest=cx.execute('SELECT name,bytes,sha256 FROM artifacts WHERE project_id=?',(pid,)).fetchall()
    if not manifest:raise RuntimeError('Tidak ada artefak')
    for name,length,sha in manifest:
        file=root/name
        if not file.is_file() or any(p.is_symlink() for p in (file,*file.parents) if p!=root.parent):
            raise RuntimeError(f'File hilang/symlink: {name}')
        binary=file.read_bytes()
        if len(binary)!=length or hashlib.sha256(binary).hexdigest()!=sha:
            raise RuntimeError(f'Artefak dimodifikasi sesudah delivery: {name}')
    return root,row[1]


def build_command(image,project,script,script_name,args=None, docker_prefix=None):
    name='wfs-qa-'+secrets.token_hex(7)
    return name,[
        *(docker_prefix or ['docker']),'run','--rm','--name',name,'--network','none','--read-only','--init',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64',
        '--memory','512m','--memory-swap','512m','--cpus','1','--user','10001:10001',
        '--tmpfs','/tmp:rw,nosuid,noexec,size=64m',
        '--mount',f'type=bind,source={project},target=/workspace,readonly',
        '--mount',f'type=bind,source={script},target=/trusted/{script_name},readonly',
        '--workdir','/workspace',image,*(['python','-B',f'/trusted/{script_name}'] if script_name.endswith('.py') else ['node',f'/trusted/{script_name}']),*(args or [])
    ]


def _verify_staging(prefix, image, project, probe_root, snapshot):
    """Recheck sealed source just before Docker starts the inspected workload.

    A host administrator can still unseal files. This narrows the interval and
    detects changes; it does NOT provide a daemon-enforced TOCTOU guarantee.
    """
    if not all((image, project, probe_root, snapshot)):
        raise RunnerPolicyError('Strict QA requires immutable staging recheck inputs')
    check = subprocess.run(staging_check_command(prefix, image, project, probe_root, snapshot),
                           capture_output=True, text=True, timeout=90)
    if check.returncode != 0 or check.stdout.strip() != 'REMOTE_STAGING_MATCH_AND_SEALED':
        raise RunnerPolicyError('Immutable remote staging SHA256/flags recheck failed')


def run_check(name,cmd,timeout,docker_prefix=None,strict=False,image=None,
              expected_project=None,expected_probe=None,staging_preflight=None):
    docker = docker_prefix or ['docker']
    container_name = cmd[cmd.index('--name')+1]
    created = False
    cleanup_ok = None
    result = None
    failure = None
    try:
        if strict:
            # Docker create is non-executing. Inspect BEFORE start, then re-check
            # immutable files immediately before executing untrusted input.
            create_cmd = cmd.copy()
            create_cmd[create_cmd.index('run')] = 'create'
            create_cmd.remove('--rm')
            generated = subprocess.run(create_cmd,capture_output=True,text=True,timeout=40)
            if generated.returncode:
                raise RunnerPolicyError('Docker create failed (details withheld)')
            created = True
            inspected = subprocess.run([*docker,'inspect',container_name],capture_output=True,text=True,timeout=20)
            if inspected.returncode:
                raise RunnerPolicyError('Unable to inspect strict QA container')
            inspect_container(json.loads(inspected.stdout)[0],image,expected_project,expected_probe)
            if staging_preflight is None:
                raise RunnerPolicyError('Strict QA cannot start without immediate staging recheck')
            _verify_staging(*staging_preflight)
            result = subprocess.run([*docker,'start','--attach',container_name],
                                    capture_output=True,text=True,timeout=timeout)
        else:
            result = subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    except subprocess.TimeoutExpired:
        failure = ('timeout','Sandbox timeout')
    except (OSError,RunnerPolicyError,ValueError,KeyError,IndexError,json.JSONDecodeError) as exc:
        failure = ('error',str(exc)[:300])
    finally:
        if strict or failure is not None:
            # On timeout, clean up even when Docker create/start state is unknown.
            # A successful workload with an unverified cleanup must NOT pass.
            try:
                removed = subprocess.run([*docker,'rm','-f',container_name],
                                         capture_output=True,text=True,timeout=20)
                absent = subprocess.run([*docker,'inspect',container_name],
                                        capture_output=True,text=True,timeout=20)
                healthy = subprocess.run([*docker,'info','--format','{{.ServerVersion}}'],
                                         capture_output=True,text=True,timeout=20)
                cleanup_ok = (healthy.returncode == 0 and absent.returncode != 0
                              and (removed.returncode == 0 or not created))
            except (OSError,subprocess.TimeoutExpired):
                cleanup_ok = False
    if failure:
        return {'name':name,'status':failure[0],'exit_code':None,'stdout':'',
                'stderr':failure[1], 'cleanup_verified':cleanup_ok}
    if strict and not cleanup_ok:
        return {'name':name,'status':'error','exit_code':None,'stdout':'',
                'stderr':'Strict QA container cleanup not independently verified',
                'cleanup_verified':False}
    return {'name':name,'status':'pass' if result.returncode==0 else 'fail',
            'exit_code':result.returncode,'stdout':result.stdout[-2000:],
            'stderr':result.stderr[-2000:], 'cleanup_verified':cleanup_ok}


def main():
    p=argparse.ArgumentParser(description='Run user-approved, isolated Docker checks and save report in dashboard.')
    p.add_argument('project_id',help='20-hex ID from WFS dashboard')
    p.add_argument('--runtime',action='store_true',help='Explicitly execute generated FastAPI application code in sandbox')
    p.add_argument('--accept-risk',action='store_true',help='Confirm explicit consent to execute untrusted generated code')
    p.add_argument('--timeout',type=int,default=90)
    p.add_argument('--strict-remote',action='store_true',help='Require remote TLS rootless engine and digest-pinned QA images')
    p.add_argument('--attempt-id',default=os.getenv('WFS_RUNNER_ATTEMPT_ID',''),help='Required unique 32-hex QA attempt identifier for strict remote QA')
    p.add_argument('--runner-host',default=os.getenv('WFS_RUNNER_DOCKER_HOST',''))
    p.add_argument('--runner-ca',default=os.getenv('WFS_RUNNER_CA',''))
    p.add_argument('--runner-cert',default=os.getenv('WFS_RUNNER_CERT',''))
    p.add_argument('--runner-key',default=os.getenv('WFS_RUNNER_KEY',''))
    p.add_argument('--remote-project-root',default=os.getenv('WFS_RUNNER_PROJECT_ROOT',''),help='Pre-staged, approved project directory on remote runner host')
    p.add_argument('--remote-probe-root',default=os.getenv('WFS_RUNNER_PROBE_ROOT',''),help='Trusted probes directory on remote runner host')
    args=p.parse_args()
    if args.runtime and not args.accept_risk:
        p.error('Runtime code execution requires --accept-risk; review source before running')
    root,stack=check_project(args.project_id)
    if args.runtime and stack!='fastapi':p.error('--runtime currently supports FastAPI only')
    prefix=['docker']
    if args.strict_remote:
        prefix=remote_docker_prefix(args.runner_host,args.runner_ca,args.runner_cert,args.runner_key)
        remote_project=remote_staging_path(args.remote_project_root)
        remote_probe=remote_staging_path(args.remote_probe_root,trusted=True)
        py_image=validate_image(os.getenv('WFS_QA_PYTHON_DIGEST',''))
        node_image=validate_image(os.getenv('WFS_QA_NODE_DIGEST',''))
        if args.runtime:
            runtime_image=validate_image(os.getenv('WFS_QA_RUNTIME_DIGEST',''))
        probe=subprocess.run([*prefix,'info','--format','{{json .}}'],capture_output=True,text=True,timeout=20)
        if probe.returncode:
            raise RunnerPolicyError('Strict remote runner unavailable: '+probe.stderr[-500:])
        check_daemon(json.loads(probe.stdout))
        validate_attempt_path(remote_project,args.project_id,args.attempt_id)
        snapshot=local_snapshot(root,[ROOT/'scripts/qa_probe.py',ROOT/'scripts/qa-node.js'])
        verified=subprocess.run(staging_check_command(prefix,py_image,remote_project,remote_probe,snapshot),capture_output=True,text=True,timeout=90)
        if verified.returncode or verified.stdout.strip() != 'REMOTE_STAGING_MATCH_AND_SEALED':
            raise RunnerPolicyError('Remote staging project/probe SHA256 differs from local approved files')
    result=subprocess.run([*prefix,'info','--format','{{.ServerVersion}}'],capture_output=True,text=True,timeout=20)
    if result.returncode!=0:raise RuntimeError('Docker Desktop engine tidak tersedia')
    steps=[]
    image=py_image if args.strict_remote else BASE_IMAGE
    if args.runtime and args.strict_remote:
        image=runtime_image
    elif args.runtime:
        # Image contains trusted dependencies, not generated requirements.txt.
        build=subprocess.run(['docker','build','-f',str(ROOT/'docker/qa-python.Dockerfile'),'-t',QA_IMAGE,str(ROOT)],capture_output=True,text=True,timeout=180)
        if build.returncode:raise RuntimeError('QA image build gagal: '+build.stderr[-800:])
        image=QA_IMAGE
    project_mount=remote_project if args.strict_remote else root
    python_probe=(remote_probe+'/qa_probe.py') if args.strict_remote else ROOT/'scripts/qa_probe.py'
    node_probe=(remote_probe+'/qa-node.js') if args.strict_remote else ROOT/'scripts/qa-node.js'
    _,cmd=build_command(image,project_mount,python_probe,'qa_probe.py',['--runtime-fastapi'] if args.runtime else [],docker_prefix=prefix)
    steps.append(run_check('Python AST + JSON'+(' + FastAPI ASGI smoke / pytest' if args.runtime else ''),cmd,min(180,max(20,args.timeout)),prefix,args.strict_remote,image,str(project_mount) if args.strict_remote else None,str(python_probe) if args.strict_remote else None,
        (prefix,py_image,remote_project,remote_probe,snapshot) if args.strict_remote else None))
    node_image=node_image if args.strict_remote else NODE_IMAGE
    _,cmd=build_command(node_image,project_mount,node_probe,'qa-node.js',docker_prefix=prefix)
    steps.append(run_check('Node JS syntax',cmd,min(180,max(20,args.timeout)),prefix,args.strict_remote,node_image,str(project_mount) if args.strict_remote else None,str(node_probe) if args.strict_remote else None,
        (prefix,py_image,remote_project,remote_probe,snapshot) if args.strict_remote else None))
    passed=all(x['status']=='pass' for x in steps)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3)
    report={'project_id':args.project_id,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'stack':stack,'status':'passed' if passed else 'failed','runtime_opt_in':bool(args.runtime),'strict_remote':bool(args.strict_remote),'checks':steps,
            'disclaimer':'Sandbox checks are partial. PASS is not a production security certificate; no public deploy performed.'}
    folder=DATA/'reports'/args.project_id;folder.mkdir(parents=True,exist_ok=True)
    dest=folder/(stamp+'.json');dest.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':report['status'],'report':str(dest),'checks':[{'name':x['name'],'status':x['status']} for x in steps]},ensure_ascii=False,indent=2))
    return 0 if passed else 1

if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,sqlite3.Error,subprocess.TimeoutExpired,ValueError) as exc:
        print('QA error:',exc,file=sys.stderr);sys.exit(2)
