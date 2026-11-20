#!/usr/bin/env python3
"""OFFLINE operator comparison against manually normalized provider line items.

Never calls provider or changes local spend/attempts. CSV must be produced and
verified from an independent official provider source by the human operator.
Required columns: response_id,actual_usd; IDs must be actual response IDs, not
model names, internal attempt IDs or a daily aggregate. No invoice is bundled.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def compare(db_path:Path,export_path:Path,expected_sha256:str,tolerance_usd:float=0.01):
    if not re.fullmatch(r'[a-f0-9]{64}',expected_sha256):raise ValueError('Independent export SHA-256 required')
    if export_path.is_symlink() or not export_path.is_file() or export_path.stat().st_size>10_000_000:
        raise ValueError('Invalid export file')
    if hashlib.sha256(export_path.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Provider CSV digest mismatch')
    if not 0<=tolerance_usd<=100 or not math.isfinite(tolerance_usd):
        raise ValueError('Invalid difference threshold')
    invoices={}
    with export_path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or set(reader.fieldnames)!= {'response_id','actual_usd'}:
            raise ValueError('CSV must contain only response_id,actual_usd columns')
        for r in reader:
            rid=r['response_id']
            if not rid or not re.fullmatch(r'[A-Za-z0-9._:-]{8,160}',rid) or rid in invoices:
                raise ValueError('Missing/duplicate/unsafe provider response ID')
            try:amount=Decimal(r['actual_usd'])
            except (InvalidOperation,TypeError):raise ValueError('Invalid provider USD amount') from None
            if not amount.is_finite() or amount<0 or amount>1_000_000:
                raise ValueError('Provider USD must be finite and nonnegative')
            invoices[rid]=amount
    if not invoices:
        raise ValueError('At least one independently confirmed response line is required')
    if db_path.is_symlink() or not db_path.is_file():raise ValueError('Local ledger database unavailable')
    # Read-only URI avoids creating or modifying missing databases.
    from urllib.parse import quote
    cx=sqlite3.connect('file:'+quote(str(db_path.resolve()),safe='/')+'?mode=ro',uri=True)
    cx.row_factory=sqlite3.Row
    try:
        cols={x['name'] for x in cx.execute('PRAGMA table_info(usage)')}
        if 'provider_response_id' not in cols:
            raise ValueError('Ledger schema is older than v2.9')
        usages=cx.execute('''SELECT u.provider_response_id,u.estimated_usd,p.organization_id,p.workspace_id,
                u.project_id,u.model FROM usage u JOIN projects p ON p.id=u.project_id''').fetchall()
        unresolved=cx.execute("SELECT COUNT(*) n FROM provider_attempts WHERE status='billing_unknown'").fetchone()['n']
    finally:cx.close()
    matched=[];missing_local=[];missing_export=[]
    tenant=defaultdict(lambda:{'matched_actual_usd':Decimal('0'),'matched_estimated_usd':Decimal('0'),'matched_calls':0})
    local_ids=set()
    for r in usages:
        rid=r['provider_response_id'];estimated=r['estimated_usd']
        if not rid or estimated is None:
            missing_export.append({'reason':'local_unpriced_or_missing_response_id','project':r['project_id']})
            continue
        local_ids.add(rid)
        if rid not in invoices:
            missing_export.append({'reason':'provider_response_missing_from_export','project':r['project_id']})
            continue
        actual=invoices[rid];estimated=Decimal(str(estimated));diff=actual-estimated
        key=(r['organization_id'],r['workspace_id'])
        tenant[key]['matched_actual_usd']+=actual
        tenant[key]['matched_estimated_usd']+=estimated
        tenant[key]['matched_calls']+=1
        matched.append({'organization_id':key[0],'workspace_id':key[1],
                        'delta_usd':str(diff),'within_tolerance':abs(diff)<=Decimal(str(tolerance_usd))})
    missing_local=[{'reason':'provider_response_not_in_local_ledger','id_sha256':hashlib.sha256(k.encode()).hexdigest()[:16]}
                   for k in invoices if k not in local_ids]
    comparison_complete=bool(matched) and not (missing_local or missing_export or unresolved or any(not x['within_tolerance'] for x in matched))
    return {'classification':'OFFLINE COMPARISON, NOT INDEPENDENTLY CERTIFIED PROVIDER BILLING',
            'provider_evidence_authenticated':False,
            'operator_clearance_eligible':False,
            'comparison_complete':comparison_complete,
            'export_sha256':expected_sha256,'matched':len(matched),
            'tolerance_usd':tolerance_usd,'discrepancies':[r for r in matched if not r['within_tolerance']],
            'missing_local':missing_local,'missing_export':missing_export,'unresolved_attempts':unresolved,
            'tenant_totals':[{'organization_id':a,'workspace_id':b,'matched_calls':v['matched_calls'],
                              'matched_actual_usd':str(v['matched_actual_usd']),
                              'matched_estimated_usd':str(v['matched_estimated_usd'])} for (a,b),v in sorted(tenant.items())],
            'reconciled':False}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tolerance-usd',type=float,default=0.01)
    a=p.parse_args()
    try:
        result=compare(a.db,a.export,a.expected_sha256,a.tolerance_usd)
        if a.output.exists():raise ValueError('Refuse to replace existing audit report')
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'report':str(a.output),'offline_comparison_complete':result['comparison_complete'],
                          'authenticated_provider_reconciliation':False,'matched':result['matched']}))
        sys.exit(0 if result['comparison_complete'] else 1)
    except (OSError,ValueError,sqlite3.Error) as exc:
        p.error(str(exc))
