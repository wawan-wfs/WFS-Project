#!/usr/bin/env python3
"""Opt-in REAL remote Docker negative-check runner (no fixtures).

Must be launched by a human operator after deploying independent rootless
Linux host and immutable staging. Does not prove an unrelated firewall policy.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runner_policy import check_daemon, remote_docker_prefix, validate_image, RunnerPolicyError

PROBE='''import os,socket,sys
if os.path.exists('/var/run/docker.sock'):
 print('FAIL_SOCKET_VISIBLE');sys.exit(11)
s=socket.socket();s.settimeout(3)
try:
 s.connect(('1.1.1.1',443))
except OSError:
 print('PASS_SOCKET_ABSENT_EGRESS_BLOCKED');sys.exit(0)
else:
 print('FAIL_NETWORK_EGRESS');sys.exit(12)
'''


def command(prefix,args,timeout=30):
    result=subprocess.run([*prefix,*args],capture_output=True,text=True,timeout=timeout)
    return result.returncode,result.stdout[-1600:],result.stderr[-800:]


def acceptance(host,ca,cert,key,image):
    prefix=remote_docker_prefix(host,ca,cert,key)
    validate_image(image)
    code,out,err=command(prefix,['info','--format','{{json .}}'],20)
    if code:raise RunnerPolicyError('Cannot reach rootless daemon over verified mTLS')
    info=json.loads(out)
    check_daemon(info)
    name='wfs-acceptance-negative-'+secrets.token_hex(8)
    args=['run','--rm','--name',name,'--network','none','--read-only',
          '--cap-drop','ALL','--security-opt','no-new-privileges',
          '--pids-limit','32','--memory','256m','--memory-swap','256m','--cpus','1',
          '--user','10001:10001',image,'python','-B','-c',PROBE]
    rc=None;stdout='';stderr='';timeout=False
    try:
        rc,stdout,stderr=command(prefix,args,60)
    except subprocess.TimeoutExpired:
        timeout=True
    finally:
        # Auto --rm may already have removed the probe; still attempt an
        # explicit bounded cleanup even after a failed/timeout run.
        try:command(prefix,['rm','-f',name],20)
        except (OSError,subprocess.TimeoutExpired):pass
    try:
        ps_rc,remaining,ps_err=command(prefix,['ps','-aq','--filter','name=^/'+name+'$'],20)
        info_rc,_,_=command(prefix,['info','--format','{{.ServerVersion}}'],20)
        cleanup_verified=ps_rc==0 and info_rc==0 and not remaining.strip()
    except (OSError,subprocess.TimeoutExpired):
        cleanup_verified=False
    return {'checked_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'remote_engine':True,'reported_rootless':True,'os':info.get('OSType'),
            'negative_probe':stdout.strip(),'probe_exit':rc,'probe_timeout':timeout,
            'no_container_left':cleanup_verified,
            'passed':rc==0 and not timeout and stdout.strip()=='PASS_SOCKET_ABSENT_EGRESS_BLOCKED' and cleanup_verified,
            'limitations':'One container network probe does not prove host firewall default deny, immutable staging, client certificate revocation or paid-provider reconciliation.'}



if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--host',default=os.getenv('WFS_RUNNER_DOCKER_HOST',''))
    parser.add_argument('--ca',default=os.getenv('WFS_RUNNER_CA',''))
    parser.add_argument('--cert',default=os.getenv('WFS_RUNNER_CERT',''))
    parser.add_argument('--key',default=os.getenv('WFS_RUNNER_KEY',''))
    parser.add_argument('--image',default=os.getenv('WFS_QA_PYTHON_DIGEST',''))
    a=parser.parse_args()
    try:
        result=acceptance(a.host,a.ca,a.cert,a.key,a.image)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('PASS' if result['passed'] else 'FAIL',a.output)
        sys.exit(0 if result['passed'] else 1)
    except (OSError,ValueError,subprocess.TimeoutExpired,json.JSONDecodeError,RunnerPolicyError) as ex:
        print('REMOTE ACCEPTANCE NOT COMPLETED:',ex,file=sys.stderr)
        sys.exit(2)
