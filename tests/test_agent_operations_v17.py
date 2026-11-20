"""v1.7: persistent trace, authenticated batch review, host-only retry and React preview requests.
No GitHub, Docker or AI network needed.
"""
import importlib.util
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store
from app.main import app


class AgentOperationsV17(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app);cls.client.__enter__()
        r=cls.client.post('/api/login',json={'password':PASSWORD})
        assert r.status_code==200,r.text
        cls.headers={'X-WFS-CSRF':r.json()['csrf']}

    @classmethod
    def tearDownClass(cls):cls.client.__exit__(None,None,None)

    def project(self,stack='static',review='auto',mode='demo',status='completed'):
        pid=store.create_project('Operations QA','Build a fully accessible site with great layout',mode,stack,task_review_mode=review)['id']
        self.addCleanup(lambda: store.remove_project(pid) if store.get_project(pid) and store.get_project(pid)['status'] in ('completed','cancelled','failed') else None)
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status=?,attempts=1,phase='task_approval',worker_id=? WHERE id=?",(status,'fixture-'+pid if status=='running' else None,pid))
        return pid

    def post(self,path,data=None,auth=True):
        return self.client.post(path,json=data,headers=self.headers if auth else {})

    def test_migration_idempotent_and_authenticated_operator_timeline(self):
        store.init_db();store.init_db()
        pid=self.project()
        job=self.post(f'/api/projects/{pid}/operator-jobs',{'kind':'qa-static'}).json()['job_id']
        self.assertEqual(self.client.get(f'/api/operator/jobs/{job}').status_code,200)
        self.assertEqual(self.client.get(f'/api/operator/jobs/{job}').json()['steps'][0]['stage'],'queued')
        with TestClient(app) as other:
            self.assertEqual(other.get(f'/api/operator/jobs/{job}').status_code,401)
        self.assertIsNotNone(store.claim_operator_job(job))
        self.assertTrue(store.operator_job_step(job,'executing','Trusted bounded stage description'))
        self.assertTrue(store.operator_job_heartbeat(job))
        self.assertTrue(store.finish_operator_job(job,'completed',{'exit_code':0}))
        result=self.client.get(f'/api/operator/jobs/{job}').json()
        self.assertEqual([s['stage'] for s in result['steps']],['queued','running','executing','completed'])
        self.assertEqual(result['result']['exit_code'],0)
        self.assertFalse(result['possibly_stalled'])
        self.assertFalse(store.operator_job_heartbeat(job))
        self.assertFalse(store.operator_job_step(job,'executing','again'))

    def test_failed_job_retry_requires_csrf_and_host_reapproval(self):
        pid=self.project()
        jid=store.create_operator_job(pid,'qa-static',{})
        self.assertIsNotNone(store.claim_operator_job(jid))
        self.assertTrue(store.finish_operator_job(jid,'failed',{'exit_code':2}))
        url=f'/api/operator/jobs/{jid}/retry'
        self.assertEqual(self.post(url,auth=False).status_code,403)
        response=self.post(url)
        self.assertEqual(response.status_code,202,response.text)
        new=response.json()['job_id'];self.assertNotEqual(jid,new)
        details=self.client.get(f'/api/operator/jobs/{new}').json()
        self.assertEqual(details['retry_of'],jid)
        self.assertEqual(details['status'],'queued')
        self.assertEqual(details['steps'][0]['stage'],'queued')
        self.assertEqual(self.post(f'/api/operator/jobs/{new}/retry').status_code,409)
        self.assertTrue(store.cancel_operator_job(new))
        self.assertEqual(self.post(f'/api/operator/jobs/{new}/retry').status_code,409)
        self.assertEqual(self.post('/api/operator/jobs/not-a-job/retry').status_code,404)

    def test_react_build_request_is_stack_scoped_and_not_auto_executed(self):
        static=self.project()
        self.assertEqual(self.post(f'/api/projects/{static}/operator-jobs',{'kind':'react-build'}).status_code,409)
        pid=self.project('react-vite',mode='ai')
        result=self.post(f'/api/projects/{pid}/operator-jobs',{'kind':'react-build'})
        self.assertEqual(result.status_code,202,result.text)
        detail=self.client.get('/api/operator/jobs/'+result.json()['job_id']).json()
        self.assertEqual(detail['status'],'queued')
        self.assertEqual(detail['kind'],'react-build')

    def test_bulk_review_preserves_blocked_tasks_and_audits(self):
        pid=self.project(review='manual',mode='ai',status='running')
        tasks=[{'id':'T1','role':'Builder','division':'Engineering','task':'Build UI','files':['index.html']},
               {'id':'T2','role':'Tester','division':'Quality Lab','task':'Test UI','files':['README.md']},
               {'id':'T3','role':'Designer','division':'Creative Studio','task':'Design','files':['style.css']}]
        store.record_tasks(pid,tasks,worker_id=store.get_project(pid)['worker_id'])
        self.assertTrue(store.decide_task(pid,'T2','blocked','Needs requirements',1))
        url=f'/api/projects/{pid}/tasks/approve-pending'
        self.assertEqual(self.post(url,{'attempt':1},auth=False).status_code,403)
        self.assertEqual(self.post(url,{'attempt':2}).status_code,409)
        result=self.post(url,{'attempt':1,'feedback':'Check accessibility'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['approved'],2)
        gate=store.task_gate(pid)
        self.assertEqual((gate['approved'],gate['blocked'],gate['pending']),(2,1,0))
        self.assertEqual(store.task_feedback(pid,'T1'),'Check accessibility')
        self.assertEqual(store.task_feedback(pid,'T2'),'Needs requirements')
        self.assertEqual(self.post(url,{'attempt':1}).status_code,409)
        self.assertTrue(any(ev['state']=='task_batch_approved' for ev in store.list_events(pid)))
        with store.connect() as cx:cx.execute("UPDATE projects SET status='cancelled' WHERE id=?",(pid,))

    def test_bulk_review_blocked_in_auto_mode_and_ui_controls_present(self):
        pid=self.project(review='auto',mode='ai',status='running')
        self.assertEqual(self.post(f'/api/projects/{pid}/tasks/approve-pending',{'attempt':1}).status_code,409)
        with store.connect() as cx:cx.execute("UPDATE projects SET status='completed' WHERE id=?",(pid,))
        html=self.client.get('/').text
        for marker in ('op-search','op-status-filter','operator-detail-dialog','collab-approve-pending'):
            self.assertIn('id="'+marker+'"',html)
        self.assertIn('react-build',html)

    def test_visual_office_operator_panel_gets_only_server_records(self):
        pid=self.project()
        jid=store.create_operator_job(pid,'qa-static',{})
        response=self.client.get('/api/office/live?floor=3&project_id='+pid)
        self.assertEqual(response.status_code,200)
        jobs=response.json()['operator_jobs']
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['id'],jid)
        self.assertEqual(jobs[0]['status'],'queued')
        self.assertNotIn('options_json',jobs[0])
        other=self.project()
        self.assertEqual(self.client.get('/api/office/live?floor=1&project_id='+other).json()['operator_jobs'],[])
        self.assertTrue(store.cancel_operator_job(jid))

    def test_operator_runner_react_requires_explicit_windows_powershell(self):
        root=Path(__file__).parents[1]
        spec=importlib.util.spec_from_file_location('runner17',root/'scripts/operator-runner.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with patch.object(mod,'check_project',return_value=(root,'react-vite')):
            with patch.object(mod.shutil,'which',return_value=None):
                with self.assertRaisesRegex(RuntimeError,'requires Windows PowerShell'):
                    mod.execute({'project_id':'a'*20,'kind':'react-build','id':'b'*24})

if __name__=='__main__':unittest.main()
