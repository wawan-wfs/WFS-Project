"""Offline SSE admission and cursor tests; these do not certify ingress rate limits."""
from __future__ import annotations
import unittest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
# Establish the isolated test environment before importing app.config.
from test_system import PASSWORD  # noqa: F401
from app import main
from app.sse_limits import StreamLimit


class Request:
    headers = {}
    async def is_disconnected(self):
        return False


def event(i):
    return {'id': i, 'project_id': 'project_A', 'agent': 'Worker', 'state': 'done',
            'message': 'actual_event_%d' % i, 'created_at': '2026-11-08T00:00:00Z'}


class SSEAdmissionV37(unittest.IsolatedAsyncioTestCase):
    async def test_same_session_limit_429_then_release(self):
        limiter = StreamLimit(per_session=2, total=3)
        with patch.object(main, 'stream_limit', limiter), \
             patch.object(main.store, 'session_valid', return_value=True), \
             patch.object(main.store, 'session_account', return_value={'id': 'acct', 'organization_id': 'default'}), \
             patch.object(main.store, 'organization_mfa_required', return_value=False), \
             patch.object(main.store, 'activity_cursor', return_value={'events': []}):
            one = await main.live_events(Request(), after_id=0, once=True, token='session1')
            two = await main.live_events(Request(), after_id=0, once=True, token='session1')
            with self.assertRaises(HTTPException) as cm:
                await main.live_events(Request(), after_id=0, once=True, token='session1')
            self.assertEqual(cm.exception.status_code, 429)
            self.assertEqual(cm.exception.headers['Retry-After'], '3')
            self.assertNotIn('session1', str(limiter._active))
            async for _ in one.body_iterator:
                pass
            third = await main.live_events(Request(), after_id=0, once=True, token='session1')
            for resp in (two, third):
                async for _ in resp.body_iterator:
                    pass
            self.assertEqual(limiter._total, 0)
            self.assertEqual(limiter._active, {})

    async def test_global_limit_across_distinct_sessions(self):
        limiter = StreamLimit(per_session=2, total=2)
        with patch.object(main, 'stream_limit', limiter), \
             patch.object(main.store, 'session_valid', return_value=True), \
             patch.object(main.store, 'session_account', return_value={'id': 'acct', 'organization_id': 'default'}), \
             patch.object(main.store, 'organization_mfa_required', return_value=False), \
             patch.object(main.store, 'activity_cursor', return_value={'events': []}):
            r1 = await main.live_events(Request(), after_id=0, once=True, token='one')
            r2 = await main.live_events(Request(), after_id=0, once=True, token='two')
            with self.assertRaises(HTTPException) as cm:
                await main.live_events(Request(), after_id=0, once=True, token='three')
            self.assertEqual(cm.exception.status_code, 429)
            for resp in (r1, r2):
                async for _ in resp.body_iterator:
                    pass
            self.assertEqual(limiter._total, 0)

    async def test_batch_pagination_closes_after_250_without_skipping(self):
        limiter = StreamLimit()
        calls = []
        def read(after_id, limit, project_id, scope_user):
            calls.append(after_id)
            # Three consecutive pages. The real store applies ACL before paging.
            return {'events': [event(n) for n in range(after_id + 1, after_id + 101)]}
        with patch.object(main, 'stream_limit', limiter), \
             patch.object(main.store, 'session_valid', return_value=True), \
             patch.object(main.store, 'session_account', return_value={'id': 'acct', 'organization_id': 'default'}), \
             patch.object(main.store, 'organization_mfa_required', return_value=False), \
             patch.object(main.store, 'can_access_project', return_value=True), \
             patch.object(main.store, 'activity_cursor', side_effect=read), \
             patch.object(main.asyncio, 'sleep', new_callable=AsyncMock):
            res = await main.live_events(Request(), after_id=0, token='session')
            chunks = [c async for c in res.body_iterator]
            ids = [int(c.split('\n', 1)[0][4:]) for c in chunks if c.startswith('id: ')]
            self.assertEqual(ids, list(range(1, 251)))
            self.assertEqual(calls, [0, 100, 200])
            self.assertEqual(limiter._total, 0)
            # A new stream can resume exactly at the last delivered ID.
            resumed = await main.live_events(Request(), after_id=ids[-1], once=True, token='session')
            next_page = [c async for c in resumed.body_iterator]
            self.assertIn('id: 251\n', ''.join(next_page))
            self.assertEqual(limiter._total, 0)

    async def test_stream_error_releases_capacity(self):
        limiter = StreamLimit(per_session=1, total=1)
        with patch.object(main, 'stream_limit', limiter), \
             patch.object(main.store, 'session_valid', return_value=True), \
             patch.object(main.store, 'session_account', return_value={'id': 'acct', 'organization_id': 'default'}), \
             patch.object(main.store, 'organization_mfa_required', return_value=False), \
             patch.object(main.store, 'activity_cursor', side_effect=RuntimeError('db failed')):
            res = await main.live_events(Request(), once=True, after_id=0, token='session')
            with self.assertRaises(RuntimeError):
                _ = [c async for c in res.body_iterator]
            self.assertEqual(limiter._total, 0)

    def test_stream_limit_is_thread_safe(self):
        from concurrent.futures import ThreadPoolExecutor
        limiter = StreamLimit(per_session=3, total=100)
        with ThreadPoolExecutor(max_workers=40) as pool:
            keys = list(pool.map(limiter.acquire, ['shared'] * 40))
        self.assertEqual(len([x for x in keys if x]), 3)
        for key in keys:
            if key: limiter.release(key)
        self.assertEqual(limiter._total, 0)


if __name__ == '__main__':
    unittest.main()
