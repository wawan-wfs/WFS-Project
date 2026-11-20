"""Offline nginx rendering tests; do not confuse with deployed TLS evidence."""
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from scripts.render_authority_mtls_proxy import render, identity

class MTLSProxyConfigV34(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        key=ec.generate_private_key(ec.SECP256R1())
        now=datetime.now(timezone.utc)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'test-only-gateway')])
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(key.public_key()).serial_number(1234)
              .not_valid_before(now-timedelta(minutes=5))
              .not_valid_after(now+timedelta(days=1))
              .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False)
              .sign(key,hashes.SHA256()))
        self.client=Path(self.tmp.name)/'client.pem'
        self.client.write_bytes(cert.public_bytes(__import__('cryptography').hazmat.primitives.serialization.Encoding.PEM))
        self.opts=dict(bind='10.18.0.5',gateway='10.18.0.6',hostname='auth.internal.example',port=9443,
            socket='/run/wfs-preview/authority/authority.sock',
            server_cert='/etc/wfs/tls/server.pem',server_key='/etc/wfs/tls/server.key',
            client_ca='/etc/wfs/tls/gateway-ca.pem',client_crl='/etc/wfs/tls/revoked.pem',client_cert=self.client)
    def test_private_mtls_crl_and_allowlist(self):
        conf=render(**self.opts)
        digest,serial=identity(self.client)
        self.assertIn(digest+':'+serial,conf)
        for expected in ('ssl_verify_client on','ssl_crl /etc/wfs/tls/revoked.pem',
                'allow 10.18.0.6','deny all','proxy_pass http://unix:',
                'access_log off','proxy_set_header Cookie ""',
                'proxy_set_header Authorization ""', 'limit_except POST'):
            with self.subTest(expected=expected):self.assertIn(expected,conf)
        self.assertNotIn('proxy_pass http://127.0.0.1:',conf)
    def test_unsafe_operator_values_rejected(self):
        cases=[('bind','0.0.0.0'),('bind','127.0.0.1'),('bind','8.8.8.8'),
            ('gateway','10.18.0.5'),('gateway','1.1.1.1'),('hostname','bad;return 200'),
            ('hostname','*.example.com'),('socket','/run/foo;evil'),
            ('server_key','/etc/a\ninclude /etc/shadow'),('port',80),('client_crl','../oops')]
        for field,value in cases:
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError):render(**{**self.opts,field:value})
    def test_invalid_client_certificate_rejected(self):
        self.client.write_text('not a certificate')
        with self.assertRaises(ValueError):render(**self.opts)

if __name__=='__main__':unittest.main()
