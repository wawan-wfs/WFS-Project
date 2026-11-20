"""Offline break-glass reset of one account's TOTP. NEVER exposed as HTTP API.

Stop Docker services and back up data/ + .env before use.
Must be launched locally by an administrator who already controls the DB.
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config


def main():
    cli=argparse.ArgumentParser(description='WFS PROJECT offline MFA emergency reset')
    cli.add_argument('--username',required=True,help='Exact account username')
    cli.add_argument('--database',type=Path,default=config.DB)
    args=cli.parse_args()
    db=args.database.resolve()
    if not db.is_file():
        raise SystemExit('Database does not exist. Stop services and check path; no file created.')
    print('WARNING: This operation clears all MFA recovery codes and revokes ALL sessions for',args.username)
    print('Before proceeding: stop Docker services; make an offline backup of data/ AND .env.')
    typed=input('Type exactly "RESET MFA '+args.username+'" to proceed: ').strip()
    if typed!='RESET MFA '+args.username:
        raise SystemExit('Cancelled; no database changes.')
    with sqlite3.connect(f'file:{db}?mode=rw',uri=True,timeout=5) as cx:
        cx.execute('PRAGMA foreign_keys=ON')
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT id FROM users WHERE username=? COLLATE NOCASE',(args.username,)).fetchone()
        if not row:
            cx.rollback();raise SystemExit('Account not found; nothing changed')
        uid=row[0]
        cx.execute('UPDATE users SET mfa_secret=NULL,mfa_last_step=-1 WHERE id=?',(uid,))
        for table in ('mfa_pending','mfa_recovery','mfa_failures'):
            cx.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
        cx.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        cx.execute("INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES('offline-operator','mfa_offline_reset',?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",(uid,))
        cx.commit()
    print('MFA reset complete. All sessions revoked. Require immediate secure re-enrollment.')


if __name__=='__main__':main()
