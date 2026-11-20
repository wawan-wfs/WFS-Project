"""Crash/reclaim fencing with a reused worker daemon identity, no real provider."""
from datetime import datetime,timedelta,timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD  # noqa: F401
from app import store,worker


class WorkerFencingV38(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_reused_daemon_gets_distinct_claim_identity(self):
        a=worker.attempt_lease_identity('same-daemon')
        b=worker.attempt_lease_identity('same-daemon')
        self.assertNotEqual(a,b)
        self.assertTrue(a.startswith('same-daemon-lease-'))

    def test_reclaim_blocks_old_finalization_and_task_mutation(self):
        pid=store.create_project('Claim fencing','Create two task files to test crash recovery','ai','static')['id']
        old=worker.attempt_lease_identity('daemon')
        claimed=store.claim(old)
        self.assertEqual(claimed['id'],pid)
        tasks=[{'id':'T1','role':'Engineer','division':'Engineering','task':'index','files':['index.html']}]
        store.record_tasks(pid,tasks,worker_id=store.get_project(pid)['worker_id'])
        store.persist_work_plan(pid,{'tasks':tasks},tasks,worker_id=store.get_project(pid)['worker_id'])
        stale=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(stale,pid))
        self.assertEqual(store.recover_stale(180),1)
        newer=worker.attempt_lease_identity('daemon')
        self.assertEqual(store.claim(newer)['id'],pid)
        self.assertTrue(store.task_transition(pid,'T1','planned','working',worker_id=newer))
        store.heartbeat(pid,old)
        store.block_outstanding_tasks(pid,worker_id=old)
        store.finish(pid,'completed',worker_id=old)
        self.assertEqual(store.get_project(pid)['worker_id'],newer)
        self.assertEqual(store.get_project(pid)['status'],'running')
        with store.connect() as cx:
            row=cx.execute('SELECT status FROM planned_tasks WHERE project_id=?',(pid,)).fetchone()
        self.assertEqual(row['status'],'working')
        with self.assertRaisesRegex(ValueError,'lease'):
            store.save_task_result(pid,'T1',{'index.html':'stale'},old)
        checksum=store.save_task_result(pid,'T1',{'index.html':'new'},newer)
        self.assertEqual(len(checksum),64)
        store.finish(pid,'completed',worker_id=newer)
        self.assertEqual(store.get_project(pid)['status'],'completed')

if __name__=='__main__':unittest.main()
