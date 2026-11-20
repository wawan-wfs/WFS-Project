"""Fail-closed UDS or operator-pinned mTLS client for preview authorization.

No SQLite, Docker API or project filesystem access is required in a dynamic-only
preview gateway. The dashboard host alone stores/revokes dashboard sessions.
"""
from __future__ import annotations

import hmac
import http.client
import json
import hashlib
import secrets
import time
import os
from pathlib import Path
import socket
import stat
import struct
import ssl
from urllib.parse import urlsplit

class AuthorityUnavailable(RuntimeError):
    pass


class _Connection(http.client.HTTPConnection):
    def __init__(self, path: Path, uid: int):
        super().__init__('localhost', timeout=3)
        self.path, self.uid = path, uid

    def connect(self):
        if not hasattr(socket,'SO_PEERCRED'):
            raise AuthorityUnavailable('Linux peer credentials required')
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            self.sock.settimeout(3)
            self.sock.connect(str(self.path))
            peer=self.sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
            _pid,uid,_gid=struct.unpack('3i',peer)
            if uid!=self.uid:
                raise AuthorityUnavailable('Authorization service UID mismatch')
        except Exception:
            self.sock.close()
            self.sock=None
            raise


def _settings():
    raw=os.getenv('WFS_PREVIEW_AUTHORITY_SOCKET','').strip()
    key=os.getenv('WFS_PREVIEW_AUTHORITY_KEY','')
    uid=os.getenv('WFS_PREVIEW_AUTHORITY_UID','')
    if not raw or not os.path.isabs(raw) or '..' in Path(raw).parts or not uid.isdecimal() or len(key)<32:
        raise AuthorityUnavailable('Independent authorization service not configured')
    p=Path(raw)
    try:
        root=p.parent
        st=root.lstat()
        sd=p.lstat()
        if not stat.S_ISDIR(st.st_mode) or not stat.S_ISSOCK(sd.st_mode):
            raise AuthorityUnavailable('Authorization endpoint is not a private Unix socket')
        if st.st_mode & 0o022 or sd.st_mode & 0o022:
            raise AuthorityUnavailable('Authorization socket directory or socket writable by others')
        if sd.st_uid!=int(uid) or st.st_uid not in (0,int(uid)):
            raise AuthorityUnavailable('Authorization socket owner mismatch')
        if p.is_symlink() or root.is_symlink():
            raise AuthorityUnavailable('Authorization socket symlink forbidden')
    except OSError:
        raise AuthorityUnavailable('Authorization socket unavailable') from None
    return p, int(uid), key


def _trusted_file(raw: str, *, key: bool = False) -> Path:
    """Reject relative/symlink/writable service credentials before SSL loads them."""
    if os.name != 'posix' or not hasattr(os, 'getuid'):
        raise AuthorityUnavailable('mTLS credential validation requires Linux/POSIX service host')
    if not raw or not os.path.isabs(raw) or '..' in Path(raw).parts:
        raise AuthorityUnavailable('Absolute trusted TLS credential path required')
    path = Path(raw)
    try:
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o022:
            raise AuthorityUnavailable('TLS credential is a symlink or writable by others')
        if key and (meta.st_mode & 0o077 or meta.st_uid not in (0, os.getuid())):
            raise AuthorityUnavailable('TLS private key permissions/owner unsafe')
    except OSError:
        raise AuthorityUnavailable('TLS credential file unavailable') from None
    return path


def _mtls_settings():
    """No HTTP downgrade, proxy fallback, CA bypass or user-controlled target."""
    endpoint = os.getenv('WFS_PREVIEW_AUTHORITY_URL', '').strip()
    shared_key = os.getenv('WFS_PREVIEW_AUTHORITY_KEY', '')
    if len(shared_key) < 32:
        raise AuthorityUnavailable('Preview authority signing key not configured')
    try:
        address = urlsplit(endpoint)
        if (address.scheme != 'https' or not address.hostname or address.username or
                address.password or address.path not in ('','/') or address.query or
                address.fragment or address.port is None or not 1 <= address.port <= 65535):
            raise ValueError('Endpoint must be exact HTTPS host:port')
        # No ambiguous host encoding and no userinfo, IPv6 parsing is handled by urlsplit.
        if any(ch.isspace() for ch in endpoint) or len(endpoint) > 255:
            raise ValueError('Malformed endpoint')
    except ValueError:
        raise AuthorityUnavailable('Explicit trusted mTLS authority origin required') from None
    ca = _trusted_file(os.getenv('WFS_PREVIEW_AUTHORITY_CA', ''))
    cert = _trusted_file(os.getenv('WFS_PREVIEW_AUTHORITY_CERT', ''))
    keyfile = _trusted_file(os.getenv('WFS_PREVIEW_AUTHORITY_CLIENT_KEY', ''), key=True)
    try:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        context.load_cert_chain(certfile=str(cert), keyfile=str(keyfile))
    except (ssl.SSLError, OSError, ValueError):
        raise AuthorityUnavailable('TLS verification credentials invalid') from None
    return address.hostname, address.port, context, shared_key


def _connection_and_key():
    mode = os.getenv('WFS_PREVIEW_AUTHORITY_MODE', 'uds').strip().lower()
    if mode == 'uds':
        sock, uid, key = _settings()
        return _Connection(sock, uid), key
    if mode == 'mtls':
        host, port, context, key = _mtls_settings()
        return http.client.HTTPSConnection(host=host, port=port, context=context, timeout=3), key
    raise AuthorityUnavailable('Unrecognized authority transport; no fallback')


def call(action: str, payload: dict) -> dict:
    if action not in ('ticket','exchange','verify'):
        raise AuthorityUnavailable('Unsupported authority operation')
    connection,key=_connection_and_key()
    body=json.dumps(payload,sort_keys=True,separators=(',',':')).encode('utf-8')
    if len(body)>1024:
        raise AuthorityUnavailable('Authorization request exceeds size limit')
    path='/internal/'+action
    timestamp=str(int(time.time()))
    nonce=secrets.token_hex(16)
    msg=(timestamp+'\n'+nonce+'\n'+path+'\n').encode()+body
    signature=hmac.new(key.encode(),msg,hashlib.sha256).hexdigest()
    try:
        connection.request('POST',path,body=body,headers={
            'Content-Type':'application/json','Content-Length':str(len(body)),
            'X-WFS-Authority-Time':timestamp,'X-WFS-Authority-Nonce':nonce,
            'X-WFS-Authority-Signature':signature,'Accept':'application/json'})
        response=connection.getresponse()
        buf=response.read(2049)
        if len(buf)>2048 or response.status!=200:
            raise AuthorityUnavailable('Authorization denied or service failed')
        result=json.loads(buf)
        if not isinstance(result,dict) or result.get('ok') is not True:
            raise AuthorityUnavailable('Invalid authorization response')
        return result
    except (OSError, ValueError, http.client.HTTPException, TimeoutError):
        raise AuthorityUnavailable('Authorization service unreachable or invalid') from None
    finally:
        connection.close()


def enabled():
    # Mandatory production mode is fail-closed even when the endpoint is missing.
    return (os.getenv('WFS_PREVIEW_AUTHORITY_REQUIRED') == '1' or
            os.getenv('WFS_PREVIEW_AUTHORITY_MODE','uds').strip().lower() != 'uds' or
            bool(os.getenv('WFS_PREVIEW_AUTHORITY_SOCKET','').strip()) or
            bool(os.getenv('WFS_PREVIEW_AUTHORITY_URL','').strip()))
