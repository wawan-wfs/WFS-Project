"""v2.6 adversarial organization boundary integration tests against real FastAPI and SQLite."""
from __future__ import annotations
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import auth, store
from app.main import app

BRIEF = 'Build a private application with files, clear QA checks and user dashboards'
PASS = 'SecureOrgPassword-2026!'


class OrganizationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patchers=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'store.sqlite3'),
                       patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patchers:p.start()
        store.init_db()
        store.init_db()  # idempotent migration
        self.alpha=store.provision_organization('alpha-org','Alpha Organization','org_alpha',auth.hash_password(PASS))
        self.beta=store.provision_organization('beta-org','Beta Organization','org_beta',auth.hash_password(PASS))
        self.clients=[]
        self.owner,self.owner_csrf=self.login('admin',PASSWORD)
        self.alpha_client,self.alpha_csrf=self.login('org_alpha',PASS)
        self.beta_client,self.beta_csrf=self.login('org_beta',PASS)
        self.default_project=self.project(self.owner,self.owner_csrf,'Default Private','private')
        self.alpha_project=self.project(self.alpha_client,self.alpha_csrf,'Alpha Workspace','workspace')
        self.beta_project=self.project(self.beta_client,self.beta_csrf,'Beta Workspace','workspace')

    def tearDown(self):
        for c in self.clients:c.__exit__(None,None,None)
        for p in reversed(self.patchers):p.stop()
        self.temp.cleanup()

    def login(self,username,password):
        client=TestClient(app);client.__enter__();self.clients.append(client)
        r=client.post('/api/login',json={'username':username,'password':password})
        self.assertEqual(r.status_code,200,r.text)
        return client,{'X-WFS-CSRF':r.json()['csrf']}

    def project(self,client,csrf,title,visibility):
        r=client.post('/api/projects',headers=csrf,json={
            'title':title,'prompt':BRIEF,'mode':'demo','stack':'static','visibility':visibility})
        self.assertEqual(r.status_code,202,r.text)
        return r.json()['id']

    def test_legacy_default_and_idempotent_migration(self):
        self.assertEqual(store.get_project(self.default_project)['organization_id'],'default')
        self.assertEqual(store.get_project(self.alpha_project)['organization_id'],'alpha-org')
        store.init_db()
        self.assertEqual(store.get_project(self.alpha_project)['organization_id'],'alpha-org')
        self.assertEqual(store.user_by_username('org_alpha')['organization_id'],'alpha-org')

    def test_cross_organization_resources_never_resolve_even_if_workspace_shared(self):
        # Each tenant has a workspace-visible mission; it must NOT cross orgs.
        for client,foreign in ((self.owner,self.alpha_project),(self.alpha_client,self.default_project),
                               (self.alpha_client,self.beta_project),(self.beta_client,self.alpha_project)):
            for route in (f'/api/projects/{foreign}',f'/api/projects/{foreign}/events',
                          f'/api/projects/{foreign}/files',f'/api/projects/{foreign}/download',
                          f'/api/projects/{foreign}/budget',f'/api/projects/{foreign}/collaboration',
                          f'/api/projects/{foreign}/access',f'/api/projects/{foreign}/trace',
                          f'/preview/{foreign}/index.html',f'/api/workspace/events?project_id={foreign}',
                          f'/api/office/live?project_id={foreign}',f'/api/finops/report?project_id={foreign}'):
                self.assertEqual(client.get(route).status_code,404,(client,route))
        self.assertEqual(self.alpha_client.get(f'/api/projects/{self.alpha_project}').status_code,200)
        for client,own,foreign in ((self.owner,self.default_project,self.alpha_project),
                                    (self.alpha_client,self.alpha_project,self.default_project),
                                    (self.beta_client,self.beta_project,self.alpha_project)):
            listing=client.get('/api/projects').json()
            ids={x['id'] for x in listing}
            self.assertIn(own,ids)
            self.assertNotIn(foreign,ids)

    def test_finops_queue_search_sse_and_operator_job_scoped(self):
        store.usage(self.alpha_project,'alpha-agent','shared-llm',101,50)
        store.usage(self.beta_project,'beta-agent','shared-llm',300,30)
        store.operator_event(self.alpha_project,'alpha-agent','working','ALPHA_SECRET_WORK')
        store.operator_event(self.beta_project,'beta-agent','working','BETA_SECRET_WORK')
        with store.connect() as cx:
            jid=uuid.uuid4().hex[:24]
            cx.execute('''INSERT INTO operator_jobs(id,project_id,kind,options_json,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)''',(jid,self.alpha_project,'qa-static','{}','queued',store.now(),store.now()))
        self.assertEqual(self.beta_client.get('/api/operator/jobs/'+jid).status_code,404)
        self.assertEqual(self.owner.get('/api/operator/jobs/'+jid).status_code,404)
        self.assertEqual(self.alpha_client.get('/api/operator/jobs/'+jid).status_code,200)
        for client,allowed,disallowed in ((self.alpha_client,self.alpha_project,self.beta_project),
                                         (self.beta_client,self.beta_project,self.alpha_project),
                                         (self.owner,self.default_project,self.alpha_project)):
            for route in ('/api/queue','/api/operator/jobs','/api/workspace/events',
                          '/api/workspace/activity','/api/office/live',
                          '/api/agents/directory','/api/finops/report?period=all',
                          '/api/finops/export.csv?period=all','/api/live/events?once=true'):
                reply=client.get(route)
                self.assertEqual(reply.status_code,200,(route,reply.text[:200]))
                self.assertNotIn(disallowed,reply.text,route)
            self.assertNotIn(disallowed,client.get('/api/projects').text)
        self.assertEqual(self.alpha_client.get('/api/finops/report?period=all').json()['calls'],1)
        self.assertEqual(self.beta_client.get('/api/finops/report?period=all').json()['calls'],1)
        self.assertEqual(self.owner.get('/api/finops/report?period=all').json()['calls'],0)
        self.assertEqual(self.owner.get('/api/live/cursor').json()['cursor'],store.live_event_cursor('owner'))

    def test_cross_organization_grant_and_revision_are_denied(self):
        reply=self.alpha_client.post(f'/api/projects/{self.alpha_project}/members',headers=self.alpha_csrf,
                       json={'user_id':self.beta,'permission':'edit'})
        self.assertEqual(reply.status_code,422,reply.text)
        self.assertFalse(store.can_access_project(self.alpha_project,self.beta,write=True))
        with self.assertRaises(ValueError):
            store.create_project('Impossible revision',BRIEF,'ai','static',parent_id=self.alpha_project,created_by=self.beta)
        self.assertEqual(self.alpha_client.post(f'/api/projects/{self.beta_project}/notes',headers=self.alpha_csrf,
                    json={'category':'review','message':'cross tenant write'}).status_code,404)

    def test_team_directory_and_cost_price_isolation(self):
        owners={u['username'] for u in self.owner.get('/api/team/directory').json()}
        alpha={u['username'] for u in self.alpha_client.get('/api/team/directory').json()}
        self.assertIn('admin',owners);self.assertNotIn('org_alpha',owners)
        self.assertIn('org_alpha',alpha);self.assertNotIn('admin',alpha)
        self.assertEqual([u['username'] for u in self.owner.get('/api/users').json()['users']],['admin'])
        store.set_model_price('shared-llm',1,2,scope_user=self.alpha)
        store.set_model_price('shared-llm',20,40,scope_user=self.beta)
        store.usage(self.alpha_project,'alpha-agent','shared-llm',1_000_000,0)
        store.usage(self.beta_project,'beta-agent','shared-llm',1_000_000,0)
        self.assertEqual(self.alpha_client.get('/api/finops/report?period=all').json()['estimated_usd'],1)
        self.assertEqual(self.beta_client.get('/api/finops/report?period=all').json()['estimated_usd'],20)
        self.assertEqual(self.owner.get('/api/finops/prices').json(),[])
        self.assertEqual(self.alpha_client.get('/api/finops/prices').json()[0]['model'],'shared-llm')

    def test_scope_revocation_is_immediate(self):
        self.assertIn(self.alpha_project,store.visible_project_ids(self.alpha))
        with store.connect() as cx:
            cx.execute('UPDATE users SET disabled=1 WHERE id=?',(self.alpha,))
        self.assertEqual(self.alpha_client.get('/api/projects').status_code,401)
        self.assertFalse(store.can_access_project(self.alpha_project,self.alpha))
        self.assertEqual(store.visible_project_ids(self.alpha),set())

if __name__=='__main__':unittest.main()
