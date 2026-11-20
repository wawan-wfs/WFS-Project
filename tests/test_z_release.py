"""Regression tests for final local release gates and provider privacy."""
import json
import os
import unittest
from unittest.mock import patch
# Import the established isolated test environment before app.config so this
# module also runs independently, not only after earlier test files seeded DB.
from test_system import PASSWORD
from fastapi.testclient import TestClient
from app import config, pipeline, provider, store, worker
from app.main import app

class ReleaseGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
    def test_durable_login_throttle(self):
        ip='198.51.100.86'
        store.login_success(ip)
        self.assertFalse(store.login_locked(ip))
        for _ in range(8):store.login_failure(ip)
        self.assertTrue(store.login_locked(ip))
        # Querying via a fresh DB connection proves it persists to SQLite.
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT count(*) FROM auth_failures WHERE ip=?',(ip,)).fetchone()[0],8)
        store.login_success(ip)
        self.assertFalse(store.login_locked(ip))

    def test_high_qa_issues_fail_closed_until_human_approval(self):
        project=store.create_project('Review Gate','Build a landing site with usable interactions and design','ai','static')
        pid=project['id']
        def fake(role,instructions,message,budget):
            if role=='Product Manager':return {'summary':'Functional website', 'acceptance_criteria':['Interactive'], 'tasks':[{'role':'Frontend Engineer','description':'Write landing','files':['index.html','app.js']}]}
            if role=='Software Architect':return {'components':['site']}
            if role=='UI/UX Designer':return {'layout':'modern'}
            if role=='Frontend Engineer':return {'files':{'index.html':'<!doctype html><html><body><button>Button</button><script src="app.js"></script></body></html>','app.js':'document.querySelector("button").onclick=()=>alert("hi")'}}
            if role=='QA Reviewer':return {'summary':'High risk found','issues':[{'severity':'high','file':'app.js','description':'Unresolved test issue'}]}
            if role=='QA Repair Engineer':return {'files':{}}
            raise AssertionError(role)
        with patch.object(pipeline.provider,'invoke',side_effect=fake):
            self.assertTrue(worker.execute_one())
        self.assertEqual(store.get_project(pid)['status'],'review_required')
        self.assertIn('WFS_DELIVERY.md',{x['name'] for x in store.list_artifacts(pid)})
        with TestClient(app) as client:
            from test_system import PASSWORD
            c=client.post('/api/login',json={'password':PASSWORD})
            self.assertEqual(c.status_code,200)
            csrf=c.json()['csrf']
            url=f'/api/projects/{pid}/approve'
            self.assertEqual(client.post(url).status_code,403)
            self.assertEqual(client.post(url,headers={'X-WFS-CSRF':csrf}).status_code,200)
            self.assertEqual(client.post(url,headers={'X-WFS-CSRF':csrf}).status_code,409)
            self.assertEqual(client.get(f'/api/projects/{pid}').json()['status'],'completed')
        self.assertTrue(any(x['agent']=='Human Release Approver' for x in store.list_events(pid)))

    def test_provider_disables_storage_and_accounts_tokens(self):
        observed=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':'{"ready":true}'}]}],'usage':{'input_tokens':120,'output_tokens':32}}).encode()
        def fake_urlopen(req,timeout):
            observed.append(json.loads(req.data.decode()))
            return Response()
        pid=store.create_project('Provider Test','Test provider JSON response and privacy settings','ai','static')['id']
        budget=provider.CallBudget(pid)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'safe-test-key'}),patch.object(provider.request,'urlopen',side_effect=fake_urlopen):
            out=provider.invoke('QA Reviewer','Return a JSON object','Test',budget)
        self.assertEqual(out,{'ready':True})
        self.assertIs(observed[0]['store'],False)
        self.assertEqual(budget.tokens,152)
        self.assertEqual(store.get_usage(pid)['input_tokens'],120)

    def test_incomplete_provider_response_not_treated_as_success(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return json.dumps({'status':'incomplete','output':[]}).encode()
        pid=store.create_project('Incomplete Model','Test non completed provider response','ai','static')['id']
        with patch.dict(os.environ,{'OPENAI_API_KEY':'safe-test-key'}),patch.object(provider.request,'urlopen',return_value=Response()):
            with self.assertRaisesRegex(provider.ProviderFailure,'tidak selesai'):
                provider.invoke('QA Reviewer','Return JSON','Test',provider.CallBudget(pid))

    def test_approval_cannot_bypass_other_status(self):
        pid=store.create_project('Pending Mission','Build a safe responsive static website','demo','static')['id']
        self.assertFalse(store.approve(pid))
        self.assertEqual(store.get_project(pid)['status'],'queued')
        self.assertEqual(store.cancel(pid),'cancelled')

if __name__=='__main__':unittest.main()

# Additional scenario tests; intentionally no API key or actual Docker is needed.
class EndToEndAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
    def test_idempotency_conflict_and_case_insensitive_paths(self):
        from app import validation
        with self.assertRaisesRegex(ValueError,'Windows'):
            validation.check_files({'index.html':'<h1>ok</h1>','Main.js':'console.log(1)','main.js':'console.log(2)'})
        with self.assertRaisesRegex(ValueError,'React/Vite'):
            validation.check_files({'package.json':'{}'},'react-vite')
        self.assertEqual(validation.clean_path('.env.example'),'.env.example')
        first=store.create_project('Same Brief','Build a modern landing page for a brand','demo','static','same-key-example-2026')
        again=store.create_project('Same Brief','Build a modern landing page for a brand','demo','static','same-key-example-2026')
        self.assertEqual(first['id'],again['id'])
        with self.assertRaisesRegex(ValueError,'brief yang berbeda'):
            store.create_project('Different Brief','Build a different landing page with charts','demo','static','same-key-example-2026')
        store.cancel(first['id'])

    def test_operator_built_react_preview_inline_sandbox(self):
        from app import preview
        pid=store.create_project('React Preview','Build a responsive interactive React app','ai','react-vite')['id']
        root=config.DATA/'previews'/pid
        (root/'assets').mkdir(parents=True,exist_ok=True)
        (root/'index.html').write_text('<!doctype html><html><head><link rel="stylesheet" href="./assets/index-abc.css"></head><body><div id="root"></div><script type="module" crossorigin src="./assets/index-abc.js"></script></body></html>')
        (root/'assets/index-abc.css').write_text('body{background:#fff}')
        (root/'assets/index-abc.js').write_text('document.getElementById("root").innerText="React built"')
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+pid,pid))
        self.assertTrue(store.finish(pid,'completed',worker_id='fixture-'+pid))
        with TestClient(app) as client:
            from test_system import PASSWORD
            login=client.post('/api/login',json={'password':PASSWORD})
            self.assertEqual(login.status_code,200)
            r=client.get(f'/preview/{pid}/index.html')
            self.assertEqual(r.status_code,200)
            self.assertIn('React built',r.text)
            self.assertIn('body{background:#fff}',r.text)
            self.assertNotIn('src="./assets/',r.text)
            self.assertIn('sandbox allow-scripts',r.headers['Content-Security-Policy'])
            self.assertTrue(client.get(f'/api/projects/{pid}').json()['preview_ready'])

    def test_real_http_adapter_against_local_fixture(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import threading
        class Fixture(BaseHTTPRequestHandler):
            requests=[]
            def log_message(self,*args):pass
            def do_POST(self):
                size=int(self.headers.get('Content-Length','0'))
                req=json.loads(self.rfile.read(size))
                Fixture.requests.append(req)
                instr=req.get('instructions','')
                if 'bernama Product Manager ' in instr:
                    result={'summary':'Test local HTTP provider','tasks':[{'role':'Frontend Engineer','description':'Make site','files':['index.html','app.js']}], 'acceptance_criteria':['HTML valid']}
                elif 'bernama Software Architect ' in instr:result={'components':['static']}
                elif 'bernama UI/UX Designer ' in instr:result={'visual_direction':'simple'}
                elif 'bernama Frontend Engineer ' in instr:result={'files':{'index.html':'<html><body><div id="root">ok</div><script src="app.js"></script></body></html>','app.js':'console.log("hello")'}}
                elif 'bernama QA Reviewer ' in instr:result={'summary':'Passed advisory review','issues':[]}
                else:result={'summary':'Unexpected role', 'issues':[]}
                payload={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(result)}]}],'usage':{'input_tokens':5,'output_tokens':9}}
                data=json.dumps(payload).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        pid=store.create_project('Mock HTTP Provider','Build a landing page with a button and a real event','ai','static')['id']
        store.change_priority(pid,3)  # isolate integration fixture from jobs left by other test modules
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'fixture-only','WFS_ALLOW_HTTP_PROVIDER':'true'}),patch.object(config,'API_BASE',f'http://127.0.0.1:{server.server_port}/v1/responses'):
                self.assertTrue(worker.execute_one())
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)
        self.assertEqual(store.get_project(pid)['status'],'completed',store.get_project(pid)['error'])
        self.assertGreaterEqual(len(Fixture.requests),5)
        self.assertTrue(all(req.get('store') is False for req in Fixture.requests))
        self.assertGreaterEqual(store.get_usage(pid)['input_tokens'],25)
        self.assertIn('index.html',{x['name'] for x in store.list_artifacts(pid)})
