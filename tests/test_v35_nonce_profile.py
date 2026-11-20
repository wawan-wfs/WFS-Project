"""Concurrency and additive SQLite index proof, no physical-host claims."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import store
from scripts.profile_nonce_v35 import profile

class NonceProfileV35(unittest.TestCase):
    def test_profile_cross_process_only_one_replay_wins(self):
        report=profile(workers=4,count=16)
        self.assertEqual(report['same_nonce_accepted'],1)
        self.assertEqual(report['unique_accepted'],16)
        self.assertFalse(report['real_host_proof'])

    def test_bounds_are_bounded(self):
        for w,n in ((0,1),(17,40),(2,1),(1,2049)):
            with self.subTest(workers=w,count=n),self.assertRaises(ValueError):
                profile(workers=w,count=n)

    def test_nonce_age_index_is_additive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with patch.object(store,'DATA',p),patch.object(store,'DB',p/'db.sqlite3'),patch.object(store,'PROJECTS',p/'projects'):
                store.init_db();store.init_db()
                with store.connect() as db:
                    names={r['name'] for r in db.execute('PRAGMA index_list(preview_authority_nonces)')}
                    self.assertIn('idx_preview_authority_nonce_age',names)

if __name__=='__main__':unittest.main()
