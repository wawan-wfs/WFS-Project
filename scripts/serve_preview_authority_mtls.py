#!/usr/bin/env python3
"""Explicit opt-in mTLS endpoint on a private IP for the DB-owning authority.

Never bind the public Internet, a wildcard address or the preview gateway host.
Real deployment still requires independent firewall, private PKI, short-lived
certs / revocation and operator verification. This script does NOT certify them.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import ssl
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.preview_authority_client import _trusted_file, AuthorityUnavailable


def private_listener(host: str) -> bool:
    try:
        ip=ipaddress.ip_address(host)
    except ValueError:
        return False
    return (ip.is_loopback or ip.is_private) and not (ip.is_unspecified or ip.is_multicast or ip.is_link_local)


def settings(host: str, port: int, cert: str, private_key: str, ca: str):
    if not private_listener(host):
        raise ValueError('Bind only a concrete private/loopback IP; never 0.0.0.0, :: or public IP')
    if not 1<=port<=65535 or len(os.getenv('WFS_PREVIEW_AUTHORITY_KEY',''))<32:
        raise ValueError('Explicit port and separately managed 32+ character HMAC key required')
    certfile=_trusted_file(cert)
    keyfile=_trusted_file(private_key,key=True)
    cafile=_trusted_file(ca)
    # Fail before starting the process if certificate/key/CA cannot be loaded.
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.verify_mode=ssl.CERT_REQUIRED
    ctx.load_cert_chain(str(certfile),str(keyfile))
    ctx.load_verify_locations(cafile=str(cafile))
    return str(certfile),str(keyfile),str(cafile)


def main():
    import uvicorn
    p=argparse.ArgumentParser(description='mTLS-only internal preview authority; private IP required')
    p.add_argument('--bind',required=True,help='Concrete private/loopback IP, never wildcard')
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--server-cert',required=True)
    p.add_argument('--server-key',required=True)
    p.add_argument('--client-ca',required=True)
    args=p.parse_args()
    try:
        cert,key,ca=settings(args.bind,args.port,args.server_cert,args.server_key,args.client_ca)
    except (ValueError,AuthorityUnavailable,ssl.SSLError,OSError) as exc:
        p.error(str(exc))
    uvicorn.run('app.preview_authority:app',host=args.bind,port=args.port,
                ssl_certfile=cert,ssl_keyfile=key,ssl_ca_certs=ca,
                ssl_cert_reqs=ssl.CERT_REQUIRED,log_level='warning',access_log=False,
                proxy_headers=False,workers=1)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
