"""Isolated-origin, short-lived preview grant store and minimal gateway.

A *separate* hostname with TLS-terminating trusted proxy is mandatory. This app
must not be mounted under the primary dashboard origin. It only renders the
bounded, script-inlined static/React preview, never proxies untrusted containers.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from . import dynamic_broker
from . import preview_authority_client as authority
from . import store


class GatewayError(ValueError):pass


def public_origin() -> str:
    raw=os.getenv('WFS_PREVIEW_PUBLIC_ORIGIN','').strip().rstrip('/')
    parsed=urlsplit(raw)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise GatewayError('Dedicated HTTPS preview origin not configured')
    host=parsed.hostname.lower()
    try:ipaddress.ip_address(host);raise GatewayError('Preview origin must be a distinct DNS hostname')
    except ValueError as ex:
        if isinstance(ex,GatewayError):raise
    if host=='localhost' or host.endswith('.localhost') or '.' not in host:
        raise GatewayError('Preview hostname cannot be localhost or an unqualified name')
    dashboard={x.strip().lower() for x in os.getenv('WFS_ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',')}
    if host in dashboard or '*' in dashboard:
        raise GatewayError('Preview and dashboard origins must not overlap')
    return raw


def install(cx):
    cx.execute('BEGIN IMMEDIATE')
    cx.execute('''CREATE TABLE IF NOT EXISTS preview_grants (
        ticket_hash TEXT PRIMARY KEY, cookie_hash TEXT UNIQUE,
        organization_id TEXT NOT NULL, project_id TEXT NOT NULL, user_id TEXT NOT NULL,
        dashboard_session_hash TEXT NOT NULL, created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL, redeemed_at TEXT, revoked_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE)''')
    cx.execute('CREATE INDEX IF NOT EXISTS idx_preview_grants_user_project ON preview_grants(user_id,project_id,expires_at)')
    cx.execute('COMMIT')


def _hash(secret:str)->str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _expires(seconds=300):
    return (datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(timespec='seconds')


def _ready(cx,project_id,user_id,session_hash):
    row=cx.execute('''SELECT p.organization_id,p.status,p.stack,u.disabled,
        (SELECT organization_id FROM users WHERE id=?) as user_org,
        (SELECT expires_at FROM sessions WHERE id_hash=? AND user_id=?) AS session_expiry
        FROM projects p JOIN users u ON u.id=? WHERE p.id=?''',
        (user_id,session_hash,user_id,user_id,project_id)).fetchone()
    if not row or row['disabled'] or row['organization_id']!=row['user_org'] or not row['session_expiry'] or row['session_expiry']<=store.now():
        raise GatewayError('Preview identity or dashboard session revoked')
    if row['status'] not in ('completed','review_required') or row['stack'] not in ('static','react-vite','fastapi','node-web'):
        raise GatewayError('Preview not available for this project')
    return row['organization_id']


def dynamic_hostname(pid:str)->str:
    if not dynamic_broker.PID_RE.fullmatch(pid):raise GatewayError('Invalid dynamic project ID')
    suffix=os.getenv('WFS_PREVIEW_DYNAMIC_DOMAIN','').strip().lower().strip('.')
    if (not suffix or not suffix.isascii() or not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',suffix)
        or suffix.endswith('.localhost') or suffix.endswith('.local') or suffix=='localhost'
        or suffix==urlsplit(public_origin()).hostname):
        raise GatewayError('Dedicated per-project dynamic hostname not configured')
    return pid+'.'+suffix


def issue(project_id:str,user_id:str,session_token:str) -> str:
    origin=public_origin() # refuse to issue links unless a dedicated HTTPS origin configured
    if not store.can_access_project(project_id,user_id,write=False):
        raise GatewayError('Project not accessible')
    ticket=secrets.token_urlsafe(40)
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        session_hash=_hash(session_token)
        org=_ready(cx,project_id,user_id,session_hash)
        stack=cx.execute('SELECT stack FROM projects WHERE id=?',(project_id,)).fetchone()['stack']
        if stack in ('fastapi','node-web'):
            dynamic_broker.project_socket(project_id)  # no ticket without provisioned private socket
            origin='https://'+dynamic_hostname(project_id)
        cx.execute('''INSERT INTO preview_grants(ticket_hash,organization_id,project_id,user_id,
            dashboard_session_hash,created_at,expires_at) VALUES(?,?,?,?,?,?,?)''',
            (_hash(ticket),org,project_id,user_id,session_hash,store.now(),_expires()))
        cx.execute('COMMIT')
    # The opaque ticket is one-use, expires quickly, is exchanged before content;
    # operator reverse proxy MUST redact /t/* in access logs.
    return origin+'/t/'+ticket


def exchange(ticket:str):
    if len(ticket)>256 or len(ticket)<20:raise GatewayError('Invalid ticket')
    cookie=secrets.token_urlsafe(48)
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('''SELECT project_id,user_id,dashboard_session_hash,organization_id
            FROM preview_grants WHERE ticket_hash=? AND redeemed_at IS NULL AND revoked_at IS NULL
            AND expires_at>?''',(_hash(ticket),store.now())).fetchone()
        if not row:raise GatewayError('Preview ticket expired or already used')
        org=_ready(cx,row['project_id'],row['user_id'],row['dashboard_session_hash'])
        if org!=row['organization_id'] or not store.can_access_project(row['project_id'],row['user_id']):
            raise GatewayError('Preview project access revoked')
        cx.execute('UPDATE preview_grants SET cookie_hash=?,redeemed_at=? WHERE ticket_hash=?',
                   (_hash(cookie),store.now(),_hash(ticket)))
        cx.execute('COMMIT')
    return row['project_id'],cookie


def verify(project_id:str,cookie:str):
    if not 30<len(cookie)<256:raise GatewayError('Missing preview session')
    with store.connect() as cx:
        row=cx.execute('''SELECT user_id,organization_id,dashboard_session_hash FROM preview_grants
            WHERE project_id=? AND cookie_hash=? AND redeemed_at IS NOT NULL
            AND revoked_at IS NULL AND expires_at>?''',(project_id,_hash(cookie),store.now())).fetchone()
        if not row:raise GatewayError('Preview session expired or revoked')
        org=_ready(cx,project_id,row['user_id'],row['dashboard_session_hash'])
        if org!=row['organization_id']:
            raise GatewayError('Preview organization changed')
        if not store.can_access_project(project_id,row['user_id']):
            raise GatewayError('Preview project permission revoked')
    return True


def revoke(project_id:str,user_id:str):
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        n=cx.execute('UPDATE preview_grants SET revoked_at=? WHERE user_id=? AND project_id=? AND revoked_at IS NULL',
                     (store.now(),user_id,project_id)).rowcount
        cx.execute('COMMIT')
    return n


app=FastAPI(title='WFS preview isolated-origin gateway',docs_url=None,redoc_url=None,openapi_url=None)


@app.middleware('http')
async def gate(request:Request,call_next):
    # Require an operator-controlled loopback TLS reverse proxy. This header
    # must be removed from incoming browser requests and reset at the proxy.
    from fastapi.responses import PlainTextResponse
    try:
        origin=public_origin()
        host=urlsplit(origin).netloc.lower()
        expected=os.getenv('WFS_PREVIEW_PROXY_KEY','')
        actual=request.headers.get('host','').lower()
        dynamic=False
        if actual!=host:
            m=re.fullmatch(r'([a-f0-9]{20})\.(.+)',actual)
            if not m or dynamic_hostname(m.group(1))!=actual:
                raise GatewayError('Preview origin mismatch')
            dynamic=True
        if len(expected)<32:
            raise GatewayError('Preview proxy configuration not trusted')
        if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            raise GatewayError('Gateway must only receive requests from loopback proxy')
        if not hmac.compare_digest(request.headers.get('x-wfs-preview-proxy-key',''),expected):
            raise GatewayError('Proxy authorization required')
        if request.headers.get('x-forwarded-proto','')!='https':
            raise GatewayError('TLS must be terminated at dedicated gateway origin')
    except GatewayError:
        response=PlainTextResponse('Preview gateway unavailable',status_code=503)
    else:
        response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy']=response.headers.get('Content-Security-Policy',"default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    return response


@app.get('/t/{ticket}',include_in_schema=False)
def redeem(ticket:str,request:Request):
    try:
        # Check hostname before consuming an otherwise valid one-use ticket.
        if len(ticket)>256 or len(ticket)<20:raise GatewayError('Invalid ticket')
        if authority.enabled():
            entry=authority.call('ticket',{'ticket':ticket})
            dynamic=True
            entry={'id':entry['project_id'],'stack':entry['stack']}
        else:
            with store.connect() as cx:
                entry=cx.execute("""SELECT p.stack,p.id FROM preview_grants g
                    JOIN projects p ON p.id=g.project_id WHERE g.ticket_hash=?
                    AND g.redeemed_at IS NULL AND g.revoked_at IS NULL AND g.expires_at>?""",
                    (_hash(ticket),store.now())).fetchone()
            if not entry:raise GatewayError('Ticket unavailable')
            dynamic=entry['stack'] in ('fastapi','node-web')
        host=request.headers.get('host','').lower()
        expected=dynamic_hostname(entry['id']) if dynamic else urlsplit(public_origin()).netloc.lower()
        if host!=expected:raise GatewayError('Wrong preview hostname')
        if authority.enabled():
            receipt=authority.call('exchange',{'ticket':ticket})
            pid,cookie=receipt['project_id'],receipt['cookie']
            if pid!=entry['id'] or not dynamic:
                raise GatewayError('Authorization service response mismatch')
        else:
            pid,cookie=exchange(ticket)
    except (GatewayError,authority.AuthorityUnavailable,KeyError,TypeError):raise HTTPException(404,'Preview ticket unavailable') from None
    response=RedirectResponse('/' if dynamic else '/p/'+pid+'/index.html',status_code=303)
    response.set_cookie('wfs_preview',cookie,secure=True,httponly=True,samesite='lax',
                        path='/' if dynamic else '/p/'+pid,max_age=300)
    return response


@app.get('/p/{pid}/index.html',include_in_schema=False)
def show(pid:str,request:Request):
    if authority.enabled():
        raise HTTPException(404,'Static preview unavailable on dynamic-only isolated gateway')
    try:verify(pid,request.cookies.get('wfs_preview',''))
    except GatewayError:raise HTTPException(404,'Preview unavailable') from None
    # Reuse exactly the bounded inline/opaque sandbox content from the legacy
    # preview route; no Docker port proxying or extra static assets.
    from .main import preview as render_local
    return render_local(pid,token='gateway-scope-already-verified')


@app.api_route('/{path:path}',methods=['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'],include_in_schema=False)
async def dynamic_preview(path:str,request:Request):
    # No dynamic content on the shared static origin. Per-project DNS isolation
    # is mandatory to keep browser origin, storage and cookies tenant-scoped.
    host=request.headers.get('host','').lower()
    match=re.fullmatch(r'([a-f0-9]{20})\.(.+)',host)
    if not match:
        raise HTTPException(404,'Preview unavailable')
    pid=match.group(1)
    try:
        if dynamic_hostname(pid)!=host:raise GatewayError('Wrong preview origin')
        if authority.enabled():
            authority.call('verify',{'project_id':pid,'cookie':request.cookies.get('wfs_preview','')})
        else:
            with store.connect() as cx:
                project=cx.execute('SELECT stack FROM projects WHERE id=?',(pid,)).fetchone()
            if not project or project['stack'] not in ('fastapi','node-web'):
                raise GatewayError('Not a dynamic preview project')
            verify(pid,request.cookies.get('wfs_preview',''))
        response=await dynamic_broker.proxy(request,pid)
        # Untrusted application scripts may operate only within this distinct
        # per-project HTTPS origin, not the WFS dashboard or static gateway.
        response.headers['Content-Security-Policy']=(
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        return response
    except dynamic_broker.BrokerOverloaded:
        # Only reachable after the per-request authorization check above.
        # Do not leak this distinction for an unauthenticated project.
        raise HTTPException(503,'Preview temporarily busy',headers={'Retry-After':'2'}) from None
    except (GatewayError,dynamic_broker.BrokerUnavailable,authority.AuthorityUnavailable):
        raise HTTPException(404,'Preview unavailable') from None
