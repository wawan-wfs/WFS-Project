"""Adversarial v2.8 admission tests: real isolated SQLite, mocked TLS proxy.

No real paid provider, browser GPU, Docker daemon or TLS deployment is used here.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from test_system import PASSWORD  # initialize isolated test configuration before app import
from app import auth, quota, store, preview_gateway, config
from app.main import app as api

PASS='OrgTestPassword-2026!'
BRIEF='Build a production-shaped private application with QA and user-facing dashboards'
ORIGIN='https://preview.wfs.example.test'
KEY='preview-proxy-shared-test-key-very-long-2026'


class TenantAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        p=Path(self.tmp.name)
        self.patchers=[patch.object(store,'DATA',p),patch.object(store,'DB',p/'data.sqlite3'),
                       patch.object(store,'PROJECTS',p/'projects'),
                       patch.object(config,'PROJECTS',p/'projects'),patch.object(config,'DATA',p),
                       patch.dict(os.environ,{'WFS_PREVIEW_PUBLIC_ORIGIN':ORIGIN,
                           'WFS_PREVIEW_PROXY_KEY':KEY},clear=False)]
        for x in self.patchers:x.start()
        store.init_db();store.init_db()
        self.alpha=store.provision_organization('org-alpha','Alpha','aadmin',auth.hash_password(PASS))
        self.beta=store.provision_organization('org-beta','Beta','badmin',auth.hash_password(PASS))
        self.alpha_p=store.create_project('Alpha App',BRIEF,'demo','static',created_by=self.alpha)['id']
        self.alpha_p2=store.create_project('Alpha Second',BRIEF,'demo','static',created_by=self.alpha)['id']
        self.beta_p=store.create_project('Beta App',BRIEF,'demo','static',created_by=self.beta)['id']
        store.set_model_price('metered-model',10_000,0,self.alpha)
        store.set_model_price('metered-model',10_000,0,self.beta)
        self.client=TestClient(api);self.client.__enter__()
        self.r=self.client.post('/api/login',json={'username':'aadmin','password':PASS})
        self.assertEqual(self.r.status_code,200,self.r.text)
        self.csrf={'X-WFS-CSRF':self.r.json()['csrf']}

    def tearDown(self):
        self.client.__exit__(None,None,None)
        for x in reversed(self.patchers):x.stop()
        self.tmp.cleanup()

    def test_atomic_org_limit_blocks_second_parallel_project(self):
        quota.set_scope_limit(self.alpha,'organization',0.75)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures=[pool.submit(quota.reserve,p,'metered-model',20,0) for p in
                     [self.alpha_p,self.alpha_p2]*4]
            granted=[];denied=[]
            for f in futures:
                try:granted.append(f.result())
                except quota.QuotaDenied as exc:denied.append(str(exc))
        self.assertEqual(len(granted),3) # 3 * $0.20 = $0.60
        self.assertEqual(len(denied),5)
        self.assertIsNone(quota.reserve(self.beta_p,'metered-model',20,0))  # no hard limit configured for beta
        quota.finish(granted[0],'released')
        self.assertIsNotNone(quota.reserve(self.alpha_p,'metered-model',20,0))

    def test_workspace_limit_and_project_limit_are_independent(self):
        quota.set_scope_limit(self.alpha,'workspace',0.3)
        p=quota.reserve(self.alpha_p,'metered-model',20,0)
        with self.assertRaises(quota.QuotaDenied):quota.reserve(self.alpha_p2,'metered-model',20,0)
        quota.finish(p,'released')
        store.set_project_budget(self.alpha_p,0.15)
        with self.assertRaises(quota.QuotaDenied):quota.reserve(self.alpha_p,'metered-model',20,0)
        self.assertIsNotNone(quota.reserve(self.alpha_p2,'metered-model',20,0))

    def test_reservation_settlement_and_double_spend_prevention(self):
        quota.set_scope_limit(self.alpha,'organization',0.5)
        r=quota.reserve(self.alpha_p,'metered-model',30,0)
        # Record with real token counts; reserve must settle in the SAME txn.
        self.assertAlmostEqual(store.usage(self.alpha_p,'QA','metered-model',25,0,reservation_id=r),0.25)
        with self.assertRaises(quota.QuotaDenied):
            store.usage(self.alpha_p,'QA','metered-model',25,0,reservation_id=r)
        self.assertEqual(store.get_usage(self.alpha_p)['calls'],1)
        with self.assertRaises(quota.QuotaDenied):quota.reserve(self.alpha_p2,'metered-model',30,0)
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT status FROM cost_reservations WHERE id=?',(r,)).fetchone()[0],'settled')

    def test_price_change_during_request_uses_reserved_snapshot(self):
        quota.set_scope_limit(self.alpha,'organization',0.5)
        rid=quota.reserve(self.alpha_p,'metered-model',20,0)
        store.set_model_price('metered-model',1,1,self.alpha)
        self.assertEqual(store.usage(self.alpha_p,'Engineer','metered-model',20,0,reservation_id=rid),0.2)
        with store.connect() as cx:
            row=cx.execute('SELECT input_rate_snapshot FROM usage WHERE project_id=?',(self.alpha_p,)).fetchone()
            self.assertEqual(row['input_rate_snapshot'],10000)

    def test_price_scoping_and_api_client_cannot_supply_org(self):
        quota.set_scope_limit(self.alpha,'organization',0.4)
        self.assertEqual(self.client.post('/api/finops/limits',json={'scope':'organization','limit_usd':7}).status_code,403)
        resp=self.client.post('/api/finops/limits',headers=self.csrf,json={'scope':'organization','limit_usd':0.41,'organization_id':'org-beta'})
        self.assertEqual(resp.status_code,422,resp.text)
        self.assertEqual(quota.read_scope_limits(self.beta),[])
        self.assertEqual(self.client.get('/api/finops/limits').json()[0]['limit_usd'],0.4)
        valid=self.client.post('/api/finops/limits',headers=self.csrf,json={'scope':'organization','limit_usd':0.41})
        self.assertEqual(valid.status_code,200,valid.text)
        self.assertEqual(self.client.post('/api/finops/limits',headers=self.csrf,json={'scope':'workspace','workspace_id':'foreign','limit_usd':1}).status_code,403)
        self.assertEqual(self.client.post(f'/api/projects/{self.beta_p}/preview-ticket',headers=self.csrf).status_code,404)

    def gateway_headers(self):
        return {'host':'preview.wfs.example.test','x-forwarded-proto':'https','x-wfs-preview-proxy-key':KEY}

    def test_one_use_preview_ticket_session_and_revocation(self):
        # Mark as completed; bypass no project authorization on server.
        with store.connect() as cx:
            cx.execute('UPDATE projects SET status=? WHERE id=?',('completed',self.alpha_p))
        r=self.client.post(f'/api/projects/{self.alpha_p}/preview-ticket',headers=self.csrf)
        self.assertEqual(r.status_code,201,r.text)
        ticket=urlsplit(r.json()['url']).path
        with TestClient(preview_gateway.app,base_url=ORIGIN) as gw:
            bad=gw.get(ticket,headers={'host':'preview.wfs.example.test'},follow_redirects=False)
            self.assertEqual(bad.status_code,503)
            first=gw.get(ticket,headers=self.gateway_headers(),follow_redirects=False)
            self.assertEqual(first.status_code,303,first.text)
            self.assertNotIn('wfs_session',first.headers.get('set-cookie',''))
            replay=gw.get(ticket,headers=self.gateway_headers(),follow_redirects=False)
            self.assertEqual(replay.status_code,404)
            target=first.headers['location']
            self.assertTrue(target.startswith('/p/'+self.alpha_p))
            visible=gw.get(target,headers=self.gateway_headers())
            # Source not yet delivered; authorization succeeds, payload is absent.
            self.assertEqual(visible.status_code,409,visible.text)  # no delivered artifact yet
            self.assertNotIn('Preview session expired',visible.text)
            revoke=self.client.delete(f'/api/projects/{self.alpha_p}/preview-grants',headers=self.csrf)
            self.assertEqual(revoke.status_code,200,revoke.text)
            self.assertEqual(revoke.json()['revoked'],1)
            self.assertEqual(gw.get(target,headers=self.gateway_headers()).status_code,404)

    def test_separate_origin_renders_verified_html_and_session_revoke(self):
        data=b'<!doctype html><html><body><h1>Approved static preview</h1></body></html>'
        target=store.PROJECTS/self.alpha_p
        target.mkdir(parents=True,exist_ok=True)
        (target/'index.html').write_bytes(data)
        with store.connect() as cx:
            cx.execute('UPDATE projects SET status=? WHERE id=?',('completed',self.alpha_p))
            cx.execute('INSERT INTO artifacts(project_id,name,bytes,sha256) VALUES(?,?,?,?)',
                       (self.alpha_p,'index.html',len(data),hashlib.sha256(data).hexdigest()))
        response=self.client.post(f'/api/projects/{self.alpha_p}/preview-ticket',headers=self.csrf)
        self.assertEqual(response.status_code,201,response.text)
        ticket=urlsplit(response.json()['url']).path
        with TestClient(preview_gateway.app,base_url=ORIGIN) as gw:
            exchanged=gw.get(ticket,headers=self.gateway_headers(),follow_redirects=False)
            self.assertEqual(exchanged.status_code,303)
            page=gw.get(exchanged.headers['location'],headers=self.gateway_headers())
            self.assertEqual(page.status_code,200,page.text)
            self.assertIn('Approved static preview',page.text)
            self.assertIn('sandbox allow-scripts',page.headers['content-security-policy'])
            self.assertEqual(page.headers['x-frame-options'],'DENY')
            # Logout from the main dashboard must invalidate the other-origin
            # preview cookie even though the gateway itself has no dashboard cookie.
            r=self.client.post('/api/logout',headers=self.csrf)
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(gw.get(exchanged.headers['location'],headers=self.gateway_headers()).status_code,404)

    def test_preview_revocation_on_logout_access_removal(self):
        with store.connect() as cx:
            cx.execute('UPDATE projects SET status=? WHERE id=?',('completed',self.alpha_p))
        session=self.client.cookies.get('wfs_session')
        ticket=preview_gateway.issue(self.alpha_p,self.alpha,session).split('/t/')[1]
        pid,cookie=preview_gateway.exchange(ticket)
        self.assertTrue(preview_gateway.verify(pid,cookie))
        # Disabled account is enforced on EACH request, not just issuance.
        with store.connect() as cx:
            cx.execute('UPDATE users SET disabled=1 WHERE id=?',(self.alpha,))
        with self.assertRaises(preview_gateway.GatewayError):preview_gateway.verify(pid,cookie)

    def test_gateway_not_available_without_distinct_origin_and_proxy(self):
        with patch.dict(os.environ,{'WFS_PREVIEW_PUBLIC_ORIGIN':'http://localhost:8080'}):
            with self.assertRaises(preview_gateway.GatewayError):preview_gateway.public_origin()
        with patch.dict(os.environ,{'WFS_PREVIEW_PUBLIC_ORIGIN':'https://localhost:8443'}):
            with self.assertRaises(preview_gateway.GatewayError):preview_gateway.public_origin()
        with patch.dict(os.environ,{'WFS_PREVIEW_PROXY_KEY':'short'}):
            with TestClient(preview_gateway.app,base_url=ORIGIN) as gw:
                self.assertEqual(gw.get('/p/'+self.alpha_p+'/index.html',headers=self.gateway_headers()).status_code,503)


if __name__=='__main__':unittest.main()
