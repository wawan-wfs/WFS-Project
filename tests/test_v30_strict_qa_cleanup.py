"""Deterministic runner lifecycle policy tests; NOT live Docker security evidence."""
from __future__ import annotations
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v30_sandbox_qa',ROOT/'scripts/sandbox-qa.py')
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

class StrictQaLifecycle(unittest.TestCase):
    def setUp(self):
        self.cmd=['docker','run','--rm','--name','wfs-test-v30','--network','none','image@sha256:'+'a'*64,'python','-B','probe.py']
        self.calls=[]
        self.preflight=(['docker'],'image@sha256:'+'a'*64,'/srv/wfs-runner/staging/'+'b'*20+'/'+'c'*32,'/srv/wfs-runner/trusted/v28',{'project':{},'trusted':{}})

    def fake(self,cmd,**kwargs):
        cmd=list(cmd)
        self.calls.append(cmd)
        if 'create' in cmd:return subprocess.CompletedProcess(cmd,0,'cid','')
        if 'inspect' in cmd:
            # First inspect checks runtime policies, second proves cleanup.
            if sum('inspect' in c for c in self.calls)==1:
                return subprocess.CompletedProcess(cmd,0,'[{"HostConfig":{}}]','')
            return subprocess.CompletedProcess(cmd,1,'','Error: No such object')
        if 'start' in cmd:return subprocess.CompletedProcess(cmd,0,'qa success','')
        if 'rm' in cmd:return subprocess.CompletedProcess(cmd,0,'','')
        return subprocess.CompletedProcess(cmd,0,'','')

    def run_strict(self,**extra):
        with patch.object(qa.subprocess,'run',side_effect=self.fake),\
             patch.object(qa,'inspect_container'),\
             patch.object(qa,'_verify_staging') as preflight:
            result=qa.run_check('probe',self.cmd,25,['docker'],True,'image@sha256:'+'a'*64,
                '/srv/wfs-runner/staging/project','/srv/wfs-runner/trusted/v28/qa_probe.py',
                self.preflight,**extra)
        return result,preflight

    def test_strict_success_rechecks_staging_and_confirms_no_container(self):
        r,check=self.run_strict()
        self.assertEqual(r['status'],'pass')
        self.assertTrue(r['cleanup_verified'])
        check.assert_called_once_with(*self.preflight)
        self.assertTrue(any('start' in c for c in self.calls))
        self.assertTrue(any('rm' in c for c in self.calls))

    def test_strict_cleanup_failure_cannot_pass(self):
        original=self.fake
        def failed_rm(cmd,**kw):
            if 'rm' in cmd:return subprocess.CompletedProcess(cmd,1,'','cannot remove')
            return original(cmd,**kw)
        self.fake=failed_rm
        r,_=self.run_strict()
        self.assertEqual(r['status'],'error')
        self.assertFalse(r['cleanup_verified'])

    def test_daemon_disappears_after_cleanup_cannot_pass(self):
        original=self.fake
        def daemon_offline(cmd,**kw):
            if 'info' in cmd:return subprocess.CompletedProcess(cmd,1,'','daemon unavailable')
            return original(cmd,**kw)
        self.fake=daemon_offline
        r,_=self.run_strict()
        self.assertEqual(r['status'],'error')
        self.assertFalse(r['cleanup_verified'])

    def test_staging_recheck_failure_prevents_start(self):
        with patch.object(qa.subprocess,'run',side_effect=self.fake),\
             patch.object(qa,'inspect_container'),\
             patch.object(qa,'_verify_staging',side_effect=qa.RunnerPolicyError('seal mismatch')):
            r=qa.run_check('probe',self.cmd,25,['docker'],True,'image@sha256:'+'a'*64,
                           'project','probe',self.preflight)
        self.assertEqual(r['status'],'error')
        self.assertFalse(any('start' in c for c in self.calls))
        self.assertTrue(r['cleanup_verified'])

    def test_missing_preflight_denies_execution(self):
        with patch.object(qa.subprocess,'run',side_effect=self.fake),\
             patch.object(qa,'inspect_container'):
            r=qa.run_check('probe',self.cmd,25,['docker'],True,'image@sha256:'+'a'*64,
                           'project','probe')
        self.assertEqual(r['status'],'error')
        self.assertFalse(any('start' in c for c in self.calls))

    def test_timeout_cleanup_is_not_reported_as_pass(self):
        original=self.fake
        def timeout(cmd,**kw):
            if 'start' in cmd:raise subprocess.TimeoutExpired(cmd,25)
            return original(cmd,**kw)
        self.fake=timeout
        r,_=self.run_strict()
        self.assertEqual(r['status'],'timeout')
        self.assertTrue(r['cleanup_verified'])

    def test_staging_recheck_rejects_false_success_marker(self):
        with patch.object(qa,'staging_check_command',return_value=['docker','run','--rm']),\
             patch.object(qa.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'REMOTE_STAGING_MATCH_AND_SEALED\nnoise','')):
            with self.assertRaises(qa.RunnerPolicyError):qa._verify_staging(*self.preflight)

if __name__=='__main__':unittest.main()
