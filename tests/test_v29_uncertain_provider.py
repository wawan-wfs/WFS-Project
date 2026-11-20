"""Offline mock of potentially billable provider failures under tenant budgets."""
from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD
from app import store, config, auth, provider, quota

PASS='V29-Local-Test-Password!'
class UnknownBilling(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        p=Path(self.temp.name)
        self.patchers=[patch.object(store,'DATA',p),patch.object(store,'DB',p/'d.sqlite3'),
                       patch.object(store,'PROJECTS',p/'projects'),patch.object(config,'DATA',p),
                       patch.object(config,'PROJECTS',p/'projects'),patch.dict(os.environ,{
                       'OPENAI_API_KEY':'test-only','WFS_MODEL_QA':'metered-model'})]
        for x in self.patchers:x.start()
        store.init_db()
        self.user=store.provision_organization('org-v29','V29 org','v29user',auth.hash_password(PASS))
        self.other=store.provision_organization('org-other-v29','Other','otheruser',auth.hash_password(PASS))
        self.pid=store.create_project('A','Make a working app with UI and tests','ai','static',created_by=self.user)['id']
        self.pid2=store.create_project('B','Make a separate UI and tests','ai','static',created_by=self.user)['id']
        self.otherpid=store.create_project('C','Make a different app with tests','ai','static',created_by=self.other)['id']
        store.set_model_price('metered-model',100,100,self.user)
        store.set_model_price('metered-model',100,100,self.other)
        quota.set_scope_limit(self.user,'organization',10)
        quota.set_scope_limit(self.other,'organization',10)

    def tearDown(self):
        for x in reversed(self.patchers):x.stop()
        self.temp.cleanup()

    def test_failed_call_is_unknown_liability_and_blocks_only_own_org(self):
        with patch.object(provider,'_call_model',side_effect=provider.ProviderFailure('Simulated sent request timeout')):
            with self.assertRaisesRegex(provider.ProviderFailure,'timeout'):
                provider.invoke('QA Reviewer','instruction','message',provider.CallBudget(self.pid))
        with store.connect() as cx:
            last=cx.execute('SELECT status FROM provider_attempts WHERE project_id=?',(self.pid,)).fetchone()
            self.assertEqual(last['status'],'billing_unknown')
            held=cx.execute('SELECT status,expires_at FROM cost_reservations WHERE project_id=?',(self.pid,)).fetchone()
            self.assertEqual(held['status'],'reserved')
            self.assertTrue(held['expires_at'].startswith('9999'))
        with self.assertRaisesRegex(quota.QuotaDenied,'reconciliation'):
            quota.reserve(self.pid2,'metered-model',10,10)
        self.assertIsNotNone(quota.reserve(self.otherpid,'metered-model',10,10))

    def test_retry_error_followed_by_success_retains_unknown_attempt(self):
        import json
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,*a):
                return json.dumps({'id':'resp_retry_v29_000001','status':'completed',
                    'output':[{'content':[{'type':'output_text','text':'{\"valid\":true}'}]}],
                    'usage':{'input_tokens':20,'output_tokens':30}}).encode()
        failure=provider.error.HTTPError('https://example.invalid',503,'Service Unavailable',None,None)
        with patch.object(provider.request,'urlopen',side_effect=[failure,Response()]),patch.object(provider.time,'sleep'):
            result=provider.invoke('QA Reviewer','instruction','message',provider.CallBudget(self.pid))
        self.assertTrue(result['valid'])
        self.assertEqual(store.get_usage(self.pid)['calls'],1)
        with store.connect() as cx:
            statuses={r['status'] for r in cx.execute('SELECT status FROM provider_attempts WHERE project_id=?',(self.pid,))}
        self.assertEqual(statuses,{'billing_unknown','completed'})
        with self.assertRaisesRegex(quota.QuotaDenied,'reconciliation'):
            quota.reserve(self.pid2,'metered-model',10,10)

    def test_no_usage_field_cannot_be_charged_as_zero(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,*a):return b'{"status":"completed","output":[{"content":[{"type":"output_text","text":"{}"}]}]}'
        with patch.object(provider.request,'urlopen',return_value=Response()):
            with self.assertRaisesRegex(provider.ProviderFailure,'usage missing'):
                provider.invoke('QA Reviewer','instruction','message',provider.CallBudget(self.pid))
        self.assertEqual(store.get_usage(self.pid)['calls'],0)
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT status FROM provider_attempts WHERE project_id=?',(self.pid,)).fetchone()['status'],'billing_unknown')

if __name__=='__main__':unittest.main()
