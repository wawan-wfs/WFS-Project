"""Verify that a successful pytest exit cannot hide missing transport evidence."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tempfile import TemporaryDirectory

script = Path(__file__).resolve().parents[1] / 'scripts' / 'run-operator-evidence-v46.py'
spec = importlib.util.spec_from_file_location('wfs_operator_v46', script)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class OperatorEvidenceV46(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.report = Path(temp.name) / 'focused.xml'
        self.root = ET.Element('testsuite')
        for group, names in collector.CASES.items():
            for name in names:
                ET.SubElement(self.root, 'testcase', classname='tests.'+group, name=name)

    def result(self, rc=0):
        ET.ElementTree(self.root).write(self.report)
        return collector.focused_result(self.report, rc)

    def test_complete_run(self):
        self.assertEqual(self.result()['status'], 'PASS_LOCAL')
        self.assertEqual(len(self.result()['cases']), 17)

    def test_unix_skip_blocks_even_with_zero_exit(self):
        ET.SubElement(self.root[0], 'skipped', message='Runtime does not permit AF_UNIX sockets')
        result = self.result()
        self.assertEqual(result['status'], 'BLOCKED_RUNTIME')
        self.assertEqual(collector.exit_status({'focused': result, 'http': {'status': 'PASS_LOCAL'}}), 77)

    def test_missing_or_duplicate_case_fails(self):
        case = self.root[0]
        self.root.remove(case)
        result = self.result()
        self.assertIn('NOT_RUN', result['cases'].values())
        self.assertEqual(result['status'], 'FAIL')
        self.root.extend([case, case])
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_unexpected_skip_bad_xml_and_nonzero_fail(self):
        self.assertEqual(self.result(rc=2)['status'], 'FAIL')
        ET.SubElement(self.root[-1], 'skipped', message='unexpected')
        self.assertEqual(self.result()['status'], 'FAIL')
        self.report.write_text('<bad')
        self.assertEqual(collector.focused_result(self.report, 0)['status'], 'FAIL')

    def test_failed_or_timed_out_gate_precedes_blocked(self):
        self.assertEqual(collector.exit_status({'uds': {'status': 'BLOCKED_RUNTIME'},
                                                'http': {'status': 'TIMEOUT'}}), 1)
        with patch.object(collector.subprocess, 'run',
                          side_effect=[collector.subprocess.TimeoutExpired('test', 55),
                                       collector.subprocess.CompletedProcess([], 0)]):
            result = collector.run(('uds', 'http'))
        self.assertEqual(result['uds']['status'], 'TIMEOUT')
        self.assertEqual(result['http']['status'], 'PASS_LOCAL')

    def test_two_api_evidence_requires_every_check_and_real_process_count(self):
        sample = dict.fromkeys(collector.UDS_CHECKS, True)
        sample.update(classification='PASS_LOCAL_UDS', separate_api_processes=3)
        self.assertEqual(collector.uds_result(json.dumps(sample), 0)['status'], 'PASS_LOCAL')
        sample['transport_secret_rotation'] = False
        self.assertEqual(collector.uds_result(json.dumps(sample), 0)['status'], 'FAIL')
        blocked = collector.uds_result('{"classification":"BLOCKED_RUNTIME"}', 77)
        self.assertEqual(blocked['status'], 'BLOCKED_RUNTIME')
        self.assertEqual(set(blocked['cases'].values()), {'NOT_RUN'})
        self.assertEqual(collector.uds_result('unexpected output', 77)['status'], 'FAIL')
