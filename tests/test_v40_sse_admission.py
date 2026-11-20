"""Real local child-process admission checks; does not attest production ingress."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from test_system import PASSWORD  # deterministic bootstrap, never use live credentials
from app import auth,main,store
from app.sse_admission import AdmissionClient,AdmissionLedger,AdmissionUnavailable,signature

SECRET='test-secret-for-wfs-sse-admission-v40-unique-credential'

class FakeRequest:
    headers={}
    async def is_disconnected(self):return False

@unittest.skipUnless(os.name=='posix','Operator admission authority is Linux-only')
class AdmissionProcessV40(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.sock=root/'private.sock';self.db=root/'edge.sqlite';self.wfs=root/'wfs.sqlite'
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',self.wfs),
                      patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.org_a=store.provision_organization('edge-a','Edge A','edgealpha',auth.hash_password(PASSWORD))
        self.org_b=store.provision_organization('edge-b','Edge B','edgebeta',auth.hash_password(PASSWORD))
        self.project_a=store.create_project('Edge A project','Build an isolated app for tenant A','demo','static',created_by=self.org_a)['id']
        self.project_b=store.create_project('Edge B project','Build an isolated app for tenant B','demo','static',created_by=self.org_b)['id']
        exp=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(timespec='seconds')
        store.session_create('edge-session-a',exp,user_id=self.org_a)
        store.session_create('edge-session-b',exp,user_id=self.org_b)
        store.operator_event(self.project_a,'Agent A','done','A_UNIQUE_EVENT')
        store.operator_event(self.project_b,'Agent B','done','B_UNIQUE_EVENT')
        self.proc=None
        self.start()
        self.client=AdmissionClient(self.sock,SECRET)
        self.envpatch=patch.dict(os.environ,{'WFS_SSE_EDGE_SOCKET':str(self.sock),'WFS_SSE_EDGE_SECRET':SECRET})
        self.envpatch.start()

    def start(self):
        env={**os.environ,'WFS_SSE_EDGE_SECRET':SECRET,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
        identity_args=['--identity-db',str(self.wfs)] if getattr(self,'require_assertion',False) else []
        self.proc=subprocess.Popen([sys.executable,'-m','app.sse_admission','--socket',str(self.sock),
             '--db',str(self.db),'--per-session','2','--per-organization','2','--total','3',*identity_args],
             env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            if self.sock.exists():
                try:
                    probe=AdmissionClient(self.sock,SECRET)
                    probe.request('release',lease='0'*32)
                    return
                except AdmissionUnavailable:pass
            if self.proc.poll() is not None:break
            time.sleep(.03)
        if self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=3)
        raise RuntimeError('SSE authority process could not start: '+self.proc.stderr.read().decode(errors='replace')[-1200:])

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=3)
            self.proc.stderr.close()
            self.proc=None
        if self.sock.exists():self.sock.unlink()

    async def asyncTearDown(self):
        self.envpatch.stop()
        self.stop()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    async def test_two_tenants_natted_sessions_concurrent_disconnect_replay(self):
        tabs=[]
        try:
            a=await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
            b=await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
            tabs.extend((a,b))
            with self.assertRaises(HTTPException) as cm:
                await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
            self.assertEqual(cm.exception.status_code,429)
            # Same NAT doesn't affect the independent organization capacity.
            c=await main.live_events(FakeRequest(),after_id=0,token='edge-session-b',once=True)
            tabs.append(c)
            emitted=''.join([chunk async for chunk in a.body_iterator])
            self.assertIn('A_UNIQUE_EVENT',emitted)
            self.assertNotIn('B_UNIQUE_EVENT',emitted)
            tabs.remove(a)
            other=''.join([chunk async for chunk in c.body_iterator])
            self.assertIn('B_UNIQUE_EVENT',other)
            self.assertNotIn('A_UNIQUE_EVENT',other)
            tabs.remove(c)
            # A slot is released even before first body pull.
            await b.body_iterator.aclose()
            tabs.remove(b)
            again=await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
            await again.body_iterator.aclose()
        finally:
            for r in tabs:await r.body_iterator.aclose()

    async def test_crash_restart_ttl_and_fail_closed(self):
        first=self.client.acquire('edge-session-a','edge-a')
        self.assertTrue(first)
        self.stop()
        with self.assertRaises(HTTPException) as exc:
            await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
        self.assertEqual(exc.exception.status_code,503)
        self.start()
        second=self.client.acquire('edge-session-a','edge-a')
        self.assertTrue(second)
        self.assertIsNone(self.client.acquire('edge-session-a','edge-a'))
        with sqlite3.connect(self.db) as cx:
            cx.execute('UPDATE leases SET expires=? WHERE lease=?',(int(time.time())-1,first))
        replacement=self.client.acquire('edge-session-a','edge-a')
        self.assertTrue(replacement)
        self.client.release(second)
        self.client.release(replacement)

    async def test_authenticated_control_and_replay_deny(self):
        unauthenticated=AdmissionClient(self.sock,'other-credential-that-is-not-authorized-123456')
        self.assertEqual(unauthenticated.request('acquire',session_key='a'*64,organization='edge-a')['status'],'denied')
        ledger=AdmissionLedger(self.db,per_session=2,per_organization=2,total=3)
        body={'action':'acquire','timestamp':int(time.time()),'nonce':'a'*32,
              'session_key':'b'*64,'organization':'edge-a'}
        signed={**body,'mac':signature(SECRET,body)}
        self.assertEqual(ledger.execute(signed,SECRET)['status'],'allowed')
        self.assertEqual(ledger.execute(signed,SECRET)['status'],'denied')
        self.assertEqual(ledger.execute({**signed,'organization':'edge-b'},SECRET)['status'],'denied')
        self.assertEqual(ledger.execute({**signed,'nonce':'z'*32},SECRET)['status'],'denied')

    async def test_session_revocation_remains_required_inside_stream(self):
        response=await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
        await response.body_iterator.__anext__()
        store.session_delete('edge-session-a')
        assert not ''.join([chunk async for chunk in response.body_iterator]).strip()

    async def test_assertion_authority_real_uds_when_available(self):
        self.stop()
        self.require_assertion=True
        self.start()
        with patch.dict(os.environ,{'WFS_SSE_EDGE_ASSERTIONS':'1'}):
            a=await main.live_events(FakeRequest(),after_id=0,project_id=self.project_a,token='edge-session-a',once=True)
            body=''.join([chunk async for chunk in a.body_iterator])
            self.assertIn('A_UNIQUE_EVENT',body)
            self.assertNotIn('B_UNIQUE_EVENT',body)
            self.assertEqual(self.client.request('acquire',session_key='a'*64,organization='edge-a')['status'],'unauthorized')
            self.stop()
            with self.assertRaises(HTTPException) as err:
                await main.live_events(FakeRequest(),after_id=0,token='edge-session-a',once=True)
            self.assertEqual(err.exception.status_code,503)


if __name__=='__main__':unittest.main()
