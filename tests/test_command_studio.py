"""v1.4 command plane controls and audit tracing. No external AI or Docker used."""
from test_system import PASSWORD  # establishes an isolated SQLite and session config
import io
import json
import unittest
from fastapi.testclient import TestClient
from app import store
from app.main import app


class CommandStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()
        login=cls.client.post('/api/login',json={'password':PASSWORD})
        assert login.status_code==200,login.text
        cls.csrf=login.json()['csrf']

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    def setUp(self):
        self.ids=[]

    def tearDown(self):
        for pid in self.ids:
            row=store.get_project(pid)
            if row and row['status'] in ('queued','paused','running'):
                store.cancel(pid)
            if row and row['status']=='cancel_requested':
                store.finish(pid,'cancelled',worker_id=store.get_project(pid)['worker_id'])

    def project(self,title='Command test mission'):
        pid=store.create_project(title,'Build a production quality landing page with links','demo','static')['id']
        self.ids.append(pid)
        return pid

    def post(self,path,data=None,csrf=True):
        headers={'X-WFS-CSRF':self.csrf} if csrf else {}
        return self.client.post(path,json=data,headers=headers)

    def test_pending_priority_order_and_claim(self):
        low=self.project('First low')
        high=self.project('Second urgent')
        self.assertEqual(self.post(f'/api/projects/{low}/priority',{'priority':0}).status_code,200)
        self.assertEqual(self.post(f'/api/projects/{high}/priority',{'priority':3}).status_code,200)
        queue=self.client.get('/api/queue').json()['queued']
        positions={x['id']:x['position'] for x in queue}
        self.assertLess(positions[high],positions[low])
        self.assertEqual(self.client.get(f'/api/projects/{high}').json()['queue_position'],positions[high])
        picked=store.claim('wfs-test-command-worker')
        self.assertEqual(picked['id'],high)
        self.assertEqual(picked['priority'],3)
        self.assertEqual(self.post(f'/api/projects/{high}/pause').status_code,409)
        self.assertEqual(self.post(f'/api/projects/{high}/priority',{'priority':1}).status_code,409)
        store.finish(high,'cancelled',worker_id=store.get_project(high)['worker_id'])

    def test_hold_resume_csrf_and_cancel(self):
        pid=self.project('Hold me')
        self.assertEqual(self.post(f'/api/projects/{pid}/pause',csrf=False).status_code,403)
        self.assertEqual(self.post(f'/api/projects/{pid}/pause').json()['status'],'paused')
        self.assertEqual(self.post(f'/api/projects/{pid}/pause').status_code,409)
        self.assertFalse(any(x['id']==pid for x in self.client.get('/api/queue').json()['queued']))
        self.assertTrue(any(x['id']==pid for x in self.client.get('/api/queue').json()['paused']))
        self.assertEqual(self.post(f'/api/projects/{pid}/archive',{'archive':True}).status_code,409)
        self.assertEqual(self.post(f'/api/projects/{pid}/delete',{'confirm_id':pid}).status_code,409)
        self.assertEqual(self.post(f'/api/projects/{pid}/resume').json()['status'],'queued')
        self.assertEqual(self.post(f'/api/projects/{pid}/resume').status_code,409)
        self.assertEqual(self.post(f'/api/projects/{pid}/cancel').json()['status'],'cancelled')
        self.assertTrue(any(x['state']=='paused' for x in store.list_events(pid)))

    def test_priority_validation(self):
        pid=self.project()
        for priority in (-1,4,True,1.5,'2'):
            self.assertEqual(self.post(f'/api/projects/{pid}/priority',{'priority':priority}).status_code,422)
        self.assertEqual(self.post(f'/api/projects/{pid}/priority',{'priority':2},csrf=False).status_code,403)
        self.assertEqual(self.post(f'/api/projects/{pid}/priority',{'priority':2}).json()['priority'],2)
        self.assertEqual(store.get_project(pid)['priority'],2)

    def test_audit_trace_and_agent_detail(self):
        pid=self.project('Traceability Project')
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+pid,pid))
        aid=store.agent_start(pid,'Architect Agent','Architecture','Design the database and API routes',worker_id=store.get_project(pid)['worker_id'])
        store.agent_finish(aid,'done',worker_id=store.get_project(store.agent_run_detail(aid)['project_id'])['worker_id'])
        store.operator_event(pid,'Quality Lab','done','Manual QA checks should be reviewed')
        resp=self.client.get(f'/api/projects/{pid}/trace')
        self.assertEqual(resp.status_code,200)
        trace=resp.json()
        self.assertEqual(trace['project']['id'],pid)
        self.assertTrue(any(a['id']==aid for a in trace['agent_runs']))
        self.assertTrue(any(e['agent']=='Quality Lab' for e in trace['events']))
        self.assertNotIn('worker_id',str(trace))
        self.assertNotIn('session_secret',str(trace))
        output=self.client.get(f'/api/projects/{pid}/trace/download')
        self.assertIn('attachment',output.headers['Content-Disposition'])
        self.assertEqual(json.loads(output.content)['project']['id'],pid)
        agent=self.client.get(f'/api/agents/runs/{aid}').json()
        self.assertEqual(agent['division'],'Architecture')
        self.assertFalse(agent['live'])
        self.assertNotIn('worker_id',agent)
        self.assertEqual(self.client.get('/api/agents/runs/999999999').status_code,404)

    def test_monotonic_cursor_event_history(self):
        pid=self.project('Cursor audit project')
        for n in range(3):store.operator_event(pid,'Control Agent','done',f'Milestone {n}')
        first=self.client.get('/api/workspace/events',params={'after_id':0,'limit':2,'project_id':pid}).json()
        self.assertEqual(len(first['events']),2)
        self.assertTrue(first['has_more'])
        second=self.client.get('/api/workspace/events',params={'after_id':first['next_cursor'],'limit':2,'project_id':pid}).json()
        self.assertEqual(len(second['events']),2)
        ids=[x['id'] for x in first['events']+second['events']]
        self.assertEqual(ids,sorted(set(ids)))
        self.assertEqual(self.client.get('/api/workspace/events?limit=201').status_code,422)
        self.assertEqual(self.client.get('/api/workspace/events?project_id=bad').status_code,404)

    def test_authorization_and_html_controls(self):
        with TestClient(app) as unauth:
            for path in ('/api/queue','/api/workspace/events','/api/agents/runs/1'):
                self.assertEqual(unauth.get(path).status_code,401)
        html=self.client.get('/').text
        for attr in ('page-queue','queue-pending','queue-paused','priority-save-btn','hold-btn','resume-btn',
                     'office-phase-rail','office-queue-peek','trace-download-link','activity-next-btn'):
            self.assertIn('id="'+attr+'"',html)

    def test_migration_is_idempotent(self):
        store.init_db()
        store.init_db()
        with store.connect() as cx:
            columns={r['name'] for r in cx.execute('PRAGMA table_info(projects)')}
        self.assertIn('priority',columns)
        self.assertIn('queued_at',columns)


if __name__=='__main__':unittest.main()
