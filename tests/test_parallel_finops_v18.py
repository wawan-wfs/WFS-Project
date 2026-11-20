"""v1.8 acceptance: parallel claims, nonblocking approval, cost snapshots, node preview contracts.
No Docker daemon, live AI key, or external network is needed.
"""
from __future__ import annotations
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store, config, validation, pipeline
from app.main import app

class ParallelFinopsV18(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patchers=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'wfs.sqlite3'),
                       patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patchers:p.start()
        store.init_db()
        self.client=TestClient(app);self.client.__enter__()
        r=self.client.post('/api/login',json={'password':PASSWORD})
        self.assertEqual(r.status_code,200,r.text)
        self.csrf={'X-WFS-CSRF':r.json()['csrf']}
    def tearDown(self):
        self.client.__exit__(None,None,None)
        for p in reversed(self.patchers):p.stop()
        self.tmp.cleanup()
    def create(self,mode='demo',review='auto',stack='static'):
        return store.create_project('Parallel test','Make a useful accessible working application',mode,stack,task_review_mode=review)['id']
    def post(self,url,payload=None,csrf=True):
        return self.client.post(url,json=payload,headers=self.csrf if csrf else {})

    def test_atomic_claims_global_capacity_and_worker_isolation(self):
        ids=[self.create() for _ in range(5)]
        with patch.object(config,'MAX_ACTIVE_PROJECTS',2):
            with ThreadPoolExecutor(max_workers=5) as pool:
                claimed=list(pool.map(lambda i:store.claim('worker-'+str(i)),range(5)))
            active=[r for r in claimed if r is not None]
            self.assertEqual(len(active),2)
            self.assertEqual(len({r['id'] for r in active}),2)
            snapshot=store.concurrency_snapshot()
            self.assertEqual((snapshot['active_count'],snapshot['free_slots'],snapshot['queued_count']),(2,0,3))
            self.assertIsNone(store.claim('sixth'))
            store.finish(active[0]['id'],'completed',worker_id=store.get_project(active[0]['id'])['worker_id'])
            next_=store.claim('sixth')
            self.assertIsNotNone(next_)
            self.assertEqual(store.concurrency_snapshot()['active_count'],2)

    def test_checkpoint_releases_worker_and_resumes_without_replanning(self):
        pid=self.create(mode='ai',review='manual')
        plan_calls=[];feedback=[]
        def fake(role,instructions,message,budget):
            if role=='Product Manager':
                plan_calls.append(1)
                return {'summary':'build full page','acceptance_criteria':['works'],
                        'tasks':[{'role':'Frontend Engineer','description':'Build page','files':['index.html']}]}
            if role=='Software Architect':return {'components':['page']}
            if role=='UI/UX Designer':return {'visual_direction':'premium'}
            if role=='Frontend Engineer':
                feedback.append(json.loads(message)['approved_operator_feedback'])
                return {'files':{'index.html':'<html><body>Working</body></html>'}}
            if role=='QA Reviewer':return {'summary':'pass','issues':[]}
            raise AssertionError(role)
        with patch.object(config,'MAX_ACTIVE_PROJECTS',1),patch.object(pipeline.provider,'invoke',side_effect=fake):
            first=store.claim('w1');self.assertEqual(first['id'],pid)
            with self.assertRaises(pipeline.Deferred):pipeline.run(first)
            waiting=store.get_project(pid)
            self.assertEqual(waiting['status'],'awaiting_approval')
            self.assertIsNone(waiting['worker_id'])
            self.assertEqual(store.concurrency_snapshot()['active_count'],0)
            second=self.create()
            other=store.claim('w2')
            self.assertEqual(other['id'],second)
            store.finish(second,'completed',worker_id=store.get_project(second)['worker_id'])
            self.assertEqual(self.post(f'/api/projects/{pid}/tasks/T1/review',{'decision':'approved','feedback':'High contrast','attempt':1}).status_code,200)
            self.assertEqual(store.get_project(pid)['status'],'queued')
            resumed=store.claim('w3')
            self.assertEqual(resumed['id'],pid)
            self.assertEqual(resumed['attempts'],1)
            result=pipeline.run(resumed)
            store.finish(pid,'review_required' if result=='review_required' else 'completed',worker_id=store.get_project(pid)['worker_id'])
        self.assertEqual(len(plan_calls),1)
        self.assertEqual(feedback,['High contrast'])
        self.assertEqual(store.get_project(pid)['status'],'completed')
        self.assertIsNone(store.get_checkpoint(pid))

    def test_pricing_snapshot_and_unpriced_usage_are_distinct(self):
        pid=self.create()
        path='/api/finops/prices'
        self.assertEqual(self.post(path,{'model':'example','input_usd_per_million':2,'output_usd_per_million':8},csrf=False).status_code,403)
        with TestClient(app) as guest:self.assertEqual(guest.get('/api/finops/report').status_code,401)
        self.assertEqual(self.post(path,{'model':'model-x','input_usd_per_million':2,'output_usd_per_million':8}).status_code,200)
        self.assertAlmostEqual(store.usage(pid,'Engineer','model-x',1_000_000,1_000_000),10,places=5)
        self.assertEqual(self.post(path,{'model':'model-x','input_usd_per_million':4,'output_usd_per_million':16}).status_code,200)
        self.assertAlmostEqual(store.usage(pid,'Engineer','model-x',1_000_000,1_000_000),20,places=5)
        store.usage(pid,'Planner','model-unknown',100,200)
        r=self.client.get('/api/finops/report?period=all&project_id='+pid)
        self.assertEqual(r.status_code,200,r.text)
        report=r.json()
        self.assertEqual(report['calls'],3)
        self.assertAlmostEqual(report['estimated_usd'],30)
        self.assertEqual(report['unpriced_calls'],1)
        self.assertFalse(report['price_coverage_complete'])
        self.assertEqual(report['input_tokens'],2_000_100)
        self.assertEqual(len(report['by_model']),2)
        self.assertEqual(self.client.get('/api/concurrency').status_code,200)
        self.assertEqual(self.client.get('/api/finops/report?period=99d').status_code,422)
        self.assertEqual(self.post(path,{'model':'abc','input_usd_per_million':-1,'output_usd_per_million':0}).status_code,422)
        self.assertEqual(self.post(path,{'model':'../bad','input_usd_per_million':1,'output_usd_per_million':2}).status_code,422)

    def test_node_web_preview_request_and_validation(self):
        pkg=json.dumps({'name':'demo','scripts':{'start':'node server.js'},'type':'commonjs'})
        files={'server.js':"require('node:http').createServer((req,res)=>res.end('ok')).listen(8000,'0.0.0.0');",
               'package.json':pkg}
        self.assertGreater(len(validation.check_files(files,'node-web')),0)
        with self.assertRaises(ValueError):validation.check_files({'server.js':'','package.json':json.dumps({'scripts':{},'dependencies':{'express':'*'}})},'node-web')
        pid=self.create(mode='ai',stack='node-web')
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+pid,pid))
        self.assertTrue(store.finish(pid,'completed',worker_id='fixture-'+pid))
        requested=self.post(f'/api/projects/{pid}/operator-jobs',{'kind':'preview-start'})
        self.assertEqual(requested.status_code,202,requested.text)
        self.assertEqual(self.client.get('/api/operator/jobs/'+requested.json()['job_id']).json()['status'],'queued')
        html=self.client.get('/').text
        self.assertIn('id="page-finops"',html)
        self.assertIn('node-web',html)
        self.assertIn('/static/finops.js',html)
        self.assertEqual(self.client.get('/static/finops.js').status_code,200)

    def test_preview_runner_node_command_has_isolation_flags(self):
        import importlib.util
        from unittest.mock import patch
        root=Path(self.tmp.name)
        (root/'server.js').write_text('process.stdout.write("ok")')
        spec=importlib.util.spec_from_file_location('wfs_node_runner',Path(__file__).parents[1]/'scripts/operator-runner.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        commands=[]
        def fake_docker(args,timeout=30):
            commands.append(args)
            if args[:2]==['network','ls']:return 'wfs-preview-internal'
            if args[0]=='run':return 'a'*64
            return ''
        with patch.object(mod,'check_project',return_value=(root,'node-web')):
            with patch('app.artifacts.source_files',return_value={'package.json':json.dumps({'name':'demo','scripts':{'start':'node server.js'}})}):
                with patch.object(mod,'docker',side_effect=fake_docker):
                    response=mod.preview_start('a'*20)
        self.assertEqual(response['stack'],'node-web')
        self.assertTrue(response['url'].startswith('http://127.0.0.1:'))
        cmd=next(x for x in commands if x[0]=='run')
        for item in ('--read-only','--cap-drop','no-new-privileges','--user','--network','node:22-alpine'):
            self.assertIn(item,cmd)
        self.assertEqual(cmd[cmd.index('--network')+1],'wfs-preview-internal')
        self.assertIn('readonly',next(x for x in cmd if x.startswith('type=bind,source=') and 'server.js' not in x))

    def test_optional_cost_ceiling_fails_closed_without_pricing(self):
        from app import provider
        pid=self.create(mode='ai')
        with patch.object(config,'MAX_ESTIMATED_COST_USD',0.00001):
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-not-real'},clear=False):
                with self.assertRaisesRegex(provider.ProviderFailure,'tarif model'):
                    provider.invoke('Frontend Engineer','instructions','brief',provider.CallBudget(pid))
            store.set_model_price(config.MODEL,2,10)
            store.usage(pid,'Engineer',config.MODEL,5000,5000)
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-not-real'},clear=False):
                with self.assertRaisesRegex(provider.ProviderFailure,'Batas estimasi biaya'):
                    provider.invoke('Frontend Engineer','instructions','brief',provider.CallBudget(pid))

if __name__=='__main__':unittest.main()
