"""Negative tests for strict remote runner admission; no live Docker implied."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v27_runner_policy', ROOT/'scripts/runner_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class RunnerPolicyTests(unittest.TestCase):
    def test_rejects_mutable_images_and_garbage(self):
        for bad in ('python:3.12-slim','node:latest','', 'python@sha256:'+'0'*63,'node@sha256:'+'0'*64+'-x'):
            with self.subTest(bad=bad),self.assertRaises(policy.RunnerPolicyError):
                policy.validate_image(bad)
        self.assertEqual(policy.validate_image('docker.io/library/python@sha256:'+'a'*64),'docker.io/library/python@sha256:'+'a'*64)

    def test_no_socket_or_insecure_tcp(self):
        for bad in ('unix:///var/run/docker.sock','tcp://127.0.0.1','tcp://user:pass@host:2376','tcp://host:2376/evil','ssh://host'):
            with self.subTest(bad=bad),self.assertRaises(policy.RunnerPolicyError):
                policy.remote_docker_prefix(bad,'missing','missing','missing')

    def test_requires_private_key_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            files=[Path(d)/f for f in ('ca.pem','cert.pem','key.pem')]
            for f in files:
                f.write_text('test')
            if os.name!='nt':
                files[-1].chmod(0o644)
                with self.assertRaises(policy.RunnerPolicyError):
                    policy.remote_docker_prefix('tcp://runner.example:2376',*(str(f) for f in files))
                files[-1].chmod(0o600)
            args=policy.remote_docker_prefix('tcp://runner.example:2376',*(str(f) for f in files))
            self.assertIn('--tlsverify',args)

    def test_daemon_rejects_nonrootless(self):
        for bad in ({'OSType':'linux','SecurityOptions':[]},{'OSType':'windows','SecurityOptions':['name=rootless']},
                    {'OSType':'linux','SecurityOptions':['name=rootless'],'Swarm':{'LocalNodeState':'active'}}):
            with self.assertRaises(policy.RunnerPolicyError):policy.check_daemon(bad)
        policy.check_daemon({'OSType':'linux','SecurityOptions':['name=rootless']})

    def test_inspect_denies_unsafe_runtime(self):
        name='python@sha256:'+'a'*64
        safe={'Config':{'Image':name,'User':'10001:10001'},'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,
             'CapAdd':None,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'Devices':[],
             'Memory':536870912,'MemorySwap':536870912,'NanoCpus':1000000000,'PidsLimit':64},
             'Mounts':[{'Type':'bind','Source':'/srv/wfs-runner/staging/p','Destination':'/workspace','RW':False},
                       {'Type':'bind','Source':'/srv/wfs-runner/trusted/qa_probe.py','Destination':'/trusted/qa_probe.py','RW':False}]}
        policy.inspect_container(safe,name,'/srv/wfs-runner/staging/p','/srv/wfs-runner/trusted/qa_probe.py')
        for field,value in [('NetworkMode','bridge'),('ReadonlyRootfs',False),('Privileged',True),('CapAdd',['SYS_ADMIN']),('Memory',0)]:
            modified={'Config':safe['Config'],'HostConfig':{**safe['HostConfig'],field:value},'Mounts':safe['Mounts']}
            with self.subTest(field=field),self.assertRaises(policy.RunnerPolicyError):policy.inspect_container(modified,name)
        modified={**safe,'Mounts':[{**safe['Mounts'][0],'RW':True},safe['Mounts'][1]]}
        with self.assertRaises(policy.RunnerPolicyError):policy.inspect_container(modified,name)

    def test_remote_mount_allowlist(self):
        for bad in ('/','/var/run/docker.sock','/srv/wfs-runner/staging/../private','/srv/wfs-runner/staging/p/',''):
            with self.subTest(bad=bad),self.assertRaises(policy.RunnerPolicyError):policy.remote_staging_path(bad)
        self.assertEqual(policy.remote_staging_path('/srv/wfs-runner/staging/p'),'/srv/wfs-runner/staging/p')

if __name__=='__main__':unittest.main()

class StagingSnapshotTests(unittest.TestCase):
    def test_snapshot_hashes_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'source.py').write_text('print(1)')
            (p/'trusted.py').write_text('pass')
            snap=policy.local_snapshot(p,[p/'trusted.py'])
            self.assertIn('source.py',snap['project'])
            self.assertIn('trusted.py',snap['trusted'])
            if os.name!='nt':
                (p/'bad').symlink_to('/etc/passwd')
                with self.assertRaises(policy.RunnerPolicyError):policy.local_snapshot(p,[p/'trusted.py'])

    def test_staging_check_command_is_networkless_and_pinned(self):
        image='docker.io/library/python@sha256:'+'b'*64
        cmd=policy.staging_check_command(['docker'],image,'/srv/wfs-runner/staging/project','/srv/wfs-runner/trusted/scripts',{'project':{},'trusted':{}})
        self.assertIn('--network',cmd)
        self.assertIn('none',cmd)
        self.assertIn(image,cmd)
        self.assertNotIn('/var/run/docker.sock',' '.join(cmd))
