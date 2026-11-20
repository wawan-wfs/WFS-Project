"""Actual localhost TLS handshake tests; NOT an independent physical host proof."""
from __future__ import annotations

import hashlib
import hmac
import http.server
import ipaddress
import json
import os
import ssl
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from app import preview_authority_client as authority

KEY = 'distinct-operator-only-signature-key-at-least-32-chars'


def certificate(issuer_key, issuer_name, name, public_key, san=None, ca=False):
    now=datetime.now(timezone.utc)
    builder=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)]))
        .issuer_name(issuer_name).public_key(public_key).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(hours=1)).not_valid_after(now+timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=ca,path_length=0 if ca else None),critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,
            data_encipherment=False,key_agreement=False,key_cert_sign=ca,crl_sign=ca,
            encipher_only=False,decipher_only=False),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key),critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),critical=False))
    if san: builder=builder.add_extension(x509.SubjectAlternativeName(san),critical=False)
    return builder.sign(issuer_key,hashes.SHA256())


def write(path,content,private=False):
    path.write_bytes(content)
    path.chmod(0o600 if private else 0o644)
    return str(path)


def pubpem(cert):return cert.public_bytes(serialization.Encoding.PEM)
def privpem(key):return key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())


class AuthorityHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        count=int(self.headers.get('Content-Length','0'))
        body=self.rfile.read(count)
        stamp=self.headers.get('X-WFS-Authority-Time','')
        nonce=self.headers.get('X-WFS-Authority-Nonce','')
        signature=self.headers.get('X-WFS-Authority-Signature','')
        message=(stamp+'\n'+nonce+'\n'+self.path+'\n').encode()+body
        if (self.path not in ('/internal/ticket','/internal/verify','/internal/exchange')
                or not hmac.compare_digest(hmac.new(KEY.encode(),message,hashlib.sha256).hexdigest(),signature)):
            self.send_error(403)
            return
        response=json.dumps({'ok':True,'project_id':'a'*20,'stack':'fastapi'}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self,*args):pass


class MTLSAuthorityV33(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wfs-v33-local-mtls-')
        root=Path(self.tmp.name)
        ca_key=ec.generate_private_key(ec.SECP256R1())
        ca_subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'WFS test-only CA')])
        ca_cert=certificate(ca_key,ca_subject,'WFS test-only CA',ca_key.public_key(),ca=True)
        server_key=ec.generate_private_key(ec.SECP256R1())
        server_cert=certificate(ca_key,ca_subject,'localhost test server',server_key.public_key(),
            [x509.IPAddress(ipaddress.ip_address('127.0.0.1'))])
        client_key=ec.generate_private_key(ec.SECP256R1())
        client_cert=certificate(ca_key,ca_subject,'WFS test-only client',client_key.public_key())
        self.ca=write(root/'root.pem',pubpem(ca_cert))
        self.cert=write(root/'client.pem',pubpem(client_cert))
        self.key=write(root/'client.key',privpem(client_key),private=True)
        srv_cert=write(root/'server.pem',pubpem(server_cert))
        srv_key=write(root/'server.key',privpem(server_key),private=True)
        self.server=http.server.HTTPServer(('127.0.0.1',0),AuthorityHandler)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(srv_cert,srv_key)
        ctx.load_verify_locations(self.ca)
        ctx.verify_mode=ssl.CERT_REQUIRED
        self.server.socket=ctx.wrap_socket(self.server.socket,server_side=True)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
        self.settings={
            'WFS_PREVIEW_AUTHORITY_MODE':'mtls',
            'WFS_PREVIEW_AUTHORITY_KEY':KEY,
            'WFS_PREVIEW_AUTHORITY_URL':f'https://127.0.0.1:{self.server.server_port}',
            'WFS_PREVIEW_AUTHORITY_CA':self.ca,
            'WFS_PREVIEW_AUTHORITY_CERT':self.cert,
            'WFS_PREVIEW_AUTHORITY_CLIENT_KEY':self.key,
            'WFS_PREVIEW_AUTHORITY_SOCKET':'',
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.tmp.cleanup()

    def test_real_mutual_tls_handshake_and_hmac(self):
        with patch.dict(os.environ,self.settings):
            self.assertTrue(authority.enabled())
            reply=authority.call('ticket',{'ticket':'x'*30})
            self.assertEqual(reply['project_id'],'a'*20)

    def test_untrusted_ca_rejected(self):
        # A syntactically valid but different CA must be rejected at TLS handshake.
        fake_key=ec.generate_private_key(ec.SECP256R1())
        fake_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'wrong CA')])
        fake=certificate(fake_key,fake_name,'wrong CA',fake_key.public_key(),ca=True)
        other=write(Path(self.tmp.name)/'other.pem',pubpem(fake))
        with patch.dict(os.environ,{**self.settings,'WFS_PREVIEW_AUTHORITY_CA':other}):
            with self.assertRaises(authority.AuthorityUnavailable):
                authority.call('ticket',{'ticket':'x'*30})

    def test_missing_client_cert_and_bad_tls_policy_rejected(self):
        with patch.dict(os.environ,{**self.settings,'WFS_PREVIEW_AUTHORITY_CERT':''}):
            with self.assertRaises(authority.AuthorityUnavailable):authority.call('verify',{'project_id':'a'*20})
        for endpoint in ('http://127.0.0.1:9443','https://localhost:9443/path',
                         'https://user:pass@localhost:9443','https://localhost:9443?x=1',
                         'https://localhost','https://example.com:8443/#fragment'):
            with self.subTest(endpoint=endpoint):
                with patch.dict(os.environ,{**self.settings,'WFS_PREVIEW_AUTHORITY_URL':endpoint}):
                    with self.assertRaises(authority.AuthorityUnavailable):authority.call('ticket',{})

    def test_hostname_mismatch_rejected(self):
        with patch.dict(os.environ,{**self.settings,
                'WFS_PREVIEW_AUTHORITY_URL':f'https://localhost:{self.server.server_port}'}):
            with self.assertRaises(authority.AuthorityUnavailable):
                authority.call('ticket',{'ticket':'x'*30})

    def test_listener_private_only_and_invalid_credentials_fail(self):
        from scripts.serve_preview_authority_mtls import private_listener, settings
        self.assertTrue(private_listener('127.0.0.1'))
        self.assertTrue(private_listener('10.14.3.7'))
        for host in ('0.0.0.0','::','8.8.8.8','wfs.example.org','169.254.10.1'):
            with self.subTest(host=host):self.assertFalse(private_listener(host))
        with patch.dict(os.environ,self.settings):
            with self.assertRaises(ValueError):
                settings('0.0.0.0',9443,self.cert,self.key,self.ca)
            with self.assertRaises(ValueError):
                settings('127.0.0.1',0,self.cert,self.key,self.ca)

    def test_unsafe_key_permissions_and_mode_fail_closed(self):
        Path(self.key).chmod(0o644)
        try:
            with patch.dict(os.environ,self.settings):
                with self.assertRaises(authority.AuthorityUnavailable):authority.call('ticket',{})
        finally: Path(self.key).chmod(0o600)
        with patch.dict(os.environ,{**self.settings,'WFS_PREVIEW_AUTHORITY_MODE':'bad'}):
            with self.assertRaises(authority.AuthorityUnavailable):authority.call('ticket',{})


if __name__=='__main__':unittest.main()
