"""Mocks validate reporting semantics, not actual Linux/Docker measurements."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('acceptance_v30_host',ROOT/'scripts/acceptance_v30_host.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
PID='a'*20
ATT='b'*32
STAGE=Path(f'/srv/wfs-runner/staging/{PID}/{ATT}')

class HostEvidence(unittest.TestCase):
    def test_fails_closed_without_real_host(self):
        with patch.object(module.platform,'system',return_value='Windows'),\
             patch.object(module.Path,'is_file',return_value=False),\
             patch.object(module.subprocess,'run',side_effect=FileNotFoundError()):
            report=module.collect(STAGE,PID,ATT)
        self.assertFalse(report['local_prerequisites_passed'])
        self.assertFalse(report['independent_host_verified'])
        self.assertFalse(report['certificate_revocation_verified'])

    def test_host_probe_reaches_internet_fails(self):
        def command(args,**kw):
            if args[0]=='docker':
                return subprocess.CompletedProcess(args,0,json.dumps({'OSType':'linux','SecurityOptions':['name=rootless']}),'')
            return subprocess.CompletedProcess(args,0,'ext4\n','')
        class DummySocket:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.object(module.platform,'system',return_value='Linux'),\
             patch.object(module.Path,'is_file',return_value=True),\
             patch.object(module.Path,'read_text',return_value='1024'),\
             patch.object(module.subprocess,'run',side_effect=command),\
             patch.object(module,'check_staging',return_value={'sealed_entries':2}),\
             patch.object(module.socket,'create_connection',return_value=DummySocket()):
            report=module.collect(STAGE,PID,ATT,probe_egress=True)
        self.assertFalse(report['local_prerequisites_passed'])
        self.assertFalse(report['host_egress_denied'])
        self.assertIn('Host outbound probe reached public IP',report['errors'])

    def test_even_positive_local_checks_cannot_prove_independent_host(self):
        def command(args,**kw):
            if args[0]=='docker':
                return subprocess.CompletedProcess(args,0,json.dumps({'OSType':'linux','SecurityOptions':['name=rootless']}),'')
            return subprocess.CompletedProcess(args,0,'ext4\n','')
        with patch.object(module.platform,'system',return_value='Linux'),\
             patch.object(module.Path,'is_file',return_value=True),\
             patch.object(module.Path,'read_text',return_value='1024'),\
             patch.object(module.subprocess,'run',side_effect=command),\
             patch.object(module,'check_staging',return_value={'sealed_entries':2}),\
             patch.object(module.socket,'create_connection',side_effect=OSError('denied')):
            report=module.collect(STAGE,PID,ATT,probe_egress=True)
        self.assertTrue(report['local_prerequisites_passed'])
        self.assertFalse(report['independent_host_verified'])
        self.assertFalse(report['firewall_default_deny_verified'])

if __name__=='__main__':unittest.main()
