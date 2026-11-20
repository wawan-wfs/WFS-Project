"""Stopped-clone batch checks use genuine SQLite snapshots and project files."""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest

import test_v42_artifact_recovery as fixture
from app import artifact_recovery, store


class DeliveredCloneV44(unittest.TestCase):
    setUp=fixture.ArtifactRecoveryV42.setUp
    publish=fixture.ArtifactRecoveryV42.publish

    def prepare(self):
        self.assertTrue(store.finish(self.pid,'completed',worker_id='lease42'))
        second=store.create_project('Second delivery','A separate review-required delivery','demo','static')['id']
        self.assertEqual(store.claim('lease-next')['id'],second)
        store.publish_artifacts(second,{'index.html':'<html>Two</html>'},'static','lease-next')
        self.assertTrue(store.finish(second,'review_required',worker_id='lease-next'))
        store.create_project('Queued only','Do not expect artifact files for queued projects','demo','static')
        target=self.base/'restored'
        (target/'data').mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as source,closing(sqlite3.connect(target/'data'/'wfs.sqlite3')) as dst:
            source.backup(dst)
        shutil.copytree(self.projects,target/'data'/'projects')
        return target,second

    def test_batch_verifies_completed_and_review_required_not_queued(self):
        target,_=self.prepare()
        result=artifact_recovery.verify_delivered_clone(target)
        self.assertEqual(result['status'],'DELIVERED_MATCH')
        self.assertEqual(result['checked'],2)
        self.assertEqual({r['snapshot_project_status'] for r in result['results']},{'completed','review_required'})

    def test_tampered_candidate_and_missing_directory_fail_batch(self):
        target,second=self.prepare()
        root=target/'data'/'projects'
        (root/self.pid/'index.html').write_text('changed')
        shutil.rmtree(root/second)
        result=artifact_recovery.verify_delivered_clone(target)
        self.assertEqual(result['status'],'DELIVERED_MISMATCH')
        self.assertEqual({r['status'] for r in result['results']},{'MISMATCH','MISSING_OR_UNSAFE_DIRECTORY'})
        self.assertEqual((self.delivery/'index.html').read_text(),fixture.OLD['index.html'])

    def test_cli_exits_nonzero_for_empty_delivery_and_invalid_combination(self):
        script=Path(__file__).resolve().parents[1]/'scripts'/'verify-artifact-generation.py'
        env={**os.environ,'PYTHONPATH':str(script.parents[1])}
        result=subprocess.run([sys.executable,str(script),'--clone-root',str(self.base)],env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2)
        self.assertIn(b'NO_DELIVERED_PROJECTS',result.stdout)
        result=subprocess.run([sys.executable,str(script),'--clone-root',str(self.base),'--db',str(self.db)],
                              env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2)

    def test_expected_inventory_rejects_delivered_project_entirely_missing(self):
        target,second=self.prepare()
        required=[second,self.pid]
        complete=artifact_recovery.verify_delivered_clone(target,expected_projects=required)
        self.assertEqual((complete['status'],complete['expected_projects'],complete['missing_expected_projects']),
                         ('DELIVERED_MATCH',2,[]))
        with closing(sqlite3.connect(target/'data'/'wfs.sqlite3')) as cx:
            cx.execute('DELETE FROM artifacts WHERE project_id=?',(second,))
            cx.execute('DELETE FROM projects WHERE id=?',(second,))
            cx.commit()
        shutil.rmtree(target/'data'/'projects'/second)
        script=Path(__file__).resolve().parents[1]/'scripts'/'verify-artifact-generation.py'
        env={**os.environ,'PYTHONPATH':str(script.parents[1])}
        result=subprocess.run([sys.executable,str(script),'--clone-root',str(target),
                               '--require-project',self.pid,'--require-project',second],
                              env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertEqual((report['status'],report['checked'],report['missing_expected_projects']),
                         ('DELIVERED_MISMATCH',1,[second]))
        self.assertEqual(artifact_recovery.verify_delivered_clone(target)['status'],'DELIVERED_MATCH')

    def test_expected_inventory_rejects_invalid_ids_and_non_delivered_state(self):
        target,second=self.prepare()
        with self.assertRaises(ValueError):
            artifact_recovery.verify_delivered_clone(target,expected_projects=['invalid'])
        with closing(sqlite3.connect(target/'data'/'wfs.sqlite3')) as cx:
            cx.execute("UPDATE projects SET status='queued'")
            cx.commit()
        report=artifact_recovery.verify_delivered_clone(target,expected_projects=[second])
        self.assertEqual((report['status'],report['checked'],report['missing_expected_projects']),
                         ('DELIVERED_MISMATCH',0,[second]))

    def test_exact_inventory_accepts_complete_set_and_rejects_additional_delivery(self):
        target,second=self.prepare()
        self.assertEqual(artifact_recovery.verify_delivered_clone(
            target,expected_projects=[second,self.pid],exact_inventory=True)['status'],'DELIVERED_MATCH')
        self.assertEqual(artifact_recovery.verify_delivered_clone(
            target,expected_projects=[self.pid])['status'],'DELIVERED_MATCH')
        script=Path(__file__).resolve().parents[1]/'scripts'/'verify-artifact-generation.py'
        env={**os.environ,'PYTHONPATH':str(script.parents[1])}
        result=subprocess.run([sys.executable,str(script),'--clone-root',str(target),
                               '--require-project',self.pid,'--exact-inventory'],
                              env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertEqual((report['status'],report['missing_expected_projects'],
                          report['unexpected_delivered_projects'],report['unexpected_delivered_count']),
                         ('DELIVERED_MISMATCH',[],[second],1))

    def test_exact_inventory_rejects_empty_and_duplicate_expected_ids(self):
        target,_=self.prepare()
        for expected in ([],[self.pid,self.pid]):
            with self.subTest(expected_count=len(expected)),self.assertRaises(ValueError):
                artifact_recovery.verify_delivered_clone(target,expected_projects=expected,exact_inventory=True)

    def inventory_command(self,*args):
        script=Path(__file__).resolve().parents[1]/'scripts'/'verify-artifact-generation.py'
        env={**os.environ,'PYTHONPATH':str(script.parents[1])}
        return subprocess.run([sys.executable,str(script),*map(str,args)],env=env,
                              capture_output=True,timeout=5)

    def test_backup_fingerprints_detect_self_consistent_mixed_generation(self):
        source,second=self.prepare()
        inventory=self.base/'inventory.json'
        written=self.inventory_command('--clone-root',source,'--record-inventory',inventory)
        self.assertEqual(written.returncode,0,written.stderr)
        original=inventory.read_bytes()
        target=shutil.copytree(source,self.base/'candidate')
        check=lambda: self.inventory_command('--clone-root',target,'--inventory-file',inventory)
        self.assertEqual(check().returncode,0)
        content=b'<html>Different generation</html>'
        (target/'data'/'projects'/second/'index.html').write_bytes(content)
        with closing(sqlite3.connect(target/'data'/'wfs.sqlite3')) as cx:
            cx.execute("UPDATE artifacts SET bytes=?,sha256=? WHERE project_id=? AND name='index.html'",
                       (len(content),hashlib.sha256(content).hexdigest(),second))
            cx.commit()
        self.assertEqual(artifact_recovery.verify_delivered_clone(
            target,expected_projects=[self.pid,second],exact_inventory=True)['status'],'DELIVERED_MATCH')
        result=check()
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertEqual(report['mismatched_project_fingerprints'],[second])
        self.assertEqual(inventory.read_bytes(),original)
        self.assertEqual(self.inventory_command('--clone-root',source,'--record-inventory',inventory).returncode,2)
        self.assertEqual(inventory.read_bytes(),original)

    def test_backup_inventory_options_reject_invalid_or_clone_local_file(self):
        target,_=self.prepare()
        inventory=self.base/'inventory.json'
        for invalid in ('null','{"schema":1,"schema":2,"projects":{}}',' '*131073,'['*2000):
            inventory.write_text(invalid)
            self.assertEqual(self.inventory_command('--clone-root',target,'--inventory-file',inventory).returncode,2)
        self.assertEqual(self.inventory_command('--clone-root',target,'--record-inventory',
                                               target/'untrusted-inventory.json').returncode,2)
        self.assertFalse((target/'untrusted-inventory.json').exists())

    def test_unverified_backup_does_not_export_inventory(self):
        target,second=self.prepare()
        (target/'data'/'projects'/second/'index.html').write_text('wrong backup bytes')
        inventory=self.base/'inventory.json'
        result=self.inventory_command('--clone-root',target,'--record-inventory',inventory)
        self.assertEqual(result.returncode,2)
        self.assertFalse(inventory.exists())

    def test_pinned_summary_accepts_intact_clone_without_details(self):
        source,second=self.prepare()
        sidecar=self.base/'backup.json'
        self.assertEqual(self.inventory_command('--clone-root',source,'--record-inventory',sidecar).returncode,0)
        pin=hashlib.sha256(sidecar.read_bytes()).hexdigest()
        clone=shutil.copytree(source,self.base/'intact')
        result=self.inventory_command('--clone-root',clone,'--inventory-file',sidecar,
                                      '--inventory-sha256',pin.upper(),'--summary-only')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{
            'schema':'wfs-recovery-summary-v1','status':'DELIVERED_MATCH','reference':'SHA256_PINNED',
            'checked':2,'expected_projects':2,'missing_projects':0,'unexpected_projects':0,
            'different_generations':0,'artifact_check_failures':0})
        for private in (self.pid,second,pin,'index.html',str(clone),str(sidecar)):
            self.assertNotIn(private.encode(),result.stdout)

    def test_pinned_summary_distinguishes_missing_and_mixed_clones(self):
        source,second=self.prepare()
        sidecar=self.base/'backup.json'
        self.assertEqual(self.inventory_command('--clone-root',source,'--record-inventory',sidecar).returncode,0)
        pin=hashlib.sha256(sidecar.read_bytes()).hexdigest()
        missing=shutil.copytree(source,self.base/'incomplete')
        mixed=shutil.copytree(source,self.base/'mixed')
        with closing(sqlite3.connect(missing/'data'/'wfs.sqlite3')) as cx:
            cx.execute('DELETE FROM artifacts WHERE project_id=?',(second,))
            cx.execute('DELETE FROM projects WHERE id=?',(second,))
            cx.commit()
        shutil.rmtree(missing/'data'/'projects'/second)
        content=b'<html>Replacement generation</html>'
        (mixed/'data'/'projects'/second/'index.html').write_bytes(content)
        with closing(sqlite3.connect(mixed/'data'/'wfs.sqlite3')) as cx:
            cx.execute("UPDATE artifacts SET bytes=?,sha256=? WHERE project_id=? AND name='index.html'",
                       (len(content),hashlib.sha256(content).hexdigest(),second))
            cx.commit()
        for clone,expected in ((missing,(1,0)),(mixed,(0,1))):
            result=self.inventory_command('--clone-root',clone,'--inventory-file',sidecar,
                                          '--inventory-sha256',pin,'--summary-only')
            self.assertEqual(result.returncode,2)
            report=json.loads(result.stdout)
            self.assertEqual(report['status'],'DELIVERED_MISMATCH')
            self.assertEqual((report['missing_projects'],report['different_generations']),expected)
            self.assertEqual(report['artifact_check_failures'],0)
            self.assertNotIn(second.encode(),result.stdout)

    def test_inventory_pin_rejects_even_semantically_equal_reencoded_reference(self):
        source,_=self.prepare()
        sidecar=self.base/'backup.json'
        self.assertEqual(self.inventory_command('--clone-root',source,'--record-inventory',sidecar).returncode,0)
        original=sidecar.read_bytes()
        pin=hashlib.sha256(original).hexdigest()
        sidecar.write_bytes(original+b'\n')
        options=('--clone-root',source,'--inventory-file',sidecar,'--summary-only')
        self.assertEqual(self.inventory_command(*options).returncode,0)
        result=self.inventory_command(*options,'--inventory-sha256',pin)
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertEqual((report['status'],report['checked']),('INVENTORY_CHECKSUM_MISMATCH',0))
        self.assertNotIn(pin.encode(),result.stdout)
        self.assertEqual(self.inventory_command(*options,'--inventory-sha256','not-hex').returncode,2)
        self.assertEqual(self.inventory_command('--clone-root',source,'--inventory-sha256',pin).returncode,2)
