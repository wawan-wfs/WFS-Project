#!/usr/bin/env python3
"""Run disposable local gates independently and write a bounded status report."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
GATES={
    'manifest':('scripts/verify-release.py',),
    'uds':('scripts/sse-two-api-lab.py',),
    'postgres-replica':('scripts/postgres-replica-lab.py',),
    'postgres-scale':('scripts/postgres-quota-lab.py',),
    'http':('scripts/http-e2e.py',),
    'workers':('scripts/parallel-e2e.py',),
}


def run(gates):
    env={**os.environ,'PYTHONPATH':str(ROOT)}
    env.pop('OPENAI_API_KEY',None)
    records={}
    for name in gates:
        start=time.monotonic()
        try:
            result=subprocess.run([sys.executable,*GATES[name]],cwd=ROOT,env=env,timeout=55)
            rc=result.returncode
            status='PASS_LOCAL' if rc==0 else 'BLOCKED_RUNTIME' if name=='uds' and rc==77 else 'FAIL'
        except subprocess.TimeoutExpired:
            rc=None
            status='TIMEOUT'
        records[name]={'status':status,'returncode':rc,'elapsed_seconds':round(time.monotonic()-start,3)}
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path,help='New status JSON (existing files are not overwritten)')
    parser.add_argument('--gate',action='append',choices=GATES)
    args=parser.parse_args()
    gates=tuple(dict.fromkeys(args.gate or GATES))
    with args.output.open('x',encoding='utf-8') as out:
        result=run(gates)
        json.dump({'classification':'LOCAL_ONLY','production_admission':'DENIED',
                   'utc':datetime.now(timezone.utc).isoformat(),'gates':result},out,indent=2)
        out.write('\n')
    if any(r['status'] in ('FAIL','TIMEOUT') for r in result.values()):return 1
    if any(r['status']=='BLOCKED_RUNTIME' for r in result.values()):return 77
    return 0


if __name__=='__main__':
    raise SystemExit(main())
