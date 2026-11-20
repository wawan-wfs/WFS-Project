"""Local-only Unix-socket dynamic-preview transport, never an Internet ingress.

The generated workload must listen on an operator-provisioned Unix socket in an
isolated runtime. It must NEVER be permitted to access this gateway's SQLite,
user sessions, Docker control socket or proxy key. Each project gets its OWN
DNS origin; per-request authorization is performed by preview_gateway.
"""
from __future__ import annotations

import asyncio
import os
import re
import socket
import stat
import threading
import h11
import struct
from pathlib import Path
from urllib.parse import unquote

from fastapi import Request
from fastapi.responses import Response

MAX_REQUEST=1_000_000
MAX_RESPONSE=4_000_000
MAX_ACTIVE_PER_PROJECT=4
MAX_ACTIVE_TOTAL=32
# Whole-operation limits, not just per-recv idle socket timeouts.
BODY_DEADLINE_SECONDS=5.0
UPSTREAM_DEADLINE_SECONDS=8.0
CONNECT_DEADLINE_SECONDS=2.0


class BrokerLimit:
    # Only local worker bounds. Ingress must additionally enforce global limits.
    def __init__(self, per_project=MAX_ACTIVE_PER_PROJECT, total=MAX_ACTIVE_TOTAL):
        self.per_project=per_project
        self.total=total
        self._lock=threading.Lock()
        self._projects={}
        self._total=0

    def acquire(self, pid):
        with self._lock:
            if self._total>=self.total or self._projects.get(pid,0)>=self.per_project:
                return False
            self._projects[pid]=self._projects.get(pid,0)+1
            self._total+=1
            return True

    def release(self, pid):
        with self._lock:
            if not self._projects.get(pid):return
            count=self._projects[pid]-1
            if count:self._projects[pid]=count
            else:del self._projects[pid]
            self._total-=1


broker_limit=BrokerLimit()
PID_RE=re.compile(r'^[a-f0-9]{20}$')

class BrokerUnavailable(ValueError):
    pass


class BrokerOverloaded(BrokerUnavailable):
    """Authenticated preview reached its bounded per-worker capacity."""
    pass



def project_socket(pid: str) -> Path:
    if not PID_RE.fullmatch(pid):
        raise BrokerUnavailable('Invalid project ID')
    raw=os.getenv('WFS_PREVIEW_SOCKET_ROOT','')
    root=Path(raw)
    if not raw or not root.is_absolute() or '..' in root.parts:
        raise BrokerUnavailable('Trusted socket root not configured')
    try:
        st_root=root.lstat()
        if not stat.S_ISDIR(st_root.st_mode) or st_root.st_mode & 0o022:
            raise BrokerUnavailable('Socket root must not be group/world writable')
        owner=os.getenv('WFS_PREVIEW_SOCKET_UID','')
        if not owner.isdecimal() or st_root.st_uid not in (0,int(owner)):
            raise BrokerUnavailable('Socket root ownership is not trusted')
        target=root/(pid+'.sock')
        st=target.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_mode & 0o022:
            raise BrokerUnavailable('Expected private Unix socket missing')
        # A specific operator-designated UID must own the socket (not the
        # arbitrary UID hosting the untrusted preview application).
        owner=os.getenv('WFS_PREVIEW_SOCKET_UID','')
        if not owner.isdecimal() or st.st_uid!=int(owner):
            raise BrokerUnavailable('Socket owner does not match operator policy')
    except (OSError,ValueError) as e:
        if isinstance(e,BrokerUnavailable):raise
        raise BrokerUnavailable('Trusted preview socket unavailable') from None
    return target


def safe_target(request: Request) -> str:
    raw=request.scope.get('raw_path',b'/')
    if not isinstance(raw,bytes) or len(raw)>2048:
        raise BrokerUnavailable('Invalid preview request path')
    try: text=raw.decode('ascii','strict')
    except UnicodeError:raise BrokerUnavailable('Invalid path encoding') from None
    lower=text.lower()
    # Reject ambiguous percent decoding, backslashes and separator encodings.
    if any(x in lower for x in ('%25','%2f','%5c','%00','%0d','%0a')) or '\\' in text or '\x00' in text:
        raise BrokerUnavailable('Ambiguous path encoding')
    path=unquote(text)
    if not path.startswith('/') or '//' in path or any(x in ('.','..') or x.startswith('.') for x in path.split('/') if x):
        raise BrokerUnavailable('Unsafe preview path')
    q=request.url.query
    if len(q)>2048 or '\r' in q or '\n' in q or any(x in q.lower() for x in ('%0d','%0a','%00')):
        raise BrokerUnavailable('Invalid preview query')
    return path+('?' + q if q else '')


async def proxy(request:Request,pid:str)->Response:
    if not broker_limit.acquire(pid):
        raise BrokerOverloaded('Preview capacity exhausted')
    try:
        return await _proxy_approved(request,pid)
    finally:
        broker_limit.release(pid)


async def _request_body(request: Request) -> bytes:
    """Bound total upload wall time, even for clients sending one byte at a time."""
    content_length=request.headers.get('content-length','')
    if content_length and (not content_length.isdecimal() or int(content_length)>MAX_REQUEST):
        raise BrokerUnavailable('Request too large')
    pieces=[]
    total=0
    try:
        async with asyncio.timeout(BODY_DEADLINE_SECONDS):
            async for chunk in request.stream():
                total+=len(chunk)
                if total>MAX_REQUEST:
                    raise BrokerUnavailable('Request too large')
                pieces.append(chunk)
    except TimeoutError:
        raise BrokerUnavailable('Preview request body deadline exceeded') from None
    return b''.join(pieces)


async def _unix_exchange(sock: Path, method: str, target: str, body: bytes, headers: dict):
    """Cancellation-safe HTTP/1.1 over a trusted Unix socket using h11.

    One absolute deadline caps connect + headers + streamed response, including
    slow-trickle workloads. No detached blocking thread or orphaned active slot.
    """
    writer=None
    try:
        async with asyncio.timeout(UPSTREAM_DEADLINE_SECONDS):
            reader,writer=await asyncio.wait_for(
                asyncio.open_unix_connection(str(sock)), CONNECT_DEADLINE_SECONDS)
            transport_socket=writer.get_extra_info('socket')
            if transport_socket is None or not hasattr(socket,'SO_PEERCRED'):
                raise BrokerUnavailable('Linux peer credential verification required')
            owner=os.getenv('WFS_PREVIEW_SOCKET_UID','')
            if not owner.isdecimal():
                raise BrokerUnavailable('Operator socket UID missing')
            try:
                peer=transport_socket.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
                _pid,uid,_gid=struct.unpack('3i',peer)
            except (OSError,struct.error):
                raise BrokerUnavailable('Could not verify socket peer') from None
            if uid != int(owner):
                raise BrokerUnavailable('Untrusted preview socket peer')
            protocol=h11.Connection(h11.CLIENT, max_incomplete_event_size=16384)
            wire_headers=[(k.encode('ascii'),v.encode('latin1')) for k,v in headers.items()]
            wire_headers.append((b'Connection',b'close'))
            wire_headers.append((b'Content-Length',str(len(body)).encode('ascii')))
            writer.write(protocol.send(h11.Request(method=method.encode('ascii'),
                target=target.encode('ascii'),headers=wire_headers)))
            if body:
                writer.write(protocol.send(h11.Data(data=body)))
            writer.write(protocol.send(h11.EndOfMessage()))
            await writer.drain()
            result_status=None
            result_type='application/octet-stream'
            payload=bytearray()
            while True:
                event=protocol.next_event()
                if event is h11.NEED_DATA:
                    block=await reader.read(65536)
                    protocol.receive_data(block)
                    continue
                if isinstance(event,h11.InformationalResponse):
                    # Ignore 100 Continue only; reject switching protocols.
                    if event.status_code!=100:
                        raise BrokerUnavailable('Unsupported upstream response')
                elif isinstance(event,h11.Response):
                    if result_status is not None or not 100 <= event.status_code <= 599:
                        raise BrokerUnavailable('Invalid backend status')
                    result_status=event.status_code
                    for key,value in event.headers:
                        if key.lower()==b'content-type':
                            if len(value)>180 or b'\r' in value or b'\n' in value:
                                raise BrokerUnavailable('Invalid backend content type')
                            result_type=value.decode('latin1')
                elif isinstance(event,h11.Data):
                    payload.extend(event.data)
                    if len(payload)>MAX_RESPONSE:
                        raise BrokerUnavailable('Backend response too large')
                elif isinstance(event,h11.EndOfMessage):
                    if result_status is None:
                        raise BrokerUnavailable('Missing backend response')
                    return result_status,bytes(payload),result_type
                elif event is h11.PAUSED:
                    raise BrokerUnavailable('Upstream pipelining is not supported')
    except (TimeoutError,asyncio.TimeoutError):
        raise BrokerUnavailable('Preview upstream deadline exceeded') from None
    except (OSError,h11.RemoteProtocolError,h11.LocalProtocolError,UnicodeError,ValueError):
        raise BrokerUnavailable('Internal preview workload unavailable') from None
    finally:
        if writer is not None:
            writer.close()
            # Closing the transport immediately terminates upstream I/O, even
            # when this coroutine was cancelled by a disconnected browser.


async def _proxy_approved(request:Request,pid:str)->Response:
    method=request.method.upper()
    if method not in ('GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'):
        raise BrokerUnavailable('Method denied')
    path=safe_target(request)
    sock=project_socket(pid)
    body=await _request_body(request)
    # Never forward cookies, auth, x-forwarded headers or CORS metadata to
    # an untrusted generated application.
    headers={'Accept':request.headers.get('accept','*/*'), 'Host':'localhost'}
    ct=request.headers.get('content-type','')
    if ct and len(ct)<200 and '\r' not in ct and '\n' not in ct:
        headers['Content-Type']=ct
    status,payload,typ=await _unix_exchange(sock,method,path,body,headers)
    out=Response(content=b'' if method=='HEAD' else payload,status_code=status,media_type=None)
    out.headers['Content-Type']=typ
    out.headers['Cache-Control']='no-store'
    return out
