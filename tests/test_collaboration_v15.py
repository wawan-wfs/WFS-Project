"""v1.5 tests for durable tasks, authenticated collaboration and SSE replay.
No external API, browser or Docker required.
"""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store, pipeline, worker
from app.main import app, encode_sse_event

class CollaborationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)
        cls.client.__enter__()
        response=cls.client.post('/api/login',json={'password':PASSWORD})
        assert response.status_code==200,response.text
        cls.csrf=response.json()['csrf']

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    def setUp(self):self.ids=[]

    def tearDown(self):
        for pid in self.ids:
            obj=store.get_project(pid)
            if obj and obj['status'] in ('queued','paused','running'):
                store.cancel(pid)
            if obj and obj['status']=='cancel_requested':store.finish(pid,'cancelled',worker_id=store.get_project(pid)['worker_id'])
            store.block_outstanding_tasks(pid,worker_id=(store.get_project(pid)['worker_id'] or 'inactive-test-claim'))

    def create(self,mode='demo'):
        pid=store.create_project('Collaboration Test','Create a fully functional and responsive landing page',mode,'static')['id']
        self.ids.append(pid)
        return pid

    def test_task_state_machine_and_handoff_audit(self):
        pid=self.create()
        self.assertTrue(store.change_priority(pid,3))
        claimed=store.claim('collab-worker')
        self.assertEqual(claimed['id'],pid)
        plan=[{'id':'T1','role':'Frontend Engineer','division':'Engineering','task':'Build frontend','files':['index.html','app.js']},
              {'id':'T2','role':'Documentation Engineer','division':'Documentation','task':'Write readme','files':['README.md']}]
        self.assertEqual(store.record_tasks(pid,plan,worker_id=store.get_project(pid)['worker_id']),1)
        self.assertTrue(store.task_transition(pid,'T1','planned','working',worker_id=store.get_project(pid)['worker_id']))
        self.assertFalse(store.task_transition(pid,'T1','planned','working',worker_id=store.get_project(pid)['worker_id']))
        self.assertTrue(store.task_transition(pid,'T1','working','done',worker_id=store.get_project(pid)['worker_id']))
        self.assertFalse(store.task_transition(pid,'T1','working','failed',worker_id=store.get_project(pid)['worker_id']))
        with self.assertRaises(ValueError):store.task_transition(pid,'T1','done','working',worker_id=store.get_project(pid)['worker_id'])
        self.assertTrue(store.record_handoff(pid,'Product Manager','Frontend Engineer','Validated plan and file ownership',worker_id=(store.get_project(pid)['worker_id'] or 'inactive-test-claim')))
        view=self.client.get(f'/api/projects/{pid}/collaboration').json()
        self.assertEqual(view['attempt'],1)
        self.assertEqual(view['task_counts']['done'],1)
        self.assertEqual(view['task_counts']['planned'],1)
        self.assertEqual(view['handoffs'][0]['destination'],'Frontend Engineer')
        store.block_outstanding_tasks(pid,worker_id=(store.get_project(pid)['worker_id'] or 'inactive-test-claim'))
        self.assertEqual(store.collaboration_details(pid)['task_counts']['blocked'],1)
        store.finish(pid,'failed',worker_id=store.get_project(pid)['worker_id'])
        self.assertFalse(store.record_handoff(pid,'Source','Target','not completed',worker_id=(store.get_project(pid)['worker_id'] or 'inactive-test-claim')))
        self.assertIn('collaboration',self.client.get(f'/api/projects/{pid}/trace').json())

    def test_operator_note_validation_auth_and_audit(self):
        pid=self.create()
        url=f'/api/projects/{pid}/notes'
        with TestClient(app) as no_auth:
            self.assertEqual(no_auth.get(f'/api/projects/{pid}/collaboration').status_code,401)
            self.assertEqual(no_auth.post(url,json={'category':'review','message':'Needs testing'}).status_code,401)
        self.assertEqual(self.client.post(url,json={'category':'decision','message':'Use local QA'}).status_code,403)
        headers={'X-WFS-CSRF':self.csrf}
        self.assertEqual(self.client.post(url,json={'category':'unknown','message':'Bad note'},headers=headers).status_code,422)
        self.assertEqual(self.client.post(url,json={'category':'review','message':'x'},headers=headers).status_code,422)
        self.assertEqual(self.client.post(url,json={'category':'review','message':'X'*1600},headers=headers).status_code,422)
        self.assertEqual(self.client.post('/api/projects/abc/notes',json={'category':'review','message':'Missing project'},headers=headers).status_code,404)
        note=self.client.post(url,json={'category':'review','message':'Check keyboard access <script>alert(1)</script>'},headers=headers)
        self.assertEqual(note.status_code,201,note.text)
        self.assertEqual(note.json()['category'],'review')
        view=self.client.get(f'/api/projects/{pid}/collaboration').json()
        self.assertEqual(len(view['notes']),1)
        self.assertIn('NOT sent to AI',view['notice'])
        self.assertTrue(any(e['state']=='note' for e in store.list_events(pid)))
        self.assertIn('notes',self.client.get(f'/api/projects/{pid}/trace').json()['collaboration'])

    def test_sse_authenticated_replay_and_cursor(self):
        pid=self.create()
        initial=self.client.get('/api/live/cursor').json()['cursor']
        self.assertGreaterEqual(initial,1)
        store.operator_event(pid,'Product Manager','working','Planning milestone')
        response=self.client.get(f'/api/live/events?once=true&after_id={initial}&project_id={pid}')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.headers['content-type'].startswith('text/event-stream'))
        self.assertIn('event: wfs-event',response.text)
        self.assertIn('Planning milestone',response.text)
        self.assertNotIn('wfs_session',response.text)
        marker=store.live_event_cursor()
        empty=self.client.get(f'/api/live/events?once=true&after_id={marker}').text
        self.assertNotIn('event: wfs-event',empty)
        self.assertEqual(self.client.get('/api/live/events?after_id=-1&once=true').status_code,422)
        self.assertEqual(self.client.get('/api/live/events?project_id=bad&once=true').status_code,404)
        with TestClient(app) as visitor:
            self.assertEqual(visitor.get('/api/live/cursor').status_code,401)
            self.assertEqual(visitor.get('/api/live/events?once=true').status_code,401)

    def test_sse_encoder_has_id_and_json(self):
        sample={'id':3,'project_id':'a'*20,'agent':'Engineering','message':'Hello', 'state':'done','created_at':'now'}
        encoded=encode_sse_event(sample)
        self.assertTrue(encoded.startswith('id: 3\nevent: wfs-event\n'))
        self.assertTrue(encoded.endswith('\n\n'))
        self.assertIn('"message":"Hello"',encoded)

    def test_pipeline_real_task_and_handoff_records_with_mock_model(self):
        pid=self.create(mode='ai')
        self.assertTrue(store.change_priority(pid,3))
        def fake(role,sys_prompt,message,budget):
            if role=='Product Manager':return {'summary':'Responsive site','acceptance_criteria':['works'],
                'tasks':[{'role':'Frontend Engineer','description':'Create a usable landing page','files':['index.html','app.js']}]}
            if role=='Software Architect':return {'components':['Web']}
            if role=='UI/UX Designer':return {'visual_direction':'dark'}
            if role=='Frontend Engineer':return {'files':{'index.html':'<!doctype html><html><body><button>Press</button><script src="app.js"></script></body></html>',
                                                      'app.js':'document.querySelector("button").addEventListener("click",()=>alert("ok"));'}}
            if role=='QA Reviewer':return {'summary':'Advisory review complete','issues':[]}
            raise AssertionError(role)
        with patch.object(pipeline.provider,'invoke',side_effect=fake):
            self.assertTrue(worker.execute_one())
        self.assertEqual(store.get_project(pid)['status'],'completed')
        view=store.collaboration_details(pid)
        self.assertEqual(view['task_counts']['done'],1)
        self.assertEqual(view['task_counts']['working'],0)
        self.assertEqual(len(view['handoffs']),4)
        self.assertTrue(any(x['source']=='Quality Lab' for x in view['handoffs']))

    def test_migration_idempotent_existing_database(self):
        store.init_db();store.init_db()
        with store.connect() as cx:
            for table in ('planned_tasks','agent_handoffs','operator_notes'):
                self.assertTrue(cx.execute('SELECT name FROM sqlite_master WHERE name=?',(table,)).fetchone())

    def test_new_interface_and_assets_present(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        for marker in ('page-collaboration','collab-tasks','collab-handoffs','collab-notes','collab-note-form','live-event-status'):
            self.assertIn('id="'+marker+'"',response.text)
        for filename in ('/static/collaboration.js','/static/style.css'):
            self.assertEqual(self.client.get(filename).status_code,200)

if __name__=='__main__':unittest.main()
