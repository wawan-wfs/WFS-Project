"""Run multiple real worker PROCESSES against a temporary SQLite queue (demo only).

No Docker, paid model, external network, or user files are touched.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    with tempfile.TemporaryDirectory(prefix='wfs-parallel-e2e-') as directory:
        env=os.environ.copy()
        salt=secrets.token_hex(16);password='parallel-'+secrets.token_hex(12)
        phash=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000).hex()
        env.update(WFS_DATA_DIR=directory,WFS_SESSION_SECRET=secrets.token_hex(32),
                   WFS_ADMIN_PASSWORD_HASH=f'pbkdf2_sha256:260000:{salt}:{phash}',
                   WFS_MAX_ACTIVE_PROJECTS='3')
        env.pop('OPENAI_API_KEY',None)
        os.environ.update({key:env[key] for key in ('WFS_DATA_DIR','WFS_SESSION_SECRET','WFS_ADMIN_PASSWORD_HASH','WFS_MAX_ACTIVE_PROJECTS')})
        from app import store
        store.init_db()
        ids=[store.create_project(f'Parallel demo {i+1}','Create an accessible landing page with three content sections','demo','static')['id'] for i in range(9)]
        children=[]
        try:
            for _ in range(3):
                children.append(subprocess.Popen([sys.executable,'-m','app.worker'],cwd=ROOT,env=env,
                                                 stdout=subprocess.DEVNULL,stderr=subprocess.PIPE))
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                records=[store.get_project(pid) for pid in ids]
                if all(r['status']=='completed' for r in records):break
                if any(r['status'] in ('failed','cancelled','interrupted') for r in records):
                    raise AssertionError('Worker failed: '+str([(r['id'],r['status'],r['error']) for r in records if r['status']!='completed']))
                if store.concurrency_snapshot()['active_count']>3:raise AssertionError('Global active cap exceeded')
                time.sleep(.12)
            else:raise TimeoutError('Timed out waiting for all 9 demo missions')
            if not all(r['attempts']==1 for r in records):raise AssertionError('Duplicate project attempt detected')
            artifacts=sum(len(store.list_artifacts(pid)) for pid in ids)
            if artifacts<27:raise AssertionError('Expected demo files missing')
            print(f'PASS: 3 worker processes completed {len(ids)} independent projects, {artifacts} validated artifacts; attempts=1 each')
        finally:
            for child in children:
                if child.poll() is None:child.terminate()
            for child in children:
                try:child.communicate(timeout=6)
                except subprocess.TimeoutExpired:
                    child.kill();child.communicate(timeout=2)

if __name__=='__main__':main()
