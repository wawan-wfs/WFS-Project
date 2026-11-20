"""v1.2 regression: versioned revisions, tamper detection, lifecycle, operator QA."""
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD  # sets isolated env BEFORE app.config import
from fastapi.testclient import TestClient
from app import config, store, worker, pipeline, provider
from app.main import app


class ExtendedFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
        cls.client=TestClient(app)
        cls.client.__enter__()
        r=cls.client.post('/api/login',json={'password':PASSWORD})
        assert r.status_code==200, r.text
        cls.csrf=r.json()['csrf']
    @classmethod
    def tearDownClass(cls):cls.client.__exit__(None,None,None)

    def post(self,url,data=None):
        return self.client.post(url,json=data,headers={'X-WFS-CSRF':self.csrf})

    def demo(self):
        p=store.create_project('Initial Demo','Build a responsive functional static application','demo','static')
        worker.execute_one()
        self.assertEqual(store.get_project(p['id'])['status'],'completed')
        return p['id']

    def test_revision_preserves_parent_and_creates_new_version(self):
        parent=self.demo()
        original=(config.PROJECTS/parent/'index.html').read_text()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'local-fixture-value'}):
            result=self.post(f'/api/projects/{parent}/revisions',{'prompt':'Revise only app.js to include a new event log and preserve the rest'})
        self.assertEqual(result.status_code,202,result.text)
        child=result.json()['id']
        self.assertEqual(store.get_project(child)['parent_id'],parent)
        def fake(role,instructions,message,budget):
            if role=='Product Manager':return {'summary':'Simple change','tasks':[{'role':'Frontend Engineer','description':'Change only JavaScript','files':['app.js']}]}
            if role=='Software Architect':return {'components':['existing pages'], 'integration':'reuse existing files'}
            if role=='UI/UX Designer':return {'layout':'preserve existing design'}
            if role=='Frontend Engineer':
                self.assertIn('existing_project_files',message)
                return {'files':{'app.js':'console.log("Revision two");'}}
            if role=='QA Reviewer':return {'summary':'Review advisory only','issues':[]}
            raise AssertionError(role)
        with patch.object(pipeline.provider,'invoke',side_effect=fake):
            self.assertTrue(worker.execute_one())
        self.assertEqual(store.get_project(child)['status'],'completed',store.get_project(child)['error'])
        self.assertEqual((config.PROJECTS/child/'index.html').read_text(),original)
        self.assertNotEqual((config.PROJECTS/child/'app.js').read_text(),(config.PROJECTS/parent/'app.js').read_text())
        self.assertIn('Parent revision: '+parent,(config.PROJECTS/child/'WFS_DELIVERY.md').read_text())
        self.assertEqual(self.post(f'/api/projects/{parent}/delete',{'confirm_id':parent}).status_code,409)
        self.assertEqual(self.client.get(f'/api/projects/{parent}').json()['revisions'][0]['id'],child)

    def test_integrity_prevents_tampered_read_zip_preview_and_revision(self):
        parent=self.demo()
        target=config.PROJECTS/parent/'index.html'
        target.write_text(target.read_text()+'<div>TAMPER</div>')
        self.assertEqual(self.client.get(f'/api/projects/{parent}/files/index.html').status_code,409)
        self.assertEqual(self.client.get(f'/api/projects/{parent}/download').status_code,409)
        self.assertEqual(self.client.get(f'/preview/{parent}/index.html').status_code,409)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'local-fixture-value'}):
            self.assertEqual(self.post(f'/api/projects/{parent}/revisions',{'prompt':'Make an improved working website with more features'}).status_code,409)

    def test_archive_restore_search_stats_and_delete(self):
        parent=self.demo()
        self.assertEqual(self.post(f'/api/projects/{parent}/archive',{'archive':True}).status_code,200)
        self.assertTrue(store.get_project(parent)['archived_at'])
        self.assertNotIn(parent,{p['id'] for p in self.client.get('/api/projects').json()})
        self.assertIn(parent,{p['id'] for p in self.client.get('/api/projects?include_archived=true').json()})
        self.assertGreater(self.client.get('/api/dashboard-stats').json()['archived'],0)
        self.assertEqual(self.post(f'/api/projects/{parent}/archive',{'archive':False}).json()['archived'],False)
        self.assertIsNone(store.get_project(parent)['archived_at'])
        self.assertEqual(self.post(f'/api/projects/{parent}/delete',{'confirm_id':'not-the-id'}).status_code,400)
        self.assertEqual(self.post(f'/api/projects/{parent}/delete',{'confirm_id':parent}).json()['deleted'],True)
        self.assertIsNone(store.get_project(parent))
        self.assertFalse((config.PROJECTS/parent).exists())

    def test_operator_qa_report_and_unsafe_files(self):
        parent=self.demo()
        path=config.DATA/'reports'/parent;path.mkdir(parents=True,exist_ok=True)
        (path/'20261104T000000-test.json').write_text(json.dumps({'project_id':parent,'status':'passed','created_at':'2026-11-04','checks':[{'name':'AST','status':'pass'}]}))
        (path/'20261104T000001-wrong.json').write_text(json.dumps({'project_id':'wrong','status':'passed'}))
        report=self.client.get(f'/api/projects/{parent}/qa-runs').json()
        self.assertEqual(len(report),1)
        self.assertEqual(report[0]['checks'][0]['status'],'pass')

    def test_call_budget_persists_between_attempts(self):
        pid=store.create_project('Budget Check','Build a test app with persistent accounting','ai','static')['id']
        store.usage(pid,'Frontend Engineer','test',100,250)
        budget=provider.CallBudget(pid)
        self.assertEqual(budget.tokens,350)
        self.assertEqual(budget.count,1)
        store.cancel(pid)

    def test_revising_queued_project_refused_and_wrong_stack_refused(self):
        parent=store.create_project('Pending Work','Build a useful web app and tests','demo','static')['id']
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fixture'}):
            self.assertEqual(self.post(f'/api/projects/{parent}/revisions',{'prompt':'Create another version with many extra capabilities'}).status_code,409)
        with self.assertRaisesRegex(ValueError,'Revisi'):
            store.create_project('Bad child','Improve the source code with tests','ai','react-vite',parent_id=parent)
        self.assertEqual(self.post(f'/api/projects/{parent}/archive',{'archive':True}).status_code,409)
        self.assertEqual(self.post(f'/api/projects/{parent}/delete',{'confirm_id':parent}).status_code,409)
        store.cancel(parent)


class SandboxArguments(unittest.TestCase):
    def test_isolation_command(self):
        spec=importlib.util.spec_from_file_location('sandbox_qa',Path(__file__).resolve().parents[1]/'scripts/sandbox-qa.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        name,cmd=module.build_command('python:3.12-slim',Path('/example/source'),Path('/example/probe.py'),'probe.py')
        self.assertTrue(name.startswith('wfs-qa-'))
        for value in ('--network','none','--read-only','--cap-drop','ALL','--pids-limit','--user','10001:10001'):
            self.assertIn(value,cmd)
        self.assertNotIn('/var/run/docker.sock',' '.join(cmd))
        self.assertNotIn('OPENAI_API_KEY',' '.join(cmd))

if __name__=='__main__':unittest.main()

class OperationalSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
        cls.client=TestClient(app)
        cls.client.__enter__()
        login=cls.client.post('/api/login',json={'password':PASSWORD})
        assert login.status_code==200,login.text
        cls.csrf=login.json()['csrf']

    @classmethod
    def tearDownClass(cls):cls.client.__exit__(None,None,None)

    def test_worker_diagnostics_and_auth(self):
        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get('/api/diagnostics').status_code,401)
            self.assertEqual(anonymous.get('/api/office').status_code,401)
            self.assertEqual(anonymous.get('/api/dashboard-stats').status_code,401)
        store.worker_ping('wfs-integration-test',None)
        r=self.client.get('/api/diagnostics')
        self.assertEqual(r.status_code,200)
        self.assertGreaterEqual(r.json()['workers_online'],1)
        self.assertEqual(r.json()['database'],'ready')
        self.assertEqual(self.client.get('/api/office').status_code,200)

    def test_office_uses_real_agent_run_events(self):
        parent=store.create_project('Office workload','Create a dashboard with accessible actions','demo','static')['id']
        record=store.claim('wfs-office-checker')
        self.assertEqual(record['id'],parent)
        agent=store.agent_start(parent,'UI/UX Engineer','Creative Studio','Design page controls',worker_id=store.get_project(parent)['worker_id'])
        overview=self.client.get('/api/office').json()
        self.assertGreaterEqual(overview['Creative Studio']['active'],1)
        store.agent_finish(agent,'done',worker_id=store.get_project(store.agent_run_detail(agent)['project_id'])['worker_id'])
        store.finish(parent,'cancelled',worker_id=store.get_project(parent)['worker_id'])
        overview=self.client.get('/api/office').json()
        self.assertEqual(overview['Creative Studio']['active'],0)
        self.assertGreaterEqual(overview['Creative Studio']['finished'],1)

    def test_schema_migration_from_previous_release(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)
            db=data/'wfs.sqlite3';projects=data/'projects'
            cx=sqlite3.connect(db)
            try:
                cx.execute('CREATE TABLE projects(id TEXT PRIMARY KEY,title TEXT NOT NULL,prompt TEXT NOT NULL, mode TEXT NOT NULL,stack TEXT NOT NULL,status TEXT NOT NULL,phase TEXT NOT NULL DEFAULT "intake",error TEXT,worker_id TEXT,heartbeat_at TEXT,attempts INTEGER NOT NULL DEFAULT 0,idempotency_key TEXT UNIQUE,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
                cx.commit()
            finally:
                cx.close()
            with patch.object(store,'DB',db),patch.object(store,'DATA',data),patch.object(store,'PROJECTS',projects):
                store.init_db()
                store.init_db()  # migration is idempotent
                with store.connect() as cx:
                    cols={r['name'] for r in cx.execute('PRAGMA table_info(projects)')}
                    self.assertTrue({'parent_id','archived_at'}.issubset(cols))
                    self.assertIsNotNone(cx.execute("SELECT 1 FROM sqlite_master WHERE name='worker_instances'").fetchone())

    def test_dockerignore_blocks_env_and_data(self):
        text=(Path(__file__).resolve().parents[1]/'.dockerignore').read_text()
        self.assertIn('\n.env\n',text)
        self.assertIn('\ndata/\n',text)
        self.assertIn('\n.git/\n',text)


class IntegrationBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):store.init_db()

    def test_failed_provider_call_is_counted_across_retries(self):
        pid=store.create_project('Failed request accounting','Build a project without consuming secrets','ai','static')['id']
        failure=provider.error.HTTPError('https://example.invalid',400,'Bad Request',None,None)
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-test-only'}),patch.object(provider.request,'urlopen',side_effect=failure):
                with self.assertRaises(provider.ProviderFailure):
                    provider.invoke('QA Reviewer','Return JSON','Test',provider.CallBudget(pid))
            data=store.get_usage(pid)
            self.assertEqual(data['calls'],0)
            self.assertEqual(data['attempts'],1)
            self.assertEqual(provider.CallBudget(pid).count,1)
        finally:store.cancel(pid)

    def test_github_publisher_dry_run_has_no_network(self):
        from contextlib import redirect_stdout
        import io,sqlite3,sys
        spec=importlib.util.spec_from_file_location('wfs_publisher',Path(__file__).resolve().parents[1]/'scripts/publish-github.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'data/wfs.sqlite3';db.parent.mkdir()
            pid='0123456789abcdefabcd'
            source=root/'data/projects'/pid/'index.html';source.parent.mkdir(parents=True);source.write_text('<h1>safe</h1>')
            cx=sqlite3.connect(db)
            try:
                cx.execute('CREATE TABLE projects (id TEXT PRIMARY KEY,status TEXT,title TEXT)')
                cx.execute('CREATE TABLE artifacts(project_id TEXT,name TEXT,bytes INT,sha256 TEXT)')
                cx.execute('INSERT INTO projects VALUES(?,?,?)',(pid,'completed','Dry run'))
                blob=source.read_bytes()
                cx.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(pid,'index.html',len(blob),hashlib.sha256(blob).hexdigest()))
                cx.commit()
            finally:cx.close()
            with patch.object(mod,'ROOT',root),patch.object(mod,'DB',db),patch.object(sys,'argv',['publish-github.py',pid,'--repo','example/myrepo']),patch.object(mod,'run',side_effect=AssertionError('No external GitHub calls during dry run')):
                stream=io.StringIO()
                with redirect_stdout(stream):result=mod.main()
                self.assertEqual(result,0)
                self.assertIn('DRY-RUN ONLY',stream.getvalue())
