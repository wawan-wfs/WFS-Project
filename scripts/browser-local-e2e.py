"""Optional real browser -> FastAPI -> SQLite -> worker demo E2E (no AI API).

Usage in development: pip install playwright; playwright install chromium
python scripts/browser-local-e2e.py
Runs a private temporary server with a test password and removes its data afterward.
Needs a Chromium browser binary. Does not require Docker or access external APIs.
"""
from __future__ import annotations
import hashlib
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit('Playwright belum ada: pip install playwright && playwright install chromium') from exc
    with tempfile.TemporaryDirectory(prefix='wfs-live-e2e-') as root:
        data=Path(root)
        pw='wfs-dev-e2e-'+secrets.token_hex(12)
        salt=secrets.token_hex(16)
        hashed=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),260000).hex()
        env=os.environ.copy()
        env['WFS_DATA_DIR']=str(data)
        env['WFS_ADMIN_PASSWORD_HASH']='pbkdf2_sha256:260000:'+salt+':'+hashed
        env['WFS_SESSION_SECRET']=secrets.token_hex(32)
        env['WFS_ALLOWED_HOSTS']='localhost,127.0.0.1,testserver'
        env.pop('OPENAI_API_KEY',None)
        port=_port()
        url=f'http://127.0.0.1:{port}'
        with open(data/'uvicorn-test.log','wb') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1',
                                     '--port',str(port),'--log-level','error'],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(60):
                    if server.poll() is not None:raise RuntimeError('Server exited before ready; inspect uvicorn-test.log')
                    try:
                        if urllib.request.urlopen(url+'/ready',timeout=1).status==200:break
                    except Exception:time.sleep(.2)
                else:raise RuntimeError('Local server not ready')
                with sync_playwright() as playwright:
                    chromium=os.environ.get('WFS_CHROMIUM_EXECUTABLE')
                    browser=playwright.chromium.launch(headless=True,executable_path=chromium or None,
                                               args=['--no-sandbox','--disable-dev-shm-usage'])
                    page=browser.new_page(viewport={'width':1440,'height':960})
                    errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    failed=[]
                    page.on('requestfailed',lambda req:failed.append(urllib.parse.urlsplit(req.url).path))
                    page.on('response',lambda res:failed.append(str(res.status)+' '+urllib.parse.urlsplit(res.url).path) if res.status>=400 else None)
                    page.goto(url,wait_until='domcontentloaded')
                    try:page.locator('#login-screen').wait_for(state='visible',timeout=8000)
                    except Exception:
                        raise RuntimeError(f'Login UI unavailable; script errors={errors}, failed resources={failed}') from None
                    page.locator('#admin-password').fill(pw,timeout=5000)
                    page.locator('#login-form button[type=submit]').click()
                    page.locator('#login-screen').wait_for(state='hidden',timeout=10000)
                    page.locator('#project-title').fill('Browser E2E demo mission')
                    page.locator('#project-prompt').fill('Make a responsive local demo website with functional button components')
                    page.locator('#project-mode').select_option('demo')
                    page.locator('#mission-form button[type=submit]').click()
                    page.locator('#page-projects').wait_for(state='visible',timeout=10000)
                    page.locator('[data-page="queue"]').first.click()
                    page.locator('#queue-pending .queue-row').first.wait_for(timeout=10000)
                    page.locator('[data-queue-pause]').first.click()
                    page.locator('#queue-paused .queue-row').first.wait_for(timeout=10000)
                    page.locator('#queue-paused [data-queue-priority]').select_option('3')
                    page.locator('#queue-paused [data-queue-save]').first.click()
                    page.wait_for_timeout(250)
                    page.locator('[data-queue-resume]').first.click()
                    page.locator('#queue-pending .queue-row').first.wait_for(timeout=10000)
                    status=subprocess.run([sys.executable,'-m','app.worker','--once'],env=env,cwd=ROOT,
                                          capture_output=True,text=True,timeout=25)
                    if status.returncode:raise RuntimeError('Worker one-shot failed: '+status.stderr[-300:])
                    page.locator('[data-page="projects"]').first.click()
                    page.locator('.project-row').first.click()
                    page.wait_for_timeout(600)
                    detail=page.locator('#mission-stats').inner_text()
                    if 'DELIVERED' not in detail.upper():
                        # Project status is shown as a label; files/preview independently verify delivery.
                        page.locator('#preview-btn').wait_for(state='visible',timeout=10000)
                    page.locator('#preview-btn').click()
                    page.locator('#preview-frame').wait_for(state='visible')
                    page.locator('#close-preview').click()
                    project_id=page.locator('.project-row').first.get_attribute('data-id')
                    trace=page.context.request.get(url+f'/api/projects/{project_id}/trace')
                    assert trace.ok,trace.status
                    body=trace.json()
                    assert body['project']['status']=='completed',body
                    assert any(e['agent']=='Delivery Manager' for e in body['events'])
                    assert len(body['artifacts'])>=3
                    page.locator('[data-page="collaboration"]').first.click()
                    page.locator('#page-collaboration').wait_for(state='visible')
                    page.locator('#collab-phase').wait_for(state='visible')
                    page.wait_for_timeout(300)
                    assert page.locator('.collab-task').count()==0 # No AI agents in demo mode
                    page.locator('#collab-note-type').select_option('review')
                    page.locator('#collab-note-text').fill('Verified via real browser; demo output is not production software')
                    page.locator('#collab-note-submit').click()
                    page.locator('.collab-record').first.wait_for(timeout=8000)
                    assert 'Verified via real browser' in page.locator('#collab-notes').inner_text()
                    page.locator('[data-page="office"]').first.click()
                    page.locator('#page-office').wait_for(state='visible')
                    page.wait_for_timeout(300)
                    assert not errors,errors
                    print('LIVE BROWSER E2E PASSED: Login -> mission -> hold -> priority -> resume -> worker -> preview -> audit -> collaboration note -> office')
                    print('Local HTTP on temporary server; demo mode, no real AI provider or Docker runtime.')
                    browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    server.kill();server.wait(timeout=2)


if __name__=='__main__':main()
