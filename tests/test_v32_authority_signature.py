"""Signed service-to-service auth rejects replay, expired timestamps, forged signatures."""
import hashlib
import hmac
import json
import os
import secrets
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.preview_authority import app
from app import store, config

KEY='operator-only-key-long-enough-for-service-to-service-auth'

class SignedAuthorityV32(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wfs-v32-authority-tests-')
        self.addCleanup(self.tmp.cleanup)
        p=Path(self.tmp.name)
        for mock in (patch.object(store,'DATA',p),patch.object(store,'DB',p/'db.sqlite3'),
                     patch.object(store,'PROJECTS',p/'projects'),patch.object(config,'DATA',p),
                     patch.object(config,'PROJECTS',p/'projects')):
            mock.start()
            self.addCleanup(mock.stop)
        store.init_db()

    def signed(self,path='/internal/ticket',body=None,stamp=None,nonce=None,key=KEY):
        body=body or {'ticket':'x'*30}
        raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
        stamp=str(stamp if stamp is not None else int(time.time()))
        nonce=nonce or secrets.token_hex(16)
        msg=(stamp+'\n'+nonce+'\n'+path+'\n').encode()+raw
        sig=hmac.new(key.encode(),msg,hashlib.sha256).hexdigest()
        return raw,{'X-WFS-Authority-Time':stamp,'X-WFS-Authority-Nonce':nonce,
                    'X-WFS-Authority-Signature':sig,'Content-Type':'application/json'}

    def test_unsigned_wrong_signature_expired_and_replay(self):
        with patch.dict(os.environ,{'WFS_PREVIEW_AUTHORITY_KEY':KEY}), patch('app.preview_authority.ticket_info',side_effect=ValueError('missing')):
            with TestClient(app) as c:
                self.assertEqual(c.post('/internal/ticket',json={'ticket':'x'*30}).status_code,403)
                raw,headers=self.signed()
                self.assertEqual(c.post('/internal/ticket',content=raw,headers={**headers,'X-WFS-Authority-Signature':'0'*64}).status_code,403)
                first=c.post('/internal/ticket',content=raw,headers=headers)
                self.assertEqual(first.status_code,404) # auth succeeded; ticket not in DB
                self.assertEqual(c.post('/internal/ticket',content=raw,headers=headers).status_code,403)
                stale,hstale=self.signed(stamp=int(time.time())-90)
                self.assertEqual(c.post('/internal/ticket',content=stale,headers=hstale).status_code,403)
                raw2,h2=self.signed(path='/internal/verify')
                self.assertEqual(c.post('/internal/ticket',content=raw2,headers=h2).status_code,403)
                self.assertEqual(c.get('/internal/ticket',headers=headers).status_code,404)

if __name__=='__main__':unittest.main()
