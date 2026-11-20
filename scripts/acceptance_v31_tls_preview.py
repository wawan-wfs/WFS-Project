#!/usr/bin/env python3
"""Operator-only real TLS negative probe. Never uses or logs login/session tokens.

Does NOT prove authenticated access, tenant revocation or runtime isolation;
those require separate browser HAR and trusted independent host review.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import re
import ssl
import sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from urllib.request import Request,urlopen


def check_origin(url:str,dynamic:bool)->str:
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
        raise ValueError('Explicit HTTPS-only origin required')
    name=p.hostname.lower()
    try:
        ipaddress.ip_address(name)
    except ValueError:pass
    else:raise ValueError('IP literal is not an accepted preview origin')
    if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',name) or name=='localhost' or name.endswith('.localhost'):
        raise ValueError('Public DNS hostname required')
    if dynamic and not re.fullmatch('[a-f0-9]{20}',name.split('.')[0]):
        raise ValueError('Dynamic hostname must begin with exact project ID')
    return 'https://'+p.netloc


def run(static_origin:str,dynamic_origins:list[str])->dict:
    origins=[check_origin(static_origin,False)]+[check_origin(x,True) for x in dynamic_origins]
    if len(set(origins))!=len(origins):raise ValueError('Origins must be distinct')
    context=ssl.create_default_context()
    checks=[]
    for i,origin in enumerate(origins):
        # Unauthenticated probes MUST fail, not serve user-generated code.
        try:
            with urlopen(Request(origin+('/p/'+'f'*20+'/index.html' if i==0 else '/'),headers={
                'User-Agent':'WFS-v31-operator-TLS-probe','Accept':'text/plain'}),timeout=9,context=context) as r:
                status=r.status;headers=r.headers
        except HTTPError as exc:
            status=exc.code;headers=exc.headers
        except (URLError,TimeoutError,OSError) as exc:
            checks.append({'origin':origin,'tls_verified':False,'unauth_denied':False,'security_headers':False,
                           'result':'FAIL: DNS/TLS/HTTP unavailable'});continue
        hsts='max-age=' in headers.get('Strict-Transport-Security','')
        csp="default-src" in headers.get('Content-Security-Policy','')
        checks.append({'origin':origin,'tls_verified':True,'unauth_denied':status in (401,403,404),
                       'security_headers':hsts and csp,'http_status':status,
                       'result':'PASS' if status in (401,403,404) and hsts and csp else 'FAIL'})
    return {'classification':'REAL TLS UNAUTHENTICATED NEGATIVE PROBE ONLY; NOT PRODUCTION ATTESTATION',
            'created_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'checks':checks,'all_negative_gates_pass':all(x['result']=='PASS' for x in checks),
            'not_proven':['authenticated preview','parallel cross-tenant access','session revocation',
                          'Docker host isolation','signed container images','actual GPU','provider billing']}


def main():
    p=argparse.ArgumentParser(description='Operator-only live TLS negative ingress check')
    p.add_argument('--static-origin',required=True)
    p.add_argument('--dynamic-origin',action='append',required=True,
                   help='Supply at least two different project-specific dynamic origins')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if len(a.dynamic_origin)<2:raise ValueError('Two dynamic origin samples required')
        result=run(a.static_origin,a.dynamic_origin)
        if a.output.exists():raise ValueError('Refusing to overwrite existing evidence')
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'PASS' if result['all_negative_gates_pass'] else 'FAIL',
                          'report':str(a.output),'probes':len(result['checks'])}))
        return 0 if result['all_negative_gates_pass'] else 1
    except (OSError,ValueError) as exc:
        p.error(str(exc))

if __name__=='__main__':sys.exit(main())
