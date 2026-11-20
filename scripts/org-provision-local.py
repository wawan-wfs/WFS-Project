"""Offline-only organization bootstrap, never callable by AI workers or HTTP routes.

Stop services and back up .env + data/ before running. Only local operators
with filesystem access can create another organization.
"""
from __future__ import annotations
import argparse
import getpass
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import auth, config, store


def main():
    parser=argparse.ArgumentParser(description='WFS local organization bootstrap (run with services stopped)')
    parser.add_argument('--id',required=True,help='3–40 lowercase letters, digits, hyphen; begins with letter')
    parser.add_argument('--name',required=True,help='Display name, 3–100 characters')
    parser.add_argument('--username',required=True,help='First account (globally unique login)')
    args=parser.parse_args()
    if not config.DB.is_file():
        parser.error('Existing SQLite database not found; initialize WFS before provisioning')
    print('STOP all WFS services; BACK UP the entire data/ directory and .env first.')
    if input(f'Type PROVISION {args.id} to proceed: ').strip()!=f'PROVISION {args.id}':
        raise SystemExit('Cancelled')
    password=getpass.getpass('New account password (minimum 12 chars): ')
    confirm=getpass.getpass('Repeat password: ')
    if password!=confirm or len(password)<12 or len(password)>256:
        raise SystemExit('Password mismatch or outside 12–256 character policy')
    try:
        uid=store.provision_organization(args.id,args.name,args.username,auth.hash_password(password),role='owner')
    except (ValueError, __import__('sqlite3').IntegrityError) as exc:
        raise SystemExit('Provisioning failed: '+str(exc)) from None
    print('Organization provisioned:',args.id,'First account ID:',uid,'Role: owner (organization-scoped)')
    print('Default policy: MFA optional. Run org-policy-local.py to enforce after recovery readiness.')


if __name__=='__main__':main()
