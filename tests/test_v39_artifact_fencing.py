"""v3.9: stale workers cannot publish or overwrite project delivery evidence."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_system import PASSWORD  # noqa: F401 - deterministic test configuration
from app import store, worker


class ArtifactLeaseFencingV39(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [patch.object(store, 'DATA', self.root),
                        patch.object(store, 'DB', self.root/'test.sqlite3'),
                        patch.object(store, 'PROJECTS', self.root/'projects')]
        for p in self.patches:
            p.start()
        store.init_db()
        self.pid = store.create_project('Fenced delivery',
            'Generate a legitimate static page with an accessible button','demo','static')['id']
        self.first = worker.attempt_lease_identity('daemon')
        self.assertEqual(store.claim(self.first)['id'], self.pid)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def publish(self, lease, marker):
        return store.publish_artifacts(self.pid,
            {'index.html':f'<!doctype html><html><body>{marker}</body></html>',
             'README.md':f'# {marker}\n'}, 'static', lease)

    def test_recovered_lease_cannot_overwrite_existing_delivery_or_manifest(self):
        self.publish(self.first, 'original')
        file = self.root/'projects'/self.pid/'index.html'
        before = file.read_bytes()
        before_manifest = store.list_artifacts(self.pid)
        stale = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec='seconds')
        with store.connect() as cx:
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(stale,self.pid))
        self.assertEqual(store.recover_stale(180),1)
        self.assertEqual(store.get_project(self.pid)['status'],'interrupted')
        self.assertTrue(store.retry(self.pid))
        successor = worker.attempt_lease_identity('daemon')
        self.assertEqual(store.claim(successor)['id'], self.pid)
        with self.assertRaisesRegex(ValueError,'lease'):
            self.publish(self.first, 'stale overwrite')
        self.assertEqual(file.read_bytes(), before)
        self.assertEqual(store.list_artifacts(self.pid), before_manifest)
        self.publish(successor, 'successor')
        self.assertIn(b'successor', file.read_bytes())
        self.assertNotEqual(store.list_artifacts(self.pid), before_manifest)
        self.assertEqual(store.get_project(self.pid)['status'], 'running')
        # A crash after artifact persistence cannot be mistaken for completion.
        store.finish(self.pid, 'completed', worker_id=self.first)
        self.assertEqual(store.get_project(self.pid)['status'], 'running')
        store.finish(self.pid, 'completed', worker_id=successor)
        self.assertEqual(store.get_project(self.pid)['status'], 'completed')

    def test_cancelled_claim_cannot_publish(self):
        self.publish(self.first,'baseline')
        snapshot = store.list_artifacts(self.pid)
        self.assertEqual(store.cancel(self.pid),'cancel_requested')
        with self.assertRaisesRegex(ValueError,'lease'):
            self.publish(self.first,'publish after cancellation')
        self.assertEqual(store.list_artifacts(self.pid),snapshot)
        self.assertIn(b'baseline',(self.root/'projects'/self.pid/'index.html').read_bytes())

    def test_missing_or_wrong_lease_rejected_without_disk_effect(self):
        for identity in (None,'',worker.attempt_lease_identity('other')):
            with self.assertRaisesRegex(ValueError,'lease'):
                self.publish(identity,'untrusted')
        self.assertFalse((self.root/'projects'/self.pid).exists())
        self.assertEqual(store.list_artifacts(self.pid),[])

    def test_failed_validation_keeps_existing_manifest_and_contents(self):
        self.publish(self.first,'baseline')
        before = store.list_artifacts(self.pid)
        with self.assertRaises(ValueError):
            store.publish_artifacts(self.pid, {'../../outside.html': 'no'},'static',self.first)
        self.assertEqual(store.list_artifacts(self.pid),before)
        self.assertIn(b'baseline',(self.root/'projects'/self.pid/'index.html').read_bytes())


    def test_database_failure_restores_previous_files_and_manifest(self):
        self.publish(self.first,'original')
        before=store.list_artifacts(self.pid)
        f=self.root/'projects'/self.pid/'index.html'
        data=f.read_bytes()
        original_connect=store.connect

        class FailingConnection:
            def __init__(self,cx):self.cx=cx
            def execute(self,sql,*args):
                if sql.startswith('INSERT INTO artifacts('):
                    raise sqlite3.OperationalError('injected manifest failure')
                return self.cx.execute(sql,*args)

        @contextmanager
        def fail_connect():
            with original_connect() as cx:
                yield FailingConnection(cx)

        with patch.object(store,'connect',fail_connect):
            with self.assertRaisesRegex(sqlite3.OperationalError,'injected'):
                self.publish(self.first,'new but rolled back')
        self.assertEqual(f.read_bytes(),data)
        self.assertEqual(store.list_artifacts(self.pid),before)
        self.assertFalse(list((self.root/'projects').glob('.wfs-previous-*')))

    def test_cancel_during_stage_is_rechecked_before_publish(self):
        from app import validation
        safe_write=validation.safe_write
        def interrupted(stage,files):
            safe_write(stage,files)
            self.assertEqual(store.cancel(self.pid),'cancel_requested')
        with patch.object(validation,'safe_write',side_effect=interrupted):
            with self.assertRaisesRegex(ValueError,'lease'):
                self.publish(self.first,'must not appear')
        self.assertFalse((self.root/'projects'/self.pid).exists())
        self.assertFalse(store.list_artifacts(self.pid))



if __name__ == '__main__':
    unittest.main()
