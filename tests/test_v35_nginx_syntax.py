"""Actual LOCAL nginx config parse with ephemeral self-signed TEST PKI.

Does not bind, serve traffic, prove host firewall, or validate production CRLs.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from scripts.render_authority_mtls_proxy import render

@unittest.skipUnless(shutil.which('nginx'), 'NGINX_NOT_INSTALLED: operator must run nginx -t')
class LocalNginxParseV35(unittest.TestCase):
    def test_rendered_mtls_config_compiles_with_local_nginx(self):
        now=datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory(prefix='wfs-v35-nginx-') as tmp:
            p=Path(tmp)
            ca_key=ec.generate_private_key(ec.SECP256R1())
            ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'WFS LOCAL TEST CA')])
            ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=4))
                .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
                .sign(ca_key,hashes.SHA256()))
            (p/'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
            def issue(hostname,eku):
                key=ec.generate_private_key(ec.SECP256R1())
                name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,hostname)])
                cert=(x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=2))
                    .add_extension(x509.ExtendedKeyUsage([eku]),critical=False)
                    .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),critical=False)
                    .sign(ca_key,hashes.SHA256()))
                (p/(hostname+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
                (p/(hostname+'.key')).write_bytes(key.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
                return p/(hostname+'.pem')
            from cryptography.x509.oid import ExtendedKeyUsageOID
            server=issue('auth.internal.example',ExtendedKeyUsageOID.SERVER_AUTH)
            client=issue('gateway.internal.example',ExtendedKeyUsageOID.CLIENT_AUTH)
            crl=(x509.CertificateRevocationListBuilder().issuer_name(ca_name)
                 .last_update(now-timedelta(minutes=2)).next_update(now+timedelta(hours=2))
                 .sign(ca_key,hashes.SHA256()))
            (p/'crl.pem').write_bytes(crl.public_bytes(serialization.Encoding.PEM))
            content=render(bind='10.18.0.5',gateway='10.18.0.6',hostname='auth.internal.example',
                port=9443,socket='/run/wfs-preview/authority/authority.sock',
                server_cert=str(server),server_key=str(p/'auth.internal.example.key'),
                client_ca=str(p/'ca.pem'),client_crl=str(p/'crl.pem'),client_cert=client)
            # nginx -t also validates local bind availability on this nginx build.
            # Substitute only the listen IP for TEST; production renderer still
            # refuses loopback/public binds. Nginx is not started.
            local_syntax_only=content.replace('listen 10.18.0.5:9443 ssl;',
                                               'listen 127.0.0.1:9443 ssl;')
            (p/'authority.inc').write_text(local_syntax_only)
            # nginx -t validates syntax and bind feasibility, without serving.
            (p/'nginx.conf').write_text('events {}\nhttp { include '+str(p/'authority.inc')+'; }\n')
            result=subprocess.run([shutil.which('nginx'),'-t','-c',str(p/'nginx.conf'),'-p',str(p)+'/'],
                                  capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0, result.stderr[-1300:])

if __name__=='__main__':unittest.main()
