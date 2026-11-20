"""Optional shared SSE admission authority over a private authenticated Unix socket.

In assertion mode, the authority independently checks real WFS sessions,
MFA policy and grants. The old API-attested protocol is local compatibility
only. Never forward identity claims from HTTP/proxy headers.

This is local cross-process admission only, NOT a certified cross-host ingress.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import sqlite3
import stat
import time
import threading
import uuid

MAX_MESSAGE = 4096
MAX_CLOCK_SKEW = 30
LEASE_TTL = 65  # SSE endpoint normally reconnects after 28 seconds.


def _json(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def signature(secret, payload):
    return hmac.new(secret.encode(),_json(payload),hashlib.sha256).hexdigest()


def validate_secret(secret):
    if not isinstance(secret,str) or len(secret)<32 or len(secret)>512:
        raise ValueError('WFS_SSE_EDGE_SECRET must be 32-512 characters')


class AdmissionUnavailable(RuntimeError):pass
class AdmissionUnauthorized(RuntimeError):pass


class AdmissionClient:
    """Caller holds no raw session tokens outside API; leases are opaque UUIDs."""
    def __init__(self,socket_path,secret,timeout=1.0):
        validate_secret(secret)
        self.path=Path(socket_path)
        self.secret=secret
        self.timeout=timeout

    def request(self,action,**fields):
        payload={'action':action,'timestamp':int(time.time()),'nonce':secrets.token_hex(16),**fields}
        message={**payload,'mac':signature(self.secret,payload)}
        try:
            info=self.path.lstat()
            parent=self.path.parent.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o077
                    or (hasattr(os,'geteuid') and parent.st_uid != os.geteuid())):
                raise AdmissionUnavailable('Untrusted SSE admission socket directory')
            if not stat.S_ISSOCK(info.st_mode) or (info.st_mode & 0o077):
                raise AdmissionUnavailable('Untrusted SSE admission socket permissions')
            if hasattr(os,'geteuid') and info.st_uid != os.geteuid():
                raise AdmissionUnavailable('Unexpected SSE admission socket owner')
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect(str(self.path))
                sock.sendall(_json(message)+b'\n')
                data=b''
                while b'\n' not in data and len(data)<MAX_MESSAGE:
                    chunk=sock.recv(min(4096,MAX_MESSAGE-len(data)))
                    if not chunk:break
                    data+=chunk
            if b'\n' not in data or len(data)>=MAX_MESSAGE:
                raise AdmissionUnavailable('SSE admission response invalid')
            response=json.loads(data.split(b'\n',1)[0])
            if not isinstance(response,dict) or response.get('status') not in ('allowed','denied','unauthorized','unavailable'):
                raise AdmissionUnavailable('SSE admission response invalid')
            if response['status']=='unavailable':
                raise AdmissionUnavailable('SSE admission authority unavailable')
            return response
        except (OSError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
            raise AdmissionUnavailable('SSE admission authority unavailable') from exc

    def acquire(self,token,organization,*,project=None,require_assertion=False):
        if require_assertion:
            issued=self.request('authorize',token=token,project=project)
            if issued['status']=='unauthorized':
                raise AdmissionUnauthorized('SSE session or project scope changed')
            if issued['status']!='allowed' or not isinstance(issued.get('assertion'),dict):
                raise AdmissionUnavailable('SSE identity issuer unavailable')
            response=self.request('acquire',assertion=issued['assertion'])
        else:
            if not isinstance(organization,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',organization):
                raise AdmissionUnavailable('Invalid server-attested organization')
            key=hashlib.sha256(token.encode()).hexdigest()
            response=self.request('acquire',session_key=key,organization=organization)
        if response['status']=='denied':return None
        if response['status']=='unauthorized':
            raise AdmissionUnauthorized('SSE session or project scope changed')
        lease=response.get('lease')
        if response['status']!='allowed' or not isinstance(lease,str) or not re.fullmatch('[a-f0-9]{32}',lease):
            raise AdmissionUnavailable('Invalid SSE admission lease')
        return lease

    async def acquire_async(self,*args,**kwargs):
        task=asyncio.create_task(asyncio.to_thread(self.acquire,*args,**kwargs))
        loop=asyncio.get_running_loop()
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            def release_late(result):
                if result.cancelled():return
                try: lease=result.result()
                except (AdmissionUnavailable,AdmissionUnauthorized,OSError,ValueError):return
                if lease:loop.run_in_executor(None,self.release,lease)
            task.add_done_callback(release_late)
            raise

    async def release_async(self,lease):
        await asyncio.shield(asyncio.to_thread(self.release,lease))

    def release(self,lease):
        # Releases are idempotent. Lost releases are eventually reclaimed by TTL;
        # no local per-process cap is bypassed if the authority fails on acquire.
        if not isinstance(lease,str) or not re.fullmatch('[a-f0-9]{32}',lease):return
        try:self.request('release',lease=lease)
        except AdmissionUnavailable:pass


class AdmissionLedger:
    def __init__(self,path,*,per_session=2,per_organization=24,total=64,ttl=LEASE_TTL,issuer=None,verifier=None):
        self.path=Path(path)
        self.per_session=per_session
        self.per_organization=per_organization
        self.total=total
        self.ttl=ttl
        self.issuer=issuer
        self.verifier=verifier
        if (issuer is None)!=(verifier is None):raise ValueError('Issuer and verifier must be configured together')
        if min(per_session,per_organization,total,ttl)<1:raise ValueError('Positive limits required')
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        directory=self.path.parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_mode & 0o077
                or (hasattr(os,'geteuid') and directory.st_uid != os.geteuid())):
            raise ValueError('SSE admission database directory must be private')
        if self.path.is_symlink() or (self.path.exists() and (not self.path.is_file() or self.path.stat().st_mode & 0o077
                or (hasattr(os,'geteuid') and self.path.stat().st_uid != os.geteuid()))):
            raise ValueError('SSE admission ledger must be private')
        with closing(self.connect()) as cx:
            cx.execute('PRAGMA journal_mode=WAL')
            cx.execute('''CREATE TABLE IF NOT EXISTS leases(
                lease TEXT PRIMARY KEY,session_key TEXT NOT NULL,
                organization TEXT NOT NULL,expires INTEGER NOT NULL)''')
            cx.execute('CREATE INDEX IF NOT EXISTS idx_sse_leases_expires ON leases(expires)')
            cx.execute('CREATE INDEX IF NOT EXISTS idx_sse_leases_session ON leases(session_key)')
            cx.execute('''CREATE TABLE IF NOT EXISTS nonces(
                nonce TEXT PRIMARY KEY,created INTEGER NOT NULL)''')
            cx.execute('CREATE INDEX IF NOT EXISTS idx_sse_nonces_created ON nonces(created)')
        os.chmod(self.path,0o600)

    def connect(self):
        cx=sqlite3.connect(str(self.path),timeout=3,isolation_level=None)
        cx.execute('PRAGMA busy_timeout=3000')
        return cx

    def execute(self,message,secret):
        validate_secret(secret)
        if not isinstance(message,dict) or len(_json(message))>MAX_MESSAGE:return {'status':'denied'}
        claimed=message.get('mac','')
        signed={k:v for k,v in message.items() if k!='mac'}
        if not isinstance(claimed,str) or not re.fullmatch(r'[a-f0-9]{64}',claimed) or not hmac.compare_digest(signature(secret,signed),claimed):
            return {'status':'denied'}
        stamp=signed.get('timestamp')
        nonce=signed.get('nonce')
        action=signed.get('action')
        t=int(time.time())
        if (type(stamp) is not int or abs(stamp-t)>MAX_CLOCK_SKEW or
            not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32}',nonce) or
            action not in ('acquire','release','authorize')):
            return {'status':'denied'}
        with closing(self.connect()) as cx:
            cx.execute('BEGIN IMMEDIATE')
            # A timestamp accepted ahead of this clock stays valid for up
            # to two skew windows after it is first observed.
            cx.execute('DELETE FROM nonces WHERE created<?',(t-2*MAX_CLOCK_SKEW-1,))
            # replay-safe across processes and service restarts
            if not cx.execute('INSERT OR IGNORE INTO nonces(nonce,created) VALUES(?,?)',(nonce,t)).rowcount:
                cx.execute('ROLLBACK');return {'status':'denied'}
            cx.execute('DELETE FROM leases WHERE expires<=?', (t,))
            if action=='release':
                lease=signed.get('lease')
                if not isinstance(lease,str) or not re.fullmatch(r'[a-f0-9]{32}',lease):
                    cx.execute('ROLLBACK');return {'status':'denied'}
                cx.execute('DELETE FROM leases WHERE lease=?',(lease,))
                cx.execute('COMMIT')
                return {'status':'allowed'}
            if action=='authorize':
                assertion=(self.issuer.issue(signed.get('token'),signed.get('project'))
                           if self.issuer is not None and set(signed)=={'action','timestamp','nonce','token','project'}
                           else None)
                cx.execute('COMMIT')
                if self.issuer is None:return {'status':'unavailable'}
                return {'status':'allowed','assertion':assertion} if assertion else {'status':'unauthorized'}
            if self.verifier is not None:
                claims=(self.verifier.verify(signed['assertion'],int(time.time()))
                        if set(signed)=={'action','timestamp','nonce','assertion'} else None)
                if claims is None:
                    cx.execute('COMMIT');return {'status':'unauthorized'}
                if not cx.execute('INSERT OR IGNORE INTO nonces VALUES(?,?)',('assertion:'+claims['jti'],t)).rowcount:
                    cx.execute('COMMIT');return {'status':'unauthorized'}
                session,org=claims['sid'],claims['org']
            else:
                session=signed.get('session_key')
                org=signed.get('organization')
                if (set(signed)!={'action','timestamp','nonce','session_key','organization'} or
                    not isinstance(session,str) or not re.fullmatch('[a-f0-9]{64}',session) or
                    not isinstance(org,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',org)):
                    cx.execute('COMMIT');return {'status':'denied'}
            counts=(cx.execute('SELECT COUNT(*) FROM leases').fetchone()[0],
                    cx.execute('SELECT COUNT(*) FROM leases WHERE session_key=?',(session,)).fetchone()[0],
                    cx.execute('SELECT COUNT(*) FROM leases WHERE organization=?',(org,)).fetchone()[0])
            if counts[0]>=self.total or counts[1]>=self.per_session or counts[2]>=self.per_organization:
                cx.execute('COMMIT');return {'status':'denied'}
            lease=uuid.uuid4().hex
            cx.execute('INSERT INTO leases VALUES(?,?,?,?)',(lease,session,org,t+self.ttl))
            cx.execute('COMMIT')
            return {'status':'allowed','lease':lease}


# On Windows builds without AF_UNIX support, importing app.main must still work.
# The optional Linux-only authority is unavailable rather than falling back to TCP.
_UnixBase = getattr(socketserver, 'UnixStreamServer', None)
if _UnixBase is None:
    class _UnixBase:
        def __init__(self,*args,**kwargs):
            raise OSError('Unix-socket admission requires an approved Linux host')


class AdmissionServer(socketserver.ThreadingMixIn,_UnixBase):
    daemon_threads=True
    allow_reuse_address=False
    request_queue_size=64
    max_handlers=32
    def __init__(self,path,ledger,secret):
        validate_secret(secret)
        path=Path(path)
        parent=path.parent
        info=parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077
                or (hasattr(os,'geteuid') and info.st_uid != os.geteuid())):
            raise ValueError('Admission socket parent must be a private 0700 directory')
        if path.exists() or path.is_symlink():raise FileExistsError('Refusing existing admission socket')
        self.ledger=ledger
        self.secret=secret
        self.slots=threading.BoundedSemaphore(self.max_handlers)
        super().__init__(str(path),AdmissionHandler)
        os.chmod(path,0o600)


    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()


class AdmissionHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            data=bytearray()
            deadline=time.monotonic()+1.0
            while b'\n' not in data and len(data)<=MAX_MESSAGE:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError
                self.request.settimeout(remaining)
                block=self.request.recv(min(1024,MAX_MESSAGE+1-len(data)))
                if not block:break
                data.extend(block)
            line=bytes(data)
            if len(line)>MAX_MESSAGE or not line.endswith(b'\n'):
                response={'status':'denied'}
            else:
                response=self.server.ledger.execute(json.loads(line),self.server.secret)
        except (ValueError,TypeError,UnicodeDecodeError,RecursionError):
            response={'status':'denied'}
        except (sqlite3.Error,OSError):
            response={'status':'unavailable'}
        try:self.wfile.write(_json(response)+b'\n')
        except OSError:pass


def main():
    parser=argparse.ArgumentParser(description='Private local SSE admission authority (no HTTP ingress)')
    parser.add_argument('--socket',required=True)
    parser.add_argument('--db',required=True)
    parser.add_argument('--per-session',type=int,default=2)
    parser.add_argument('--per-organization',type=int,default=24)
    parser.add_argument('--total',type=int,default=64)
    parser.add_argument('--identity-db',help='Read-only WFS session and grant database; enables mandatory assertions')
    args=parser.parse_args()
    secret=os.environ.get('WFS_SSE_EDGE_SECRET','')
    validate_secret(secret)
    issuer=verifier=None
    if args.identity_db:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from .sse_identity import AssertionIssuer,AssertionVerifier,SessionPolicy
        if Path(args.db).resolve()==Path(args.identity_db).resolve():
            parser.error('Quota and identity databases must be separate')
        policy=SessionPolicy(args.identity_db)
        signing_key=Ed25519PrivateKey.generate()
        issuer=AssertionIssuer(policy,signing_key)
        verifier=AssertionVerifier(policy,signing_key.public_key())
    ledger=AdmissionLedger(args.db,issuer=issuer,verifier=verifier,per_session=args.per_session,
                           per_organization=args.per_organization,total=args.total)
    with AdmissionServer(args.socket,ledger,secret) as server:
        server.serve_forever(poll_interval=0.1)

if __name__=='__main__':main()
