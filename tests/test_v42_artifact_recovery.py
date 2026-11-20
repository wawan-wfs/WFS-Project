"""Fault injection and matched restore on a disposable filesystem."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_system import PASSWORD  # Initializes isolated test configuration.
from app import artifact_recovery, store, validation

OLD={'index.html':'<html>Original</html>\n','src/about.html':'<html>About</html>\n'}
NEW={'index.html':'<html>Replacement</html>\n','src/about.html':'<html>New about</html>\n'}


class ArtifactRecoveryV42(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name).resolve()
        self.db=self.base/'data'/'wfs.sqlite3'
        self.projects=self.db.parent/'projects'
        for attr,value in dict(DATA=self.db.parent,DB=self.db,PROJECTS=self.projects).items():
            p=patch.object(store,attr,value);p.start();self.addCleanup(p.stop)
        store.init_db()
        self.pid=store.create_project('Recovery test','Build a sample offline site','demo','static')['id']
        self.assertEqual(store.claim('lease42')['id'],self.pid)
        self.delivery=self.projects/self.pid
        self.publish(OLD)

    def publish(self,files):
        return store.publish_artifacts(self.pid,files,'static','lease42')

    def report(self,candidate=None,db=None):
        return artifact_recovery.verify_generation(db or self.db,self.pid,candidate or self.delivery)

    def test_enospc_during_staging_keeps_committed_generation_and_retry_succeeds(self):
        def partial(stage,files):
            (stage/'index.html').write_bytes(b'partial')
            raise OSError(errno.ENOSPC,'fixture full')
        with patch.object(validation,'safe_write',side_effect=partial),self.assertRaises(OSError) as err:
            self.publish(NEW)
        self.assertEqual(err.exception.errno,errno.ENOSPC)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertEqual((self.delivery/'index.html').read_text(),OLD['index.html'])
        self.publish(NEW)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertEqual((self.delivery/'index.html').read_text(),NEW['index.html'])

    def test_promotion_sync_failure_restores_prior_files_and_retains_failed_candidate(self):
        original=store._sync_artifact_directory
        seen=0
        def fail_once(path):
            nonlocal seen
            if path==self.projects:
                seen+=1
                if seen==1:raise OSError(errno.EIO,'fixture fsync error')
            original(path)
        with patch.object(store,'_sync_artifact_directory',side_effect=fail_once),self.assertRaises(OSError):
            self.publish(NEW)
        self.assertEqual(seen,2)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        rejected=list(self.projects.glob('.wfs-stage-rejected-*'))
        self.assertEqual(len(rejected),1)
        self.assertEqual((rejected[0]/'index.html').read_text(),NEW['index.html'])
        self.publish(NEW)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertTrue(rejected[0].exists())

    def test_failed_first_rename_preserves_original_error_and_delivery(self):
        original=os.replace
        def rename(src,dst):
            if src==self.delivery:raise OSError(errno.ENOSPC,'fixture rename failed')
            return original(src,dst)
        with patch.object(os,'replace',side_effect=rename),self.assertRaises(OSError) as err:
            self.publish(NEW)
        self.assertEqual(err.exception.errno,errno.ENOSPC)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertFalse(list(self.projects.glob('.wfs-previous-*')))

    def test_commit_applied_then_ack_error_preserves_both_generations(self):
        original=store.connect
        class LostAck:
            def __init__(self,cx):self.cx=cx
            @property
            def in_transaction(self):return self.cx.in_transaction
            def execute(self,sql,*args):
                result=self.cx.execute(sql,*args)
                if sql=='COMMIT':raise sqlite3.OperationalError('fixture acknowledgement lost')
                return result
        @contextmanager
        def wrapped():
            with original() as cx:yield LostAck(cx)
        with patch.object(store,'connect',wrapped),self.assertRaises(sqlite3.OperationalError):
            self.publish(NEW)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertEqual((self.delivery/'index.html').read_text(),NEW['index.html'])
        previous=list(self.projects.glob('.wfs-previous-*'))
        self.assertEqual(len(previous),1)
        self.assertEqual((previous[0]/'index.html').read_text(),OLD['index.html'])

    def test_matched_snapshot_restore_to_separate_clone_and_wrong_pair_rejected(self):
        backup=self.base/'backup'
        backup.mkdir()
        saved_db=backup/'wfs.sqlite3'
        with sqlite3.connect(self.db) as source,sqlite3.connect(saved_db) as target:
            source.backup(target)
        saved_files=shutil.copytree(self.delivery,backup/'project')
        self.publish(NEW)
        self.assertEqual(self.report(saved_files)['status'],'MISMATCH')
        self.assertEqual(self.report(self.delivery,saved_db)['status'],'MISMATCH')
        clone=self.base/'restore-clone'
        clone.mkdir()
        clone_db=shutil.copy2(saved_db,clone/'wfs.sqlite3')
        clone_files=shutil.copytree(saved_files,clone/'project')
        result=self.report(clone_files,clone_db)
        self.assertEqual(result['status'],'EXACT_MATCH')
        self.assertEqual(result['matches'],2)
        self.assertEqual((self.delivery/'index.html').read_text(),NEW['index.html'])
        self.assertEqual((clone_files/'index.html').read_text(),OLD['index.html'])

    def test_unmanifested_entry_and_link_fail_closed(self):
        (self.delivery/'extra.txt').write_text('unlisted')
        self.assertEqual(self.report()['status'],'MISMATCH')
        if os.name=='posix':
            (self.delivery/'link').symlink_to(self.base)
            self.assertIn('UNSAFE_ENTRY',{i['code'] for i in self.report()['issues']})

    def test_missing_manifest_and_invalid_project_are_not_matches(self):
        self.assertEqual(artifact_recovery.verify_generation(self.db,'a'*20,self.delivery)['status'],'NO_VERIFIABLE_MANIFEST')
        with self.assertRaises(ValueError):
            artifact_recovery.verify_generation(self.db,'../not-a-project',self.delivery)
