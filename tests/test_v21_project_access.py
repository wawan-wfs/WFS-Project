"""v2.1 security regression: private project access across all read/write surfaces."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store, config
from app.main import app

BRIEF='Build a high quality application with strong privacy and a dashboard'


class ProjectScopeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        path=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'wfs.sqlite3'),patch.object(store,'PROJECTS',path/'projects')]
        for item in self.patches:item.start()
        store.init_db()
        self.owner=TestClient(app);self.owner.__enter__()
        r=self.owner.post('/api/login',json={'username':'admin','password':PASSWORD})
        self.assertEqual(r.status_code,200,r.text)
        self.owner_headers={'X-WFS-CSRF':r.json()['csrf']}
        self.developer_id=self.create_user('wfs_developer','developer')
        self.viewer_id=self.create_user('wfs_viewer','viewer')
        self.manager_id=self.create_user('wfs_manager','manager')
        self.dev,self.dev_headers=self.open_account('wfs_developer')
        self.viewer,self.viewer_headers=self.open_account('wfs_viewer')
        self.manager,self.manager_headers=self.open_account('wfs_manager')

    def tearDown(self):
        for client in (self.dev,self.viewer,self.manager,self.owner):client.__exit__(None,None,None)
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def create_user(self,name,role):
        response=self.owner.post('/api/users',headers=self.owner_headers,json={
            'username':name,'password':'Strong-Secret-123456','role':role})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['id']

    def open_account(self,name):
        client=TestClient(app);client.__enter__()
        response=client.post('/api/login',json={'username':name,'password':'Strong-Secret-123456'})
        self.assertEqual(response.status_code,200,response.text)
        return client,{'X-WFS-CSRF':response.json()['csrf']}

    def create_mission(self,client=None,headers=None,visibility='private'):
        client=client or self.owner
        headers=headers or self.owner_headers
        r=client.post('/api/projects',headers=headers,json={
            'title':'Private client project','prompt':BRIEF,'mode':'demo','stack':'static',
            'visibility':visibility})
        self.assertEqual(r.status_code,202,r.text)
        return r.json()['id']

    def grant(self,pid,who,permission='view'):
        r=self.owner.post(f'/api/projects/{pid}/members',headers=self.owner_headers,
                          json={'user_id':who,'permission':permission})
        self.assertEqual(r.status_code,201,r.text)
        return r

    def test_private_denied_across_every_project_endpoint(self):
        pid=self.create_mission()
        for path in (f'/api/projects/{pid}',f'/api/projects/{pid}/files',
                     f'/api/projects/{pid}/download',f'/api/projects/{pid}/trace',
                     f'/api/projects/{pid}/events',f'/api/projects/{pid}/budget',
                     f'/api/projects/{pid}/collaboration',f'/api/projects/{pid}/access',
                     f'/preview/{pid}/index.html',f'/api/office/live?project_id={pid}',
                     f'/api/finops/report?project_id={pid}',f'/api/finops/export.csv?project_id={pid}',
                     f'/api/operator/jobs?project_id={pid}',f'/api/workspace/events?project_id={pid}'):
            self.assertEqual(self.viewer.get(path).status_code,404,path)
        self.assertEqual(self.manager.post(f'/api/projects/{pid}/priority',headers=self.manager_headers,json={'priority':3}).status_code,404)
        self.assertEqual(self.viewer.post(f'/api/projects/{pid}/notes',headers=self.viewer_headers,json={'category':'review','message':'Unauthorized'}).status_code,403)
        self.assertEqual(self.owner.get(f'/api/projects/{pid}').status_code,200)

    def test_scope_global_views_and_finops_cost(self):
        hidden=self.create_mission()
        shared=self.create_mission(visibility='workspace')
        with store.connect() as cx:
            cx.execute("INSERT INTO usage(project_id,agent,model,input_tokens,output_tokens,estimated_usd,created_at) VALUES(?,?,?,?,?,?,?)",
                       (hidden,'Hidden Specialist','secret-ai',90,20,7.1,store.now()))
            cx.execute("INSERT INTO usage(project_id,agent,model,input_tokens,output_tokens,estimated_usd,created_at) VALUES(?,?,?,?,?,?,?)",
                       (shared,'Shared Specialist','shared-ai',5,2,0.5,store.now()))
            cx.execute("INSERT INTO agent_runs(project_id,agent,division,status,task,created_at) VALUES(?,?,?,?,?,?)",
                       (hidden,'Hidden Specialist','Engineering','working','secret work',store.now()))
            run_id=cx.execute('SELECT last_insert_rowid()').fetchone()[0]
            cx.execute("INSERT INTO artifacts(project_id,name,bytes,sha256) VALUES(?,?,?,?)",(hidden,'secret.txt',5,'f'*64))
        result=self.viewer.get('/api/projects').json()
        self.assertNotIn(hidden,[x['id'] for x in result]);self.assertIn(shared,[x['id'] for x in result])
        for route in ('/api/queue','/api/workspace/activity','/api/workspace/artifacts','/api/agents/directory','/api/operator/jobs'):
            self.assertNotIn(hidden,self.viewer.get(route).text,route)
        self.assertNotIn(hidden,self.viewer.get('/api/office/live').text)
        self.assertNotIn(hidden,self.viewer.get('/api/concurrency').text)
        self.assertEqual(self.viewer.get(f'/api/agents/runs/{run_id}').status_code,404)
        report=self.viewer.get('/api/finops/report?period=all').json()
        self.assertEqual(report['calls'],1)
        self.assertEqual(report['estimated_usd'],0.5)
        self.assertNotIn('secret-ai',self.viewer.get('/api/finops/export.csv?period=all').text)
        self.assertNotIn(hidden,self.viewer.get('/api/workspace/events').text)
        self.assertNotIn(hidden,self.viewer.get('/api/live/events?once=true').text)
        self.assertEqual(self.viewer.get('/api/dashboard-stats').json()['usage']['calls'],1)
        self.assertEqual(self.viewer.get('/api/office').status_code,200)
        self.assertNotIn('Hidden Specialist',self.viewer.get('/api/office').text)

    def test_member_can_view_but_manager_view_grant_cannot_modify(self):
        pid=self.create_mission()
        self.grant(pid,self.manager_id,'view')
        self.assertEqual(self.manager.get(f'/api/projects/{pid}').status_code,200)
        self.assertEqual(self.manager.post(f'/api/projects/{pid}/priority',headers=self.manager_headers,json={'priority':3}).status_code,404)
        self.grant(pid,self.manager_id,'edit')
        self.assertEqual(self.manager.post(f'/api/projects/{pid}/priority',headers=self.manager_headers,json={'priority':3}).status_code,200)
        self.assertEqual(self.manager.post(f'/api/projects/{pid}/members',headers=self.manager_headers,json={'user_id':self.viewer_id,'permission':'view'}).status_code,403)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,404)

    def test_grant_revoke_takes_effect_without_logout(self):
        pid=self.create_mission()
        self.grant(pid,self.viewer_id)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,200)
        response=self.owner.delete(f'/api/projects/{pid}/members/{self.viewer_id}',headers=self.owner_headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,404)
        self.assertEqual(self.viewer.get('/api/session').json()['authenticated'],True)
        logs=self.owner.get(f'/api/projects/{pid}/access').json()['audit']
        self.assertEqual(logs[0]['action'],'member_removed')

    def test_visibility_switch_and_protection_from_csrf(self):
        pid=self.create_mission(visibility='workspace')
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,200)
        self.assertEqual(self.owner.patch(f'/api/projects/{pid}/access',json={'visibility':'private'}).status_code,403)
        result=self.owner.patch(f'/api/projects/{pid}/access',headers=self.owner_headers,json={'visibility':'private'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,404)
        self.assertEqual(self.owner.patch(f'/api/projects/{pid}/access',headers=self.owner_headers,json={'visibility':'workspace'}).status_code,200)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,200)

    def test_creator_can_delegate_only_their_private_project(self):
        pid=self.create_mission(self.dev,self.dev_headers)
        self.assertEqual(self.owner.get(f'/api/projects/{pid}').status_code,200)
        self.assertEqual(self.manager.get(f'/api/projects/{pid}').status_code,404)
        self.assertEqual(self.dev.post(f'/api/projects/{pid}/members',headers=self.dev_headers,json={'user_id':self.viewer_id,'permission':'view'}).status_code,201)
        self.assertEqual(self.viewer.get(f'/api/projects/{pid}').status_code,200)
        self.assertEqual(self.dev.patch(f'/api/projects/{pid}/access',headers=self.dev_headers,json={'visibility':'workspace'}).status_code,200)
        self.assertEqual(self.manager.get(f'/api/projects/{pid}').status_code,200)

    def test_invalid_member_and_private_operator_job_are_blocked(self):
        pid=self.create_mission()
        self.assertEqual(self.owner.post(f'/api/projects/{pid}/members',headers=self.owner_headers,
                         json={'user_id':'missing','permission':'edit'}).status_code,422)
        # Ensure the direct operator-job lookup is scoped even without a project path segment.
        with store.connect() as cx:
            import uuid
            jid=uuid.uuid4().hex[:24]
            cx.execute('INSERT INTO operator_jobs(id,project_id,kind,options_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                       (jid,pid,'qa-static','{}','queued',store.now(),store.now()))
        self.assertEqual(self.viewer.get('/api/operator/jobs/'+jid).status_code,404)
        self.assertEqual(self.manager.post('/api/operator/jobs/'+jid+'/cancel',headers=self.manager_headers).status_code,404)
        self.assertEqual(self.owner.get('/api/operator/jobs/'+jid).status_code,200)


    def test_private_project_revision_inherits_members_and_visibility(self):
        parent=store.create_project('Release root',BRIEF,'ai','static',created_by='owner',visibility='workspace')['id']
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',worker_id=? WHERE id=?",('fixture-'+parent,parent))
        self.assertTrue(store.finish(parent,'completed',worker_id='fixture-'+parent))
        child=store.create_project('Release revision',BRIEF,'ai','static',parent_id=parent,created_by='owner')['id']
        self.assertEqual(store.get_project(child)['visibility'],'workspace')
        result=self.owner.patch('/api/projects/'+parent+'/access',headers=self.owner_headers,json={'visibility':'private'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(store.get_project(child)['visibility'],'private')
        self.assertEqual(self.viewer.get('/api/projects/'+child).status_code,404)
        self.grant(parent,self.viewer_id)
        next_child=store.create_project('Third release',BRIEF,'ai','static',parent_id=parent)['id']
        self.assertEqual(store.get_project(next_child)['visibility'],'private')
        self.assertEqual(self.viewer.get('/api/projects/'+next_child).status_code,200)

    def test_legacy_database_upgrade_keeps_workspace_visibility(self):
        old=store.create_project('Legacy project',BRIEF,'demo','static')['id']
        with store.connect() as cx:
            cx.execute('ALTER TABLE projects DROP COLUMN visibility')
            cx.execute('ALTER TABLE projects DROP COLUMN created_by')
        store.init_db()
        project=store.get_project(old)
        self.assertEqual(project['visibility'],'workspace')
        self.assertEqual(project['created_by'],'owner')
        self.assertEqual(self.viewer.get('/api/projects/'+old).status_code,200)


if __name__=='__main__':unittest.main()
