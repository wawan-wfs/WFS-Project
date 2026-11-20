"""Authorization and admission regressions without external infrastructure."""
import asyncio
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from test_system import PASSWORD
from app import auth, main, store
from app.sse_admission import AdmissionClient, AdmissionLedger, signature
from app.sse_identity import AssertionIssuer, AssertionVerifier, SessionPolicy, _encode
from app.sse_limits import LeasedStream, StreamLimit

SECRET = 'offline-wfs-v41-sse-test-fixture-credential'


class LocalAssertions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.db = root/'identity.sqlite'
        self.edge = root/'edge.sqlite'
        for key, value in dict(DATA=root, DB=self.db, PROJECTS=root/'projects').items():
            p = patch.object(store, key, value)
            p.start()
            self.addCleanup(p.stop)
        store.init_db()
        self.user = store.create_user('v41-builder', auth.hash_password(PASSWORD), 'developer')
        self.pid = store.create_project('Private app','Create private accessible website','demo','static',visibility='private')['id']
        self.foreign = store.provision_organization('v41-foreign','Other tenant','v41-other',auth.hash_password(PASSWORD))
        self.other_pid = store.create_project('Other app','Create other accessible website','demo','static',created_by=self.foreign)['id']
        self.token = 'fixture-v41-bearer'
        store.session_create(self.token, '2999-01-01T00:00:00+00:00', self.user)
        store.session_create('other-v41-bearer','2999-01-01T00:00:00+00:00',self.foreign)
        self.sid = hashlib.sha256(self.token.encode()).hexdigest()
        self.policy = SessionPolicy(self.db)
        self.reopen()

    def reopen(self):
        self.key = Ed25519PrivateKey.generate()
        self.issuer = AssertionIssuer(self.policy,self.key)
        self.ledger = AdmissionLedger(self.edge,per_organization=1,total=2,issuer=self.issuer,
            verifier=AssertionVerifier(self.policy,self.key.public_key()))

    def request(self, action, **fields):
        stamp=fields.pop('stamp',int(time.time()))
        nonce=fields.pop('nonce',os.urandom(16).hex())
        data = dict(action=action,timestamp=stamp,nonce=nonce,**fields)
        return self.ledger.execute({**data,'mac':signature(SECRET,data)}, SECRET)

    def grant(self):
        store.manage_project_access(self.pid,'owner',user_id=self.user,permission='view')

    def test_issuer_requires_real_bearer_and_live_tenant_grant(self):
        self.assertEqual(self.request('authorize',token=self.sid,project=None)['status'],'unauthorized')
        self.assertEqual(self.request('authorize',token=self.token,project=self.pid)['status'],'unauthorized')
        self.assertEqual(self.request('authorize',token=self.token,project=self.other_pid)['status'],'unauthorized')
        self.grant()
        issue=self.request('authorize',token=self.token,project=self.pid)
        self.assertEqual(issue['status'],'allowed')
        self.assertNotIn(self.token, str(issue))
        self.assertEqual(issue['assertion']['claims']['project'],self.pid)
        self.assertEqual(self.request('acquire',assertion=issue['assertion'])['status'],'allowed')
        self.assertEqual(self.request('acquire',session_key=self.sid,organization='default')['status'],'unauthorized')

    def test_claim_rechecks_revocation_and_mfa_before_quota_write(self):
        self.grant()
        grant=self.issuer.issue(self.token,self.pid)
        store.manage_project_access(self.pid,'owner',user_id=self.user,remove=True)
        self.assertEqual(self.request('acquire',assertion=grant)['status'],'unauthorized')
        assertion=self.issuer.issue(self.token,None)
        store.set_organization_mfa_policy('default',True)
        self.assertIsNone(self.issuer.issue(self.token,None))
        self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')
        store.set_organization_mfa_policy('default',False)
        assertion=self.issuer.issue(self.token,None)
        store.session_delete(self.token)
        self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')

    def test_signed_wrong_issuer_audience_expiry_and_tamper_are_rejected(self):
        base=self.issuer.issue(self.token,None)['claims']
        for fields in ({'iss':'other'},{'aud':'other'},{'iat':base['iat']-8,'exp':base['iat']},
                       {'exp':base['exp']+30},{'org':'v41-foreign'}):
            with self.subTest(fields=fields):
                claims={**base,**fields}
                assertion={'claims':claims,'signature':self.key.sign(_encode(claims)).hex()}
                self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')
        assertion=self.issuer.issue(self.token,None)
        assertion['claims']['jti']='0'*32
        self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')

    def test_replay_restart_ttl_and_two_independent_organization_caps(self):
        assertion=self.issuer.issue(self.token,None)
        first=self.request('acquire',assertion=assertion)
        self.assertEqual(first['status'],'allowed')
        self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')
        second=self.request('acquire',assertion=self.issuer.issue('other-v41-bearer',None))
        self.assertEqual(second['status'],'allowed')
        self.reopen()
        self.assertEqual(self.request('acquire',assertion=assertion)['status'],'unauthorized')
        self.assertEqual(self.request('acquire',assertion=self.issuer.issue(self.token,None))['status'],'denied')
        with sqlite3.connect(self.edge) as cx:
            cx.execute('UPDATE leases SET expires=0 WHERE lease=?',(first['lease'],))
        self.assertEqual(self.request('acquire',assertion=self.issuer.issue(self.token,None))['status'],'allowed')
        self.assertEqual(self.request('release',lease=second['lease'])['status'],'allowed')
        self.assertEqual(self.request('release',lease=second['lease'])['status'],'allowed')

    def test_forward_skew_nonce_cannot_replay_after_original_retention(self):
        nonce='b'*32
        base=int(time.time())
        with patch('app.sse_admission.time.time',return_value=base):
            self.assertEqual(self.request('release',lease='0'*32,nonce=nonce,stamp=base+30)['status'],'allowed')
        with patch('app.sse_admission.time.time',return_value=base+45):
            self.assertEqual(self.request('release',lease='0'*32,nonce=nonce,stamp=base+30)['status'],'denied')


class SSECancellation(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_admission_releases_a_late_reservation(self):
        client=AdmissionClient('/tmp/nonexistent',SECRET)
        started=threading.Event()
        proceed=threading.Event()
        loop=asyncio.get_running_loop()
        released=asyncio.Event()
        def acquire():
            started.set()
            self.assertTrue(proceed.wait(3))
            return 'a'*32
        def release(lease):
            self.assertEqual(lease,'a'*32)
            loop.call_soon_threadsafe(released.set)
        with patch.object(client,'acquire',side_effect=acquire),patch.object(client,'release',side_effect=release):
            task=asyncio.create_task(client.acquire_async())
            self.assertTrue(await asyncio.to_thread(started.wait,2))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            proceed.set()
            await asyncio.wait_for(released.wait(),2)

    async def test_failed_send_releases_even_before_first_chunk(self):
        limit=StreamLimit(total=1)
        lease=limit.acquire('one')
        async def payload():
            yield 'body'
        async def send(_):
            raise OSError('Client closed')
        response=main.EventStreamingResponse(LeasedStream(payload(),limit,lease))
        with self.assertRaises(Exception):
            await response({'type':'http','asgi':{'spec_version':'2.4'}},None,send)
        self.assertIsNotNone(limit.acquire('two'))

    async def test_assertion_mode_misconfiguration_returns_503(self):
        request=type('Request',(),{'headers':{}})()
        with patch.dict(os.environ,{'WFS_SSE_EDGE_ASSERTIONS':'1','WFS_SSE_EDGE_SOCKET':''}), \
             patch.object(store,'session_account',return_value={'id':'account','organization_id':'default'}):
            with self.assertRaises(HTTPException) as caught:
                await main.live_events(request,after_id=0,token='session')
        self.assertEqual(caught.exception.status_code,503)
