"""Cancellation/lease takeover must not publish simulated specialist success."""
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD  # noqa: F401
from app import store, worker, pipeline


class SpecialistCancelV39(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'db.sqlite3'),
                      patch.object(store,'PROJECTS',root/'projects')]
        for item in self.patches:item.start()
        store.init_db()
        self.pid=store.create_project('Cancellation race','Build an accessible static page with functions','ai','static')['id']
        self.lease=worker.attempt_lease_identity('agent-daemon')
        self.assertEqual(store.claim(self.lease)['id'],self.pid)
        self.task={'id':'T1','role':'Frontend Engineer','division':'Engineering',
                   'task':'Build accessible page','files':['index.html']}
        store.record_tasks(self.pid,[self.task],worker_id=store.get_project(self.pid)['worker_id'])
        store.persist_work_plan(self.pid,{'tasks':[self.task]},[self.task],worker_id=store.get_project(self.pid)['worker_id'])

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.tmp.cleanup()

    def do_call(self,on_provider):
        def provider_stub(*args):
            on_provider()
            return {'files':{'index.html':'<html><body>Safe</body></html>'}}
        with patch.object(pipeline.provider,'invoke',side_effect=provider_stub):
            return pipeline._build_task(self.pid,'Example','A static app','static',
                {},{},{},self.task,None,worker_id=self.lease)

    def assert_no_success(self,expected="cancelled"):
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM task_results WHERE project_id=?',
                (self.pid,)).fetchone()[0],0)
            states=[x['status'] for x in cx.execute('SELECT status FROM agent_runs WHERE project_id=?',(self.pid,))]
        self.assertIn(expected,states)
        self.assertNotIn('done',states)

    def test_cancel_while_model_returns_does_not_emit_done(self):
        with self.assertRaises(pipeline.Cancelled):
            self.do_call(lambda:self.assertEqual(store.cancel(self.pid),'cancel_requested'))
        self.assert_no_success()

    def test_lease_reclaim_while_model_returns_does_not_emit_done(self):
        def reclaim():
            old=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
            with store.connect() as cx:
                cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(old,self.pid))
            self.assertEqual(store.recover_stale(180),1)
            successor=worker.attempt_lease_identity('agent-daemon')
            self.assertEqual(store.claim(successor)['id'],self.pid)
        with self.assertRaises(pipeline.Cancelled):
            self.do_call(reclaim)
        self.assert_no_success("interrupted")

if __name__=='__main__':unittest.main()
