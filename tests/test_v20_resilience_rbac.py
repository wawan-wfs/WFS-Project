"""v2.0 acceptance: RBAC enforcement, durable specialist checkpoints and sandbox planning.

No paid model, GitHub write, or Docker daemon used by these tests.
"""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from app import pipeline, config
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store
from app.main import app

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wfs_runner_v20', ROOT/'scripts/operator-runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class TeamAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        data=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',data),patch.object(store,'DB',data/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',data/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.client=TestClient(app);self.client.__enter__()
        response=self.client.post('/api/login',json={'username':'admin','password':PASSWORD})
        self.assertEqual(response.status_code,200,response.text)
        self.csrf={'X-WFS-CSRF':response.json()['csrf']}
    def tearDown(self):
        self.client.__exit__(None,None,None)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def post(self,path,data=None):
        return self.client.post(path,json=data,headers=self.csrf)
    def user_client(self,username,password):
        c=TestClient(app);c.__enter__()
        r=c.post('/api/login',json={'username':username,'password':password})
        self.assertEqual(r.status_code,200,r.text)
        return c,{'X-WFS-CSRF':r.json()['csrf']}

    def test_owner_team_creation_csrf_and_no_hash_exposure(self):
        self.assertEqual(self.client.get('/api/users').status_code,200)
        self.assertEqual(self.client.post('/api/users',json={'username':'worker_a','password':'12-strong-pass','role':'developer'}).status_code,403)
        weak=self.post('/api/users',{'username':'x','password':'short','role':'owner'})
        self.assertEqual(weak.status_code,422)
        created=self.post('/api/users',{'username':'worker_a','password':'12-strong-pass','role':'developer'})
        self.assertEqual(created.status_code,201,created.text)
        users=self.client.get('/api/users').json()
        self.assertEqual(len(users['users']),2)
        self.assertNotIn('password_hash',str(users))
        self.assertEqual(self.post('/api/users',{'username':'WORKER_A','password':'12-strong-pass','role':'developer'}).status_code,409)
        self.assertTrue(any(x['action']=='user_created' for x in users['audit']))

    def test_rbac_viewer_developer_manager_enforced_by_api(self):
        for role in ('viewer','developer','manager'):
            name=role+'_user'
            self.assertEqual(self.post('/api/users',{'username':name,'password':'test-password-1234','role':role}).status_code,201)
            c,csrf=self.user_client(name,'test-password-1234')
            try:
                self.assertEqual(c.get('/api/projects').status_code,200)
                self.assertEqual(c.get('/api/users').status_code,403)
                create=c.post('/api/projects',headers=csrf,json={'title':'Role test '+role,'prompt':'Create a responsive proof of concept app','mode':'demo','stack':'static'})
                if role=='viewer':self.assertEqual(create.status_code,403)
                else:self.assertEqual(create.status_code,202,create.text)
                self.assertEqual(c.post('/api/finops/prices',headers=csrf,json={'model':'x','input_usd_per_million':1,'output_usd_per_million':1}).status_code,403)
                if role=='developer':
                    self.assertEqual(c.post('/api/projects/'+create.json()['id']+'/priority',headers=csrf,json={'priority':3}).status_code,403)
                if role=='manager':
                    self.assertEqual(c.post('/api/projects/'+create.json()['id']+'/priority',headers=csrf,json={'priority':3}).status_code,200)
                    self.assertEqual(c.post('/api/projects/'+create.json()['id']+'/delete',headers=csrf,json={'confirm_id':create.json()['id']}).status_code,403)
            finally:c.__exit__(None,None,None)

    def test_revoking_user_immediately_invalidates_session(self):
        uid=self.post('/api/users',{'username':'revocable','password':'long-unique-pass-123','role':'viewer'}).json()['id']
        c,_=self.user_client('revocable','long-unique-pass-123')
        self.assertEqual(c.get('/api/projects').status_code,200)
        self.assertEqual(self.client.patch('/api/users/'+uid,headers=self.csrf,json={'disabled':True}).status_code,200)
        self.assertEqual(c.get('/api/projects').status_code,401)
        self.assertEqual(c.post('/api/login',json={'username':'revocable','password':'long-unique-pass-123'}).status_code,401)
        self.assertEqual(self.client.patch('/api/users/owner',headers=self.csrf,json={'disabled':True}).status_code,404)
        c.__exit__(None,None,None)

    def test_owner_can_rotate_team_password_and_revoke_sessions(self):
        uid=self.post('/api/users',{'username':'rotatable','password':'original-pass-1234','role':'developer'}).json()['id']
        c,_=self.user_client('rotatable','original-pass-1234')
        self.assertEqual(self.client.patch('/api/users/'+uid,headers=self.csrf,json={'new_password':'short'}).status_code,422)
        self.assertEqual(self.client.patch('/api/users/'+uid,headers=self.csrf,json={'new_password':'new-pass-123456'}).status_code,200)
        self.assertEqual(c.get('/api/projects').status_code,401)
        self.assertEqual(c.post('/api/login',json={'username':'rotatable','password':'original-pass-1234'}).status_code,401)
        self.assertEqual(c.post('/api/login',json={'username':'rotatable','password':'new-pass-123456'}).status_code,200)
        c.__exit__(None,None,None)

    def _prepared_tasks(self):
        pid=store.create_project('Recovery test','Build multiple source files for reliable restart','ai','static')['id']
        project=store.claim('lease-one')
        self.assertEqual(project['id'],pid)
        tasks=[{'id':'T1','role':'Frontend Engineer','division':'Engineering','task':'Create index','files':['index.html']},
               {'id':'T2','role':'Documentation Engineer','division':'Documentation','task':'Write docs','files':['README.md']}]
        store.record_tasks(pid,tasks,worker_id=store.get_project(pid)['worker_id'])
        store.persist_work_plan(pid,{'tasks':tasks},tasks,worker_id=store.get_project(pid)['worker_id'])
        return pid,tasks

    def test_atomic_task_result_and_checksum_validation(self):
        pid,_=self._prepared_tasks()
        self.assertTrue(store.task_transition(pid,'T1','planned','working',worker_id=store.get_project(pid)['worker_id']))
        with self.assertRaises(ValueError):store.save_task_result(pid,'T1',{'other.html':'x'},'lease-one')
        with self.assertRaises(ValueError):store.save_task_result(pid,'T1',{'index.html':'a'},'wrong-worker')
        digest=store.save_task_result(pid,'T1',{'index.html':'<html>Verified</html>'},'lease-one')
        self.assertEqual(len(digest),64)
        self.assertEqual(store.load_task_results(pid)['T1']['index.html'],'<html>Verified</html>')
        with store.connect() as cx:
            cx.execute("UPDATE task_results SET output_json='{}' WHERE project_id=?",(pid,))
        with self.assertRaisesRegex(ValueError,'integrity'):store.load_task_results(pid)

    def test_stale_lease_reuses_finished_tasks_without_duplicate_claim(self):
        pid,_=self._prepared_tasks()
        store.task_transition(pid,'T1','planned','working',worker_id=store.get_project(pid)['worker_id'])
        store.save_task_result(pid,'T1',{'index.html':'<html>done</html>'},'lease-one')
        store.task_transition(pid,'T2','planned','working',worker_id=store.get_project(pid)['worker_id'])
        old=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
        with store.connect() as cx:cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(old,pid))
        self.assertEqual(store.recover_stale(180),1)
        self.assertEqual(store.get_project(pid)['status'],'queued')
        self.assertEqual(store.get_project(pid)['recovery_count'],1)
        resume=store.claim('lease-two')
        self.assertEqual(resume['attempts'],1)
        self.assertEqual(set(store.load_task_results(pid)),{'T1'})
        with store.connect() as cx:
            statuses={r['task_key']:r['status'] for r in cx.execute('SELECT task_key,status FROM planned_tasks WHERE project_id=?',(pid,))}
        self.assertEqual(statuses,{'T1':'done','T2':'planned'})
        with self.assertRaises(ValueError):store.save_task_result(pid,'T2',{'README.md':'text'},'lease-one')
        store.task_transition(pid,'T2','planned','working',worker_id=store.get_project(pid)['worker_id'])
        store.save_task_result(pid,'T2',{'README.md':'text'},'lease-two')
        self.assertEqual(len(store.load_task_results(pid)),2)
        store.finish(pid,'completed',worker_id='lease-one')
        self.assertEqual(store.get_project(pid)['status'],'running')
        store.finish(pid,'completed',worker_id='lease-two')
        self.assertEqual(store.get_project(pid)['status'],'completed')

    def test_recovery_is_bounded_then_requires_manual_action(self):
        pid,_=self._prepared_tasks()
        for attempt in range(3):
            with store.connect() as cx:
                cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds'),pid))
            store.recover_stale(180)
            if attempt<2:
                self.assertEqual(store.get_project(pid)['status'],'queued')
                store.claim('lease-'+str(attempt))
        self.assertEqual(store.get_project(pid)['status'],'interrupted')
        self.assertEqual(store.get_project(pid)['recovery_count'],2)
        result=self.post('/api/projects/'+pid+'/resume-tasks')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(store.get_project(pid)['status'],'queued')

    def test_recovery_claim_is_serialized_across_workers(self):
        pid,_=self._prepared_tasks()
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',
                       ((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds'),pid))
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:store.recover_stale(180),range(5)))
        self.assertEqual(sum(results),1)
        self.assertEqual(store.get_project(pid)['recovery_count'],1)

    def test_pipeline_resume_skips_successful_specialist_calls(self):
        pid=store.create_project('Restartable AI site','Build an interactive accessible website and docs','ai','static')['id']
        claimed=store.claim('specialist-worker-one')
        self.assertEqual(claimed['id'],pid)
        called=[]
        fail_doc=[True]
        def fake(role,instructions,message,budget):
            called.append(role)
            if role=='Product Manager':return {'summary':'Ready to build','acceptance_criteria':['Interactive'],
                'tasks':[{'role':'Frontend Engineer','description':'Write UI','files':['index.html','styles.css','app.js']},
                         {'role':'Documentation Engineer','description':'Write guide','files':['README.md']}]}
            if role=='Software Architect':return {'components':['UI']}
            if role=='UI/UX Designer':return {'visual_direction':'clean'}
            if role=='Frontend Engineer':return {'files':{
                'index.html':'<html><head><link rel="stylesheet" href="styles.css"></head><body><button>Test</button><script src="app.js"></script></body></html>',
                'styles.css':'body{margin:0}', 'app.js':'document.querySelector("button").addEventListener("click",()=>alert("ok"))'}}
            if role=='Documentation Engineer':
                if fail_doc[0]:fail_doc[0]=False;raise RuntimeError('Simulated model transport failure')
                return {'files':{'README.md':'# Setup\nThis is a verified sample'}}
            if role=='QA Reviewer':return {'summary':'pass','issues':[]}
            raise AssertionError(role)
        with patch.object(config,'MAX_PARALLEL',1),patch.object(pipeline.provider,'invoke',side_effect=fake):
            with self.assertRaisesRegex(RuntimeError,'transport failure'):pipeline.run(claimed)
            self.assertIn('T1',store.load_task_results(pid))
            store.block_outstanding_tasks(pid,worker_id=(store.get_project(pid)['worker_id'] or 'inactive-test-claim'))
            store.finish(pid,'failed',worker_id='specialist-worker-one')
            self.assertTrue(store.resume_partial_project(pid))
            resumed=store.claim('specialist-worker-two')
            self.assertEqual(resumed['attempts'],1)
            result=pipeline.run(resumed)
            store.finish(pid,'review_required' if result=='review_required' else 'completed',worker_id='specialist-worker-two')
        self.assertEqual(called.count('Product Manager'),1)
        self.assertEqual(called.count('Frontend Engineer'),1)
        self.assertEqual(called.count('Documentation Engineer'),2)
        self.assertEqual(store.get_project(pid)['status'],'completed')
        self.assertIsNone(store.get_checkpoint(pid))
        self.assertGreaterEqual(len(store.list_artifacts(pid)),4)

    def test_preview_trio_job_is_explicit_and_fastapi_only(self):
        fast=store.create_project('FastAPI project','Build full stack fastapi and web frontend','demo','fastapi')['id']
        store.claim('worker');store.finish(fast,'completed',worker_id=store.get_project(fast)['worker_id'])
        queued=self.post('/api/projects/'+fast+'/operator-jobs',{'kind':'preview-trio-start'})
        self.assertEqual(queued.status_code,202,queued.text)
        self.assertEqual(store.list_operator_jobs()[0]['status'],'queued')
        self.assertFalse(runner.docker_exists.__name__=='fake_docker')
        static=store.create_project('Static project','Build static web landing page for demo','demo','static')['id']
        store.claim('worker');store.finish(static,'completed',worker_id=store.get_project(static)['worker_id'])
        self.assertEqual(self.post('/api/projects/'+static+'/operator-jobs',{'kind':'preview-trio-start'}).status_code,409)

    def test_preview_gateway_contract_and_frontend_detection(self):
        root=Path(self.temp.name)/'check'
        (root/'frontend/dist').mkdir(parents=True)
        (root/'frontend/dist/index.html').write_text('<html>Hello</html>')
        self.assertEqual(runner.preview_trio_frontend(root),root/'frontend/dist')
        with patch.object(runner,'check_project',return_value=(root,'fastapi')), \
             patch.object(runner,'docker_exists',return_value=False), \
             patch.object(runner,'preview_stack_start',return_value={'url':'http://127.0.0.1:12500/'}), \
             patch.object(runner,'docker',return_value='abcdef0123456789') as dock, \
             patch.object(runner.socket,'create_connection',return_value=MagicMock()):
            with patch.object(runner.time,'sleep',return_value=None):
                out=runner.preview_trio_start('a'*20)
            self.assertIn('frontend_url',out)
            cmd=dock.call_args.args[0]
            self.assertIn('--read-only',cmd)
            self.assertIn('--cap-drop',cmd)
            self.assertIn('--network',cmd)
            self.assertTrue(any('trusted/gateway.py' in item for item in cmd))
            self.assertFalse(any('docker.sock' in item for item in cmd))

if __name__=='__main__':unittest.main()
