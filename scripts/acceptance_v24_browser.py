"""Opt-in acceptance of a *real* authenticated deployment. Never uses fixture data.
Install playwright and Chromium in the actual target machine; set WFS_E2E_PASSWORD.
Results go to data/acceptance/ and never belong in release source archives.
"""
from __future__ import annotations
import json, os, datetime, platform, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
TARGET=os.environ.get('WFS_E2E_URL','http://127.0.0.1:8080').rstrip('/')
USERNAME=os.environ.get('WFS_E2E_USERNAME','admin')
PASSWORD=os.environ.get('WFS_E2E_PASSWORD')
if not PASSWORD:raise SystemExit('Set WFS_E2E_PASSWORD in this terminal (do not commit credentials).')
out=ROOT/'data'/'acceptance'
out.mkdir(parents=True,exist_ok=True)
record={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'url':TARGET,'os':platform.platform(),'mode':'REAL_AUTHENTICATED_BROWSER',
        'chrome_edge_gpu_test':'measured only on this machine','pages':{},'errors':[]}
try:
 with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=False,channel=os.getenv('WFS_E2E_CHANNEL','chrome'))
    page=browser.new_page(viewport={'width':1440,'height':960})
    page.on('pageerror',lambda e:record['errors'].append(str(e)))
    page.goto(TARGET,wait_until='domcontentloaded',timeout=20000)
    page.locator('#login-username').fill(USERNAME)
    page.locator('#admin-password').fill(PASSWORD)
    page.locator('#login-form button[type="submit"]').click()
    page.locator('#login-screen').wait_for(state='hidden',timeout=20000)
    record['authenticated']=True
    for width,height in ((1440,960),(820,900),(390,844)):
        page.set_viewport_size({'width':width,'height':height})
        for route in ('overview','projects','queue','office','collaboration','operator',
                      'agents','quality','deliverables','activity','finops','system','team'):
            page.evaluate('(route)=>window.wfsNavigate(route)',route)
            page.wait_for_timeout(220)
            overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth+8')
            key=f'{route}_{width}'
            record['pages'][key]={'visible':page.locator('#page-'+route).is_visible(),'horizontal_overflow':overflow}
            page.screenshot(path=str(out/(key+'.png')),full_page=True,animations='disabled')
        if width==1440:
            page.evaluate('window.wfsNavigate("office")')
            page.wait_for_timeout(500)
            record['gpu']=page.evaluate('''() => ({
              webgl2: !!document.querySelector('#office-3d-canvas').getContext('webgl2'),
              renderer: window.WFSOffice3D?.metrics()?.renderer,
              assetCount: Number(document.querySelector('#office-3d-stage').dataset.assetCount||0),
              metrics:window.WFSOffice3D?.metrics(),
              heapBytes:performance.memory?.usedJSHeapSize??null,
              browser:navigator.userAgent
            })''')
            # Scene submit measurements are NOT a standalone FPS/gpu-memory certification.
            page.locator('#office-3d-turn-right').click()
            page.wait_for_timeout(600)
            record['gpu']['afterCameraInteraction']=page.evaluate('window.WFSOffice3D?.metrics()')
    page.locator('#logout-btn').click() if page.locator('#logout-btn').count() else None
    browser.close()
except Exception as exc:
    record['errors'].append(type(exc).__name__+': '+str(exc)[:350])
finally:
    (out/'ACCEPTANCE_RESULTS.json').write_text(json.dumps(record,indent=2,ensure_ascii=False))
    print('Recorded:',out/'ACCEPTANCE_RESULTS.json')
    if record['errors']:
        print('Acceptance incomplete:',record['errors']);sys.exit(1)
    if not record.get('gpu',{}).get('webgl2'):
        print('Real WebGL2 is unavailable on this machine');sys.exit(2)
    if any(not v['visible'] or v['horizontal_overflow'] for v in record['pages'].values()):
        print('Visual navigation/overflow acceptance failed');sys.exit(3)
    print('Windows real browser navigation pass. Review GPU data and screenshots manually; not security certification.')
