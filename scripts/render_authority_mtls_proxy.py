#!/usr/bin/env python3
"""Offline-only nginx mTLS authority ingress renderer (NOT a deployment action).

The exact client cert is constrained after CA+CRL validation. The HTTP app remains
on a private UDS and independently authenticates every HMAC signed operation.
"""
from __future__ import annotations

import argparse
import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtendedKeyUsageOID

SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]+$")
SAFE_HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def check_path(raw: str, what: str) -> str:
    if not SAFE_PATH.fullmatch(raw) or '..' in Path(raw).parts or raw.startswith('//'):
        raise ValueError(f'Unsafe {what} path')
    return raw


def private_ip(raw: str, what: str) -> str:
    try:
        ip=ipaddress.ip_address(raw)
    except ValueError:
        raise ValueError(f'Invalid {what} address') from None
    rfc1918 = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
    if not (ip.version == 4 and any(ip in block for block in rfc1918)):
        raise ValueError(f'{what} must be concrete private IPv4 on a separate host')
    return str(ip)


def identity(cert_path: Path) -> tuple[str, str]:
    cert=x509.load_pem_x509_certificate(cert_path.read_bytes())
    now=datetime.now(timezone.utc)
    if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
        raise ValueError('Client certificate expired or not active')
    try:
        eku=cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
            raise ValueError('Client certificate lacks clientAuth extended key usage')
    except x509.ExtensionNotFound:
        raise ValueError('Client certificate must declare clientAuth EKU') from None
    # nginx $ssl_client_fingerprint is SHA1. This is an identity selector ONLY;
    # cryptographic authentication is performed by trusted CA + ssl_crl.
    digest=cert.fingerprint(hashes.SHA1()).hex().upper()
    return digest, format(cert.serial_number, 'X')


def render(*, bind: str, gateway: str, hostname: str, port: int, socket: str,
           server_cert: str, server_key: str, client_ca: str, client_crl: str,
           client_cert: Path) -> str:
    bind=private_ip(bind, 'authority bind')
    gateway=private_ip(gateway, 'gateway')
    if bind==gateway:
        raise ValueError('Gateway and authority cannot use same IPv4 identity')
    if not SAFE_HOST.fullmatch(hostname) or hostname.startswith('localhost'):
        raise ValueError('Exact valid authority DNS name required')
    if not 1024<=port<=65535:
        raise ValueError('Privileged or invalid port forbidden')
    paths={k:check_path(v,k) for k,v in {
        'socket':socket,'server cert':server_cert,'server key':server_key,
        'client CA':client_ca,'client CRL':client_crl}.items()}
    fingerprint,serial=identity(client_cert)
    # Accept nginx documented hex fingerprint with or without colon separators,
    # paired with the certificate serial and an independently trusted CA + CRL.
    f_colon=':'.join(fingerprint[i:i+2] for i in range(0,len(fingerprint),2))
    return f'''# Generated offline. Include INSIDE nginx http {{...}}. Operator must run nginx -t.
# DENY before upstream: CA and CRL are mandatory, only one registered gateway cert.
# Long certificate fingerprints require an explicit bucket size in nginx http context.
map_hash_bucket_size 128;
map "$ssl_client_fingerprint:$ssl_client_serial" $wfs_authority_client_allowed {{
    default 0;
    "{fingerprint}:{serial}" 1;
    "{f_colon}:{serial}" 1;
}}
server {{
    listen {bind}:{port} ssl;
    server_name {hostname};
    ssl_certificate {paths['server cert']};
    ssl_certificate_key {paths['server key']};
    ssl_client_certificate {paths['client CA']};
    ssl_trusted_certificate {paths['client CA']};
    ssl_crl {paths['client CRL']};
    ssl_verify_client on;
    ssl_verify_depth 2;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    ssl_session_cache off;
    keepalive_timeout 0;
    allow {gateway};
    deny all;
    # No URI/query/cookie/token recorded, including invalid requests.
    access_log off;
    error_log /var/log/nginx/wfs-authority-error.log warn;
    client_max_body_size 2k;
    if ($wfs_authority_client_allowed != 1) {{ return 403; }}
    if ($ssl_client_verify != SUCCESS) {{ return 403; }}
    location ~ ^/internal/(ticket|exchange|verify)$ {{
        limit_except POST {{ deny all; }}
        proxy_pass http://unix:{paths['socket']}:;
        proxy_http_version 1.1;
        proxy_set_header Connection close;
        proxy_set_header Host authority.internal;
        proxy_set_header X-Forwarded-For "";
        proxy_set_header X-Forwarded-Host "";
        proxy_set_header X-Forwarded-Proto "";
        proxy_set_header Cookie "";
        proxy_set_header Authorization "";
        proxy_connect_timeout 2s;
        proxy_read_timeout 3s;
        proxy_send_timeout 3s;
        proxy_buffering off;
    }}
    location / {{ return 404; }}
}}
'''


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bind','gateway','hostname','socket','server-cert','server-key','client-ca','client-crl','client-cert','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--port',type=int,default=9443)
    a=p.parse_args()
    try:
        out=render(bind=a.bind,gateway=a.gateway,hostname=a.hostname,port=a.port,
            socket=a.socket,server_cert=a.server_cert,server_key=a.server_key,
            client_ca=a.client_ca,client_crl=a.client_crl,client_cert=Path(a.client_cert))
        target=Path(a.output)
        if target.exists():
            raise ValueError('Output already exists; cannot overwrite operator configuration')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(out,encoding='utf-8')
        target.chmod(0o600)
        print('Generated OFFLINE; NOT deployed or acceptance-tested:',target)
        return 0
    except (ValueError,OSError) as e:
        p.error(str(e))
    return 2

if __name__=='__main__':raise SystemExit(main())
