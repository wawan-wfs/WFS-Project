"""Offline adversarial GC policy tests: never claim a live Docker host."""
from __future__ import annotations
import os
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from importlib.util import spec_from_file_location, module_from_spec

MODULE=Path(__file__).resolve().parents[1]/'scripts/runner_gc_v35.py'
import sys
sys.path.insert(0,str(MODULE.parent))
spec=spec_from_file_location('runner_gc_v35',MODULE)
gc=module_from_spec(spec);spec.loader.exec_module(gc)

class RunnerGCV35(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wfs-v35-gc-')
        self.addCleanup(self.temp.cleanup)
        self.stage=Path(self.temp.name)/'staging';self.stage.mkdir()
        self.project='a'*20;self.attempt='b'*32
        self.project_dir=self.stage/self.project;self.project_dir.mkdir()
        self.path=self.project_dir/self.attempt;self.path.mkdir()
        (self.path/'app.py').write_text('print(1)')
        self.now=int(time.time())
        os.utime(self.path,(self.now-4*3600,self.now-4*3600))

    def test_dry_run_only_returns_metadata_without_deleting(self):
        result=gc.audit(self.stage,ttl_seconds=3600,now=self.now)
        self.assertEqual(len(result),1)
        self.assertTrue(result[0]['eligible'])
        self.assertFalse(result[0]['quarantined'])
        self.assertEqual(result[0]['files'],1)
        self.assertTrue(self.path.exists())

    def test_purge_requires_cooling_off_after_quarantine(self):
        self.path.rename(self.project_dir/('.gc-'+self.attempt))
        report=gc.audit(self.stage,ttl_seconds=3600,now=self.now)
        self.assertFalse(report[0]['quarantine_cooldown_passed'])

    def test_recent_attempt_not_eligible(self):
        self.assertFalse(gc.audit(self.stage,ttl_seconds=5*3600,now=self.now)[0]['eligible'])

    def test_quarantine_retry_is_detectable_and_scoped(self):
        self.path.rename(self.project_dir/('.gc-'+self.attempt))
        report=gc.audit(self.stage,ttl_seconds=3600,now=self.now)
        self.assertTrue(report[0]['quarantined'])
        self.assertEqual(report[0]['attempt_id'],self.attempt)

    def test_attacker_symlink_is_denied(self):
        (self.path/'bad').symlink_to(Path(self.temp.name))
        with self.assertRaises(gc.GarbageCollectionError): gc.audit(self.stage,ttl_seconds=3600)

    def test_attacker_extra_project_namespace_denied(self):
        (self.stage/'untrusted').mkdir()
        with self.assertRaises(gc.GarbageCollectionError): gc.audit(self.stage,ttl_seconds=3600)

    def test_attacker_symlink_project_denied(self):
        other=self.stage/('c'*20);other.symlink_to(self.project_dir)
        with self.assertRaises(gc.GarbageCollectionError): gc.audit(self.stage,ttl_seconds=3600)

    def test_hardlink_inside_stage_denied(self):
        os.link(self.path/'app.py',self.path/'another.py')
        with self.assertRaises(gc.GarbageCollectionError): gc.audit(self.stage,ttl_seconds=3600)

    def test_ttl_too_short_denied(self):
        with self.assertRaises(gc.GarbageCollectionError): gc.audit(self.stage,ttl_seconds=15)

    def test_mount_reference_for_parent_or_child_denied(self):
        self.assertTrue(gc._mounted(self.path,{str(self.path)}))
        self.assertTrue(gc._mounted(self.path,{str(self.path/'app.py')}))
        self.assertTrue(gc._mounted(self.path,{str(self.project_dir)}))
        self.assertFalse(gc._mounted(self.path,{'/tmp/irrelevant'}))

    def test_unpinned_nonroot_socket_path_is_denied(self):
        for name in ('/var/run/docker.sock','/run/user/0/docker.sock','/run/user/1000/../docker.sock'):
            with self.assertRaises(gc.GarbageCollectionError): gc._docker_socket(Path(name))

    def test_docker_inspect_malformed_fails_closed(self):
        with patch.object(gc,'_docker_socket',return_value=['docker','--host','fake']),\
             patch.object(gc,'_run_json',side_effect=[{'SecurityOptions':['name=rootless'],'OSType':'linux','Swarm':{}},{}]),\
             patch.object(gc.subprocess,'run',return_value=type('R',(),{'stdout':'a'*64,'returncode':0})()):
            with self.assertRaises(gc.GarbageCollectionError): gc.active_mount_sources(Path('/run/user/1000/docker.sock'))

    def test_mutation_requires_privileged_operator(self):
        with patch.object(gc.os,'geteuid',return_value=1000):
            with self.assertRaises(gc.GarbageCollectionError):gc.check_root()

if __name__=='__main__':unittest.main()
