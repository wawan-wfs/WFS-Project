"""v2.9 per-attempt immutable staging format/policy unit tests.

These do not prove existence of a rootless Linux runner, mTLS or chattr.
"""
import importlib.util
import json
import hashlib
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD  # ensure deterministic test config
from app import config

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runner_policy import validate_attempt_path, RunnerPolicyError


def load(path):
    spec=importlib.util.spec_from_file_location('stage_v29_'+path.stem.replace('-','_'),path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

packager=load(ROOT/'scripts/runner-stage-package-v29.py')
importer=load(ROOT/'scripts/runner-import-seal-v29.py')
PID='a'*20
ATTEMPT='b'*32

class AttemptStaging(unittest.TestCase):
    def test_one_attempt_path_must_be_exact(self):
        good=f'/srv/wfs-runner/staging/{PID}/{ATTEMPT}'
        self.assertEqual(validate_attempt_path(good,PID,ATTEMPT),good)
        for wrong in (f'/srv/wfs-runner/staging/{PID}',f'/srv/wfs-runner/staging/{PID}/',
                      good+'/../c',good.replace(ATTEMPT,'c'*32),'/etc/passwd',good+'/extra'):
            with self.subTest(wrong=wrong),self.assertRaises(RunnerPolicyError):
                validate_attempt_path(wrong,PID,ATTEMPT)

    def test_separate_attempts_cannot_overwrite_or_swap(self):
        with tempfile.TemporaryDirectory() as td:
            project_root=Path(td)/'projects';project_root.mkdir()
            project=project_root/PID;project.mkdir()
            (project/'main.py').write_text('print(42)\n')
            with patch.object(config,'PROJECTS',project_root):
                a=Path(td)/'a.tar.gz'
                meta=packager.package(PID,a,ATTEMPT)
                self.assertEqual(meta['remote_path'],f'/srv/wfs-runner/staging/{PID}/{ATTEMPT}')
                payload=importer.validate_snapshot(a,PID,ATTEMPT,meta['sha256'])
                self.assertEqual(payload['project/main.py'],b'print(42)\n')
                with self.assertRaisesRegex(ValueError,'already|overwrit'):
                    packager.package(PID,a,ATTEMPT)
                with self.assertRaisesRegex(ValueError,'identity mismatch'):
                    importer.validate_snapshot(a,PID,'c'*32,meta['sha256'])
                with self.assertRaisesRegex(ValueError,'digest mismatch'):
                    importer.validate_snapshot(a,PID,ATTEMPT,'0'*64)
                other=Path(td)/'b.tar.gz'
                next_meta=packager.package(PID,other,'c'*32)
                self.assertNotEqual(next_meta['remote_path'],meta['remote_path'])

    def test_corrupt_manifest_and_unsafe_tar_member_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)/'bad.tar.gz'
            manifest=json.dumps({'format':'wfs-sealed-snapshot-v29','project_id':PID,
                                 'attempt_id':ATTEMPT,'files':{'../escape':'ignored'}}).encode()
            with tarfile.open(archive,'w:gz') as tar:
                for name,data in [('../escape',b'bad'),('MANIFEST.json',manifest)]:
                    ti=tarfile.TarInfo(name);ti.size=len(data)
                    tar.addfile(ti,io.BytesIO(data))
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'Unsafe archive path'):
                importer.validate_snapshot(archive,PID,ATTEMPT,digest)

if __name__=='__main__':unittest.main()
