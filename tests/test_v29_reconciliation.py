"""Local operator CSV comparison is NOT proof of authentic paid provider billing."""
import hashlib
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_system import PASSWORD
from app import store, config, auth

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reconcile_v29',ROOT/'scripts/provider-reconcile-report.py')
recon=importlib.util.module_from_spec(spec);spec.loader.exec_module(recon)

class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();p=Path(self.t.name)
        self.db=p/'wfs.sqlite3';self.csv=p/'provider.csv'
        self.patches=[patch.object(store,'DATA',p),patch.object(store,'DB',self.db),
                      patch.object(store,'PROJECTS',p/'projects'),patch.object(config,'DATA',p),
                      patch.object(config,'PROJECTS',p/'projects')]
        for x in self.patches:x.start()
        store.init_db();store.init_db()
        self.a=store.provision_organization('acme-v29','Acme','acme-v29',auth.hash_password('pw-12345678'))
        self.b=store.provision_organization('beta-v29','Beta','beta-v29',auth.hash_password('pw-12345678'))
        self.pa=store.create_project('Acme project','Build a working app with QA','demo','static',created_by=self.a)['id']
        self.pb=store.create_project('Beta project','Build another app with tests','demo','static',created_by=self.b)['id']
        store.set_model_price('model29',100,100,self.a)
        store.set_model_price('model29',100,100,self.b)

    def tearDown(self):
        for x in reversed(self.patches):x.stop()
        self.t.cleanup()

    def csv_digest(self,s):
        self.csv.write_text(s)
        return hashlib.sha256(self.csv.read_bytes()).hexdigest()

    def test_response_ids_unique_and_invoice_split_tenant_scoped(self):
        store.usage(self.pa,'QA','model29',100,0,provider_response_id='resp_alpha_0001')
        store.usage(self.pb,'QA','model29',100,0,provider_response_id='resp_beta_00002')
        with self.assertRaises(sqlite3.IntegrityError):
            store.usage(self.pb,'QA','model29',100,0,provider_response_id='resp_alpha_0001')
        digest=self.csv_digest('response_id,actual_usd\nresp_alpha_0001,0.01000000\nresp_beta_00002,0.01000000\n')
        result=recon.compare(self.db,self.csv,digest)
        self.assertTrue(result['comparison_complete'],result)
        self.assertFalse(result['reconciled'], 'Self-supplied CSV cannot authenticate provider charges')
        self.assertFalse(result['operator_clearance_eligible'])
        self.assertEqual(result['matched'],2)
        self.assertEqual({x['organization_id'] for x in result['tenant_totals']},{'acme-v29','beta-v29'})
        self.assertEqual(result['export_sha256'],digest)

    def test_unknown_provider_charge_and_orphan_are_not_reconciled(self):
        store.usage(self.pa,'QA','model29',100,0,provider_response_id='resp_alpha_0001')
        # A provider-facing request that had no trustworthy usage metadata.
        attempt=store.model_attempt_started(self.pa,'QA','model29')
        store.model_attempt_finished(attempt,'billing_unknown')
        digest=self.csv_digest('response_id,actual_usd\nresp_orphan_002,0.02\n')
        r=recon.compare(self.db,self.csv,digest)
        self.assertFalse(r['reconciled'])
        self.assertEqual(r['unresolved_attempts'],1)
        self.assertEqual(len(r['missing_local']),1)
        self.assertEqual(len(r['missing_export']),1)

    def test_duplicate_provider_lines_and_wrong_digest_are_rejected(self):
        digest=self.csv_digest('response_id,actual_usd\nresp_aabbccdd,0.01\nresp_aabbccdd,0.01\n')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            recon.compare(self.db,self.csv,digest)
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            recon.compare(self.db,self.csv,'f'*64)

if __name__=='__main__':unittest.main()
