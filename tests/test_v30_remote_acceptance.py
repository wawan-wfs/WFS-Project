"""Remote acceptance false-positive regression tests. These mock the daemon."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('acceptance_v28_remote',ROOT/'scripts/acceptance_v28_remote.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class AcceptRemote(unittest.TestCase):
    def _run(self,ps_rc=0,info_rc=0,probe_timeout=False):
        def command(prefix,args,timeout=30):
            if args[0]=='info' and '{{json' in ''.join(args):
                return (0,json.dumps({'OSType':'linux','SecurityOptions':['name=rootless']}),'')
            if args[0]=='info':return (info_rc,'25.0' if info_rc==0 else '','error' if info_rc else '')
            if args[0]=='run':
                if probe_timeout:raise subprocess.TimeoutExpired(args,60)
                return 0,'PASS_SOCKET_ABSENT_EGRESS_BLOCKED\n',''
            if args[0]=='rm':return 0,'',''
            if args[0]=='ps':return ps_rc,'','offline' if ps_rc else ''
            raise AssertionError(args)
        with patch.object(mod,'remote_docker_prefix',return_value=['docker']),\
             patch.object(mod,'command',side_effect=command):
            return mod.acceptance('host','ca','cert','key','image@sha256:'+'a'*64)

    def test_good_probe_requires_daemon_alive_on_cleanup(self):
        self.assertTrue(self._run()['passed'])
        self.assertFalse(self._run(ps_rc=1)['passed'])
        self.assertFalse(self._run(info_rc=1)['passed'])

    def test_timeout_not_pass_and_cleanup_uncertainty(self):
        r=self._run(probe_timeout=True)
        self.assertFalse(r['passed'])
        self.assertTrue(r['probe_timeout'])

if __name__=='__main__':unittest.main()
