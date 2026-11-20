"""Power-loss boundary detection on a nonproduction SQLite + filesystem clone."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_system import PASSWORD  # noqa: F401
from app import store,worker,artifact_audit

class ArtifactAuditV40(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',root/'projects')]
        for p in self.patches:p.start()
        store.init_db()
        self.pid=store.create_project('Audit crash','Make a real accessible HTML template','demo','static')['id']
        self.lease=worker.attempt_lease_identity('audit')
        self.assertEqual(store.claim(self.lease)['id'],self.pid)
        self.root=root/'projects'/self.pid
        store.publish_artifacts(self.pid,{'index.html':'<!doctype html><html>Safe</html>'},'static',self.lease)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def issue_codes(self):return {x['code'] for x in artifact_audit.audit()['issues']}

    def test_clean_no_mutation(self):
        self.assertEqual(artifact_audit.audit()['status'],'CLEAN_LOCAL')
        self.assertTrue(self.root.exists())

    def test_crash_after_old_directory_rename_detected(self):
        # Simulated SIGKILL after os.replace(old,backup), before promoting stage.
        backup=self.root.parent/'.wfs-previous-crash'
        os.replace(self.root,backup)
        codes=self.issue_codes()
        self.assertIn('UNRESOLVED_STAGING_OR_BACKUP',codes)
        self.assertIn('MANIFEST_WITHOUT_SAFE_DELIVERY',codes)
        self.assertTrue(backup.exists())
        self.assertFalse(self.root.exists())

    def test_orphan_stage_and_modified_file_caught(self):
        (self.root.parent/'.wfs-stage-crash').mkdir()
        (self.root/'index.html').write_text('tampered',encoding='utf-8')
        self.assertIn('UNRESOLVED_STAGING_OR_BACKUP',self.issue_codes())
        self.assertIn('DIGEST_MISMATCH',self.issue_codes())

    def test_unmanifested_file_and_symlink_flagged(self):
        (self.root/'unexpected.txt').write_text('not in DB')
        self.assertIn('UNMANIFESTED_FILE',self.issue_codes())
        outside=self.root.parent/'out.txt'
        outside.write_text('private')
        (self.root/'unsafe').symlink_to(outside)
        self.assertIn('UNMANIFESTED_FILE',self.issue_codes()) # unexpected stays
        self.assertIn('UNSAFE_DELIVERY_FILE',self.issue_codes())

if __name__=='__main__':unittest.main()
