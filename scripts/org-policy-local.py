"""Offline-only WFS organization TOTP policy switch. Requires DB and backups."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import store, config


def main():
    parser=argparse.ArgumentParser(description='Set WFS organization authenticator enforcement offline')
    parser.add_argument('--org',required=True)
    parser.add_argument('--require-mfa',required=True,choices=['yes','no'])
    args=parser.parse_args()
    if not config.DB.is_file():parser.error('Database not found')
    required=args.require_mfa=='yes'
    print('STOP WFS services and BACK UP data/ and .env before applying policy.')
    if required:
        print('Un-enrolled members may log in with password but only access Authenticator MFA enrollment.')
        print('First test MFA recovery and emergency reset for each affected account.')
    phrase=f'POLICY {args.org} '+('REQUIRE' if required else 'OPTIONAL')
    if input(f'Type {phrase} to proceed: ').strip()!=phrase:
        raise SystemExit('Cancelled')
    try:store.set_organization_mfa_policy(args.org,required)
    except ValueError as exc:raise SystemExit(str(exc)) from None
    print('MFA policy updated for organization:',args.org)


if __name__=='__main__':main()
