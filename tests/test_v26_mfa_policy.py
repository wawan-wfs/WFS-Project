"""v2.6 mandatory organization-MFA enrollment never bypasses MFA or deadlocks setup."""
from __future__ import annotations
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store, mfa
from app.main import app


class OrganizationMFAPolicy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        path=Path(self.temp.name)
        self.patchers=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'wfs.sqlite3'),
                       patch.object(store,'PROJECTS',path/'projects')]
        for p in self.patchers:p.start()
        store.init_db()
        self.client=TestClient(app);self.client.__enter__()
        response=self.client.post('/api/login',json={'username':'admin','password':PASSWORD})
        self.assertEqual(response.status_code,200,response.text)
        self.headers={'X-WFS-CSRF':response.json()['csrf']}

    def tearDown(self):
        self.client.__exit__(None,None,None)
        for p in reversed(self.patchers):p.stop()
        self.temp.cleanup()

    def test_required_policy_restricts_existing_session_but_permits_enrollment(self):
        self.assertFalse(store.organization_mfa_required('owner'))
        self.assertEqual(self.client.get('/api/projects').status_code,200)
        store.set_organization_mfa_policy('default',True)
        self.assertTrue(store.organization_mfa_required('owner'))
        session=self.client.get('/api/session').json()
        self.assertTrue(session['mfa_setup_required'])
        for route in ('/api/projects','/api/queue','/api/office/live','/api/finops/report',
                      '/api/live/cursor','/api/operator/jobs','/api/diagnostics'):
            self.assertEqual(self.client.get(route).status_code,403,route)
        self.assertEqual(self.client.get('/api/meta').status_code,200)
        self.assertTrue(self.client.get('/api/mfa/status').json()['required_by_organization'])
        response=self.client.post('/api/mfa/setup',headers=self.headers,json={'password':PASSWORD})
        self.assertEqual(response.status_code,200,response.text)
        secret=response.json()['secret']
        code=mfa.otp(secret,int(time.time()//30)-1)
        reply=self.client.post('/api/mfa/confirm',headers=self.headers,json={'code':code})
        self.assertEqual(reply.status_code,200,reply.text)
        self.assertFalse(self.client.get('/api/session').json()['mfa_setup_required'])
        self.assertEqual(self.client.get('/api/projects').status_code,200)
        self.assertEqual(self.client.post('/api/mfa/disable',headers=self.headers,
                          json={'password':PASSWORD,'code':reply.json()['recovery_codes'][0]}).status_code,409)
        self.assertTrue(store.mfa_record('owner')['mfa_secret'])

    def test_policy_toggle_and_isolated_audit(self):
        with self.assertRaises(ValueError):store.set_organization_mfa_policy('unknown',True)
        store.set_organization_mfa_policy('default',True)
        store.set_organization_mfa_policy('default',False)
        self.assertFalse(store.organization_mfa_required('owner'))
        self.assertEqual(self.client.get('/api/projects').status_code,200)
        events=store.access_log()
        actions=[x['action'] for x in events]
        # Organization policy changes logged locally; do not expose org event
        # details across tenants via the user-directory audit API.
        self.assertNotIn('org_mfa_required',actions)


if __name__=='__main__':unittest.main()
