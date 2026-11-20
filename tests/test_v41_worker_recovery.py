"""Lease-bound agent runs, checkpoint atomicity and process-death evidence."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_system import PASSWORD  # initializes offline app test configuration
from app import artifact_audit, store

TASK = {'id':'T1','role':'Builder','division':'Engineering','task':'Build website','files':['index.html']}
FILES = {'index.html':'<!doctype html>\n<html><body>Original</body></html>\n','README.md':'# Source\n'}


class WorkerRecovery(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for key,value in dict(DATA=self.root,DB=self.root/'wfs.sqlite3',PROJECTS=self.root/'projects').items():
            p=patch.object(store,key,value)
            p.start()
            self.addCleanup(p.stop)
        store.init_db()

    def project(self,mode='auto'):
        pid=store.create_project('Durable release','Create accessible dashboard with working controls','demo','static',task_review_mode=mode)['id']
        self.assertEqual(store.claim('claim-a')['id'],pid)
        return pid

    def test_old_agent_never_appears_live_under_successor(self):
        pid=self.project()
        aid=store.agent_start(pid,'Old','Engineering','Build',worker_id='claim-a')
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=NULL WHERE id=?',(pid,))
        self.assertEqual(store.recover_stale(),1)
        self.assertTrue(store.retry(pid))
        self.assertEqual(store.claim('claim-b')['id'],pid)
        store.worker_ping('claim-b',pid)
        bid=store.agent_start(pid,'Current','Engineering','Build',worker_id='claim-b')
        self.assertFalse(store.agent_finish(bid,'cancelled',worker_id='claim-a'))
        self.assertFalse(store.agent_finish(aid,'done',worker_id='claim-b'))
        self.assertEqual(store.agent_run_detail(aid)['state'],'interrupted')
        self.assertTrue(store.agent_run_detail(bid)['live'])
        self.assertNotIn('claim_id',store.agent_run_detail(bid))
        self.assertNotIn('claim_id',store.list_agents(pid)[0])

    def test_approval_handoff_is_atomic_and_rejects_stale_writer(self):
        pid=self.project('manual')
        original=store._insert_event
        def fail(cx,pid,agent,state,message):
            if state=='awaiting_approval':raise RuntimeError('checkpoint write interrupted')
            return original(cx,pid,agent,state,message)
        with patch.object(store,'_insert_event',side_effect=fail):
            with self.assertRaises(RuntimeError):
                store.checkpoint_task_plan(pid,{},[TASK],worker_id='claim-a')
        self.assertIsNone(store.get_checkpoint(pid))
        self.assertEqual(store.task_gate(pid)['total'],0)
        self.assertTrue(store.checkpoint_task_plan(pid,{},[TASK],worker_id='claim-a'))
        self.assertEqual(store.get_project(pid)['status'],'awaiting_approval')
        self.assertEqual(store.task_gate(pid)['total'],1)
        with self.assertRaises(ValueError):
            store.checkpoint_task_plan(pid,{},[TASK],worker_id='claim-a')

    def test_identical_auto_checkpoint_retry_is_idempotent(self):
        pid=self.project()
        self.assertFalse(store.checkpoint_task_plan(pid,{'title':'stable'},[TASK],worker_id='claim-a'))
        self.assertFalse(store.checkpoint_task_plan(pid,{'title':'stable'},[TASK],worker_id='claim-a'))
        with self.assertRaisesRegex(ValueError,'differs'):
            store.checkpoint_task_plan(pid,{'title':'changed'},[TASK],worker_id='claim-a')
        self.assertEqual(store.task_gate(pid)['total'],1)
        with store.connect() as cx:
            self.assertEqual(cx.execute('SELECT COUNT(*) FROM agent_handoffs WHERE project_id=?',(pid,)).fetchone()[0],1)
        self.assertFalse(store.finish(pid,'completed',worker_id=None))
        self.assertFalse(store.event(pid,'Agent','done','No claim',worker_id=None))
        with self.assertRaises(ValueError):
            store.record_tasks(pid,[TASK],None)

    def test_process_death_after_promotion_preserves_previous_generation(self):
        pid=self.project()
        store.publish_artifacts(pid,FILES,'static','claim-a')
        prior=store.list_artifacts(pid)
        child=r"""
import os,sys
from app import store
sync=store._sync_artifact_directory
def stop_after_promotion(path):
    if path==store.PROJECTS:
        os._exit(86)
    sync(path)
store._sync_artifact_directory=stop_after_promotion
store.publish_artifacts(sys.argv[1],{'index.html':'<!doctype html><html><body>New</body></html>'},'static','claim-a')
"""
        run=subprocess.run([sys.executable,'-c',child,pid],env={**os.environ,'WFS_DATA_DIR':str(self.root)},timeout=10)
        self.assertEqual(run.returncode,86)
        self.assertEqual(store.list_artifacts(pid),prior)
        self.assertEqual(store.get_project(pid)['status'],'running')
        previous=list(store.PROJECTS.glob('.wfs-previous-*'))
        self.assertEqual(len(previous),1)
        self.assertEqual((previous[0]/'index.html').read_bytes(),FILES['index.html'].encode())
        self.assertIn(b'New',(store.PROJECTS/pid/'index.html').read_bytes())
        issues={entry['code'] for entry in artifact_audit.audit()['issues']}
        self.assertIn('UNRESOLVED_STAGING_OR_BACKUP',issues)
        self.assertIn('DIGEST_MISMATCH',issues)

    def test_republish_retains_backup_and_writes_exact_newlines(self):
        pid=self.project()
        store.publish_artifacts(pid,FILES,'static','claim-a')
        updated={**FILES,'README.md':'# New\n'}
        store.publish_artifacts(pid,updated,'static','claim-a')
        self.assertEqual((store.PROJECTS/pid/'README.md').read_bytes(),b'# New\n')
        self.assertEqual(len(list(store.PROJECTS.glob('.wfs-previous-*'))),1)
