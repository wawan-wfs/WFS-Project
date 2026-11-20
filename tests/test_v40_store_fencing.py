"""Protect active worker evidence against stale claim, even on old API paths."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_system import PASSWORD  # noqa: F401
from app import store,worker

class LegacyFencingV40(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'db.sqlite3'),
                      patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.pid=store.create_project('Lease access','Generate a static app with an accessible button','demo','static')['id']
        self.first=worker.attempt_lease_identity('worker-1')
        self.assertEqual(store.claim(self.first)['id'],self.pid)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_legacy_manifest_writer_is_always_closed(self):
        before=store.list_artifacts(self.pid)
        with self.assertRaisesRegex(ValueError,'disabled'):
            store.save_artifacts(self.pid,[('index.html',4,'a'*64)])
        self.assertEqual(store.list_artifacts(self.pid),before)

    def test_old_worker_cannot_emit_live_success_or_start_new_agent(self):
        aid=store.agent_start(self.pid,'Builder','Engineering','Implement',worker_id=self.first)
        self.assertTrue(store.event(self.pid,'Builder','working','Started',worker_id=self.first))
        stale=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(stale,self.pid))
        self.assertEqual(store.recover_stale(180),1)
        self.assertTrue(store.retry(self.pid))
        current=worker.attempt_lease_identity('worker-2')
        self.assertEqual(store.claim(current)['id'],self.pid)
        self.assertFalse(store.event(self.pid,'Builder','done','STALE_DONE',worker_id=self.first))
        self.assertFalse(store.agent_finish(aid,'done',worker_id=self.first))
        with self.assertRaisesRegex(ValueError,'lease'):
            store.agent_start(self.pid,'Old','Engineering','Stale',worker_id=self.first)
        store.phase(self.pid,'stale',worker_id=self.first)
        self.assertNotEqual(store.get_project(self.pid)['phase'],'stale')
        self.assertTrue(store.event(self.pid,'Builder','working','New owner',worker_id=current))
        with store.connect() as cx:
            logs=[r[0] for r in cx.execute('SELECT message FROM events WHERE project_id=?',(self.pid,))]
            self.assertNotIn('STALE_DONE',logs)
            self.assertEqual(cx.execute('SELECT status FROM agent_runs WHERE id=?',(aid,)).fetchone()[0],'interrupted')
        self.assertFalse(store.agent_finish(aid,'cancelled',worker_id=self.first))

    def test_stale_claim_cannot_write_plan_or_handoff_after_recovery(self):
        tasks=[{'id':'T1','role':'Frontend Engineer','division':'Engineering',
                'task':'Build HTML','files':['index.html']}]
        stale=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(stale,self.pid))
        self.assertEqual(store.recover_stale(180),1)
        self.assertTrue(store.retry(self.pid))
        successor=worker.attempt_lease_identity('successor')
        self.assertEqual(store.claim(successor)['id'],self.pid)
        with self.assertRaisesRegex(ValueError,'lease'):
            store.record_tasks(self.pid,tasks,worker_id=self.first)
        self.assertFalse(store.persist_work_plan(self.pid,{'tasks':tasks},tasks,worker_id=self.first))
        self.assertFalse(store.record_handoff(self.pid,'Old','New','stale event',worker_id=self.first))
        self.assertTrue(store.record_handoff(self.pid,'New','QA','new claim',worker_id=successor))
        store.record_tasks(self.pid,tasks,worker_id=successor)
        self.assertTrue(store.persist_work_plan(self.pid,{'tasks':tasks},tasks,worker_id=successor))
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM agent_handoffs WHERE project_id=?',(self.pid,)).fetchone()[0],1)

    def test_cancel_requested_stops_false_success(self):
        agent=store.agent_start(self.pid,'Builder','Engineering','Implement',worker_id=self.first)
        self.assertEqual(store.cancel(self.pid),'cancel_requested')
        self.assertFalse(store.agent_finish(agent,'done',worker_id=self.first))
        self.assertFalse(store.event(self.pid,'Builder','done','WRONG_DONE',worker_id=self.first))
        self.assertTrue(store.event(self.pid,'Builder','cancelled','Cancelled',worker_id=self.first))
        with self.assertRaisesRegex(ValueError,'lease'):
            store.agent_start(self.pid,'Builder','Engineering','Continue',worker_id=self.first)
        self.assertTrue(store.agent_finish(agent,'cancelled',worker_id=self.first))

if __name__=='__main__':unittest.main()
