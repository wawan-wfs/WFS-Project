"""SSE batch reauthorization negative tests; not real cross-tenant network proof."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from app import main


class LocalRequest:
    headers = {}

    async def is_disconnected(self):
        return False


def event(event_id: int, pid: str) -> dict:
    return {'id': event_id, 'project_id': pid, 'agent': 'QA', 'state': 'done',
            'message': f'SENSITIVE_{pid}', 'created_at': '2026-11-08T00:00:00+00:00'}


class StreamReauthorizationV36(unittest.IsolatedAsyncioTestCase):
    async def read_once(self, *, project=None, account_sequence=None, access=None):
        accounts = iter(account_sequence or [{'id': 'alice', 'organization_id': 'default'}] * 5)
        def account(_token):
            return next(accounts)
        with patch.object(main.store, 'session_valid', return_value=True), \
             patch.object(main.store, 'session_account', side_effect=account), \
             patch.object(main.store, 'organization_mfa_required', return_value=False), \
             patch.object(main.store, 'can_access_project', side_effect=access or (lambda p, u: True)), \
             patch.object(main.store, 'activity_cursor', return_value={'events':[
                 event(1, 'project_alpha'), event(2, 'project_beta')]}), \
             patch.object(main, '_verify_visible', return_value=None):
            response = await main.live_events(LocalRequest(), after_id=0, project_id=project,
                                              once=True, token='session-local')
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            return ''.join(chunks)

    async def test_mid_batch_revocation_does_not_leak_project(self):
        body = await self.read_once(access=lambda p, _u: p == 'project_alpha')
        self.assertIn('SENSITIVE_project_alpha', body)
        self.assertNotIn('SENSITIVE_project_beta', body)
        self.assertNotIn('id: 2\n', body)

    async def test_all_project_subscription_can_keep_authorized_events(self):
        body = await self.read_once(access=lambda p, _u: p == 'project_beta')
        self.assertNotIn('SENSITIVE_project_alpha', body)
        self.assertIn('SENSITIVE_project_beta', body)

    async def test_explicit_project_subscription_stops_after_revocation(self):
        body = await self.read_once(project='project_alpha', access=lambda p, _u: p == 'project_alpha')
        self.assertIn('SENSITIVE_project_alpha', body)
        self.assertNotIn('SENSITIVE_project_beta', body)

    async def test_session_account_swap_fails_closed(self):
        body = await self.read_once(account_sequence=[{'id': 'alice', 'organization_id': 'default'}, {'id': 'bob', 'organization_id': 'default'}])
        self.assertNotIn('SENSITIVE_', body)


if __name__ == '__main__':
    unittest.main()
