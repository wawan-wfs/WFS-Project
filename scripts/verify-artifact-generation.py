#!/usr/bin/env python3
"""Offline recovery helper. Read-only. Never promotes a candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from app.artifact_recovery import _plain_path, verify_delivered_clone, verify_generation


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate inventory key')
        result[key]=value
    return result


def read_inventory(path, expected_sha256=None):
    with _plain_path(path).open('rb') as stream:
        raw=stream.read(131073)
    if len(raw)>131072:
        raise ValueError('Inventory exceeds size limit')
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise InventoryChecksumMismatch
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique_object)


class InventoryChecksumMismatch(ValueError):
    pass


def summary(report, reference):
    return {'schema':'wfs-recovery-summary-v1','status':report['status'],
            'reference':reference,'checked':report.get('checked',0),
            'expected_projects':report.get('expected_projects',0),
            'missing_projects':len(report.get('missing_expected_projects',())),
            'unexpected_projects':report.get('unexpected_delivered_count',0),
            'different_generations':len(report.get('mismatched_project_fingerprints',())),
            'artifact_check_failures':sum(r['status']!='EXACT_MATCH' for r in report.get('results',()))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clone-root',type=Path,help='Verify all delivered projects in a stopped test clone')
    parser.add_argument('--require-project',action='append',default=[],
                        help='Require this project ID in the clone delivery inventory (repeatable)')
    parser.add_argument('--exact-inventory',action='store_true',
                        help='Reject additional delivered projects outside the required list')
    inventories=parser.add_mutually_exclusive_group()
    inventories.add_argument('--inventory-file',type=Path,help='Verify against a separately kept backup inventory')
    inventories.add_argument('--record-inventory',type=Path,help='Write a new inventory from a verified stopped backup')
    parser.add_argument('--inventory-sha256',help='Expected SHA-256 of the exact reference file bytes')
    parser.add_argument('--summary-only',action='store_true',help='Emit batch counts without project IDs or artifact names')
    parser.add_argument('--db',type=Path)
    parser.add_argument('--project')
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args()
    single=(args.db,args.project,args.candidate)
    if (args.clone_root and any(single)) or (not args.clone_root and not all(single)):
        parser.error('Specify --clone-root alone, or --db, --project and --candidate together')
    if args.require_project and not args.clone_root:
        parser.error('--require-project is only supported with --clone-root')
    if args.exact_inventory and (not args.clone_root or not args.require_project):
        parser.error('--exact-inventory requires --clone-root and --require-project')
    sidecar=args.inventory_file or args.record_inventory
    if sidecar and (not args.clone_root or args.require_project or args.exact_inventory):
        parser.error('Inventory files require --clone-root and no ID-list options')
    if args.inventory_sha256 is not None and (not args.inventory_file
                                             or not re.fullmatch('[a-fA-F0-9]{64}',args.inventory_sha256)):
        parser.error('--inventory-sha256 requires --inventory-file and a 64-character hex SHA-256')
    if args.summary_only and (not args.clone_root or args.record_inventory):
        parser.error('--summary-only requires clone verification, not inventory recording')
    reference=('SHA256_PINNED' if args.inventory_sha256 else 'FILE'
               if args.inventory_file else 'ID_LIST' if args.require_project else 'NONE')
    try:
        if sidecar and sidecar.resolve().is_relative_to(args.clone_root.resolve()):
            raise ValueError('Keep the inventory outside the clone')
        expected=None
        if args.inventory_file:
            pin=args.inventory_sha256.lower() if args.inventory_sha256 else None
            expected=read_inventory(args.inventory_file,pin)
        # Explicit null is invalid, not an implicit request to skip comparison.
        if args.inventory_file and expected is None:
            raise ValueError('Missing inventory')
        report=(verify_delivered_clone(args.clone_root,expected_projects=args.require_project,
                                       exact_inventory=args.exact_inventory,expected_inventory=expected,
                                       include_inventory=bool(args.record_inventory)) if args.clone_root else
                verify_generation(args.db,args.project,args.candidate))
        if args.record_inventory and report['status']=='DELIVERED_MATCH':
            with args.record_inventory.open('x',encoding='utf-8') as stream:
                json.dump(report.pop('inventory'),stream,indent=2,sort_keys=True)
                stream.write('\n')
    except InventoryChecksumMismatch:
        report={'status':'INVENTORY_CHECKSUM_MISMATCH'}
    except (ValueError,OSError,sqlite3.Error,RecursionError) as exc:
        parser.exit(2,f'Cannot verify offline candidate: {type(exc).__name__}\n')
    print(json.dumps(summary(report,reference) if args.summary_only else report,indent=2))
    return 0 if report['status'] in ('EXACT_MATCH','DELIVERED_MATCH') else 2


if __name__=='__main__':
    raise SystemExit(main())
