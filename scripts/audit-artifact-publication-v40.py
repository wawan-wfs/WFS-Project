#!/usr/bin/env python3
"""Operator-only read-only check; never repairs, deletes or alters projects."""
import argparse,json
from pathlib import Path
from app import artifact_audit,store

def main():
    parser=argparse.ArgumentParser(description='Read-only WFS delivery consistency audit')
    parser.add_argument('--report',type=Path,help='Optional new JSON report file (must not already exist)')
    args=parser.parse_args()
    if not store.DB.is_file():
        parser.error('WFS database missing; audit refuses to initialize or migrate a database')
    result=artifact_audit.audit()
    data=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.report:
        with args.report.open('x',encoding='utf-8') as f:f.write(data)
    else:print(data,end='')
    return 2 if result['issues'] else 0

if __name__=='__main__':raise SystemExit(main())
