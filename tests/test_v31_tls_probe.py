"""Local validation-only: does not execute real public HTTPS probes."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from email.message import Message

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls31',ROOT/'scripts/acceptance_v31_tls_preview.py')
tls=importlib.util.module_from_spec(spec);spec.loader.exec_module(tls)

class Dummy:
    def __init__(self,code=404):
        self.status=code
        self.headers=Message()
        self.headers.add_header('Strict-Transport-Security','max-age=31536000')
        self.headers.add_header('Content-Security-Policy',"default-src 'none'")
    def __enter__(self):return self
    def __exit__(self,*args):pass

class V31TLSProbe(unittest.TestCase):
    def test_origin_validation_rejects_unsafe_hosts(self):
        for bad in ('http://host.example.com','https://localhost','https://127.0.0.1',
                    'https://someone:secret@host.example.com','https://host.example.com/a'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):tls.check_origin(bad,False)
        with self.assertRaises(ValueError):tls.check_origin('https://notproject.preview.example.com',True)
    def test_network_probe_marks_missing_auth_real_evidence_only(self):
        with patch.object(tls,'urlopen',return_value=Dummy(404)):
            r=tls.run('https://static.example.com',[
                'https://'+'a'*20+'.preview.example.com',
                'https://'+'b'*20+'.preview.example.com'])
        self.assertTrue(r['all_negative_gates_pass'])
        self.assertIn('NOT PRODUCTION',r['classification'])
        with patch.object(tls,'urlopen',return_value=Dummy(200)):
            r=tls.run('https://static.example.com',[
                'https://'+'a'*20+'.preview.example.com',
                'https://'+'b'*20+'.preview.example.com'])
        self.assertFalse(r['all_negative_gates_pass'])

if __name__=='__main__':unittest.main()
