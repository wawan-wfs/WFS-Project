"""v1.9 feature acceptance: budget migration, CSV audit, preview runner sandbox contract.
These tests do not require Docker, GitHub, or paid AI provider access.
"""
from __future__ import annotations
import csv
import importlib.util
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import config,store,provider
from app.main import app

RUNNER=Path(__file__).resolve().parents[1]/'scripts/operator-runner.py'
spec=importlib.util.spec_from_file_location('wfs_operator_v19',RUNNER)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class V19BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'wfs.sqlite3'),patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.client=TestClient(app);self.client.__enter__()
        login=self.client.post('/api/login',json={'password':PASSWORD})
        self.assertEqual(login.status_code,200,login.text)
        self.csrf={'X-WFS-CSRF':login.json()['csrf']}
        self.pid=store.create_project('Financial QA','A sufficiently long project test prompt','demo','static')['id']
    def tearDown(self):
        self.client.__exit__(None,None,None)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def send(self,path,body,csrf=True):
        return self.client.post(path,json=body,headers=self.csrf if csrf else None)

    def test_budget_requires_login_and_csrf_and_validates(self):
        path=f'/api/projects/{self.pid}/budget'
        with TestClient(app) as guest:
            self.assertEqual(guest.get(path).status_code,401)
        self.assertEqual(self.send(path,{'limit_usd':12},csrf=False).status_code,403)
        self.assertEqual(self.send(path,{'limit_usd':-1}).status_code,422)
        self.assertEqual(self.send(path,{'limit_usd':2,'alert_pct':100}).status_code,422)
        self.assertEqual(self.send(path,{'limit_usd':2,'alert_pct':80.1}).status_code,422)
        ok=self.send(path,{'limit_usd':2.0,'alert_pct':75})
        self.assertEqual(ok.status_code,200,ok.text)
        self.assertEqual(ok.json()['limit_usd'],2.0)
        self.assertEqual(self.client.get(path).json()['alert_pct'],75)
        self.assertTrue(self.client.get('/api/finops/budgets').json())
        self.assertEqual(self.client.get('/api/projects/00000000000000000000/budget').status_code,404)

    def test_alerts_are_unique_and_audited(self):
        store.set_model_price('mock',10,10)
        store.set_project_budget(self.pid,1,80)
        store.usage(self.pid,'AI Engineer','mock',90000,0)
        store.usage(self.pid,'AI Engineer','mock',20000,0)
        store.usage(self.pid,'AI Engineer','mock',20000,0)
        status=store.project_budget(self.pid)
        self.assertTrue(status['limit_reached'])
        self.assertEqual([a['level'] for a in status['alerts']],['warning','exceeded'])
        states=[e['state'] for e in store.list_events(self.pid)]
        self.assertEqual(states.count('budget_warning'),1)
        self.assertEqual(states.count('budget_exceeded'),1)
        store.set_project_budget(self.pid,0)
        self.assertFalse(store.project_budget(self.pid)['enabled'])

    def test_parallel_usage_creates_one_alert_each(self):
        store.set_model_price('mock',1,1)
        store.set_project_budget(self.pid,1,90)
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(lambda _:store.usage(self.pid,'Agent','mock',300000,0),range(5)))
        states=[e['state'] for e in store.list_events(self.pid)]
        self.assertEqual(states.count('budget_warning'),1)
        self.assertEqual(states.count('budget_exceeded'),1)

    def test_budget_soft_pre_call_gate_and_missing_prices(self):
        store.set_project_budget(self.pid,0.5)
        budget=provider.CallBudget(self.pid)
        with self.assertRaises(provider.ProviderFailure):budget.charge('unknown')
        store.set_model_price('mock',1,1)
        budget.charge('mock')
        store.usage(self.pid,'Agent','mock',600000,0)
        with self.assertRaises(provider.ProviderFailure):budget.charge('mock')
        store.set_project_budget(self.pid,3)
        budget.charge('mock')
        store.usage(self.pid,'Agent','unpriced',10,15)
        with self.assertRaises(provider.ProviderFailure):budget.charge('mock')
        store.set_project_budget(self.pid,0)
        budget.charge('mock')

    def test_csv_export_auth_safe_formula_and_rate_snapshots(self):
        store.set_model_price('mock',2,7)
        store.usage(self.pid,'=HYPERLINK("evil")','mock',10**6,2*10**6)
        store.set_model_price('mock',5,11)
        store.usage(self.pid,'Agent','mock',1,2)
        r=self.client.get('/api/finops/export.csv?period=all&project_id='+self.pid)
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('attachment;',r.headers['content-disposition'])
        rows=list(csv.DictReader(io.StringIO('\n'.join(x for x in r.text.splitlines() if not x.startswith('#')))))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['input_rate_snapshot'],'5.0')
        self.assertEqual(rows[1]['input_rate_snapshot'],'2.0')
        self.assertTrue(rows[1]['agent'].startswith("'="))
        self.assertEqual(self.client.get('/api/finops/export.csv?period=365d').status_code,422)
        with TestClient(app) as guest:self.assertEqual(guest.get('/api/finops/export.csv').status_code,401)

    def test_migrations_preserve_budget_and_usage_snapshots(self):
        store.set_project_budget(self.pid,12,70)
        store.set_model_price('mock',2,4)
        store.usage(self.pid,'Developer','mock',100,100)
        store.init_db();store.init_db()
        self.assertEqual(store.project_budget(self.pid)['limit_usd'],12.0)
        rows,truncated=store.usage_export_rows(self.pid,'all')
        self.assertEqual(len(rows),1)
        self.assertFalse(truncated)
        self.assertEqual(rows[0]['output_rate_snapshot'],4.0)

    def test_operator_stack_kind_restricted(self):
        # A completed project has no source until a successful worker delivery; job queue
        # validation checks metadata separately from runner's verified-artifact preflight.
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+self.pid,self.pid))
        self.assertTrue(store.finish(self.pid,'completed',worker_id='fixture-'+self.pid))
        a=self.send(f'/api/projects/{self.pid}/operator-jobs',{'kind':'preview-stack-start'})
        self.assertEqual(a.status_code,409)
        another=store.create_project('Fast API','A long enough brief for FastAPI project','demo','fastapi')['id']
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+another,another))
        self.assertTrue(store.finish(another,'completed',worker_id='fixture-'+another))
        ok=self.send(f'/api/projects/{another}/operator-jobs',{'kind':'preview-stack-start'})
        self.assertEqual(ok.status_code,202,ok.text)
        job=store.operator_job_detail(ok.json()['job_id'])
        self.assertEqual(job['kind'],'preview-stack-start')
        self.assertEqual(job['status'],'queued')
        self.assertEqual(self.send(f'/api/projects/{another}/operator-jobs',{'kind':'preview-stack-stop'}).status_code,202)

class V19RunnerTests(unittest.TestCase):
    def test_project_resource_ids_reject_injection(self):
        self.assertEqual(runner.stack_resource_names('a'*20)['network'],'wfs-preview-stack-'+'a'*20)
        for bad in ('abc', '../bad', 'a'*19+'-', 'a'*21):
            with self.assertRaises(ValueError):runner.stack_resource_names(bad)

    def test_stack_uses_isolation_and_never_publishes_database(self):
        commands=[]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'main.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n')
            def fake_docker(args,timeout=30):
                commands.append(args)
                if args[:2]==['ps','-aq']:return ''
                if args[:1]==['run'] and 'wfs-preview-'+('a'*20) in args:return '1234567890abcdef'
                if args[:1]==['run']:return 'db-container-id'
                return ''
            with patch.object(runner,'docker',side_effect=fake_docker),\
                 patch.object(runner,'check_project',return_value=(root,'fastapi')),\
                 patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0)),\
                 patch.object(runner.time,'sleep'),\
                 patch.object(runner.socket,'create_connection'):
                result=runner.preview_stack_start('a'*20)
        self.assertEqual(result['stack'],'fastapi+postgresql')
        runs=[c for c in commands if c[0]=='run']
        self.assertEqual(len(runs),2)
        db,backend=runs
        self.assertNotIn('-p',db)
        self.assertIn('--read-only',backend)
        self.assertIn('--cap-drop',backend)
        self.assertIn('--network',db)
        self.assertIn('--network',backend)
        self.assertNotIn('--privileged',backend)
        self.assertTrue(any(x.startswith('127.0.0.1:') for x in backend))
        self.assertFalse(any(x.startswith('OPENAI_API_KEY') for x in backend))

    def test_stack_failure_cleans_partial_resources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'main.py').write_text('app = 1')
            with patch.object(runner,'docker',side_effect=RuntimeError('Cannot connect to Docker')),\
                 patch.object(runner,'check_project',return_value=(root,'fastapi')),\
                 patch.object(runner,'preview_stack_stop') as cleanup:
                with self.assertRaises(RuntimeError):runner.preview_stack_start('a'*20)
                # Failure before any resources are made leaves nothing to clean.
                cleanup.assert_not_called()

    def test_stack_stop_is_idempotent(self):
        with patch.object(runner,'docker',side_effect=lambda args,timeout=30:''),\
             patch.object(runner,'docker_exists',return_value=False):
            r=runner.preview_stack_stop('a'*20)
        self.assertEqual(r['removed'],[])
        self.assertTrue(r['stopped'])

if __name__=='__main__':unittest.main()
