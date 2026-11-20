"""Dashboard-host ONLY preview authority, reached on a private Unix socket.

This process is trusted to read WFS auth storage. The externally reachable
preview gateway MUST NOT share this process, DB, environment or socket volume.
Reverse proxies must never expose this ASGI app on a TCP/public route.
"""
from __future__ import annotations
import hmac
import hashlib
import os
import re
import time
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from . import preview_gateway, store

app=FastAPI(title='WFS internal preview authority',docs_url=None,redoc_url=None,openapi_url=None)

class Intent(BaseModel):
    ticket: str | None = Field(default=None,min_length=20,max_length=256)
    project_id: str | None = Field(default=None,min_length=20,max_length=20)
    cookie: str | None = Field(default=None,min_length=32,max_length=256)

# Durable nonce admission prevents replay across authority restarts.  A single
# SQLite writer transaction serializes multiple service workers; failures deny.
def _consume_nonce(nonce: str, now: int) -> bool:
    try:
        with store.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            # Schema must be migrated by the trusted operator/API first.
            # A missing table fails closed rather than changing production data
            # on an incoming request.
            cx.execute('DELETE FROM preview_authority_nonces WHERE used_at<?', (now-120,))
            size=cx.execute('SELECT COUNT(*) FROM preview_authority_nonces').fetchone()[0]
            if size>=8192:
                cx.execute('ROLLBACK')
                return False
            changed=cx.execute('INSERT OR IGNORE INTO preview_authority_nonces(nonce,used_at) VALUES(?,?)', (nonce,now)).rowcount
            cx.execute('COMMIT')
            return changed==1
    except (sqlite3.Error, OSError):
        # DB unreachable or locked: never downgrade to in-memory nonce checks.
        return False


@app.middleware('http')
async def only_trusted(request:Request,call_next):
    from fastapi.responses import PlainTextResponse
    def deny():return PlainTextResponse('Authorization denied',status_code=403)
    path=request.url.path
    if path not in ('/internal/ticket','/internal/exchange','/internal/verify') or request.method!='POST':
        return PlainTextResponse('Not found',status_code=404)
    key=os.getenv('WFS_PREVIEW_AUTHORITY_KEY','')
    timestamp=request.headers.get('x-wfs-authority-time','')
    nonce=request.headers.get('x-wfs-authority-nonce','')
    signature=request.headers.get('x-wfs-authority-signature','')
    if len(key)<32 or not timestamp.isdecimal() or len(timestamp)>12 or not re.fullmatch(r'[a-f0-9]{32}',nonce) or not re.fullmatch(r'[a-f0-9]{64}',signature):
        return deny()
    now=int(time.time())
    if abs(now-int(timestamp))>30:
        return deny()
    body=await request.body()
    if len(body)>1024:return deny()
    msg=(timestamp+'\n'+nonce+'\n'+path+'\n').encode()+body
    expected=hmac.new(key.encode(),msg,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):
        return deny()
    if not _consume_nonce(nonce,now):
        return deny()
    return await call_next(request)


def ticket_info(token:str)->dict:
    if not token or len(token)>256:raise ValueError('Ticket invalid')
    with store.connect() as cx:
        row=cx.execute('''SELECT p.id,p.stack FROM preview_grants g
            JOIN projects p ON p.id=g.project_id WHERE g.ticket_hash=?
            AND g.redeemed_at IS NULL AND g.revoked_at IS NULL AND g.expires_at>?''',
            (preview_gateway._hash(token),store.now())).fetchone()
    if not row:raise ValueError('Ticket not available')
    return {'project_id':row['id'],'stack':row['stack']}

@app.post('/internal/ticket',include_in_schema=False)
def lookup(payload:Intent):
    try:
        if not payload.ticket:raise ValueError('Ticket required')
        out=ticket_info(payload.ticket)
        if out['stack'] not in ('fastapi','node-web'):
            raise ValueError('Remote dynamic authority does not render static previews')
        return {'ok':True,**out}
    except (ValueError, preview_gateway.GatewayError):
        raise HTTPException(404,'Unavailable') from None

@app.post('/internal/exchange',include_in_schema=False)
def exchange(payload:Intent):
    try:
        if not payload.ticket:raise ValueError('Ticket required')
        before=ticket_info(payload.ticket)
        if before['stack'] not in ('fastapi','node-web'):
            raise ValueError('Not a dynamic preview')
        pid,cookie=preview_gateway.exchange(payload.ticket)
        if pid!=before['project_id']:
            raise ValueError('Ticket changed')
        return {'ok':True,'project_id':pid,'cookie':cookie}
    except (ValueError, preview_gateway.GatewayError):
        raise HTTPException(404,'Unavailable') from None

@app.post('/internal/verify',include_in_schema=False)
def verify(payload:Intent):
    try:
        if not payload.project_id or not payload.cookie:
            raise ValueError('Session missing')
        with store.connect() as cx:
            row=cx.execute('SELECT stack FROM projects WHERE id=?',(payload.project_id,)).fetchone()
        if not row or row['stack'] not in ('fastapi','node-web'):
            raise ValueError('Not an authorized dynamic workload')
        preview_gateway.verify(payload.project_id,payload.cookie)
        return {'ok':True,'project_id':payload.project_id}
    except (ValueError, preview_gateway.GatewayError):
        raise HTTPException(404,'Unavailable') from None
