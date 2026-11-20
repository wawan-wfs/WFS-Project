"""Local TOTP / recovery verification (RFC 6238), secret encryption at rest.

Never log one-time codes, recovery codes, or otpauth provisioning URI.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from . import config

STEP_SECONDS = 30
MAX_SKEW_STEPS = 1


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _key() -> bytes:
    if not config.SESSION_KEY:
        raise RuntimeError('WFS_SESSION_SECRET not configured')
    return hashlib.sha256(b'wfs-mfa-secrets-v1\x00' + config.SESSION_KEY.encode('utf-8')).digest()


def seal(secret: str, user_id: str) -> str:
    nonce = os.urandom(12)
    encrypted = AESGCM(_key()).encrypt(nonce, secret.encode('ascii'), user_id.encode('utf-8'))
    return base64.urlsafe_b64encode(nonce + encrypted).decode('ascii')


def unseal(value: str, user_id: str) -> str:
    raw = base64.urlsafe_b64decode(value.encode('ascii'))
    if len(raw) < 28:
        raise ValueError('invalid encrypted secret')
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], user_id.encode('utf-8')).decode('ascii')


def otp(secret: str, step: int) -> str:
    raw = base64.b32decode(secret.upper() + '=' * ((-len(secret)) % 8))
    digest = hmac.new(raw, struct.pack('>Q', int(step)), hashlib.sha1).digest()
    offset = digest[-1] & 0x0f
    number = (int.from_bytes(digest[offset:offset+4], 'big') & 0x7fffffff) % 1000000
    return f'{number:06d}'


def matching_step(secret: str, value: str, timestamp: float | None = None) -> int | None:
    if not isinstance(value, str) or len(value) != 6 or not value.isascii() or not value.isdecimal():
        return None
    at = int((timestamp if timestamp is not None else time.time()) // STEP_SECONDS)
    # Prefer current code; tolerate one 30s step of device drift.
    for offset in (0, -1, 1):
        step = at + offset
        if step >= 0 and hmac.compare_digest(otp(secret, step), value):
            return step
    return None


def uri(secret: str, username: str) -> str:
    label = quote('WFS PROJECT:' + username, safe='')
    return f'otpauth://totp/{label}?secret={secret}&issuer=WFS%20PROJECT&algorithm=SHA1&digits=6&period=30'


def recovery_codes() -> list[str]:
    return ['WFS-' + secrets.token_hex(10).upper() for _ in range(8)]


def recovery_hash(user_id: str, code: str) -> str:
    return hashlib.sha256((user_id + ':' + code.upper()).encode('ascii')).hexdigest()
