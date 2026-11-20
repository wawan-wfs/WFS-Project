"""Deterministic tests; real model and Docker runs are deliberately not claimed."""
import io
import os
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

TMP=tempfile.TemporaryDirectory()
os.environ['WFS_DATA_DIR']=TMP.name
os.environ['WFS_SESSION_SECRET']='test-test-key-not-for-deployment'
import hashlib, secrets
PASSWORD='a-test-very-strong-password'
salt=secrets.token_hex(16)
os.environ['WFS_ADMIN_PASSWORD_HASH']='pbkdf2_sha256:260000:'+salt+':'+hashlib.pbkdf2_hmac('sha256',PASSWORD.encode(),bytes.fromhex(salt),260000).hex()
os.environ.pop('OPENAI_API_KEY',None)

from fastapi.testclient import TestClient
from app import auth,config,store,validation,pipeline,worker
from app.main import app
# Legacy tests create simulated 'running' projects without worker leases. Allow test fixtures
# beyond production's active-project cap; capacity is tested separately with a scoped patch.
config.MAX_ACTIVE_PROJECTS=100

class WfsTest(unittest.TestCase):
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

    def post(self,url,data=None,csrf=True):
        h={'X-WFS-CSRF':self.csrf} if csrf else {}
        return self.client.post(url,json=data,headers=h)

    def test_login_guard_and_logout(self):
        with TestClient(app) as fresh:
            self.assertEqual(fresh.get('/api/projects').status_code,401)
            self.assertEqual(fresh.post('/api/login',json={'password':'incorrect'}).status_code,401)
            ok=fresh.post('/api/login',json={'password':PASSWORD})
            self.assertEqual(ok.status_code,200)
            self.assertEqual(fresh.get('/api/projects').status_code,200)
            self.assertEqual(fresh.post('/api/logout').status_code,403)
            c=ok.json()['csrf']
            self.assertEqual(fresh.post('/api/logout',headers={'X-WFS-CSRF':c}).status_code,200)
            self.assertEqual(fresh.get('/api/projects').status_code,401)

    def test_csrf_and_origin_check(self):
        params={'title':'My Site','prompt':'A modern working webpage, accessible','stack':'static','mode':'demo'}
        self.assertEqual(self.post('/api/projects',params,csrf=False).status_code,403)
        hostile=self.client.post('/api/projects',json=params,headers={'X-WFS-CSRF':self.csrf,'Origin':'https://attacker.invalid'})
        self.assertEqual(hostile.status_code,403)

    def test_reject_ai_without_api_key(self):
        r=self.post('/api/projects',{'title':'AI Build','prompt':'Build a real weather application','stack':'static','mode':'ai'})
        self.assertEqual(r.status_code,409)

    def test_demo_job_artifact_zip_preview_and_retry(self):
        data={'title':'WFS <script>','prompt':'Make a responsive studio design for this brand','stack':'static','mode':'demo'}
        r=self.post('/api/projects',data)
        self.assertEqual(r.status_code,202,r.text)
        pid=r.json()['id']
        self.assertEqual(worker.execute_one(),True)
        detail=self.client.get(f'/api/projects/{pid}').json()
        self.assertEqual(detail['status'],'completed',detail.get('error'))
        agents=self.client.get(f'/api/projects/{pid}/events').json()
        self.assertTrue(any(x['agent']=='Delivery Manager' for x in agents))
        files=self.client.get(f'/api/projects/{pid}/files').json()
        self.assertIn('WFS_DELIVERY.md',[x['name'] for x in files])
        r=self.client.get(f'/preview/{pid}/index.html')
        self.assertEqual(r.status_code,200)
        self.assertIn('&lt;script&gt;',r.text)
        self.assertIn('sandbox allow-scripts',r.headers['content-security-policy'])
        r=self.client.get(f'/api/projects/{pid}/download')
        with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
            self.assertIn('index.html',archive.namelist())
            self.assertIn('styles.css',archive.namelist())
            self.assertIn('app.js',archive.namelist())
        self.assertEqual(self.post(f'/api/projects/{pid}/retry').status_code,409)
        self.assertEqual(self.client.get(f'/api/projects/{pid}/files/../../.env').status_code,404)

    def test_idempotency_and_cancel(self):
        data={'title':'Queued Job','prompt':'Build a working static gallery for photos','mode':'demo','stack':'static'}
        headers={'X-WFS-CSRF':self.csrf,'Idempotency-Key':'request-replay-123'}
        x=self.client.post('/api/projects',json=data,headers=headers)
        y=self.client.post('/api/projects',json=data,headers=headers)
        self.assertEqual(x.json()['id'],y.json()['id'])
        pid=x.json()['id']
        self.assertEqual(self.post(f'/api/projects/{pid}/cancel').json()['status'],'cancelled')
        self.assertEqual(self.post(f'/api/projects/{pid}/retry').json()['status'],'queued')
        self.assertEqual(worker.execute_one(),True)
        self.assertEqual(store.get_project(pid)['status'],'completed')

    def test_real_agent_pipeline_mock(self):
        pid=store.create_project('AI Test Site','Build a functional responsive website with actions','ai','static')['id']
        original=pipeline.provider.invoke
        calls=[]
        def fake(role,instructions,message,budget):
            calls.append(role)
            if role=='Product Manager':return {'summary':'Website demonstrasi otomatis','acceptance_criteria':['Valid HTML','Valid JS'],
                   'tasks':[{'role':'Frontend Engineer','description':'Build functional front end',
                             'files':['index.html','styles.css','app.js']},
                            {'role':'Documentation Engineer','description':'Write setup guide','files':['README.md']}]}
            if role=='Software Architect':return {'components':['landing'],'integration':'static assets'}
            if role=='UI/UX Designer':return {'visual_direction':'clean','colors':{'background':'black'}}
            if role=='Frontend Engineer':return {'files':{'index.html':'<html><head><link rel="stylesheet" href="styles.css"></head><body>Test<script src="app.js"></script></body></html>',
                                                'styles.css':'body{margin:0}', 'app.js':'console.log("ready")'}}
            if role=='Documentation Engineer':return {'files':{'README.md':'# Valid setup\n\nOpen index.html'}}
            if role=='QA Reviewer':return {'summary':'AI review; not a real runtime test','issues':[]}
            raise Exception('Unexpected role: '+role)
        try:
            pipeline.provider.invoke=fake
            self.assertTrue(worker.execute_one())
        finally:
            pipeline.provider.invoke=original
        result=store.get_project(pid)
        self.assertEqual(result['status'],'completed',result['error'])
        self.assertGreaterEqual(len(store.list_agents(pid)),6)
        self.assertIn('WFS_DELIVERY.md',[x['name'] for x in store.list_artifacts(pid)])
        report=(config.PROJECTS/pid/'WFS_DELIVERY.md').read_text()
        self.assertIn('not automatically production certified',report)
        self.assertIn('QA Reviewer',calls)

    def test_malicious_paths_and_syntax(self):
        for name in ('../secrets.txt','/etc/passwd','dir/../safe.js','C:\\secrets.txt','data/file.json','.git/hooks/pre-commit','a//b.js','CON.txt'):
            with self.subTest(name=name),self.assertRaises(ValueError):validation.clean_path(name)
        with self.assertRaises(ValueError):validation.check_files({'index.html':'<h1>hi</h1>','broken.py':'def hello('})
        with self.assertRaises(ValueError):validation.check_files({'index.html':'<h1>hi</h1>','creds.js':'const k="sk-proj-123456789abcdefgh"'})
        with self.assertRaises(ValueError):pipeline._safe_tasks({'tasks':[
           {'role':'Frontend Engineer','files':['index.html']},
           {'role':'Backend Engineer','files':['index.html']} ]},'static')

    def test_stale_worker_recovery(self):
        pid=store.create_project('Recovery Check','Build a responsive website that is testable','demo','static')['id']
        claimed=store.claim('crashed-worker')
        self.assertEqual(claimed['id'],pid)
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',('2000-01-01T00:00:00+00:00',pid))
        self.assertGreaterEqual(store.recover_stale(180),1)
        self.assertEqual(store.get_project(pid)['status'],'interrupted')
        self.assertEqual(self.post(f'/api/projects/{pid}/retry').status_code,200)
        self.assertTrue(worker.execute_one())
        self.assertEqual(store.get_project(pid)['status'],'completed')

    def test_qa_repair_and_replan(self):
        pid=store.create_project('AI Fix Test','Create a static page with valid JSON configuration','ai','static')['id']
        original=pipeline.provider.invoke
        seq={'plan':0,'review':0,'repair':0}
        def fake(role,instructions,message,budget):
            if role=='Product Manager':
                seq['plan']+=1
                if seq['plan']==1:
                    return {'summary':'Bad plan','tasks':[{'role':'Invalid Role','files':['index.html']}]}
                return {'summary':'Fixed plan','tasks':[
                   {'role':'Frontend Engineer','description':'Write site and config','files':['index.html','config.json']}]}
            if role=='Software Architect':return {'components':['static site']}
            if role=='UI/UX Designer':return {'visual_direction':'minimal'}
            if role=='Frontend Engineer':return {'files':{
                  'index.html':'<html><body>Valid site</body></html>',
                  'config.json':'{"status":missing}'}}
            if role=='QA Repair Engineer':
                seq['repair']+=1
                return {'files':{'config.json':'{"status":"ready"}'}}
            if role=='QA Reviewer':
                seq['review']+=1
                return {'summary':'No remaining known issues','issues':[]}
            raise RuntimeError('unexpected '+role)
        try:
            pipeline.provider.invoke=fake
            worker.execute_one()
        finally:
            pipeline.provider.invoke=original
        self.assertEqual(store.get_project(pid)['status'],'completed',store.get_project(pid)['error'])
        self.assertEqual(seq['plan'],2)
        self.assertEqual(seq['repair'],1)
        self.assertEqual((config.PROJECTS/pid/'config.json').read_text(),'{' + '"status":"ready"}')

    def test_failed_mode_and_retry(self):
        pid=store.create_project('Failure Test','Build a sample website and then fail cleanly','ai','static')['id']
        old=pipeline.provider.invoke
        try:
            pipeline.provider.invoke=lambda *args: (_ for _ in ()).throw(RuntimeError('simulated model failure'))
            worker.execute_one()
        finally:
            pipeline.provider.invoke=old
        self.assertEqual(store.get_project(pid)['status'],'failed')
        self.assertEqual(self.post(f'/api/projects/{pid}/retry').json()['status'],'queued')
        self.assertEqual(self.post(f'/api/projects/{pid}/cancel').json()['status'],'cancelled')

    def test_usage_and_session(self):
        token=auth.create_session()
        self.assertTrue(store.session_valid(token))
        self.assertNotEqual(auth.csrf_for(token),auth.csrf_for('some-other-token'))
        store.session_delete(token)
        self.assertFalse(store.session_valid(token))
        self.assertEqual(self.client.get('/ready').status_code,200)

if __name__=='__main__':unittest.main()
