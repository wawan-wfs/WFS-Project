"""Explicit local operator workflow. Not started by the API, worker, or AI agents.

Runs one operator-approved queued job. A request in dashboard does NOT execute
anything until the human operator runs this CLI and types its unique approval.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import secrets
import time
from urllib.parse import quote
import socket
import shutil
import threading
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import store
# Original operator QA filename contains a hyphen and cannot be imported normally.
qa_spec=importlib.util.spec_from_file_location('wfs_sandbox_qa',ROOT/'scripts/sandbox-qa.py')
qa_module=importlib.util.module_from_spec(qa_spec)
qa_spec.loader.exec_module(qa_module)
check_project=qa_module.check_project

NETWORK='wfs-preview-internal'
IMAGE='wfs-project-qa-python:1.2'
STACK_IMAGE='wfs-project-preview-postgres:1.9'
POSTGRES_IMAGE='postgres:16-alpine'


def docker(args,timeout=30):
    p=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError('Docker error: '+p.stderr[-600:])
    return p.stdout.strip()


def preview_name(pid):return 'wfs-preview-'+pid


def preview_start(pid):
    root,stack=check_project(pid)
    if stack not in ('fastapi','node-web'):raise RuntimeError('FastAPI or Node Web project required')
    # Only known entrypoints. Never import/execute generated code on host.
    if stack=='fastapi':
        choices=[('app.main','app/main.py'),('main','main.py'),('src.main','src/main.py'),('server','server.py'),('api.main','api/main.py')]
        entry=next((module for module,path in choices if (root/path).is_file()),None)
        if entry is None:raise RuntimeError('No recognized FastAPI entrypoint')
    else:
        if not (root/'server.js').is_file():raise RuntimeError('Node Web requires server.js')
        # Built-in Node.js APIs only: never npm install inside the runtime preview.
        from app import artifacts
        import json
        files=artifacts.source_files(pid)
        package=json.loads(files.get('package.json','{}'))
        if package.get('dependencies') or package.get('devDependencies'):
            raise RuntimeError('Node Web preview refuses external npm dependencies')
    existing=docker(['ps','-aq','--filter','name=^/'+preview_name(pid)+'$'])
    if existing:raise RuntimeError('Preview already exists; stop it first')
    networks=docker(['network','ls','--format','{{.Name}}']).splitlines()
    if NETWORK not in networks:docker(['network','create','--internal','--driver','bridge',NETWORK])
    # FastAPI uses a trusted fixed-dependency image. Node Web uses its trusted runtime image.
    if stack=='fastapi':
        docker(['build','-f',str(ROOT/'docker/qa-python.Dockerfile'),'-t',IMAGE,str(ROOT)],timeout=240)
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    name=preview_name(pid)
    cmd=['run','--detach','--rm','--name',name,'--network',NETWORK,
         '-p',f'127.0.0.1:{port}:8000','--read-only','--init','--cap-drop','ALL',
         '--security-opt','no-new-privileges','--pids-limit','64','--memory','512m',
         '--cpus','1','--user','10001:10001','--tmpfs','/tmp:rw,nosuid,noexec,size=32m',
         '--mount',f'type=bind,source={root},target=/workspace,readonly']
    if stack=='fastapi':
        cmd += ['--mount',f'type=bind,source={ROOT/"scripts/serve_preview.py"},target=/trusted/serve_preview.py,readonly',
                '--workdir','/workspace',IMAGE,'python','-B','/trusted/serve_preview.py',entry,'--minutes','15']
    else:
        cmd += ['--env','PORT=8000','--env','HOST=0.0.0.0',
                '--mount',f'type=bind,source={ROOT/"scripts/serve_node_preview.cjs"},target=/trusted/serve_node_preview.cjs,readonly',
                '--workdir','/workspace','node:22-alpine','node','/trusted/serve_node_preview.cjs']
    container=docker(cmd,timeout=45)
    return {'container_id':container[:12], 'stack':stack,'url':f'http://127.0.0.1:{port}/',
            'note':'Local isolated preview (15 min max), WITHOUT login. Only open trusted local source. Not internet-safe.'}


def preview_stop(pid):
    name=preview_name(pid)
    current=docker(['ps','-aq','--filter','name=^/'+name+'$'])
    if current:docker(['rm','-f',name],timeout=30)
    return {'stopped':True}



def stack_resource_names(pid):
    if not re.fullmatch(r'[a-f0-9]{20}',pid):raise ValueError('Invalid project ID')
    return {'db':'wfs-preview-db-'+pid,'backend':'wfs-preview-'+pid,
            'network':'wfs-preview-stack-'+pid,'volume':'wfs-preview-pgdata-'+pid,'gateway':'wfs-preview-web-'+pid}


def docker_exists(name):
    return bool(docker(['ps','-aq','--filter','name=^/'+name+'$']))


def preview_stack_stop(pid):
    """Idempotent host-approved removal of both containers, network and ephemeral volume."""
    names=stack_resource_names(pid)
    removed=[]
    for kind in ('gateway','backend','db'):
        if docker_exists(names[kind]):
            docker(['rm','-f',names[kind]],timeout=30);removed.append(kind)
    # A Docker network delete fails closed if another container is still attached.
    if names['network'] in docker(['network','ls','--format','{{.Name}}']).splitlines():
        docker(['network','rm',names['network']],timeout=30);removed.append('network')
    if names['volume'] in docker(['volume','ls','--format','{{.Name}}']).splitlines():
        docker(['volume','rm',names['volume']],timeout=30);removed.append('volume')
    return {'stopped':True,'removed':removed,'note':'Preview database volume deleted. User project source is untouched.'}


def preview_stack_start(pid):
    """Allow-listed two-service preview: delivered FastAPI + ephemeral PostgreSQL.

    Never execute generated Dockerfiles, compose files, shell commands or requirements.
    No Docker daemon socket or provider secrets enter either preview container.
    """
    root,stack=check_project(pid)
    if stack!='fastapi':raise RuntimeError('Multi-service PostgreSQL preview supports only FastAPI deliveries')
    choices=[('app.main','app/main.py'),('main','main.py'),('src.main','src/main.py'),('server','server.py'),('api.main','api/main.py')]
    entry=next((module for module,path in choices if (root/path).is_file()),None)
    if entry is None:raise RuntimeError('No recognized FastAPI entrypoint')
    names=stack_resource_names(pid)
    if docker_exists(names['db']) or docker_exists(names['backend']):
        raise RuntimeError('Preview exists; stop it explicitly before starting another')
    # Build a fixed trusted dependency image, not generated project requirements.
    docker(['build','-f',str(ROOT/'docker/preview-stack-fastapi.Dockerfile'),'-t',STACK_IMAGE,str(ROOT)],timeout=300)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    password=secrets.token_urlsafe(24)
    ttl=int(time.time())+900
    # These resources are operator-owned and restricted to this single project.
    try:
        docker(['network','create','--internal','--driver','bridge',names['network']],timeout=30)
        docker(['volume','create',names['volume']],timeout=30)
        docker(['run','--detach','--rm','--name',names['db'],'--network',names['network'],
                '--label','wfs.preview=postgres','--label',f'wfs.expire_at={ttl}',
                '--memory','384m','--cpus','1','--pids-limit','128',
                '--security-opt','no-new-privileges',
                '--env','POSTGRES_USER=wfs','--env','POSTGRES_DB=wfs','--env','POSTGRES_PASSWORD='+password,
                '--mount',f'type=volume,source={names["volume"]},target=/var/lib/postgresql/data',
                POSTGRES_IMAGE],timeout=60)
        # Readiness checks use the PostgreSQL CLI inside the container, not AI output.
        ready=False
        for _ in range(40):
            result=subprocess.run(['docker','exec',names['db'],'pg_isready','-U','wfs','-d','wfs'],
                                  capture_output=True,text=True,timeout=5)
            if result.returncode==0:ready=True;break
            time.sleep(.5)
        if not ready:raise RuntimeError('Ephemeral PostgreSQL failed its readiness check')
        # Host port bound only to 127.0.0.1; PostgreSQL never publishes host ports.
        pg_native='postgresql://wfs:'+quote(password,safe='')+'@'+names['db']+':5432/wfs'
        url='postgresql+psycopg://wfs:'+quote(password,safe='')+'@'+names['db']+':5432/wfs'
        command=['run','--detach','--rm','--name',names['backend'],'--network',names['network'],
                 '--label','wfs.preview=postgres','--label',f'wfs.expire_at={ttl}',
                 '-p',f'127.0.0.1:{port}:8000','--read-only','--init','--cap-drop','ALL',
                 '--security-opt','no-new-privileges','--pids-limit','64','--memory','512m','--cpus','1',
                 '--user','10001:10001','--tmpfs','/tmp:rw,nosuid,noexec,size=32m',
                 '--env','DATABASE_URL='+url,'--env','POSTGRES_URL='+pg_native,'--env','PORT=8000',
                 '--mount',f'type=bind,source={root},target=/workspace,readonly',
                 '--mount',f'type=bind,source={ROOT/"scripts/serve_preview.py"},target=/trusted/serve_preview.py,readonly',
                 '--workdir','/workspace',STACK_IMAGE,
                 'python','-B','/trusted/serve_preview.py',entry,'--minutes','15']
        container=docker(command,timeout=50)
        # Confirm the backend is actually listening, not merely that Docker accepted run.
        healthy=False
        for _ in range(30):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.5):
                    healthy=True
                    break
            except (OSError,TimeoutError):
                time.sleep(.5)
        if not healthy:raise RuntimeError('FastAPI preview container did not become reachable on loopback')
    except Exception:
        # Do not leave database or password-bearing containers behind on partial start.
        try:preview_stack_stop(pid)
        except Exception:pass
        raise
    return {'container_id':container[:12],'stack':'fastapi+postgresql',
            'url':f'http://127.0.0.1:{port}/','expires_in_minutes':15,'tcp_ready':True,
            'note':'Private ephemeral PostgreSQL and FastAPI. Local only; stop job removes database volume. Database may remain after FastAPI TTL until explicit cleanup.'}


def preview_trio_frontend(root):
    """Frontend must be a delivered prebuilt static tree, not a source build."""
    # An application might deliver a React build or plain HTML in a frontend dir.
    for rel in ('frontend/dist','web/dist','frontend','web','dist','public'):
        candidate=root/rel
        if candidate.is_dir() and not candidate.is_symlink() and (candidate/'index.html').is_file():
            if any(part.is_symlink() for part in candidate.parents if part!=root.parent):
                continue
            return candidate
    raise RuntimeError('Three-service preview requires prebuilt frontend/index.html or frontend/dist/index.html (web/dist, web, dist, public also supported)')


def preview_trio_start(pid):
    """Operator-confirmed frontend + FastAPI + ephemeral PostgreSQL; no AI Docker access."""
    root,stack=check_project(pid)
    if stack!='fastapi':raise RuntimeError('FastAPI project required')
    frontend=preview_trio_frontend(root)
    names=stack_resource_names(pid)
    if docker_exists(names['gateway']):raise RuntimeError('Gateway already running; stop preview first')
    # Reuse v1.9 validated backend and DB, with rollback on gateway failure.
    backend=preview_stack_start(pid)
    ttl=int(time.time())+900
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        args=['run','--detach','--rm','--name',names['gateway'],'--network',names['network'],
            '--label','wfs.preview=postgres','--label',f'wfs.expire_at={ttl}',
            '-p',f'127.0.0.1:{port}:8000','--read-only','--init','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','0.5',
            '--user','10001:10001','--tmpfs','/tmp:rw,nosuid,noexec,size=16m',
            '--env',f'WFS_BACKEND=http://{names["backend"]}:8000',
            '--mount',f'type=bind,source={frontend},target=/workspace,readonly',
            '--mount',f'type=bind,source={ROOT/"scripts/serve_fullstack_gateway.py"},target=/trusted/gateway.py,readonly',
            '--workdir','/workspace','python:3.12-alpine','python','-B','/trusted/gateway.py']
        container=docker(args,timeout=60)
        ready=False
        for _ in range(20):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.5):
                    ready=True;break
            except (OSError,TimeoutError):time.sleep(.5)
        if not ready:raise RuntimeError('Frontend gateway was not reachable')
        return {'container_id':container[:12],'stack':'static+fastapi+postgresql',
                'frontend_url':f'http://127.0.0.1:{port}/','url':f'http://127.0.0.1:{port}/',
                'backend_url':backend['url'],'expires_in_minutes':15,
                'note':'Trusted gateway proxies /api to FastAPI and serves prebuilt frontend assets. Local only; clean up explicitly.'}
    except Exception:
        preview_stack_stop(pid)
        raise


def cleanup_expired_previews():
    """Host operator manually invokes this, or schedules it in Windows Task Scheduler."""
    containers=docker(['ps','-a','--filter','label=wfs.preview=postgres','--format','{{.Names}}']).splitlines()
    cleaned=[];now_ts=int(time.time())
    ids=set()
    for name in containers:
        m=re.fullmatch(r'wfs-preview-(?:db-|web-)?([a-f0-9]{20})',name)
        if m:ids.add(m.group(1))
    for pid in sorted(ids):
        names=stack_resource_names(pid)
        # Check both containers' metadata before removing resources.
        stamps=[]
        for key in ('db','backend','gateway'):
            if docker_exists(names[key]):
                value=docker(['inspect','--format','{{index .Config.Labels "wfs.expire_at"}}',names[key]])
                if value.isdigit():stamps.append(int(value))
        if stamps and max(stamps)<=now_ts:
            preview_stack_stop(pid);cleaned.append(pid)
    return {'expired_removed':cleaned,'active_checked':len(ids)}


def execute(job):
    pid=job['project_id'];kind=job['kind']
    if kind in ('qa-static','qa-fastapi'):
        check_project(pid)
        store.operator_job_step(job['id'],'executing','Running Docker QA in a restricted container')
        cmd=[sys.executable,str(ROOT/'scripts/sandbox-qa.py'),pid]
        if kind=='qa-fastapi':cmd+=['--runtime','--accept-risk']
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=390,cwd=ROOT)
        return (proc.returncode==0, {'exit_code':proc.returncode,'output':(proc.stdout+proc.stderr)[-2500:]})
    if kind=='preview-trio-start':
        store.operator_job_step(job['id'],'executing','Starting frontend gateway + FastAPI + PostgreSQL sandbox')
        return True,preview_trio_start(pid)
    if kind=='preview-trio-stop':
        store.operator_job_step(job['id'],'executing','Stopping three-service preview and deleting ephemeral database')
        return True,preview_stack_stop(pid)
    if kind=='preview-stack-start':
        store.operator_job_step(job['id'],'executing','Starting bounded two-service FastAPI + PostgreSQL sandbox')
        return True,preview_stack_start(pid)
    if kind=='preview-stack-stop':
        store.operator_job_step(job['id'],'executing','Stopping local FastAPI and deleting ephemeral PostgreSQL database')
        return True,preview_stack_stop(pid)
    if kind=='react-build':
        root,stack=check_project(pid)
        if stack!='react-vite':raise RuntimeError('React/Vite project required')
        powershell=shutil.which('powershell.exe') or shutil.which('powershell') or shutil.which('pwsh')
        if not powershell:raise RuntimeError('React preview build currently requires Windows PowerShell')
        store.operator_job_step(job['id'],'building','Running isolated React build with an additional BUILD confirmation')
        proc=subprocess.run([powershell,'-NoProfile','-ExecutionPolicy','Bypass','-File',
                            str(ROOT/'scripts/build-react-preview.ps1'),'-ProjectId',pid],cwd=ROOT,timeout=900)
        return (proc.returncode==0,{'exit_code':proc.returncode,
                'note':'React preview generated. Check the project preview after refreshing the dashboard.'})
    if kind=='preview-start':
        store.operator_job_step(job['id'],'executing','Starting local isolated full-stack preview')
        return True,preview_start(pid)
    if kind=='preview-stop':
        store.operator_job_step(job['id'],'executing','Stopping local isolated preview')
        return True,preview_stop(pid)
    if kind=='github-draft':
        check_project(pid)
        store.operator_job_step(job['id'],'publishing','Preparing GitHub draft PR; separate PUBLISH confirmation required')
        cmd=[sys.executable,str(ROOT/'scripts/publish-github.py'),pid,'--repo',job['options']['repo'],'--publish']
        print('GitHub CLI requires its own typed PUBLISH confirmation. No tokens are passed to AI.')
        proc=subprocess.run(cmd,cwd=ROOT,timeout=400)
        return (proc.returncode==0,{'exit_code':proc.returncode,'note':'See operator terminal for PR URL and detailed result'})
    raise RuntimeError('Unsupported operator job')


def main():
    parser=argparse.ArgumentParser(description='Human-confirmed Docker/GitHub job runner for WFS PROJECT.')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--job',help='Run one pending job ID')
    parser.add_argument('--cleanup-expired',action='store_true',help='Remove operator-owned PostgreSQL previews past their 15-minute expiry')
    args=parser.parse_args()
    store.init_db()
    if args.cleanup_expired:
        print(json.dumps(cleanup_expired_previews(),indent=2));return 0
    jobs=store.list_operator_jobs()
    pending=[j for j in jobs if j['status']=='queued']
    if args.list or not args.job:
        print(json.dumps([{'id':j['id'],'project_id':j['project_id'],'kind':j['kind'],
                           'options':j['options'],'created_at':j['created_at']} for j in pending],indent=2))
        return 0
    job=next((j for j in pending if j['id']==args.job),None)
    if job is None:raise RuntimeError('Job is not queued or not found')
    print(json.dumps({'id':job['id'],'project_id':job['project_id'],
                      'kind':job['kind'],'options':job['options']},indent=2))
    print('WARNING: Docker runtime jobs may execute untrusted generated code. Review source before running.')
    if input('Type RUN '+job['id']+' to proceed: ').strip()!='RUN '+job['id']:
        print('No action taken.');return 1
    claimed=store.claim_operator_job(job['id'])
    if not claimed:raise RuntimeError('Job was claimed by another operator')
    # Heartbeat only. On crash a running job stays ambiguous, never auto-retried.
    halt=threading.Event()
    def keepalive():
        while not halt.wait(15):
            try:
                if not store.operator_job_heartbeat(job['id']):break
            except Exception:
                break
    threading.Thread(target=keepalive,daemon=True).start()
    store.operator_job_step(job['id'],'preflight','Starting isolated operator execution after source review')
    try:
        succeeded,result=execute(claimed)
        status='completed' if succeeded else 'failed'
    except Exception as e:
        status='failed';result={'error':(type(e).__name__+': '+str(e))[:900]}
    halt.set()
    store.finish_operator_job(job['id'],status,result)
    print(json.dumps({'status':status,'result':result},indent=2))
    return 0 if status=='completed' else 2


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,ValueError,subprocess.TimeoutExpired) as exc:
        print('Operator job failed:',str(exc),file=sys.stderr);sys.exit(2)
