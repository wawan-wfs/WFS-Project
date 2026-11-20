"""One-time initialization: strong password, PBKDF2 hash and session secret."""
from __future__ import annotations
import hashlib
import os
import secrets
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
TARGET=ROOT/'.env'

def create(password=None,force=False):
    if TARGET.exists() and not force:raise FileExistsError('File .env sudah ada: bootstrap tidak menimpa credential lama')
    pwd=password or secrets.token_urlsafe(24)
    salt=secrets.token_hex(16)
    rounds=260000
    digest=hashlib.pbkdf2_hmac('sha256',pwd.encode(),bytes.fromhex(salt),rounds).hex()
    template=(ROOT/'.env.example').read_text(encoding='utf-8')
    template=template.replace('__HASH__',f'pbkdf2_sha256:{rounds}:{salt}:{digest}')
    template=template.replace('__SECRET__',secrets.token_hex(48))
    TARGET.write_text(template,encoding='utf-8')
    try:TARGET.chmod(0o600)
    except OSError:pass
    return pwd

if __name__=='__main__':
    try:
        pwd=create()
        print('\nWFS PROJECT SETUP BERHASIL')
        print('Password administrator (simpan di password manager; tidak akan ditampilkan lagi):')
        print(pwd)
        print('\nFile .env disiapkan; ubah OPENAI_API_KEY untuk fitur agent AI.')
    except FileExistsError as exc:print(str(exc));raise SystemExit(1)
