"""Persistent filesystem error fixtures against real temporary SQLite data."""
import errno
import os
import unittest
from unittest.mock import patch

from test_v42_artifact_recovery import NEW, OLD
import test_v42_artifact_recovery as fixture
from app import store


class PersistentRecoveryV43(unittest.TestCase):
    setUp=fixture.ArtifactRecoveryV42.setUp
    publish=fixture.ArtifactRecoveryV42.publish
    report=fixture.ArtifactRecoveryV42.report

    def test_persistent_directory_sync_preserves_rejected_and_original(self):
        original=store._sync_artifact_directory
        def persistent(path):
            if path==self.projects:raise OSError(errno.EIO,'fixture directory I/O')
            return original(path)
        with patch.object(store,'_sync_artifact_directory',side_effect=persistent),self.assertRaises(store.ArtifactRecoveryRequired) as err:
            self.publish(NEW)
        self.assertEqual(err.exception.original.errno,errno.EIO)
        self.assertEqual(err.exception.compensation.errno,errno.EIO)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertEqual((self.delivery/'index.html').read_text(),OLD['index.html'])
        self.assertEqual(len(list(self.projects.glob('.wfs-stage-rejected-*'))),1)

    def test_both_rename_failures_keep_stage_and_previous_for_review(self):
        original=os.replace
        def persistent(src,dst):
            if dst==self.delivery:raise OSError(errno.EIO,'fixture replacement blocked')
            return original(src,dst)
        with patch.object(os,'replace',side_effect=persistent),self.assertRaises(store.ArtifactRecoveryRequired):
            self.publish(NEW)
        self.assertFalse(self.delivery.exists())
        previous=list(self.projects.glob('.wfs-previous-*'))
        staged=list(self.projects.glob('.wfs-stage-*'))
        self.assertEqual(len(previous),1)
        self.assertEqual(len(staged),1)
        self.assertEqual(self.report(previous[0])['status'],'EXACT_MATCH')
        self.assertEqual(self.report(staged[0])['status'],'MISMATCH')
        self.assertEqual((staged[0]/'index.html').read_text(),NEW['index.html'])
        with store.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            cx.execute('ROLLBACK')
        self.publish(NEW)
        self.assertEqual(self.report()['status'],'EXACT_MATCH')
        self.assertTrue(staged[0].is_dir() and previous[0].is_dir())

    def test_persistent_rollback_rename_keeps_unmatched_delivery_and_previous(self):
        sync=store._sync_artifact_directory
        rename=os.replace
        def fail_sync(path):
            if path==self.projects:raise OSError(errno.EIO,'fixture fsync')
            return sync(path)
        def fail_rename(src,dst):
            if src==self.delivery and dst.name.startswith('.wfs-stage-rejected-'):
                raise OSError(errno.EACCES,'fixture rename denied')
            return rename(src,dst)
        with patch.object(store,'_sync_artifact_directory',side_effect=fail_sync), \
             patch.object(os,'replace',side_effect=fail_rename),self.assertRaises(store.ArtifactRecoveryRequired) as err:
            self.publish(NEW)
        self.assertEqual(err.exception.original.errno,errno.EIO)
        self.assertEqual(err.exception.compensation.errno,errno.EACCES)
        self.assertEqual(self.report()['status'],'MISMATCH')
        previous=next(self.projects.glob('.wfs-previous-*'))
        self.assertEqual(self.report(previous)['status'],'EXACT_MATCH')
        self.assertEqual(store.get_project(self.pid)['status'],'running')

