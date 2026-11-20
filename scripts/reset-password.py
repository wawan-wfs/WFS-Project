"""Offline password rotation: never exposes or saves the new plaintext password."""
from __future__ import annotations
import hashlib
import secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
FILE=ROOT/'.env'
if not FILE.is_file():raise SystemExit('File .env tidak ditemukan; jalankan bootstrap dulu')
password=secrets.token_urlsafe(24)
salt=secrets.token_hex(16)
rounds=260000
hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),rounds).hex()
lines=FILE.read_text(encoding='utf-8').splitlines()
keys={'WFS_ADMIN_PASSWORD_HASH':f'pbkdf2_sha256:{rounds}:{salt}:{hashed}',
      'WFS_SESSION_SECRET':secrets.token_hex(48)}
seen=set();result=[]
for line in lines:
    key=line.split('=',1)[0] if '=' in line else None
    if key in keys:
        result.append(f'{key}={keys[key]}'); seen.add(key)
    else:result.append(line)
for key in keys:
    if key not in seen:result.append(f'{key}={keys[key]}')
FILE.write_text('\n'.join(result)+'\n',encoding='utf-8')
print('RESET PASSWORD SUCCESS. New admin password (save now):')
print(password)
print('Semua session lama ter-invalidasi setelah service restart/rotasi secret. Jalankan docker compose down/up -d.')
