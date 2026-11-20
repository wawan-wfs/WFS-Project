"""Real, authenticated Windows Chrome/Edge acceptance runner (NOT a fixture).

Requires user-supplied server, actual GPU and Playwright. Never records passwords,
MFA codes or session cookies. Does not claim VRAM / driver telemetry unavailable to
browser APIs. Default 10-minute navigation/3D stability measurement.

PowerShell:
  $env:WFS_E2E_URL='http://127.0.0.1:8080'
  $env:WFS_E2E_CHANNEL='chrome'     # also run msedge separately
  python scripts/acceptance_v25_windows.py
"""
from __future__ import annotations
import datetime
import getpass
import json
import os
import pathlib
import platform
import sys
import time

from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'acceptance-v25'
BASE=os.environ.get('WFS_E2E_URL','http://127.0.0.1:8080').rstrip('/')
CHANNEL=os.environ.get('WFS_E2E_CHANNEL','chrome')
STABILITY_SECONDS=max(10,min(3600,int(os.getenv('WFS_E2E_STABILITY_SECONDS','600'))))
ROUTES=('overview','projects','queue','office','collaboration','operator','agents',
        'quality','deliverables','activity','finops','system','team')


def main():
    if CHANNEL not in ('chrome','msedge'):
        raise SystemExit('WFS_E2E_CHANNEL must be chrome or msedge')
    if not BASE.startswith(('http://127.0.0.1:','http://localhost:','https://')):
        raise SystemExit('Use localhost or HTTPS; refusing remote plain HTTP for credentials.')
    username=os.environ.get('WFS_E2E_USERNAME','admin')
    password=os.environ.get('WFS_E2E_PASSWORD') or getpass.getpass('WFS account password (never saved): ')
    OUT.mkdir(parents=True,exist_ok=True)
    record={
      'test':'V25_REAL_AUTHENTICATED_WINDOWS_BROWSER',
      'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'target':BASE,'channel':CHANNEL,'host_os':platform.platform(),
      'configured_stability_seconds':STABILITY_SECONDS,'pages':{},'gpu':{},'samples':[],
      'errors':[],'unverified':['GPU VRAM / device driver details must be recorded manually in Windows Task Manager',
                                'Penetration test and MFA recovery processes require separate approval']}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel=CHANNEL,headless=False)
            context=browser.new_context(viewport={'width':1440,'height':900},device_scale_factor=1)
            page=context.new_page()
            page.on('pageerror',lambda e:record['errors'].append('JS: '+str(e)[:260]))
            page.goto(BASE,wait_until='domcontentloaded',timeout=35000)
            page.locator('#login-username').fill(username)
            page.locator('#admin-password').fill(password)
            page.locator('#login-form button[type="submit"]').click()
            if page.locator('#login-screen').is_visible():
                page.wait_for_timeout(500)
                if page.locator('#login-screen').is_visible() and page.locator('#login-otp-wrap').is_visible():
                    code=os.getenv('WFS_E2E_OTP') or getpass.getpass('Authenticator/recovery code (never saved): ')
                    page.locator('#login-otp').fill(code)
                    page.locator('#login-form button[type="submit"]').click()
            page.locator('#login-screen').wait_for(state='hidden',timeout=20000)
            # Never capture a screenshot of credentials or authenticator setup secrets.
            for width,height,label in ((1440,900,'desktop'),(820,900,'tablet'),(390,844,'mobile')):
                page.set_viewport_size({'width':width,'height':height})
                for route in ROUTES:
                    page.evaluate('(r)=>window.wfsNavigate(r)',route)
                    page.wait_for_timeout(150 if route!='office' else 450)
                    visible=page.locator('#page-'+route).is_visible()
                    overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 8')
                    record['pages'][f'{label}:{route}']={'visible':visible,'overflow':overflow}
                    if route=='team':
                        # Account secret/recovery content must never enter screenshots.
                        page.locator('#mfa-panel').evaluate('(el)=>el.style.visibility="hidden"')
                    page.screenshot(path=str(OUT/f'{CHANNEL}_{label}_{route}.png'),full_page=False,animations='disabled')
                    if route=='team':page.locator('#mfa-panel').evaluate('(el)=>el.style.visibility=""')
            page.set_viewport_size({'width':1440,'height':900})
            page.evaluate('window.wfsNavigate("office")')
            page.wait_for_timeout(800)
            record['gpu']['initial']=page.evaluate('''() => {
              const c=document.querySelector('#office-3d-canvas');
              const gl=c?.getContext('webgl2');
              const dbg=gl?.getExtension('WEBGL_debug_renderer_info');
              return { webgl2:!!gl,renderer:window.WFSOffice3D?.metrics()?.renderer??null,
                glVersion:gl?.getParameter(gl.VERSION)??null,
                vendor:dbg?gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL):'not exposed',
                gpuRenderer:dbg?gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL):'not exposed',
                gpuTimerSupported:window.WFSOffice3D?.metrics()?.gpuTimerSupported??false,
                userAgent:navigator.userAgent,
                heapBytes:performance.memory?.usedJSHeapSize??null };
            }''')
            # Interact with actual 3D while recording submit frequency and optional GPU time queries.
            start=time.monotonic()
            while time.monotonic()-start<STABILITY_SECONDS:
                page.locator('#office-3d-turn-right' if len(record['samples'])%2==0 else '#office-3d-turn-left').click()
                page.wait_for_timeout(900)
                if len(record['samples'])%10==0:
                    data=page.evaluate('''() => ({
                       metrics:window.WFSOffice3D?.metrics()??{},
                       heapBytes:performance.memory?.usedJSHeapSize??null,
                       timestamp:Date.now()})''')
                    data['elapsed_sec']=round(time.monotonic()-start,1)
                    record['samples'].append(data)
                else:
                    # Preserve bounded samples while still maintaining physical movement.
                    record['samples'].append({'elapsed_sec':round(time.monotonic()-start,1)})
            record['gpu']['final']=page.evaluate('''() => ({
              metrics:window.WFSOffice3D?.metrics()??{},
              heapBytes:performance.memory?.usedJSHeapSize??null})''')
            page.screenshot(path=str(OUT/f'{CHANNEL}_office_after_stability.png'),full_page=False)
            page.locator('#logout-btn').click()
            page.locator('#login-screen').wait_for(state='visible',timeout=15000)
            record['logout_verified']=True
            browser.close()
    except Exception as exc:
        record['errors'].append(type(exc).__name__+': '+str(exc)[:350])
    finally:
        output=OUT/f'ACCEPTANCE_{CHANNEL}.json'
        output.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
        print('Evidence:',output)
    if record['errors']:
        print('FAIL:',record['errors']);return 1
    if any(not x['visible'] or x['overflow'] for x in record['pages'].values()):
        print('FAIL: responsive navigation / overflow');return 2
    if not record['gpu'].get('initial',{}).get('webgl2'):
        print('NOT VERIFIED: WebGL2 on actual hardware unavailable');return 3
    print('PASS: Real authenticated navigation and 3D observation. Review raw GPU metrics, Windows driver and VRAM manually.')
    return 0


if __name__=='__main__':sys.exit(main())
