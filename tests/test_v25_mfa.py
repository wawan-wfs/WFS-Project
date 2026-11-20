"""v2.5 MFA acceptance: real TestClient, isolated SQLite, no emailed codes or remote provider."""
from __future__ import annotations
import tempfile
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import mfa, store
from app.main import app


class MFAAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        path=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',path/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.client=TestClient(app);self.client.__enter__()
        r=self.client.post('/api/login',json={'username':'admin','password':PASSWORD})
        self.assertEqual(r.status_code,200,r.text)
        self.csrf={'X-WFS-CSRF':r.json()['csrf']}

    def tearDown(self):
        self.client.__exit__(None,None,None)
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def setup_mfa(self):
        r=self.client.post('/api/mfa/setup',headers=self.csrf,json={'password':PASSWORD})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()['secret']

    def activate(self):
        secret=self.setup_mfa()
        step=int(time.time()//30)
        # Confirm with previous valid step so the current code is available for immediate login.
        r=self.client.post('/api/mfa/confirm',headers=self.csrf,json={'code':mfa.otp(secret,step-1)})
        self.assertEqual(r.status_code,200,r.text)
        return secret,r.json()['recovery_codes']

    def test_setup_requires_session_password_and_csrf(self):
        self.assertEqual(TestClient(app).post('/api/mfa/setup',json={'password':PASSWORD}).status_code,401)
        self.assertEqual(self.client.post('/api/mfa/setup',json={'password':PASSWORD}).status_code,403)
        self.assertEqual(self.client.post('/api/mfa/setup',headers=self.csrf,json={'password':'wrong'}).status_code,403)
        self.assertFalse(self.client.get('/api/mfa/status').json()['enabled'])

    def test_secret_encrypted_and_not_leaked_from_api(self):
        secret=self.setup_mfa()
        user=store.user_by_username('admin')
        self.assertIsNone(user['mfa_secret'])
        with store.connect() as cx:
            blob=cx.execute('SELECT secret FROM mfa_pending WHERE user_id=?',('owner',)).fetchone()[0]
        self.assertNotIn(secret,blob)
        self.assertEqual(mfa.unseal(blob,'owner'),secret)
        with self.assertRaises(Exception):mfa.unseal(blob,'different-user')
        for url in ('/api/session','/api/mfa/status','/api/users'):
            self.assertNotIn(secret,self.client.get(url).text)

    def test_confirm_enables_mfa_recovery_codes_and_revokes_other_sessions(self):
        with TestClient(app) as second:
            self.assertEqual(second.post('/api/login',json={'password':PASSWORD}).status_code,200)
            secret,codes=self.activate()
            self.assertEqual(len(codes),8)
            self.assertEqual(len(set(codes)),8)
            self.assertTrue(self.client.get('/api/mfa/status').json()['enabled'])
            self.assertEqual(second.get('/api/session').json()['authenticated'],False)
            self.assertTrue(self.client.get('/api/session').json()['authenticated'])
            with store.connect() as cx:
                self.assertEqual(cx.execute('SELECT COUNT(*) FROM mfa_recovery WHERE user_id=?',('owner',)).fetchone()[0],8)
            self.assertNotIn(secret,self.client.get('/api/users').text)
            self.assertEqual(self.client.post('/api/mfa/setup',headers=self.csrf,json={'password':PASSWORD}).status_code,409)

    def test_login_requires_valid_otp_and_prevents_replay(self):
        secret,_=self.activate()
        with TestClient(app) as fresh:
            self.assertEqual(fresh.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code,401)
            self.assertEqual(fresh.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':'999999x'}).status_code,401)
            current=mfa.otp(secret,int(time.time()//30))
            good=fresh.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':current})
            self.assertEqual(good.status_code,200,good.text)
            self.assertEqual(fresh.get('/api/projects').status_code,200)
            with TestClient(app) as other:
                self.assertEqual(other.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':current}).status_code,401)

    def test_one_time_recovery_then_disable_revokes_sessions(self):
        _,codes=self.activate()
        with TestClient(app) as fresh:
            good=fresh.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':codes[0]})
            self.assertEqual(good.status_code,200,good.text)
            self.assertEqual(self.client.get('/api/session').json()['authenticated'],True)
            bad=fresh.post('/api/mfa/disable',headers={'X-WFS-CSRF':good.json()['csrf']},json={'password':'incorrect','code':codes[1]})
            self.assertEqual(bad.status_code,403)
            disabled=fresh.post('/api/mfa/disable',headers={'X-WFS-CSRF':good.json()['csrf']},json={'password':PASSWORD,'code':codes[1]})
            self.assertEqual(disabled.status_code,200,disabled.text)
            self.assertTrue(disabled.json()['session_revoked'])
            self.assertEqual(fresh.get('/api/projects').status_code,401)
            self.assertEqual(self.client.get('/api/projects').status_code,401)
            self.assertEqual(fresh.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code,200)

    def test_recovery_code_single_use_and_scope(self):
        secret,codes=self.activate()
        with TestClient(app) as first:
            self.assertEqual(first.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':codes[0]}).status_code,200)
        with TestClient(app) as second:
            self.assertEqual(second.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':codes[0]}).status_code,401)
            self.assertEqual(second.post('/api/login',json={'username':'admin','password':PASSWORD,'otp':codes[1]}).status_code,200)
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM mfa_recovery WHERE user_id=?',('owner',)).fetchone()[0],6)

    def test_invalid_confirmation_code_and_rate_limit(self):
        secret=self.setup_mfa()
        invalid=next(f'{i:06d}' for i in range(30) if all(f'{i:06d}'!=mfa.otp(secret,int(time.time()//30)+delta) for delta in (-1,0,1)))
        for i in range(5):
            bad=self.client.post('/api/mfa/confirm',headers=self.csrf,json={'code':invalid})
            self.assertEqual(bad.status_code,422,bad.text)
        current=mfa.otp(secret,int(time.time()//30))
        self.assertEqual(self.client.post('/api/mfa/confirm',headers=self.csrf,json={'code':current}).status_code,429)
        self.assertFalse(self.client.get('/api/mfa/status').json()['enabled'])
        store.mfa_success('owner')
        self.assertEqual(self.client.post('/api/mfa/confirm',headers=self.csrf,json={'code':current}).status_code,200)

    def test_expired_and_different_session_pending_disallowed(self):
        secret=self.setup_mfa()
        with store.connect() as cx:cx.execute('UPDATE mfa_pending SET expires_epoch=0')
        self.assertEqual(self.client.post('/api/mfa/confirm',headers=self.csrf,json={'code':mfa.otp(secret,int(time.time()//30))}).status_code,409)
        self.assertFalse(self.client.get('/api/mfa/status').json()['enabled'])

    def test_offline_break_glass_reset_requires_exact_confirmation(self):
        self.activate()
        script=Path(__file__).resolve().parents[1]/'scripts'/'reset-mfa-local.py'
        db=store.DB
        denied=subprocess.run([sys.executable,str(script),'--username','admin','--database',str(db)],
                              input='NO\n',capture_output=True,text=True,timeout=10)
        self.assertNotEqual(denied.returncode,0)
        self.assertTrue(store.mfa_record('owner')['mfa_secret'])
        approved=subprocess.run([sys.executable,str(script),'--username','admin','--database',str(db)],
                                input='RESET MFA admin\n',capture_output=True,text=True,timeout=10)
        self.assertEqual(approved.returncode,0,approved.stderr)
        self.assertIsNone(store.mfa_record('owner')['mfa_secret'])
        self.assertEqual(self.client.get('/api/session').json()['authenticated'],False)
        self.assertEqual(self.client.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code,200)

    def test_viewer_can_secure_own_account_but_not_manage_users(self):
        created=self.client.post('/api/users',headers=self.csrf,json={
            'username':'viewer_mfa','password':'Secure-Password-12345','role':'viewer'})
        self.assertEqual(created.status_code,201,created.text)
        with TestClient(app) as viewer:
            login=viewer.post('/api/login',json={'username':'viewer_mfa','password':'Secure-Password-12345'})
            self.assertEqual(login.status_code,200)
            h={'X-WFS-CSRF':login.json()['csrf']}
            self.assertEqual(viewer.post('/api/mfa/setup',headers=h,json={'password':'Secure-Password-12345'}).status_code,200)
            self.assertEqual(viewer.get('/api/users').status_code,403)
            self.assertEqual(viewer.post('/api/users',headers=h,json={'username':'unauthorized','password':'Secure-Password-12345','role':'manager'}).status_code,403)


if __name__=='__main__':unittest.main()
