"""Local two-tenant multi-tab stream pressure with real SQLite grants, not edge proof."""
import asyncio
from datetime import datetime,timedelta,timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_system import PASSWORD
from app import store,main,auth
from app.sse_limits import StreamLimit


class Request:
    headers={}
    async def is_disconnected(self):return False


class MultiTenantSSEV38(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'wfs.sqlite3'),patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.a=store.provision_organization('v38-a','Tenant A','tenanta',auth.hash_password(PASSWORD))
        self.b=store.provision_organization('v38-b','Tenant B','tenantb',auth.hash_password(PASSWORD))
        self.pa=store.create_project('A','Build isolated artifact for tenant A','demo','static',created_by=self.a)['id']
        self.pb=store.create_project('B','Build isolated artifact for tenant B','demo','static',created_by=self.b)['id']
        expires=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(timespec='seconds')
        store.session_create('a-session',expires,user_id=self.a)
        store.session_create('b-session',expires,user_id=self.b)
        store.operator_event(self.pa,'Agent A','done','tenant-A-only')
        store.operator_event(self.pb,'Agent B','done','tenant-B-only')
        self.limiter=StreamLimit(per_session=2,total=3)
        self.p=patch.object(main,'stream_limit',self.limiter)
        self.p.start()

    async def asyncTearDown(self):
        self.p.stop()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    async def test_many_tabs_and_delayed_consumers_keep_isolated_slots(self):
        from fastapi import HTTPException
        tabs=[]
        try:
            tabs.append(await main.live_events(Request(),after_id=0,once=True,token='a-session'))
            tabs.append(await main.live_events(Request(),after_id=0,once=True,token='a-session'))
            with self.assertRaises(HTTPException) as cm:
                await main.live_events(Request(),after_id=0,once=True,token='a-session')
            self.assertEqual(cm.exception.status_code,429)
            b=await main.live_events(Request(),after_id=0,once=True,token='b-session')
            tabs.append(b)
            self.assertEqual(self.limiter._total,3)
            # A slow client that has not consumed its stream holds its slot.
            first=await tabs[0].body_iterator.__anext__()
            self.assertIn('wfs-stream-open',first)
            self.assertEqual(self.limiter._total,3)
            chunks=[]
            async for c in tabs[0].body_iterator:chunks.append(c)
            self.assertIn('tenant-A-only',''.join(chunks))
            self.assertNotIn('tenant-B-only',''.join(chunks))
            tabs.pop(0)
            self.assertEqual(self.limiter._total,2)
            # Tenant B receives only its independently scoped events.
            got=''.join([c async for c in b.body_iterator])
            self.assertIn('tenant-B-only',got)
            self.assertNotIn('tenant-A-only',got)
            tabs.remove(b)
        finally:
            for stream in tabs:
                await stream.body_iterator.aclose()
        self.assertEqual(self.limiter._total,0)

if __name__=='__main__':unittest.main()
