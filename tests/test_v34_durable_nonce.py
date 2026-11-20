"""SQLite durable nonce evidence, no external host or TLS proof."""
from __future__ import annotations
import hmac
import hashlib
import json
import secrets
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import store
from app.preview_authority import app, _consume_nonce

KEY = 'durable-nonce-auth-signing-secret-32-bytes-minimum'

class DurableNonceV34(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wfs-v34-nonce-')
        self.addCleanup(self.temp.cleanup)
        p=Path(self.temp.name)
        patches=[patch.object(store,'DATA',p),patch.object(store,'DB',p/'db.sqlite3'),
                 patch.object(store,'PROJECTS',p/'projects')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        store.init_db()

    def signed(self,nonce):
        body=json.dumps({'ticket':'z'*30},sort_keys=True,separators=(',',':')).encode()
        stamp=str(int(time.time()))
        path='/internal/ticket'
        sig=hmac.new(KEY.encode(),(stamp+'\n'+nonce+'\n'+path+'\n').encode()+body,hashlib.sha256).hexdigest()
        return body,{'X-WFS-Authority-Time':stamp,'X-WFS-Authority-Nonce':nonce,
                     'X-WFS-Authority-Signature':sig,'Content-Type':'application/json'}

    def test_replay_is_denied_across_app_client_lifetimes(self):
        nonce=secrets.token_hex(16)
        body,headers=self.signed(nonce)
        with patch.dict('os.environ',{'WFS_PREVIEW_AUTHORITY_KEY':KEY}), patch('app.preview_authority.ticket_info',side_effect=ValueError):
            with TestClient(app) as client:
                self.assertEqual(client.post('/internal/ticket',content=body,headers=headers).status_code,404)
            with TestClient(app) as fresh_client:
                self.assertEqual(fresh_client.post('/internal/ticket',content=body,headers=headers).status_code,403)
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM preview_authority_nonces WHERE nonce=?',(nonce,)).fetchone()[0],1)

    def test_locked_or_missing_db_denies_without_memory_fallback(self):
        # When the trusted store cannot be opened, a signed request is denied.
        with patch.object(store,'connect',side_effect=sqlite3.OperationalError('unavailable')):
            self.assertFalse(_consume_nonce(secrets.token_hex(16),int(time.time())))

    def test_parallel_reuse_admits_only_one_request(self):
        nonce=secrets.token_hex(16)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _: _consume_nonce(nonce,int(time.time())),range(8)))
        self.assertEqual(results.count(True),1)
        self.assertEqual(results.count(False),7)

    def test_old_nonces_expire_and_uniqueness_remains(self):
        old=secrets.token_hex(16)
        with store.connect() as cx:cx.execute('INSERT INTO preview_authority_nonces(nonce,used_at) VALUES(?,?)',(old,int(time.time())-200))
        self.assertTrue(_consume_nonce(secrets.token_hex(16),int(time.time())))
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM preview_authority_nonces WHERE nonce=?',(old,)).fetchone()[0],0)
        current=secrets.token_hex(16)
        self.assertTrue(_consume_nonce(current,int(time.time())))
        self.assertFalse(_consume_nonce(current,int(time.time())))

if __name__=='__main__':unittest.main()
