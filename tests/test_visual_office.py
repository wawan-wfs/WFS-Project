"""v1.3: server truth for animated agent office + authenticated menu APIs."""
import os
import re
import unittest
from pathlib import Path
from test_system import PASSWORD  # sets isolated test env
from fastapi.testclient import TestClient
from app import store, config
from app.main import app


class VisualOfficeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()
        logged = cls.client.post('/api/login', json={'password': PASSWORD})
        assert logged.status_code == 200, logged.text
        cls.csrf = logged.json()['csrf']

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    def test_new_endpoints_auth_required(self):
        with TestClient(app) as anonymous:
            for path in ('/api/office/live','/api/agents/directory',
                         '/api/workspace/activity','/api/workspace/artifacts',
                         '/api/workspace/capabilities'):
                self.assertEqual(anonymous.get(path).status_code,401,path)

    def test_floor_validation_and_project_validation(self):
        for bad in ('0','4','-1'):
            self.assertEqual(self.client.get('/api/office/live?floor='+bad).status_code,422)
        self.assertEqual(self.client.get('/api/office/live?project_id=not-real').status_code,404)

    def test_three_floor_groups_are_exact(self):
        expected={1:{'Management','Architecture','Operations'},
                  2:{'Engineering','Creative Studio','AI & Data','Documentation'},
                  3:{'Quality Lab','Infrastructure','Security'}}
        for floor,divisions in expected.items():
            payload=self.client.get('/api/office/live?floor='+str(floor)).json()
            self.assertEqual(set(payload['divisions']),divisions)
            self.assertEqual(payload['floor'],floor)
            self.assertTrue(all(x['division'] in divisions for x in payload['agents']))

    def test_live_agent_requires_both_recent_worker_and_project(self):
        pid=store.create_project('Visual Agents Test','Write website components in a monitored task','demo','static')['id']
        worker_id='wfs-visual-probe-worker'
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',phase='implementation',worker_id=?,heartbeat_at=? WHERE id=?",(worker_id,store.now(),pid))
        agent_id=store.agent_start(pid,'Frontend Engineer','Engineering','Build responsive menu layout',worker_id=worker_id)
        try:
            # Merely having a 'working' record must not animate a fake agent.
            stale=self.client.get(f'/api/office/live?floor=2&project_id={pid}').json()
            self.assertEqual(stale['agents'][0]['state'],'interrupted')
            self.assertFalse(stale['agents'][0]['live'])
            store.worker_ping(worker_id,pid)
            live=self.client.get(f'/api/office/live?floor=2&project_id={pid}').json()
            self.assertTrue(live['agents'][0]['live'])
            self.assertEqual(live['divisions']['Engineering']['working'],1)
            self.assertEqual(live['project']['phase'],'implementation')
            self.assertEqual(len(self.client.get('/api/office/live?floor=1&project_id='+pid).json()['agents']),0)
            directory=self.client.get('/api/agents/directory').json()
            self.assertTrue(any(a['id']==agent_id and a['live'] for a in directory))
            self.assertNotIn('worker_id',live['agents'][0])
        finally:
            store.agent_finish(agent_id,'done',worker_id=store.get_project(store.agent_run_detail(agent_id)['project_id'])['worker_id'])
            store.finish(pid,'cancelled',worker_id=store.get_project(pid)['worker_id'])
        completed=self.client.get(f'/api/office/live?floor=2&project_id={pid}').json()
        self.assertEqual(completed['agents'][0]['state'],'done')
        self.assertFalse(completed['agents'][0]['live'])

    def test_activity_and_catalog_are_real_records_only(self):
        pid=store.create_project('Visual Ledger Test','Implement a delivery audit artifact listing','demo','static')['id']
        store.operator_event(pid,'Security Engineer','working','Review static output without executing it')
        activity=self.client.get('/api/workspace/activity').json()
        self.assertTrue(any(e['project_id']==pid and e['agent']=='Security Engineer' for e in activity))
        self.assertFalse(any('API_KEY' in str(x) for x in activity))
        self.assertIsInstance(self.client.get('/api/workspace/artifacts').json(),list)
        store.cancel(pid)

    def test_capabilities_never_expose_secrets(self):
        result=self.client.get('/api/workspace/capabilities')
        self.assertEqual(result.status_code,200)
        data=result.json()
        self.assertEqual(data['deployment'],'local-multiuser-rbac')
        self.assertEqual(data['limits']['max_parallel'],config.MAX_PARALLEL)
        self.assertFalse(data['security']['docker_socket_mounted'])
        self.assertNotIn('session_secret',str(data).lower())
        self.assertNotIn('admin_password',str(data).lower())
        self.assertNotIn('openai_api_key',str(data).lower())

    def test_project_metadata_requires_csrf_and_persists(self):
        pid=store.create_project('Metadata Original','Create a web app with access control checks','demo','static')['id']
        endpoint=f'/api/projects/{pid}/metadata'
        self.assertEqual(self.client.post(endpoint,json={'title':'New Display Name'}).status_code,403)
        self.assertEqual(self.client.post(endpoint,headers={'X-WFS-CSRF':self.csrf},json={'title':' a '}).status_code,422)
        original_prompt=store.get_project(pid)['prompt']
        response=self.client.post(endpoint,headers={'X-WFS-CSRF':self.csrf},json={
            'title':'Team Project 2026','notes':'QA needs a security sign-off before deployment.'})
        self.assertEqual(response.status_code,200,response.text)
        record=store.get_project(pid)
        self.assertEqual(record['title'],'Team Project 2026')
        self.assertIn('security sign-off',record['notes'])
        self.assertEqual(record['prompt'],original_prompt)
        self.assertTrue(any(x['state']=='metadata' for x in store.list_events(pid)))
        store.cancel(pid)

    def test_all_menu_views_and_controls_are_shipped(self):
        html=self.client.get('/').text
        from html.parser import HTMLParser
        class ElementReader(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids=set()
                self.pages=[]
            def handle_starttag(self,tag,attrs):
                data=dict(attrs)
                if 'id' in data:self.ids.add(data['id'])
                if 'data-page' in data:self.pages.append(data['data-page'])
        soup=ElementReader()
        soup.feed(html)
        for page in ('overview','projects','office','agents','quality','deliverables','activity','system'):
            self.assertIn('page-'+page,soup.ids)
            self.assertIn(page,soup.pages)
        for i in ('office-project-filter','world-room-grid','office-agent-list','office-event-stream',
                  'agent-directory','qa-board','deliverable-list','activity-feed','system-health-cards',
                  'preview-dialog','file-dialog','login-screen','agent-dialog',
                  'office-demo-btn','metadata-dialog','pref-save','project-status-filter'):
            self.assertIn(i,soup.ids)
        self.assertEqual(self.client.get('/static/studio.js').status_code,200)
        self.assertEqual(self.client.get('/static/style.css').status_code,200)
        self.assertIn('agent-enter',self.client.get('/static/style.css').text)

if __name__=='__main__':unittest.main()
