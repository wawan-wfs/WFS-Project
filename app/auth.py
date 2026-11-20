"""Local multiuser RBAC session authentication, revocation and CSRF protection."""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from . import config, store, mfa


def hash_password(password: str, salt: str | None = None, rounds: int = 260000):
    salt = salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),rounds)
    return f'pbkdf2_sha256:{rounds}:{salt}:{digest.hex()}'


def verify_password(password: str, encoded: str):
    try:
        algo, rounds, salt, expected = encoded.split(':')
        if algo != 'pbkdf2_sha256' or not (200000 <= int(rounds) <= 1000000):
            return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError,TypeError):
        return False


def create_session(user_id="owner", device_label="Browser session"):
    token=secrets.token_urlsafe(48)
    expires=(datetime.now(timezone.utc)+timedelta(seconds=config.AUTH_TTL_SECONDS)).isoformat(timespec='seconds')
    store.session_create(token,expires,user_id,device_label)
    return token


def csrf_for(token):
    return hmac.new(config.SESSION_KEY.encode(),('csrf:'+token).encode(),'sha256').hexdigest()


def verify_account_password(account, password):
    row=store.user_by_username(account['username'])
    encrypted=config.PASSWORD_HASH if row and row['id']=='owner' else (row or {}).get('password_hash','')
    return verify_password(password,encrypted)


def verify_second_factor(account, code: str) -> bool:
    row=store.mfa_record(account['id'])
    if not row or not row['mfa_secret'] or store.mfa_locked(account['id']):return False
    if code.startswith('WFS-'):
        ok=store.mfa_consume_code(account['id'],recovery_hash=mfa.recovery_hash(account['id'],code))
    else:
        step=mfa.matching_step(mfa.unseal(row['mfa_secret'],account['id']),code)
        ok=step is not None and store.mfa_consume_code(account['id'],matched_step=step)
    if ok:store.mfa_success(account['id'])
    else:store.mfa_failure(account['id'])
    return ok


def permitted_write(role, path):
    if path.startswith('/api/mfa/') or path.startswith('/api/sessions') or path.endswith('/preview-ticket') or path.endswith('/preview-grants'):return True
    if role=='owner':return True
    if path=='/api/logout':return True
    if role=='manager':
        return not (path.startswith('/api/users') or path=='/api/finops/prices'
                    or (path.startswith('/api/projects/') and path.endswith('/delete')))
    if role=='developer':
        if path=='/api/projects':return True
        return path.startswith('/api/projects/') and (path.endswith(('/revisions','/notes','/access','/members')) or '/members/' in path)
    return False


def require_role(request:Request,*roles):
    account=store.session_account(request.cookies.get('wfs_session',''))
    if account is None:raise HTTPException(401,'Login diperlukan')
    if account['role'] not in roles:raise HTTPException(403,'Role tidak memiliki izin')
    return account


def current_session(request:Request):
    token=request.cookies.get('wfs_session','')
    user=store.session_account(token) if token else None
    if user is None:
        raise HTTPException(status_code=401,detail='Sesi login diperlukan')
    # Secure enrollment exception prevents organization-MFA lockout/deadlock:
    # authenticated un-enrolled accounts can still set up TOTP, view their
    # session policy and sign out, but cannot use project or billing APIs.
    if store.organization_mfa_required(user['id']) and not store.mfa_record(user['id'])['mfa_secret']:
        allowed=('/api/session','/api/logout','/api/meta','/api/workspace/capabilities')
        if request.url.path not in allowed and not request.url.path.startswith(('/api/mfa/','/api/sessions')):
            raise HTTPException(status_code=403,detail='MFA enrollment required by organization policy')
    writing=request.method.upper() not in ('GET','HEAD','OPTIONS') and not request.url.path.endswith(('/preview-ticket','/preview-grants'))
    if writing and not permitted_write(user['role'],request.url.path):
        raise HTTPException(status_code=403,detail='Akses tulis tidak diizinkan untuk role ini')
    # Per-project checks apply to *all* nested endpoints, files, previews, QA, and mutation.
    # Deny unknown and private projects identically (404) to prevent ID probing.
    pid=request.path_params.get('pid')
    if pid and not store.can_access_project(pid,user['id'],write=writing):
        raise HTTPException(404,'Proyek tidak ditemukan')
    jid=request.path_params.get('jid')
    if jid:
        job_pid=store.operator_job_project(jid)
        if not job_pid or not store.can_access_project(job_pid,user['id'],write=writing):
            raise HTTPException(404,'Operator job not found')
    return token


def require_csrf(request:Request,token:str):
    supplied=request.headers.get('x-wfs-csrf','')
    if not supplied or not hmac.compare_digest(supplied,csrf_for(token)):
        raise HTTPException(status_code=403,detail='Token CSRF tidak valid')
    origin=request.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        candidate=urlsplit(origin)
        expected=urlsplit(str(request.base_url))
        if (candidate.scheme,candidate.netloc)!=(expected.scheme,expected.netloc):
            raise HTTPException(status_code=403,detail='Origin tidak diizinkan')


def password_is_set():
    return config.configured()
