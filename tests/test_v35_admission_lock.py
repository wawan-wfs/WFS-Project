"""Offline import/cleanup lock compatibility, no real daemon required."""
from __future__ import annotations
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

source=Path(__file__).resolve().parents[1]/'scripts/runner-import-seal-v29.py'
spec=importlib.util.spec_from_file_location('wfs_seal_v29',source)
seal=importlib.util.module_from_spec(spec);spec.loader.exec_module(seal)

class OperatorAdmissionLock(unittest.TestCase):
    def test_pause_marker_prevents_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'.admissions-paused').write_text('DISABLED\n')
            with patch.object(seal,'ROOT',root),patch.object(seal.os,'geteuid',return_value=0):
                with self.assertRaisesRegex(ValueError,'paused'):
                    with seal.operator_admission_lock(): pass

    def test_lock_is_released_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(seal,'ROOT',root):
                with seal.operator_admission_lock(): self.assertTrue((root/'.operator-maintenance.lock').exists())
                with seal.operator_admission_lock():pass

if __name__=='__main__':unittest.main()
