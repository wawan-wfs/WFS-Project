"""Authenticated WFS PROJECT API and UI. The web process cannot execute AI code."""
from __future__ import annotations
import io
import asyncio
import os
import json
import shutil
import re
import time
import secrets
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from . import auth, config, store, mfa, validation, quota, preview_gateway, artifacts as artifact_mod, preview as preview_mod
from .pipeline import DIVISIONS
from .sse_limits import stream_limit, MAX_EVENTS_PER_CONNECTION, LeasedStream
from .sse_admission import AdmissionClient, AdmissionUnavailable, AdmissionUnauthorized

@asynccontextmanager
async def lifespan(app):
    if not config.configured():
        raise RuntimeError('WFS belum dikonfigurasi: jalankan python scripts/bootstrap.py dan restart.')
    store.init_db()
    yield

app=FastAPI(title='WFS PROJECT — AI Software House',version='4.9.0-rc1' ,lifespan=lifespan,
            docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=[x.strip() for x in os.getenv('WFS_ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',') if x.strip()])
app.mount('/static',StaticFiles(directory=str(config.STATIC)),name='static')

@app.middleware('http')
async def security_headers(request:Request,call_next):
    result=await call_next(request)
    if not request.url.path.startswith('/preview/'):
        result.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'"
    result.headers['X-Content-Type-Options']='nosniff'
    result.headers['X-Frame-Options']='DENY' if not request.url.path.startswith('/preview/') else 'SAMEORIGIN'
    result.headers['Referrer-Policy']='no-referrer'
    result.headers['Cache-Control']='no-store'
    result.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    return result

class MetadataUpdate(BaseModel):
    title: str | None = Field(default=None,min_length=3,max_length=120)
    notes: str | None = Field(default=None,max_length=6000)

class RevisionCreate(BaseModel):
    prompt: str = Field(min_length=10,max_length=12000)

class PriorityCommand(BaseModel):
    priority: int = Field(strict=True,ge=0,le=3)

class ArchiveCommand(BaseModel):
    archive: bool = True

class DeleteCommand(BaseModel):
    confirm_id: str

class Login(BaseModel):
    username:str=Field(default='admin',min_length=3,max_length=32,pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$')
    password:str=Field(min_length=1,max_length=256)
    otp:str|None=Field(default=None,max_length=64)

class MFASetup(BaseModel):
    password:str=Field(min_length=1,max_length=256)

class MFAConfirm(BaseModel):
    code:str=Field(min_length=6,max_length=6)

class MFADisable(BaseModel):
    password:str=Field(min_length=1,max_length=256)
    code:str=Field(min_length=6,max_length=64)

class ProjectCreate(BaseModel):
    title:str=Field(min_length=3,max_length=120)
    prompt:str=Field(min_length=10,max_length=20000)
    stack:str=Field(default='static',pattern='^(static|fastapi|react-vite|node-web)$')
    mode:str=Field(default='ai',pattern='^(ai|demo)$')
    task_review_mode:str=Field(default='auto',pattern='^(auto|manual)$')
    visibility:str=Field(default='private',pattern='^(workspace|private)$')


@app.get('/',include_in_schema=False)
def home():return FileResponse(config.STATIC/'index.html')

@app.get('/health')
def health():return {'status':'ok'}

@app.get('/ready')
def ready():
    try:
        with store.connect() as cx:cx.execute('SELECT 1').fetchone()
    except Exception:raise HTTPException(503,'Database tidak siap') from None
    return {'status':'ready'}

@app.post('/api/login')
def login(body:Login,request:Request,response:Response):
    key=request.client.host if request.client else 'unknown'
    if store.login_locked(key):
        raise HTTPException(429,'Terlalu banyak percobaan login; coba lagi dalam 5 menit')
    account=store.user_by_username(body.username)
    password_hash=config.PASSWORD_HASH if account and account['id']=='owner' else (account or {}).get('password_hash','')
    if not account or account['disabled'] or not auth.verify_password(body.password,password_hash):
        store.login_failure(key)
        raise HTTPException(401,'Username atau password tidak valid')
    if account.get('mfa_secret'):
        # Successful password authentication precedes any MFA-specific error.
        if not body.otp:
            raise HTTPException(401,'Kode autentikator atau recovery code diperlukan')
        if not auth.verify_second_factor(account,body.otp):
            store.login_failure(key)
            raise HTTPException(401,'Kode autentikator atau recovery code tidak valid')
    store.login_success(key)
    token=auth.create_session(account['id'],request.headers.get('user-agent','Browser session'))
    response.set_cookie('wfs_session',token,max_age=config.AUTH_TTL_SECONDS,httponly=True,
                        secure=config.COOKIE_SECURE,samesite='strict',path='/')
    return {'authenticated':True,'csrf':auth.csrf_for(token),'expires_in':config.AUTH_TTL_SECONDS,'user':{'username':account['username'],'role':account['role']}}

@app.get('/api/session')
def session(request:Request):
    token=request.cookies.get('wfs_session','')
    if not token or not store.session_valid(token):return {'authenticated':False}
    account=store.session_account(token)
    mfa_enabled=bool(store.mfa_record(account['id'])['mfa_secret'])
    mfa_required=store.organization_mfa_required(account['id'])
    return {'authenticated':True,'csrf':auth.csrf_for(token),
            'user':{k:v for k,v in account.items() if k in ('id','username','role')},
            'mfa_enabled':mfa_enabled,'mfa_required':mfa_required,
            'mfa_setup_required':bool(mfa_required and not mfa_enabled)}

@app.get('/api/sessions')
def account_sessions(token=Depends(auth.current_session)):
    return {'sessions':store.list_account_sessions(_account(token)['id'],token)}

@app.delete('/api/sessions/{session_id}')
def account_session_revoke(session_id:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    if not store.revoke_account_session(_account(token)['id'],session_id):
        raise HTTPException(404,'Session not found')
    return {'revoked':True}

@app.post('/api/sessions/revoke-others')
def account_revoke_other_sessions(request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    n=store.revoke_other_account_sessions(_account(token)['id'],token)
    return {'revoked_count':n}

@app.post('/api/logout')
def logout(request:Request,response:Response,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    store.session_delete(token)
    response.delete_cookie('wfs_session',path='/')
    return {'authenticated':False}

@app.get('/api/mfa/status')
def mfa_status(token=Depends(auth.current_session)):
    user=store.session_account(token)
    return {'enabled':bool(store.mfa_record(user['id'])['mfa_secret']),
            'required_by_organization':store.organization_mfa_required(user['id'])}


@app.post('/api/mfa/setup')
def mfa_setup(body:MFASetup,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    account=store.session_account(token)
    if store.mfa_locked(account['id']):
        raise HTTPException(429,'Too many MFA setup attempts; retry in 5 minutes')
    if not auth.verify_account_password(account,body.password):
        store.mfa_failure(account['id'])
        raise HTTPException(403,'Password verification failed')
    if store.mfa_record(account['id'])['mfa_secret']:
        raise HTTPException(409,'MFA already enabled')
    store.mfa_success(account['id'])
    secret=mfa.new_secret()
    store.mfa_begin(account['id'],token,mfa.seal(secret,account['id']),int(time.time())+600)
    return {'secret':secret,'otpauth_uri':mfa.uri(secret,account['username']),'expires_in':600,
            'notice':'Store this in an authenticator. Secret is shown only during setup.'}


@app.post('/api/mfa/confirm')
def mfa_confirm(body:MFAConfirm,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    user=store.session_account(token)
    encrypted=store.mfa_pending_secret(user['id'],token)
    if not encrypted:raise HTTPException(409,'Setup expired; start again')
    if store.mfa_locked(user['id']):
        raise HTTPException(429,'Too many incorrect MFA codes; retry in 5 minutes')
    matched=mfa.matching_step(mfa.unseal(encrypted,user['id']),body.code)
    if matched is None:
        store.mfa_failure(user['id'])
        raise HTTPException(422,'Invalid code')
    recovery=mfa.recovery_codes()
    if not store.mfa_activate(user['id'],token,encrypted,matched,[mfa.recovery_hash(user['id'],code) for code in recovery]):
        raise HTTPException(409,'Setup expired or already enabled')
    store.mfa_success(user['id'])
    return {'enabled':True,'recovery_codes':recovery,'notice':'Save offline: recovery codes cannot be viewed again.'}


@app.post('/api/mfa/disable')
def mfa_disable(body:MFADisable,request:Request,response:Response,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    account=store.session_account(token)
    if store.organization_mfa_required(account['id']):
        raise HTTPException(409,'Organization policy requires MFA; cannot disable')
    if store.mfa_locked(account['id']):
        raise HTTPException(429,'Too many MFA setup attempts; retry in 5 minutes')
    if not auth.verify_account_password(account,body.password):
        store.mfa_failure(account['id'])
        raise HTTPException(403,'Password verification failed')
    if not store.mfa_record(account['id'])['mfa_secret']:
        raise HTTPException(409,'MFA not enabled')
    if not auth.verify_second_factor(account,body.code):
        raise HTTPException(403,'MFA verification failed')
    store.mfa_disable(account['id'])
    response.delete_cookie('wfs_session',path='/')
    return {'enabled':False,'session_revoked':True}


@app.get('/api/meta')
def meta(token=Depends(auth.current_session)):
    return {'brand':'WFS PROJECT','version':app.version,'mode':'ai' if config.ai_enabled() else 'demo',
           'divisions':[{'name':n,'description':d} for n,d in DIVISIONS],
           'floors':[{'id':1,'name':'Strategy Floor','divisions':['Management','Architecture','Operations']},
                      {'id':2,'name':'Production Floor','divisions':['Engineering','Creative Studio','AI & Data','Documentation']},
                      {'id':3,'name':'Reliability Floor','divisions':['Quality Lab','Infrastructure','Security']}],
           'capabilities':{'real_ai':config.ai_enabled(),'durable_queue':True,'runtime_qa':False,'qa_release_gate':True,
                           'stacks':['static','fastapi','react-vite','node-web'],'auto_deploy':False,'revisions':True,'artifact_integrity':True,'operator_qa_reports':True,'queue_manager':True,'audit_trace':True,'event_cursor':True,'collaboration_board':True,'live_sse':True,'human_task_gate':True,'operator_jobs':True,'github_draft_requests':True,'fastapi_runtime_qa':True,'operator_job_timeline':True,'operator_job_retry':True,'react_build_requests':True,'batch_task_approval':True,'nonblocking_approval':True,'multi_project_parallel':True,'finops_estimates':True,'node_web_preview':True,'postgres_preview_request':True,'project_budgets':True,'finops_csv_export':True,'multiuser_rbac':True,'task_result_resume':True,'frontend_backend_db_preview_request':True,'private_projects':True,'project_memberships':True}}

class UserCreate(BaseModel):
    username:str=Field(min_length=3,max_length=32,pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$')
    password:str=Field(min_length=12,max_length=256)
    role:str=Field(pattern='^(manager|developer|viewer)$')

class UserUpdate(BaseModel):
    role:str|None=Field(default=None,pattern='^(manager|developer|viewer)$')
    disabled:bool|None=None
    new_password:str|None=Field(default=None,min_length=12,max_length=256)

@app.get('/api/users')
def users(request:Request,token=Depends(auth.current_session)):
    auth.require_role(request,'owner')
    return {'users':store.list_users(_account(token)['id']),'audit':store.access_log(scope_user=_account(token)['id'])}

@app.post('/api/users',status_code=201)
def user_create(body:UserCreate,request:Request,token=Depends(auth.current_session)):
    auth.require_role(request,'owner')
    auth.require_csrf(request,token)
    try:
        uid=store.create_user(body.username,auth.hash_password(body.password),body.role,actor_id=_account(token)['id'])
    except __import__('sqlite3').IntegrityError:
        raise HTTPException(409,'Username sudah digunakan') from None
    return {'id':uid,'username':body.username,'role':body.role}

@app.patch('/api/users/{uid}')
def user_update(uid:str,body:UserUpdate,request:Request,token=Depends(auth.current_session)):
    auth.require_role(request,'owner')
    auth.require_csrf(request,token)
    if body.role is None and body.disabled is None and body.new_password is None:raise HTTPException(422,'No changes provided')
    if not store.change_user(uid,body.role,body.disabled,actor_id=_account(token)['id'],password_hash=auth.hash_password(body.new_password) if body.new_password else None):raise HTTPException(404,'User not found or protected')
    return {'updated':True}

def _account(token):
    return store.session_account(token)


def _visible(token):
    return store.visible_project_ids(_account(token)['id'])


def _visible_row(row, visible, key='project_id'):
    return visible is None or row.get(key) in visible


def _verify_visible(pid, token, write=False):
    if not store.can_access_project(pid,_account(token)['id'],write=write):
        raise HTTPException(404,'Proyek tidak ditemukan')


class ProjectMemberCommand(BaseModel):
    user_id:str=Field(min_length=1,max_length=64)
    permission:str=Field(pattern='^(view|edit)$')

class ProjectVisibilityCommand(BaseModel):
    visibility:str=Field(pattern='^(private|workspace)$')


@app.get('/api/team/directory')
def team_directory(token=Depends(auth.current_session)):
    return store.public_user_directory(_account(token)['id'])


@app.get('/api/projects/{pid}/access')
def project_access(pid:str,token=Depends(auth.current_session)):
    access=store.project_access(pid)
    return {**access,'audit':store.project_access_audit(pid)}


def _allow_manage(pid, token):
    p=store.get_project(pid)
    account=_account(token)
    if account['role']!='owner' and p['created_by']!=account['id']:
        raise HTTPException(403,'Only the project creator or Owner can manage access')


@app.patch('/api/projects/{pid}/access')
def update_access(pid:str,body:ProjectVisibilityCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    _allow_manage(pid,token)
    store.manage_project_access(pid,_account(token)['id'],visibility=body.visibility)
    return store.project_access(pid)


@app.post('/api/projects/{pid}/members',status_code=201)
def grant_member(pid:str,body:ProjectMemberCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    _allow_manage(pid,token)
    try:store.manage_project_access(pid,_account(token)['id'],user_id=body.user_id,permission=body.permission)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    return store.project_access(pid)


@app.delete('/api/projects/{pid}/members/{uid}')
def revoke_member(pid:str,uid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    _allow_manage(pid,token)
    try:store.manage_project_access(pid,_account(token)['id'],user_id=uid,remove=True)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    return store.project_access(pid)


@app.get('/api/office')
def office(token=Depends(auth.current_session)):
    return store.scope_office_overview(_visible(token))

@app.get('/api/office/live')
def office_live(floor:int=1,project_id:str|None=None,token=Depends(auth.current_session)):
    if floor not in (1,2,3):raise HTTPException(422,'Floor harus 1, 2, atau 3')
    if project_id is not None:_verify_visible(project_id,token)
    data=store.office_live(floor,project_id,scope_user=_account(token)['id'])
    ids=_visible(token)
    if ids is not None:
        data['agents']=[r for r in data['agents'] if _visible_row(r,ids)]
        data['events']=[r for r in data['events'] if _visible_row(r,ids)]
        data['operator_jobs']=[r for r in data['operator_jobs'] if _visible_row(r,ids)]
        if data['project'] and data['project']['id'] not in ids:data['project']=None
        for division in data['divisions']:
            data['divisions'][division]={k:0 for k in data['divisions'][division]}
        for agent in data['agents']:
            state=agent['state'];counts=data['divisions'].get(agent['division'],{})
            if state in counts:counts[state]+=1
    return data

@app.get('/api/agents/directory')
def agent_directory(token=Depends(auth.current_session)):
    ids=_visible(token)
    return [a for a in store.agent_directory(scope_user=_account(token)['id']) if _visible_row(a,ids)]

@app.get('/api/workspace/activity')
def workspace_activity(token=Depends(auth.current_session)):
    ids=_visible(token)
    return [a for a in store.recent_activity(scope_user=_account(token)['id']) if _visible_row(a,ids)]

@app.get('/api/workspace/artifacts')
def workspace_artifacts(token=Depends(auth.current_session)):
    ids=_visible(token)
    return [a for a in store.artifact_catalog(scope_user=_account(token)['id']) if _visible_row(a,ids)]

@app.get('/api/workspace/capabilities')
def capabilities(token=Depends(auth.current_session)):
    # Do not return secrets, hashes, network credentials or raw environment.
    return {'deployment':'local-multiuser-rbac','real_ai_configured':config.ai_enabled(),
            'model_routing':{'master':os.getenv('WFS_MODEL_MASTER') or config.MODEL,
                  'worker':os.getenv('WFS_MODEL_WORKER') or config.MODEL,
                  'qa':os.getenv('WFS_MODEL_QA') or config.MODEL},
            'limits':{'max_tasks':config.MAX_TASKS,'max_parallel':config.MAX_PARALLEL,'max_active_projects':config.MAX_ACTIVE_PROJECTS,
                 'max_model_calls':config.MAX_CALLS,'max_total_tokens':config.MAX_TOKENS},
            'security':{'csrf':True,'session_login':True,'docker_socket_mounted':False,
                        'public_deployment_supported':False,'rbac':True,'runtime_qa_requires_operator':True}}

@app.get('/api/diagnostics')
def diagnostics(token=Depends(auth.current_session)):
    data=store.diagnostics()
    ids=_visible(token)
    if ids is not None:
        # Idle workers have no tenant/project assignment. Aggregate their
        # availability without revealing identifiers; assigned workers remain
        # restricted to projects the current session can access.
        unassigned=sum(1 for x in data['workers'] if x['current_project'] is None)
        data['workers']=[x for x in data['workers'] if x['current_project'] in ids]
        data['workers_online']=len(data['workers'])+unassigned
        states=store.scope_dashboard_stats(ids)['statuses']
        data['queued']=states.get('queued',0);data['running']=states.get('running',0)
        data['review_required']=states.get('review_required',0);data['paused']=states.get('paused',0)
    return data


class TaskReviewCommand(BaseModel):
    decision:str=Field(pattern='^(approved|blocked)$')
    feedback:str=Field(default='',max_length=1000)
    attempt:int=Field(ge=1)

class OperatorJobCreate(BaseModel):
    kind:str=Field(pattern='^(qa-static|qa-fastapi|github-draft|preview-start|preview-stop|preview-stack-start|preview-stack-stop|preview-trio-start|preview-trio-stop|react-build)$')
    repo:str|None=Field(default=None,max_length=180)

class BatchTaskApproval(BaseModel):
    attempt:int=Field(ge=1)
    feedback:str=Field(default='',max_length=1000)

class OperatorNoteCreate(BaseModel):
    category: str = Field(pattern='^(decision|blocker|review)$')
    message: str = Field(min_length=3,max_length=1500)

@app.get('/api/projects/{pid}/collaboration')
def collaboration(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.collaboration_details(pid)

@app.post('/api/projects/{pid}/notes',status_code=201)
def create_operator_note(pid:str,body:OperatorNoteCreate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    note=store.add_operator_note(pid,body.category,body.message)
    if note is None:raise HTTPException(404,'Proyek tidak ditemukan')
    return note


@app.post('/api/projects/{pid}/tasks/{task_key}/review')
def task_review(pid:str,task_key:str,body:TaskReviewCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not re.fullmatch(r'T[1-9][0-9]{0,2}',task_key):raise HTTPException(422,'Invalid task key')
    if not store.decide_task(pid,task_key,body.decision,body.feedback,body.attempt):
        raise HTTPException(409,'Task cannot be changed: finished, stale attempt, or automatic mode')
    return {'task_key':task_key,'decision':body.decision,'gate':store.task_gate(pid)}

@app.post('/api/projects/{pid}/tasks/approve-pending')
def task_batch_approve(pid:str,body:BatchTaskApproval,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    n=store.approve_pending_tasks(pid,body.attempt,body.feedback)
    if n is None:raise HTTPException(409,'No pending tasks to approve, or stale project attempt')
    return {'approved':n,'gate':store.task_gate(pid)}

@app.get('/api/operator/jobs')
def operator_jobs(project_id:str|None=None,token=Depends(auth.current_session)):
    if project_id is not None:_verify_visible(project_id,token)
    ids=_visible(token)
    return [job for job in store.list_operator_jobs(project_id,scope_user=_account(token)['id']) if _visible_row(job,ids)]

@app.get('/api/operator/jobs/{jid}')
def operator_job_details(jid:str,token=Depends(auth.current_session)):
    if not re.fullmatch(r'[a-f0-9]{24}',jid):raise HTTPException(404,'Job not found')
    item=store.operator_job_detail(jid)
    if item is None:raise HTTPException(404,'Job not found')
    if item['status']=='running':
        from datetime import datetime,timezone
        try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(item['updated_at'])).total_seconds()
        except (TypeError,ValueError):age=0
        item['possibly_stalled']=age>900
    else:item['possibly_stalled']=False
    return item

@app.post('/api/operator/jobs/{jid}/retry',status_code=202)
def operator_job_retry(jid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    if not re.fullmatch(r'[a-f0-9]{24}',jid):raise HTTPException(404,'Job not found')
    new_id=store.retry_operator_job(jid)
    if new_id is None:raise HTTPException(409,'Retry is only available for failed/rejected jobs on delivered projects')
    return {'job_id':new_id,'status':'queued','notice':'Requires separate typed host confirmation; no automatic execution'}

@app.post('/api/operator/jobs/{jid}/cancel')
def operator_job_cancel(jid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    if not re.fullmatch(r'[a-f0-9]{24}',jid):raise HTTPException(404,'Job not found')
    if not store.cancel_operator_job(jid):raise HTTPException(409,'Only queued jobs can be cancelled')
    return {'status':'cancelled'}

@app.post('/api/projects/{pid}/operator-jobs',status_code=202)
def operator_job_create(pid:str,body:OperatorJobCreate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    options={}
    if body.kind=='github-draft':
        if not body.repo or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}/[A-Za-z0-9_.-]{1,100}',body.repo):
            raise HTTPException(422,'GitHub repository must be owner/repo')
        options={'repo':body.repo}
    elif body.repo is not None:
        raise HTTPException(422,'Repository only supported for GitHub jobs')
    try:
        jid=store.create_operator_job(pid,body.kind,options)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    return {'job_id':jid,'status':'queued','notice':'No Docker/GitHub execution occurs until separate host operator approves and runs the job'}

@app.get('/api/live/cursor')
def stream_cursor(token=Depends(auth.current_session)):
    return {'cursor':store.live_event_cursor(_account(token)['id'])}


def encode_sse_event(row:dict)->str:
    # Only SQLite-authenticated event fields are sent; never include credentials/worker IDs.
    return 'id: '+str(row['id'])+'\nevent: wfs-event\ndata: '+json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n\n'

class EventStreamingResponse(StreamingResponse):
    async def __call__(self,scope,receive,send):
        try:
            await super().__call__(scope,receive,send)
        finally:
            await self.body_iterator.aclose()


@app.get('/api/live/events')
async def live_events(request:Request,after_id:int=Query(default=0,ge=0,le=9223372036854775807),
                      project_id:str|None=None,once:bool=False,
                      token=Depends(auth.current_session)):
    if project_id is not None:_verify_visible(project_id,token)
    header=request.headers.get('last-event-id','')
    if header.isdecimal():after_id=max(after_id,min(int(header[:20]),9223372036854775807))
    # Fail with 429 *before* opening an SSE response when this process has
    # reached its bounded stream capacity. Ingress must enforce cluster limits.
    # Auth middleware has already validated the session. Organization is derived
    # from a server-side account, NEVER forwarded Host/X-Org or proxy headers.
    original_account=store.session_account(token)
    authority_path=os.getenv('WFS_SSE_EDGE_SOCKET','').strip()
    require_assertion=os.getenv('WFS_SSE_EDGE_ASSERTIONS')=='1'
    limiter=stream_limit
    try:
        if require_assertion and not authority_path:
            raise AdmissionUnavailable('Assertions require a configured SSE authority')
        if authority_path:
            secret=os.getenv('WFS_SSE_EDGE_SECRET','')
            account=original_account
            if not account or not store.session_valid(token):
                raise HTTPException(401,'Session no longer valid')
            limiter=AdmissionClient(authority_path,secret)
            lease=await limiter.acquire_async(token,account['organization_id'],project=project_id,
                require_assertion=require_assertion)
        else:
            lease=stream_limit.acquire(token)
    except AdmissionUnauthorized:
        raise HTTPException(403,'SSE session or project scope no longer authorized') from None
    except (AdmissionUnavailable,ValueError,OSError):
        # No silent fallback to process-local limits if shared admission is enabled.
        raise HTTPException(503,'Shared SSE admission unavailable',headers={'Retry-After':'5'}) from None
    if lease is None:
        raise HTTPException(429,'Too many active event subscriptions',headers={'Retry-After':'3'})

    cursor=after_id
    sent=0
    start=time.monotonic()
    last_keepalive=start
    async def stream():
        if not original_account or not store.session_valid(token):return
        yield ': wfs-stream-open\nretry: 2500\n\n'
        async for chunk in _bounded_events():
            yield chunk

    async def _bounded_events():
        nonlocal cursor,sent,last_keepalive
        while True:
            if await request.is_disconnected() or not store.session_valid(token):return
            account=store.session_account(token)
            if (not original_account or not account or account['id']!=original_account['id']
                    or account['organization_id']!=original_account['organization_id']):return
            # Policy can change mid-stream; do not keep an old SSE subscription
            # alive after mandatory organization MFA starts to apply.
            if store.organization_mfa_required(account['id']) and not store.mfa_record(account['id'])['mfa_secret']:
                return
            if project_id and not store.can_access_project(project_id,account['id']):return
            records=store.activity_cursor(after_id=cursor,limit=100,project_id=project_id,scope_user=account['id'])['events']
            for row in records:
                # A grant/session can be revoked after the bulk query but before
                # a queued event is emitted. Re-check per event and fail closed.
                # Do not advance the cursor past a denied row or leak its data.
                if not store.session_valid(token):return
                live_account=store.session_account(token)
                if (not live_account or live_account['id']!=account['id']
                        or live_account['organization_id']!=account['organization_id']):return
                if store.organization_mfa_required(live_account['id']):
                    factor=store.mfa_record(live_account['id'])
                    if not factor or not factor['mfa_secret']:return
                if not store.can_access_project(row['project_id'],live_account['id']):
                    # For an explicitly selected project, revoke the stream.
                    # For all-project subscriptions a revoked project can be
                    # skipped while keeping authorized projects live.
                    if project_id:return
                    cursor=row['id']
                    continue
                cursor=row['id']
                yield encode_sse_event(row)
                sent+=1
                # A bounded connection prevents one high-volume subscription
                # from monopolizing a worker. Native EventSource reconnects
                # with the last emitted event ID; no synthetic event is sent.
                if sent>=MAX_EVENTS_PER_CONNECTION:return
            if once:return   # Deterministic authenticated replay for smoke tests and diagnostics.
            current=time.monotonic()
            if current-start>28:return  # Reconnect with Last-Event-ID; keeps proxy connections bounded.
            if current-last_keepalive>=12:
                yield ': heartbeat\n\n'
                last_keepalive=current
            await asyncio.sleep(1.2)
    return EventStreamingResponse(LeasedStream(stream(),limiter,lease),media_type='text/event-stream',headers={
        'Cache-Control':'no-cache, no-store','X-Accel-Buffering':'no','X-Content-Type-Options':'nosniff'})

@app.get('/api/queue')
def queue_manager(token=Depends(auth.current_session)):
    data=store.queue_snapshot(scope_user=_account(token)['id'])
    ids=_visible(token)
    if ids is not None:
        data['queued']=[x for x in data['queued'] if x['id'] in ids]
        data['paused']=[x for x in data['paused'] if x['id'] in ids]
        for i,row in enumerate(data['queued'],1):row['position']=i
    return data

@app.get('/api/workspace/events')
def cursor_events(after_id:int=Query(ge=0,default=0),limit:int=Query(ge=1,le=200,default=50),
                  project_id:str|None=None,token=Depends(auth.current_session)):
    if project_id is not None:_verify_visible(project_id,token)
    return store.activity_cursor(after_id,limit,project_id,scope_user=_account(token)['id'])

@app.get('/api/agents/runs/{run_id}')
def agent_run(run_id:int,token=Depends(auth.current_session)):
    if run_id<1:raise HTTPException(404,'Agent run tidak ditemukan')
    result=store.agent_run_detail(run_id)
    if not result:raise HTTPException(404,'Agent run tidak ditemukan')
    _verify_visible(result['project_id'],token)
    return result

@app.get('/api/projects')
def projects(include_archived:bool=False,token=Depends(auth.current_session)):
    ids=_visible(token)
    return [p for p in store.list_projects(include_archived=include_archived,scope_user=_account(token)['id']) if ids is None or p['id'] in ids]

@app.get('/api/dashboard-stats')
def dashboard_stats(token=Depends(auth.current_session)):
    return store.scope_dashboard_stats(_visible(token))

@app.get('/api/concurrency')
def concurrency(token=Depends(auth.current_session)):
    return store.scope_concurrency(store.concurrency_snapshot(),_visible(token))

@app.get('/api/finops/report')
def finops_report(period:str=Query(default='30d',pattern='^(7d|30d|all)$'),project_id:str|None=None,token=Depends(auth.current_session)):
    if project_id is not None:_verify_visible(project_id,token)
    return store.cost_report(project_id,period,scope_user=_account(token)['id'])

@app.get('/api/finops/prices')
def finops_prices(token=Depends(auth.current_session)):
    return store.get_model_prices(_account(token)['id'])

class ModelPriceUpdate(BaseModel):
    model:str=Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9._:/-]+$')
    input_usd_per_million:float=Field(ge=0,le=10000,allow_inf_nan=False)
    output_usd_per_million:float=Field(ge=0,le=10000,allow_inf_nan=False)

@app.post('/api/finops/prices')
def finops_update_price(body:ModelPriceUpdate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    try:store.set_model_price(body.model,body.input_usd_per_million,body.output_usd_per_million,_account(token)['id'])
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    return {'model':body.model,'saved':True,'note':'Applies only to new usage; existing cost snapshots are unchanged'}

class ProjectBudgetCommand(BaseModel):
    limit_usd:float=Field(ge=0,le=100000,allow_inf_nan=False)
    alert_pct:int=Field(default=80,strict=True,ge=10,le=99)

@app.get('/api/projects/{pid}/budget')
def read_project_budget(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.project_budget(pid)

@app.post('/api/projects/{pid}/budget')
def update_project_budget(pid:str,body:ProjectBudgetCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    try:result=store.set_project_budget(pid,body.limit_usd,body.alert_pct)
    except ValueError as e:raise HTTPException(422,str(e)) from None
    return result

class SpendLimitCommand(BaseModel):
    model_config = {'extra':'forbid'}  # never silently accept a forged organization ID
    scope: str = Field(pattern='^(organization|workspace)$')
    workspace_id: str = Field(default='default',min_length=1,max_length=80,pattern=r'^[A-Za-z0-9_-]+$')
    limit_usd: float = Field(ge=0,le=1000000,allow_inf_nan=False)

@app.get('/api/finops/limits')
def get_spend_limits(token=Depends(auth.current_session)):
    return quota.read_scope_limits(_account(token)['id'])

@app.post('/api/finops/limits')
def update_spend_limits(body:SpendLimitCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    try:return quota.set_scope_limit(_account(token)['id'],body.scope,body.limit_usd,body.workspace_id)
    except quota.QuotaDenied as exc:raise HTTPException(403,str(exc)) from None

@app.get('/api/finops/budgets')
def finops_budgets(token=Depends(auth.current_session)):
    ids=_visible(token)
    return [x for x in store.list_project_budgets() if _visible_row(x,ids)]

@app.get('/api/finops/export.csv')
def finops_csv(period:str=Query(default='30d',pattern='^(7d|30d|all)$'),
               project_id:str|None=None,token=Depends(auth.current_session)):
    import csv
    if project_id is not None:_verify_visible(project_id,token)
    rows,truncated=store.usage_export_rows(project_id,period,scope_user=_account(token)['id'])
    out=io.StringIO(newline='')
    out.write('# WFS PROJECT v2.0 estimate export; NOT official provider billing; newest 30000 calls maximum\r\n')
    if truncated:out.write('# TRUNCATED: more rows exist than exported\r\n')
    writer=csv.writer(out,lineterminator='\r\n')
    fields=['id','created_at','project_id','agent','model','input_tokens','output_tokens','estimated_usd','input_rate_snapshot','output_rate_snapshot']
    writer.writerow(fields)
    def safe(value):
        if value is None:return ''
        if isinstance(value,str):
            value=value.replace('\r',' ').replace('\n',' ')
            if value.lstrip().startswith(('=','+','-','@','\t')):return "'"+value
        return value
    for record in rows:writer.writerow([safe(record[f]) for f in fields])
    return Response(content=out.getvalue(),media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':'attachment; filename="wfs-finops-estimates.csv"',
        'X-WFS-Report-Truncated':str(truncated).lower(),'Cache-Control':'no-store'})

@app.post('/api/projects',status_code=202)
def create_project(body:ProjectCreate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    if body.mode=='ai' and not config.ai_enabled():raise HTTPException(409,'API model belum diatur. Gunakan demo mode atau isi OPENAI_API_KEY.')
    if body.mode=='demo' and body.stack!='static':raise HTTPException(422,'Mode demo hanya menyediakan situs statis')
    if body.mode=='demo' and body.task_review_mode!='auto':raise HTTPException(422,'Demo does not create specialist tasks')
    key=request.headers.get('idempotency-key')
    if key is not None and (len(key)<8 or len(key)>100 or not re.fullmatch(r'[A-Za-z0-9._:-]+',key)):
        raise HTTPException(400,'Idempotency-Key tidak valid')
    try:return store.create_project(body.title.strip(),body.prompt.strip(),body.mode,body.stack,key,task_review_mode=body.task_review_mode,created_by=_account(token)['id'],visibility=body.visibility)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None


def get_or_404(pid):
    if not re.fullmatch(r'[a-f0-9]{20}',pid):raise HTTPException(404,'Proyek tidak ditemukan')
    record=store.get_project(pid)
    if not record:raise HTTPException(404,'Proyek tidak ditemukan')
    return record

@app.get('/api/projects/{pid}')
def detail(pid:str,token=Depends(auth.current_session)):
    obj=get_or_404(pid)
    obj['usage']=store.get_usage(pid)
    obj['cost_estimate']=store.cost_report(pid,period='all')
    obj['queue_position']=store.queue_position(pid,scope_user=_account(token)['id'])
    obj['revisions']=[{'id':p['id'],'status':p['status'],'created_at':p['created_at']} for p in store.list_projects(include_archived=True) if p['parent_id']==pid]
    obj['qa_reports']=operator_reports(pid)
    obj['resumable_tasks']=obj['status'] in ('failed','interrupted') and bool(store.get_checkpoint(pid))
    obj['preview_ready']=obj['status'] in ('completed','review_required') and ((obj['stack']=='static' and bool(store.list_artifacts(pid))) or (obj['stack']=='react-vite' and preview_mod.is_ready(pid)))
    return obj

@app.get('/api/projects/{pid}/events')
def events(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.list_events(pid)

@app.get('/api/projects/{pid}/agents')
def agents(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.list_agents(pid)

@app.get('/api/projects/{pid}/files')
def files(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.list_artifacts(pid)

@app.get('/api/projects/{pid}/files/{path:path}')
def file_read(pid:str,path:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    try:validation.clean_path(path)
    except ValueError:raise HTTPException(404,'File tidak ditemukan') from None
    allowed={r['name'] for r in store.list_artifacts(pid)}
    if path not in allowed:raise HTTPException(404,'File tidak ditemukan')
    try:target=artifact_mod.verified(pid)[path]
    except artifact_mod.ArtifactChanged as exc:raise HTTPException(409,str(exc)) from None
    return {'name':path,'content':target.read_text(encoding='utf-8')}

@app.get('/api/projects/{pid}/download')
def download(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    artifacts=store.list_artifacts(pid)
    if not artifacts:raise HTTPException(409,'Belum ada hasil')
    try:sources=artifact_mod.verified(pid)
    except artifact_mod.ArtifactChanged as exc:raise HTTPException(409,str(exc)) from None
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path,source in sources.items():
            z.write(source,arcname=path)
    buffer.seek(0)
    return StreamingResponse(buffer,media_type='application/zip',headers={
      'Content-Disposition':f'attachment; filename="wfs-{pid}.zip"', 'X-Content-Type-Options':'nosniff'})


@app.post('/api/projects/{pid}/metadata')
def change_metadata(pid:str,body:MetadataUpdate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    current=get_or_404(pid)
    title=body.title.strip() if body.title is not None else None
    if title is not None and len(title)<3:
        raise HTTPException(422,'Judul proyek minimal 3 karakter')
    if body.title is None and body.notes is None:
        raise HTTPException(422,'Tidak ada field metadata untuk disimpan')
    if not store.update_project_metadata(pid,title,body.notes):
        raise HTTPException(404,'Proyek tidak ditemukan')
    return {'id':pid,'title':title if title is not None else current['title'],
            'notes':body.notes if body.notes is not None else current.get('notes','')}

@app.post('/api/projects/{pid}/revisions',status_code=202)
def revise(pid:str,body:RevisionCreate,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    parent=get_or_404(pid)
    if parent['status']!='completed':raise HTTPException(409,'Versi induk harus completed sebelum direvisi')
    if not config.ai_enabled():raise HTTPException(409,'Revisi AI memerlukan OPENAI_API_KEY')
    try:artifact_mod.source_files(pid)
    except (artifact_mod.ArtifactChanged,ValueError) as exc:raise HTTPException(409,str(exc)) from None
    key=request.headers.get('idempotency-key')
    if key is not None and (len(key)<8 or len(key)>100 or not re.fullmatch(r'[A-Za-z0-9._:-]+',key)):
        raise HTTPException(400,'Idempotency-Key tidak valid')
    title=(parent['title'][:103]+' / Revision')[:120]
    # A revision belongs to the authenticated project member's organization,
    # never to the built-in default organization owner.
    try:result=store.create_project(title,body.prompt.strip(),'ai',parent['stack'],key,
                                    parent_id=pid,created_by=_account(token)['id'],visibility=parent['visibility'])
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    return {**result,'parent_id':pid}

@app.post('/api/projects/{pid}/pause')
def pause_queued_project(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.change_queue_state(pid,'pause'):
        raise HTTPException(409,'Hanya proyek queued yang bisa ditahan; gunakan approval gate untuk menahan coding saat review')
    return {'status':'paused'}

@app.post('/api/projects/{pid}/resume')
def resume_queued_project(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.change_queue_state(pid,'resume'):
        raise HTTPException(409,'Hanya proyek paused yang bisa dilanjutkan')
    return {'status':'queued'}

@app.post('/api/projects/{pid}/priority')
def set_queue_priority(pid:str,body:PriorityCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.change_priority(pid,body.priority):
        raise HTTPException(409,'Prioritas hanya dapat diubah sebelum worker mulai bekerja')
    return {'priority':body.priority,'queue_position':store.queue_position(pid,scope_user=_account(token)['id'])}

@app.get('/api/projects/{pid}/trace')
def trace(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return store.project_trace(pid)

@app.get('/api/projects/{pid}/trace/download')
def trace_download(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    payload=json.dumps(store.project_trace(pid),ensure_ascii=False,indent=2).encode('utf-8')
    return Response(payload,media_type='application/json',headers={
        'Content-Disposition':f'attachment; filename="wfs-trace-{pid}.json"',
        'Cache-Control':'no-store'})

@app.post('/api/projects/{pid}/archive')
def archive(pid:str,body:ArchiveCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.set_archived(pid,body.archive):raise HTTPException(409,'Proyek aktif tidak dapat diarsipkan')
    store.operator_event(pid,'Workspace Admin','archived' if body.archive else 'restored','Status arsip proyek diubah operator')
    return {'archived':body.archive}

@app.post('/api/projects/{pid}/delete')
def remove(pid:str,body:DeleteCommand,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if body.confirm_id!=pid:raise HTTPException(400,'Konfirmasi project ID tidak cocok')
    if not store.remove_project(pid):raise HTTPException(409,'Proyek aktif atau memiliki revisi turunan; tidak dapat dihapus')
    for root in (config.PROJECTS,preview_mod.PREVIEWS,config.DATA/'reports'):
        target=root/pid
        if target.is_symlink():target.unlink()
        elif target.is_dir():shutil.rmtree(target)
    return {'deleted':True}


def operator_reports(pid:str):
    root=config.DATA/'reports'/pid
    if root.is_symlink() or not root.is_dir():return []
    reports=[]
    for path in sorted(root.glob('*.json'),reverse=True)[:25]:
        if path.is_symlink() or path.stat().st_size>80000:continue
        try:
            obj=json.loads(path.read_text(encoding='utf-8'))
            if obj.get('project_id')!=pid:continue
            raw_checks=obj.get('checks',[])
            checks=[{'name':str(x.get('name',''))[:100], 'status':str(x.get('status','unknown'))[:30]}
                    for x in raw_checks[:30] if isinstance(x,dict)] if isinstance(raw_checks,list) else []
            reports.append({'run_id':path.stem,'created_at':str(obj.get('created_at',''))[:50],
                'status':str(obj.get('status','unknown'))[:35],'checks':checks})
        except (OSError,ValueError):continue
    return reports

@app.get('/api/projects/{pid}/qa-runs')
def qa_runs(pid:str,token=Depends(auth.current_session)):
    get_or_404(pid)
    return operator_reports(pid)

@app.post('/api/projects/{pid}/cancel')
def cancel(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    status=store.cancel(pid)
    if status in ('cancelled','cancel_requested'):
        store.operator_event(pid,'Master Orchestrator','cancel',f'Pembatalan diminta; state: {status}')
    return {'status':status}

@app.post('/api/projects/{pid}/resume-tasks')
def resume_tasks(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.resume_partial_project(pid):
        raise HTTPException(409,'No resumable task checkpoint for this project')
    return {'status':'queued','preserved_results':len(store.load_task_results(pid))}

@app.post('/api/projects/{pid}/retry')
def retry(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    result=store.retry(pid)
    if not result:raise HTTPException(409,'Hanya proyek gagal, terinterupsi, atau dibatalkan yang bisa diulang')
    store.operator_event(pid,'Master Orchestrator','queued','Proyek dijadwalkan ulang; proses dimulai dari awal')
    return {'status':'queued'}

@app.post('/api/projects/{pid}/approve')
def approve(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    get_or_404(pid)
    if not store.approve(pid):
        raise HTTPException(409,'Hanya proyek berstatus review_required yang dapat disetujui')
    store.operator_event(pid,'Human Release Approver','approved','Pengguna mengakui temuan QA dan menyetujui artefak untuk diunduh; persetujuan bukan bukti production-ready')
    return {'status':'completed','approval':'manual'}

@app.post('/api/projects/{pid}/preview-ticket',status_code=201)
def create_preview_ticket(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    account=_account(token)
    if not store.can_access_project(pid,account['id'],write=False):
        raise HTTPException(404,'Proyek tidak ditemukan')
    try:url=preview_gateway.issue(pid,account['id'],token)
    except preview_gateway.GatewayError as exc:raise HTTPException(503,str(exc)) from None
    return {'url':url,'ttl_seconds':300,'note':'One-use URL; dedicated TLS preview gateway required. Do not log or share.'}

@app.delete('/api/projects/{pid}/preview-grants')
def revoke_preview_tickets(pid:str,request:Request,token=Depends(auth.current_session)):
    auth.require_csrf(request,token)
    account=_account(token)
    if not store.can_access_project(pid,account['id']):
        raise HTTPException(404,'Proyek tidak ditemukan')
    return {'revoked':preview_gateway.revoke(pid,account['id'])}

@app.get('/preview/{pid}/index.html',include_in_schema=False)
def preview(pid:str,token=Depends(auth.current_session)):
    p=get_or_404(pid)
    if p['status'] not in ('completed','review_required'):
        raise HTTPException(404,'Preview hanya tersedia setelah delivery selesai')
    if p['stack']=='react-vite':
        try:html_doc=preview_mod.inline_react(pid)
        except preview_mod.PreviewUnavailable as exc:raise HTTPException(404,str(exc)) from None
        return Response(html_doc,media_type='text/html',headers={
            'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; font-src data:; form-action 'none'; base-uri 'none'",
            'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
    if p['stack']!='static':raise HTTPException(404,'Preview dinamis FastAPI tidak didukung; unduh kode dan uji terisolasi')
    try:verified=artifact_mod.verified(pid)
    except artifact_mod.ArtifactChanged as exc:raise HTTPException(409,str(exc)) from None
    allowed=set(verified)
    if 'index.html' not in allowed:raise HTTPException(404,'Preview belum tersedia')
    root=config.PROJECTS/pid
    html_doc=(root/'index.html').read_text(encoding='utf-8')
    # Inline known local assets only; external scripts/stylesheets remain blocked by CSP.
    for name in sorted(allowed):
        if '/' in name:continue
        if name.endswith('.css'):
            pattern=r'<link\b(?=[^>]*\bhref\s*=\s*[\'\"]'+re.escape(name)+r'[\'\"])[^>]*>'
            content=(root/name).read_text(encoding='utf-8').replace('</style','<\\/style')
            html_doc=re.sub(pattern,lambda m:'<style>'+content+'</style>',html_doc,flags=re.I)
        if name.endswith('.js'):
            pattern=r'<script\b(?=[^>]*\bsrc\s*=\s*[\'\"]'+re.escape(name)+r'[\'\"])[^>]*>\s*</script>'
            content=(root/name).read_text(encoding='utf-8').replace('</script','<\\/script')
            html_doc=re.sub(pattern,lambda m:'<script>'+content+'</script>',html_doc,flags=re.I)
    return Response(html_doc,media_type='text/html',headers={
        'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; font-src data:; form-action 'none'; base-uri 'none'",
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store',
    })
