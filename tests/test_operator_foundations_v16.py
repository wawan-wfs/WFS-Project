"""v1.6 task-gate, queued operator actions and local-only preview construction.
No network, Docker, GitHub credentials, or real AI calls are needed.
"""
import json
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store, pipeline, worker
from app.main import app


class OperatorFoundationsV16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)
        cls.client.__enter__()
        response=cls.client.post('/api/login',json={'password':PASSWORD})
        assert response.status_code==200,response.text
        cls.headers={'X-WFS-CSRF':response.json()['csrf']}

    @classmethod
    def tearDownClass(cls):cls.client.__exit__(None,None,None)

    def create(self,mode='demo',review='auto',stack='static'):
        project=store.create_project('Human Gate Test','Build a working accessible website for our customer',mode,stack,
                                     task_review_mode=review)
        self.addCleanup(self.clean,project['id'])
        return project['id']

    @staticmethod
    def clean(pid):
        project=store.get_project(pid)
        if project and project['status'] in ('queued','paused','running'):
            store.cancel(pid)
        if project and store.get_project(pid)['status']=='cancel_requested':store.finish(pid,'cancelled',worker_id=store.get_project(pid)['worker_id'])

    @staticmethod
    def running(pid):
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',phase='task_approval',attempts=1,worker_id=? WHERE id=?",('fixture-'+pid,pid))

    def plan(self,pid):
        self.running(pid)
        tasks=[{'id':'T1','role':'Frontend Engineer','division':'Engineering','task':'Build UI','files':['index.html']},
               {'id':'T2','role':'Documentation Engineer','division':'Documentation','task':'Write docs','files':['README.md']}]
        store.record_tasks(pid,tasks,worker_id=store.get_project(pid)['worker_id'])

    def post(self,url,body,authorized=True):
        return self.client.post(url,json=body,headers=self.headers if authorized else {})

    def test_manual_approvals_persist_and_are_audited(self):
        pid=self.create(mode='ai',review='manual');self.plan(pid)
        info=self.client.get(f'/api/projects/{pid}/collaboration').json()
        self.assertEqual(info['task_review_mode'],'manual')
        self.assertEqual([t['decision'] for t in info['tasks']],['pending','pending'])
        self.assertEqual(store.task_gate(pid)['approved'],0)
        body={'decision':'approved','feedback':'Use semantic HTML and keyboard-friendly navigation','attempt':1}
        url=f'/api/projects/{pid}/tasks/T1/review'
        self.assertEqual(self.post(url,body,False).status_code,403)
        self.assertEqual(self.post(url,body).status_code,200)
        self.assertEqual(store.task_feedback(pid,'T1'),body['feedback'])
        self.assertEqual(store.task_gate(pid)['pending'],1)
        self.assertEqual(self.post(f'/api/projects/{pid}/tasks/T2/review',{'decision':'blocked','feedback':'Wait for design','attempt':1}).status_code,200)
        self.assertEqual(store.task_gate(pid)['blocked'],1)
        self.assertEqual(self.post(f'/api/projects/{pid}/tasks/T2/review',{'decision':'approved','feedback':'Include usage guide','attempt':1}).status_code,200)
        self.assertEqual(store.task_gate(pid)['approved'],2)
        self.assertTrue(any(e['state']=='task_approved' for e in store.list_events(pid)))

    def test_stale_and_nonplanned_task_mutations_rejected(self):
        pid=self.create(mode='ai',review='manual');self.plan(pid)
        api=f'/api/projects/{pid}/tasks/T1/review'
        self.assertEqual(self.post(api,{'decision':'approved','feedback':'ok','attempt':2}).status_code,409)
        self.assertEqual(self.post(api,{'decision':'delete','attempt':1}).status_code,422)
        self.assertEqual(self.post(f'/api/projects/{pid}/tasks/foo/review',{'decision':'approved','attempt':1}).status_code,422)
        self.assertTrue(store.task_transition(pid,'T1','planned','working',worker_id=store.get_project(pid)['worker_id']))
        self.assertEqual(self.post(api,{'decision':'blocked','attempt':1}).status_code,409)
        pid2=self.create(mode='ai',review='auto');self.plan(pid2)
        self.assertEqual(self.post(f'/api/projects/{pid2}/tasks/T1/review',{'decision':'blocked','attempt':1}).status_code,409)

    def test_idempotency_includes_approval_mode(self):
        a=store.create_project('Idempotent Human','Build excellent navigation on mobile','ai','static','id-review-test',task_review_mode='manual')
        self.addCleanup(self.clean,a['id'])
        b=store.create_project('Idempotent Human','Build excellent navigation on mobile','ai','static','id-review-test',task_review_mode='manual')
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(ValueError):
            store.create_project('Idempotent Human','Build excellent navigation on mobile','ai','static','id-review-test',task_review_mode='auto')

    def test_manual_pipeline_waits_before_coding_and_injects_feedback(self):
        # v1.8 changes the worker-blocking approval gate into a persisted checkpoint.
        pid=self.create(mode='ai',review='manual')
        observed=[]
        def fake(role,system,message,budget):
            if role=='Product Manager':return {'summary':'a complete site','acceptance_criteria':['works'],
                'tasks':[{'role':'Frontend Engineer','description':'Build UI','files':['index.html']}]}
            if role=='Software Architect':return {'components':['one']}
            if role=='UI/UX Designer':return {'visual_direction':'accessible'}
            if role=='Frontend Engineer':
                observed.append(json.loads(message).get('approved_operator_feedback'))
                return {'files':{'index.html':'<!doctype html><html><body>Ready</body></html>'}}
            if role=='QA Reviewer':return {'summary':'review','issues':[]}
            raise AssertionError(role)
        self.running(pid)
        with patch.object(pipeline.provider,'invoke',side_effect=fake):
            with self.assertRaises(pipeline.Deferred):
                pipeline.run(store.get_project(pid))
            self.assertEqual(store.get_project(pid)['status'],'awaiting_approval')
            self.assertIsNone(store.get_project(pid)['worker_id'])
            self.assertEqual(observed,[])
            self.assertIsNotNone(store.get_checkpoint(pid))
            self.assertEqual(self.post(f'/api/projects/{pid}/tasks/T1/review',{
                'decision':'approved','feedback':'Use bright typography','attempt':1}).status_code,200)
            self.assertEqual(store.get_project(pid)['status'],'queued')
            resumed=store.claim('resume-test-worker')
            self.assertIsNotNone(resumed)
            self.assertEqual(resumed['id'],pid)
            self.assertEqual(resumed['attempts'],1)
            outcome=pipeline.run(resumed)
            store.finish(pid,'review_required' if outcome=='review_required' else 'completed',worker_id=store.get_project(pid)['worker_id'])
        self.assertEqual(store.get_project(pid)['status'],'completed')
        self.assertEqual(observed,['Use bright typography'])
        self.assertEqual(store.collaboration_details(pid)['task_counts']['done'],1)

    def test_operator_jobs_authorization_validation_and_result(self):
        pid=self.create();self.running(pid)
        url=f'/api/projects/{pid}/operator-jobs'
        self.assertEqual(self.post(url,{'kind':'qa-static'}).status_code,409)
        store.finish(pid,'completed',worker_id=store.get_project(pid)['worker_id'])
        self.assertEqual(self.post(url,{'kind':'qa-static'},False).status_code,403)
        self.assertEqual(self.post(url,{'kind':'github-draft'}).status_code,422)
        self.assertEqual(self.post(url,{'kind':'github-draft','repo':'!invalid'}).status_code,422)
        r=self.post(url,{'kind':'qa-static'})
        self.assertEqual(r.status_code,202,r.text)
        jid=r.json()['job_id']
        jobs=self.client.get('/api/operator/jobs?project_id='+pid).json()
        self.assertEqual(jobs[0]['status'],'queued')
        self.assertIsNone(jobs[0]['result'].get('url'))
        self.assertEqual(store.claim_operator_job(jid)['kind'],'qa-static')
        self.assertIsNone(store.claim_operator_job(jid))
        self.assertTrue(store.finish_operator_job(jid,'completed',{'output':'clean syntax'}))
        self.assertFalse(store.finish_operator_job(jid,'completed',{}))
        self.assertEqual(self.client.get('/api/operator/jobs?project_id='+pid).json()[0]['result']['output'],'clean syntax')
        self.assertTrue(any(e['agent']=='Operator Job Center' for e in store.list_events(pid)))

    def test_runtime_preview_request_only_for_fastapi(self):
        pid=self.create();self.running(pid);store.finish(pid,'completed',worker_id=store.get_project(pid)['worker_id'])
        self.assertEqual(self.post(f'/api/projects/{pid}/operator-jobs',{'kind':'preview-start'}).status_code,409)
        target=self.create(mode='ai',stack='fastapi');self.running(target);store.finish(target,'completed',worker_id=store.get_project(target)['worker_id'])
        for kind in ('preview-start','preview-stop','qa-fastapi'):
            r=self.post(f'/api/projects/{target}/operator-jobs',{'kind':kind})
            self.assertEqual(r.status_code,202,r.text)
        approved=self.post(f'/api/projects/{target}/operator-jobs',{'kind':'github-draft','repo':'myorg/myrepo'})
        self.assertEqual(approved.status_code,202,approved.text)
        self.assertEqual(len(self.client.get('/api/operator/jobs?project_id='+target).json()),4)
        self.assertEqual(self.post(f'/api/projects/{target}/operator-jobs',{'kind':'qa-static'}).status_code,409)

    def test_unauthed_operator_job_listing_blocked(self):
        with TestClient(app) as guest:
            self.assertEqual(guest.get('/api/operator/jobs').status_code,401)
            self.assertEqual(guest.post('/api/projects/'+'a'*20+'/operator-jobs',json={'kind':'qa-static'}).status_code,401)

    def test_operator_hub_ui_and_scripts(self):
        html=self.client.get('/').text
        for marker in ('page-operator','op-job-form','op-project','op-kind','op-repo','op-jobs','task-review-mode'):
            self.assertIn('id="'+marker+'"',html)
        self.assertEqual(self.client.get('/static/operator.js').status_code,200)
        self.assertTrue((Path(__file__).parents[1]/'scripts/operator-runner.py').is_file())


if __name__=='__main__':unittest.main()

# Additional security regression cases keep job cancellation and sandbox flags explicit.
class OperatorJobSafetyV16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app);cls.client.__enter__()
        cls.csrf=cls.client.post('/api/login',json={'password':PASSWORD}).json()['csrf']

    @classmethod
    def tearDownClass(cls):cls.client.__exit__(None,None,None)

    def test_cancel_queued_job_and_prevent_project_deletion_with_jobs(self):
        pid=store.create_project('Operator Job Test','Build a working user interface','demo','static')['id']
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='completed',attempts=1 WHERE id=?",(pid,))
        r=self.client.post(f'/api/projects/{pid}/operator-jobs',json={'kind':'qa-static'},headers={'X-WFS-CSRF':self.csrf})
        self.assertEqual(r.status_code,202)
        jid=r.json()['job_id']
        self.assertFalse(store.remove_project(pid))
        self.assertEqual(self.client.post(f'/api/operator/jobs/{jid}/cancel').status_code,403)
        self.assertEqual(self.client.post(f'/api/operator/jobs/{jid}/cancel',headers={'X-WFS-CSRF':self.csrf}).status_code,200)
        self.assertEqual(self.client.post(f'/api/operator/jobs/{jid}/cancel',headers={'X-WFS-CSRF':self.csrf}).status_code,409)
        self.assertEqual(store.list_operator_jobs(pid)[0]['status'],'cancelled')
        self.assertIsNone(store.claim_operator_job(jid))
        self.assertTrue(store.remove_project(pid))

    def test_preview_docker_arguments_are_local_and_hardened(self):
        import importlib.util
        from unittest.mock import patch
        import tempfile
        ROOT=Path(__file__).parents[1]
        scripts=str(ROOT/'scripts')
        if scripts not in sys.path:sys.path.insert(0,scripts)
        spec=importlib.util.spec_from_file_location('wfs_operator_runner',ROOT/'scripts/operator-runner.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        calls=[]
        def fake_docker(args,timeout=30):
            calls.append(args)
            if args[:2]==['network','ls']:return ''
            if args[:2]==['ps','-aq']:return ''
            if args[0]=='run':return 'deadbeef'*8
            return ''
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp);(project/'app').mkdir();(project/'app/main.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n')
            with patch.object(module,'check_project',return_value=(project,'fastapi')):
                with patch.object(module,'docker',side_effect=fake_docker):
                    r=module.preview_start('f'*20)
        run=next(c for c in calls if c[0]=='run')
        self.assertTrue(r['url'].startswith('http://127.0.0.1:'))
        self.assertIn('--read-only',run)
        self.assertIn('--cap-drop',run)
        self.assertIn('no-new-privileges',run)
        self.assertEqual(run[run.index('--network')+1],'wfs-preview-internal')
        self.assertTrue(run[run.index('-p')+1].startswith('127.0.0.1:'))
        self.assertIn('readonly',run[run.index('--mount')+1])
        self.assertIn('15',run)
        self.assertTrue(any(c[:3]==['network','create','--internal'] for c in calls))
