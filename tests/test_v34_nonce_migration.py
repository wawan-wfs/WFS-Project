"""Local additive migration simulation: old DB lacks the new nonce table.

This is NOT a real Windows backup/restore drill or proof of the exact v3.3 binary.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import store, config, auth

class NonceSchemaMigrationV34(unittest.TestCase):
    def test_idempotent_migration_preserves_project_identity(self):
        with tempfile.TemporaryDirectory(prefix='wfs-v34-schema-') as tmp:
            p=Path(tmp)
            with (patch.object(store,'DATA',p),patch.object(store,'DB',p/'db.sqlite3'),
                  patch.object(store,'PROJECTS',p/'projects'),patch.object(config,'DATA',p),
                  patch.object(config,'PROJECTS',p/'projects')):
                store.init_db()
                uid=store.provision_organization('nonce-old-org','Nonce Org','nonceuser',auth.hash_password('test-password-12chars'))
                pid=store.create_project('Old project','Existing source and authorization data','demo','static',created_by=uid)['id']
                with store.connect() as cx:
                    cx.execute('DROP TABLE preview_authority_nonces')  # simulate prior schema on isolated clone
                store.init_db()
                store.init_db()
                with store.connect() as cx:
                    self.assertIsNotNone(cx.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone())
                    self.assertIsNotNone(cx.execute("SELECT 1 FROM sqlite_master WHERE name='preview_authority_nonces'").fetchone())
                    self.assertEqual(cx.execute('SELECT COUNT(*) FROM preview_authority_nonces').fetchone()[0],0)

if __name__=='__main__':unittest.main()
