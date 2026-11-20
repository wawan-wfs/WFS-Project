"""Optional offline Chromium UI smoke. All sample telemetry is a FIXTURE, not AI work.

Requires: pip install playwright && playwright install chromium
Usage: python scripts/browser-ui-fixture-smoke.py
This deliberately does not connect to localhost, live AI, external APIs, or Docker.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import shutil
import os
ROOT=Path(__file__).resolve().parents[1]/'app'/'static'

html=(ROOT/'index.html').read_text()
html=html.replace('<script src="/static/finops.js"></script>','').replace('<script src="/static/team.js"></script>','').replace('<script src="/static/access.js"></script>','').replace('<script src="/static/operator.js"></script>','').replace('<script src="/static/app.js"></script>','').replace('<script src="/static/studio.js"></script>','').replace('<script src="/static/office3d.js"></script>','').replace('<script src="/static/office3d-assets.js"></script>','').replace('<script src="/static/ux-v23.js"></script>','').replace('<link rel="stylesheet" href="/static/ux-v23.css" />','').replace('<link rel="stylesheet" href="/static/ux-v24.css" />','').replace('<link rel="stylesheet" href="/static/ux-v25.css">','').replace('<script src="/static/mfa-ui.js"></script>','').replace('<script src="/static/office3d-software.js"></script>','').replace('<link rel="stylesheet" href="/static/ux-v22.css" />','').replace('<script src="/static/collaboration.js"></script>','').replace('<link rel="stylesheet" href="/static/style.css" />','')
meta={
 'version':(ROOT.parents[1]/'VERSION').read_text().strip(),'capabilities':{'real_ai':False},'divisions':[{'name':n,'description':desc} for n,desc in [
 ('Management','Product planning, requirements, delivery'),('Architecture','System architecture'),('Operations','Release management'),
 ('Engineering','Frontend/backend engineering'),('Creative Studio','UI/UX design'),('AI & Data','AI and databases'),('Documentation','Docs'),
 ('Quality Lab','Software QA'),('Infrastructure','Deployment'),('Security','AppSec')]]}
projects=[{'id':'a'*20,'title':'WFS Studio Demo (fixture)','mode':'demo','stack':'static','status':'running','phase':'implementation',
    'created_at':'2026-11-04T01:00:00+00:00','updated_at':'2026-11-04T02:00:00+00:00','archived_at':None,'parent_id':None}]
projects += [
 {'id':'b'*20,'title':'Queued Demo Mission (fixture)','mode':'demo','stack':'static','status':'queued','phase':'intake',
 'created_at':'2026-11-04T01:01:00+00:00','updated_at':'2026-11-04T01:01:00+00:00','archived_at':None,'parent_id':None,'priority':3},
 {'id':'c'*20,'title':'Held Demo Mission (fixture)','mode':'demo','stack':'static','status':'paused','phase':'held',
 'created_at':'2026-11-04T01:02:00+00:00','updated_at':'2026-11-04T01:02:00+00:00','archived_at':None,'parent_id':None,'priority':1}]
queue={'queued':[{'id':'b'*20,'title':'Queued Demo Mission (fixture)','stack':'static','mode':'demo','status':'queued',
 'priority':3,'position':1,'queued_at':'2026-11-04T01:01:00+00:00'}],
 'paused':[{'id':'c'*20,'title':'Held Demo Mission (fixture)','stack':'static','mode':'demo','status':'paused',
 'priority':1,'position':None,'queued_at':'2026-11-04T01:02:00+00:00'}]}
agentbase={'id':1,'project_id':'a'*20,'project_title':'WFS Studio Demo (fixture)','agent':'Product Manager','division':'Management','status':'working','state':'working','task':'Menyusun arsitektur platform dan user stories','created_at':'2026-11-04T01:03:00+00:00','finished_at':None,'live':True}
agent2={**agentbase,'id':2,'agent':'Software Architect','division':'Architecture','task':'Mendesain API dan database schema'}
agent3={**agentbase,'id':3,'agent':'Frontend Engineer','division':'Engineering','task':'Mengembangkan dashboard React'}
activity=[{'id':1,'project_id':'a'*20,'agent':'Product Manager','project_title':projects[0]['title'],'state':'working','message':'Menyusun desain dan kebutuhan teknis','created_at':'2026-11-04T01:03:00+00:00'}]
import json
import base64
payload={'meta':meta,'projects':projects,'agents':[agentbase,agent2,agent3],'activity':activity,'queue':queue,
'collaboration':{'project_id':'a'*20,'title':'WFS Studio Demo (fixture)','phase':'implementation','status':'running','attempt':1,
 'tasks':[{'task_key':'T1','role':'Frontend Engineer','division':'Engineering','description':'Build dashboard UX','status':'working','files':['index.html','app.js'],'created_at':'2026-11-04T01:00:00+00:00','started_at':'2026-11-04T01:03:00+00:00','finished_at':None}],
 'task_counts':{'planned':0,'working':1,'done':0,'failed':0,'blocked':0},
 'handoffs':[{'id':1,'attempt':1,'source':'Product Manager','destination':'Software Architect','summary':'Approved plan and file ownership','created_at':'2026-11-04T01:01:00+00:00'}],
 'notes':[{'id':1,'category':'decision','message':'QA before releasing','created_at':'2026-11-04T01:02:00+00:00'}]}}
payload['assetFiles']={f.stem:base64.b64encode(f.read_bytes()).decode('ascii') for f in (ROOT/'models').glob('*.glb')}
def shot(page, **options):
    page.evaluate("document.activeElement?.blur(); document.body.classList.add('wfs-capture'); window.scrollTo(0,0)")
    page.wait_for_timeout(65)
    try:
        return getattr(page,'screenshot')(**options)
    finally:
        page.evaluate("document.body.classList.remove('wfs-capture')")

with sync_playwright() as pw:
    executable=os.getenv('WFS_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
    browser=pw.chromium.launch(headless=True,executable_path=executable, args=['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1540,'height':960},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded')
    page.add_style_tag(content=(ROOT/'style.css').read_text())
    page.add_style_tag(content=(ROOT/'ux-v22.css').read_text())
    page.add_style_tag(content=(ROOT/'ux-v23.css').read_text())
    page.add_style_tag(content=(ROOT/'ux-v24.css').read_text())
    page.add_style_tag(content=(ROOT/'ux-v25.css').read_text())
    page.evaluate('''fixture => {
        window.__fixture=fixture;window.EventSource=undefined; // no network in fixture smoke
        window.fetch=async (path,opts={})=>{
          const f=window.__fixture, u=new URL(path,'http://localhost');const p=u.pathname;
          const ok=data=>new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
          if(p.startsWith('/static/models/') && p.endsWith('.glb')){const name=p.split('/').pop().replace('.glb','');const bin=atob(f.assetFiles[name]||'');if(!bin)return new Response('Missing asset',{status:404});const bytes=Uint8Array.from(bin,c=>c.charCodeAt(0));return new Response(bytes.buffer,{status:200,headers:{'Content-Type':'model/gltf-binary'}});}
          if(p==='/api/session')return ok({authenticated:true,csrf:'fakecsrf',user:{id:'owner',username:'admin',role:'owner'}});
          if(p==='/api/mfa/status')return ok({enabled:false});
          if(p==='/api/team/directory')return ok([{id:'owner',username:'admin',role:'owner'},{id:'fixture1',username:'frontend-dev',role:'developer'}]);
          if(p.endsWith('/access'))return ok({visibility:'private',created_by:'owner',members:[{user_id:'fixture1',username:'frontend-dev',permission:'view',granted_at:'2026-11-07T09:00:00Z'}],audit:[{actor_id:'owner',target_id:'fixture1',action:'member_view',at:'2026-11-07T09:00:00Z'}]});
          if(p==='/api/users')return ok({users:[{id:'owner',username:'admin',role:'owner',disabled:0,created_at:'2026-11-07T08:00:00Z'},{id:'fixture1',username:'frontend-dev',role:'developer',disabled:0,created_at:'2026-11-07T09:00:00Z'}],audit:[{action:'user_created',actor_id:'owner',subject_id:'fixture1',created_at:'2026-11-07T09:00:00Z'}]});
          if(p==='/api/finops/limits')return ok([{scope:'organization',scope_id:'default',limit_usd:2.5,updated_at:'2026-11-08T00:00:00Z'}]);
          if(p==='/api/finops/budgets')return ok([{project_id:'a'.repeat(20),limit_usd:1.5,alert_pct:80,estimated_usd:0.017,unpriced_calls:1,percent_used:1.13,limit_reached:false}]);
          if(p==='/api/finops/prices')return ok([{model:'fixture-model',input_usd_per_million:0.4,output_usd_per_million:1.7}]);
          if(p==='/api/concurrency')return ok({max_active_projects:3,active_count:1,queued_count:1,awaiting_approval_count:1,free_slots:2,active:[{id:'a'.repeat(20),title:'Demo Project (fixture)',phase:'implementation'}]});
          if(p==='/api/finops/report')return ok({period:'30d',estimated_usd:0.017,calls:3,input_tokens:10000,output_tokens:6000,unpriced_calls:1,price_coverage_complete:false,model_attempts:{completed:3},by_day:[{day:'2026-11-07',calls:3,input_tokens:10000,output_tokens:6000,estimated_usd:0.017,unpriced_calls:1}],by_model:[{name:'fixture-model',calls:3,input_tokens:10000,output_tokens:6000,estimated_usd:0.017,unpriced_calls:1}],by_project:[{name:'a'.repeat(20),calls:3,input_tokens:10000,output_tokens:6000,estimated_usd:0.017,unpriced_calls:1}],disclaimer:'Fixture values, not a provider invoice'});

          if(p==='/api/live/cursor')return ok({cursor:4});
          if(p==='/api/meta')return ok(f.meta);
          if(p==='/api/operator/jobs')return ok([{id:'e'.repeat(24),project_id:'a'.repeat(20),kind:'qa-static',options:{},status:'queued',created_at:'2026-11-07T08:00:00Z',result:{}}]);
          if(p==='/api/operator/jobs/'+ 'e'.repeat(24))return ok({id:'e'.repeat(24),project_id:'a'.repeat(20),kind:'qa-static',options:{},status:'queued',created_at:'2026-11-07T08:00:00Z',updated_at:'2026-11-07T08:00:00Z',result:{},steps:[{id:1,stage:'queued',summary:'Operator request waiting for approval',created_at:'2026-11-07T08:00:00Z'}],possibly_stalled:false});
          if(p==='/api/projects')return ok(f.projects);
          if(p==='/api/queue')return ok(f.queue);
          if(p==='/api/agents/runs/1')return ok(f.agents[0]);
          if(p==='/api/workspace/events')return ok({events:f.activity,next_cursor:1,has_more:false});
          if(p==='/api/diagnostics')return ok({database:'ready',workers_online:1,workers:[{worker_id:'fixture'}],running:1,queued:0,review_required:0});
          if(p==='/api/office')return ok({'Management':{active:1,finished:0},'Architecture':{active:1,finished:0}});
          if(p==='/api/dashboard-stats')return ok({usage:{input_tokens:100,output_tokens:200},statuses:{running:1},archived:0});
          if(p==='/api/agents/directory')return ok(f.agents);
          if(p==='/api/workspace/activity')return ok(f.activity);
          if(p==='/api/workspace/artifacts')return ok([]);
          if(p==='/api/workspace/capabilities')return ok({real_ai_configured:false,model_routing:{master:'mock',worker:'mock',qa:'mock'},limits:{max_parallel:2,max_tasks:8,max_model_calls:24,max_total_tokens:300000},security:{}});
          if(p==='/api/office/live'){
            const floor=Number(u.searchParams.get('floor')||1);
            const divs=floor===1?['Management','Architecture','Operations']:floor===2?['Engineering','Creative Studio','AI & Data','Documentation']:['Quality Lab','Infrastructure','Security'];
            return ok({floor,divisions:Object.fromEntries(divs.map(x=>[x,{working:1,done:0,failed:0}])),agents:f.agents.filter(a=>divs.includes(a.division)),workers_online:1,operator_jobs:[{id:'e'.repeat(24),project_id:'a'.repeat(20),kind:'qa-static',status:'queued',updated_at:'2026-11-07T08:00:00Z'}],project:{title:f.projects[0].title,status:'running',phase:'implementation'},events:f.activity});
          }
          if(p.startsWith('/api/projects/') && p.endsWith('/collaboration'))return ok(f.collaboration);
          if(p.startsWith('/api/projects/')){if(p.endsWith('/events'))return ok(f.activity);if(p.endsWith('/agents'))return ok(f.agents);if(p.endsWith('/files'))return ok([]);return ok({...f.projects[0],usage:{calls:0,attempts:0,input_tokens:0,output_tokens:0},qa_reports:[],revisions:[],preview_ready:false});}
          return ok([]);
        }
      }''',payload)
    page.add_script_tag(content=(ROOT/'app.js').read_text())
    page.add_script_tag(content=(ROOT/'office3d-software.js').read_text())
    page.add_script_tag(content=(ROOT/'office3d-assets.js').read_text())
    page.add_script_tag(content=(ROOT/'office3d.js').read_text())
    page.add_script_tag(content=(ROOT/'studio.js').read_text())
    page.add_script_tag(content=(ROOT/'collaboration.js').read_text())
    page.add_script_tag(content=(ROOT/'operator.js').read_text())
    page.add_script_tag(content=(ROOT/'finops.js').read_text())
    page.add_script_tag(content=(ROOT/'team.js').read_text())
    page.add_script_tag(content=(ROOT/'access.js').read_text())
    page.add_script_tag(content=(ROOT/'mfa-ui.js').read_text())
    page.add_script_tag(content=(ROOT/'ux-v23.js').read_text())
    page.wait_for_timeout(500)
    page.evaluate('''() => {
      const ids=['mfa-setup-password','mfa-confirm-code','mfa-disable-password','mfa-disable-code'];
      for(const id of ids)document.getElementById(id).value='fixture-only';
      window.wfsMfaClear();
      if(ids.some(id=>document.getElementById(id).value))throw Error('MFA cleanup left input values');
    }''')
    captures=((49, 'V49_FIXTURE_SCREENS'),(48, 'V48_FIXTURE_SCREENS'),(47, 'V47_FIXTURE_SCREENS'),(46, 'V46_FIXTURE_SCREENS'),(45, 'V45_FIXTURE_SCREENS'),(44, 'V44_FIXTURE_SCREENS'),
              (43, 'V43_FIXTURE_SCREENS'),(42, 'V42_FIXTURE_SCREENS'),
              (41, 'V41_FIXTURE_SCREENS'),(33, 'V33_FIXTURE_SCREENS'),
              (32, 'V32_FIXTURE_SCREENS'),(31, 'V31_FIXTURE_SCREENS'),
              (30, 'V30_FIXTURE_SCREENS'),(29, 'V29_FIXTURE_SCREENS'),
              (28, 'V28_FIXTURE_SCREENS'),(26, 'V26_FIXTURE_SCREENS'),(25, 'V25_SCREENS'))
    capture=next(((v, folder) for v, folder in captures if os.environ.get(f'WFS_V{v}_CAPTURE')=='1'),None)
    if capture:
        version,folder=capture
        output=Path(__file__).resolve().parents[1]/'docs'/folder
        output.mkdir(parents=True,exist_ok=True)
        if version>=41:
            page.evaluate('''() => {
                const label=document.createElement('div');
                label.textContent='UI FIXTURE · NOT LIVE';
                label.setAttribute('aria-hidden','true');
                label.style.cssText='position:fixed;right:12px;bottom:12px;z-index:2147483647;background:#10192b;color:#fff;border:1px solid #8798bc;border-radius:5px;padding:4px 7px;font:600 10px system-ui;pointer-events:none';
                document.body.append(label);
            }''')
        routes=('overview','projects','queue','office','collaboration','operator','agents',
                'quality','deliverables','activity','finops','system','team')
        for label,width,height in (('DESKTOP',1440,900),('MOBILE',390,844)):
            page.set_viewport_size({'width':width,'height':height})
            for number,route in enumerate(routes,1):
                page.evaluate('(name)=>window.wfsNavigate(name)',route)
                page.wait_for_timeout(140 if route!='office' else 450)
                assert page.locator('#page-'+route).is_visible(),(label,route)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+8'),(label,route)
                if route=='team':
                    assert page.locator('#mfa-panel').count()==1
                    assert 'NOT ENABLED' in page.locator('#mfa-status').inner_text()
                dest=output/f'{label}_{number:02d}_{route}.png'
                page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
                page.screenshot(path=str(dest),full_page=False,animations='disabled',timeout=12000)
            page.evaluate('window.wfsNavigate("team")')
            page.wait_for_timeout(200)
            page.locator('#mfa-panel').screenshot(path=str(output/f'{label}_MFA_PANEL.png'),animations='disabled')
            print('UI FIXTURE',label,'13 routes + MFA, no horizontal overflow')
        page.evaluate('window.wfsNavigate("office")')
        page.wait_for_timeout(350)
        page.locator('#office-3d-turn-right').click()
        page.wait_for_timeout(300)
        metrics=page.evaluate('window.WFSOffice3D.metrics()')
        assert metrics['renderer'] in ('cpu-3d','webgl2'),metrics
        assert 'gpuTimerSupported' in metrics and 'meanGpuTimeMs' in metrics
        print('OFFICE METRICS',metrics)
        # Show the actual second-factor login form without credentials/OTP filled.
        page.set_viewport_size({'width':1440,'height':900})
        page.locator('#login-screen').evaluate('(el)=>el.hidden=false')
        page.locator('#login-otp-wrap').evaluate('(el)=>el.hidden=false')
        page.locator('#admin-password').fill('')
        page.locator('#login-otp').fill('')
        page.screenshot(path=str(output/'LOGIN_2FA_FIXTURE.png'),animations='disabled')
        # Exercise the actual login form's MFA challenge branch with a fake server response.
        page.evaluate("""() => {
          const base=window.fetch;
          window.fetch=(path,options={})=>{
            if(path==='/api/login'){
              const payload=JSON.parse(options.body||'{}');
              if(payload.otp!=='123456')return Promise.resolve(new Response(JSON.stringify({detail:'Kode autentikator atau recovery code diperlukan'}),{status:401,headers:{'Content-Type':'application/json'}}));
              return Promise.resolve(new Response(JSON.stringify({authenticated:true,csrf:'fixturecsrf',user:{id:'owner',username:'admin',role:'owner'}}),{status:200,headers:{'Content-Type':'application/json'}}));
            }
            return base(path,options);
          };
          document.querySelector('#login-otp-wrap').hidden=true;
        }""")
        page.locator('#admin-password').fill('synthetic-example-only')
        page.locator('#login-form button[type="submit"]').click()
        page.wait_for_timeout(100)
        assert page.locator('#login-otp-wrap').is_visible(),'MFA challenge did not reveal OTP input'
        page.locator('#login-otp').fill('123456')
        page.locator('#login-form button[type="submit"]').click()
        page.locator('#login-screen').wait_for(state='hidden',timeout=10000)
        print('v2.5 login 2FA challenge UI flow: PASS (fake server)')
        assert not errors,errors
        browser.close()
        raise SystemExit(0)
    if os.environ.get('WFS_RESPONSIVE_AUDIT_ONLY')=='1':
        names=('overview','projects','queue','office','collaboration','operator','agents',
               'quality','deliverables','activity','finops','system','team')
        for width in (1440,820,390):
            page.set_viewport_size({'width':width,'height':900 if width>390 else 844})
            for name in names:
                page.evaluate('(name)=>window.wfsNavigate(name)',name)
                page.wait_for_timeout(65)
                assert page.locator('#page-'+name).is_visible(),(width,name)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+8'),(width,name)
            print('FINAL DESIGN: 13 routes, no horizontal overflow at',width,flush=True)
        browser.close()
        raise SystemExit(0)
    if os.environ.get('WFS_AUDIT_MOBILE_ONLY')=='1':
        output=Path(__file__).resolve().parents[1]/'docs'/'V24_SCREENS'
        output.mkdir(parents=True,exist_ok=True)
        page.set_viewport_size({'width':390,'height':844})
        for i,name in enumerate(('overview','projects','queue','office','collaboration','operator','agents',
                    'quality','deliverables','activity','finops','system','team'),1):
            dest=output/f'MOBILE_{i:02d}_{name}.png'
            if dest.exists():continue
            page.evaluate('(name)=>window.wfsNavigate(name)',name)
            page.wait_for_timeout(100)
            assert page.locator('#page-'+name).is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+8'),name
            page.screenshot(path=str(dest),full_page=False,animations='disabled',timeout=12000)
            print('MOBILE CAPTURED',name,flush=True)
        browser.close()
        raise SystemExit(0)
    print('Login hidden:',not page.locator('#login-screen').is_visible())
    assert page.locator('#command-trigger').count()==1
    page.locator('#command-trigger').click()
    assert page.locator('#command-dialog').is_visible()
    page.locator('#command-search').fill('AI Cost')
    page.locator('#command-search').press('Enter')
    assert page.locator('#page-finops').is_visible(), 'command palette did not navigate'
    page.keyboard.press('Control+k')
    assert page.locator('#command-dialog').is_visible()
    page.locator('#command-search').fill('office')
    page.locator('#command-search').press('Enter')
    assert page.locator('#page-office').is_visible(), 'keyboard palette navigation failed'
    print('Command palette and keyboard navigation: PASS')
    page.evaluate("window.wfsNavigate('overview')");page.wait_for_timeout(100)
    print('Overview visible:',page.locator('#page-overview').is_visible())
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_MISSION_CONTROL_DESKTOP.png'),full_page=True,animations='disabled')
    page.locator('[data-page="office"]').first.click()
    page.wait_for_timeout(300)
    print('Office visible:',page.locator('#page-office').is_visible(),'rooms',page.locator('.world-room').count())
    assert page.evaluate("window.WFSOffice3D?.supported === true"), '3D renderer unavailable'
    assert page.locator('#office-3d-stage').get_attribute('data-mode') == '3d'
    assert page.locator('#office-3d-rooms button').count()==3
    page.locator('#office-building-toggle').click()
    page.wait_for_timeout(350)
    assert page.locator('#office-3d-rooms [data-building-floor]').count()==3
    assert 'BUILDING' in page.locator('#office-3d-mode').inner_text()
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_BUILDING_OVERVIEW_DESKTOP.png'),full_page=True,animations='disabled')
    page.locator('#office-3d-rooms [data-building-floor="2"]').click()
    page.wait_for_timeout(200)
    assert page.locator('[data-visual-floor="2"]').first.get_attribute('class').find('selected')!=-1
    page.locator('[data-visual-floor="1"]').click()
    page.wait_for_timeout(250)
    assert page.locator('#office-3d-rooms [data-building-floor]').count()==0
    # v2.4 native inspector: real run vs idle, no spurious live claim on vacant room.
    page.locator('#office-3d-rooms [data-name="Management"]').click()
    assert 'Product Manager' in page.locator('#office-3d-task-agent').inner_text()
    assert 'Menyusun arsitektur' in page.locator('#office-3d-task-name').inner_text()
    assert 'LIVE execution confirmed' in page.locator('#office-3d-task-status').inner_text()
    assert page.locator('#office-3d-open-agent').is_enabled()
    page.locator('#office-3d-open-agent').click()
    page.locator('#agent-dialog').wait_for(state='visible',timeout=5000)
    page.locator('#close-agent').click()
    page.locator('#office-3d-rooms [data-name="Operations"]').click()
    assert 'No agent task recorded' in page.locator('#office-3d-task-status').inner_text()
    assert page.locator('#office-3d-open-agent').is_disabled()
    print('v2.4 native live/idle task inspector: PASS')
    print('3-floor 3D Building Overview and selection: PASS')
    frame_before=page.locator('#office-3d-canvas').evaluate('(c)=>c.toDataURL()')
    page.locator('#office-3d-turn-right').click();page.wait_for_timeout(180)
    frame_after=page.locator('#office-3d-canvas').evaluate('(c)=>c.toDataURL()')
    assert frame_before != frame_after, '3D orbit interaction did not update the frame'
    page.locator('#office-3d-reset').click()
    assert page.locator('#office-3d-stage').get_attribute('data-support') in ('webgl-3d','cpu-3d')
    office3d=Path(__file__).resolve().parents[1]/'docs'/'V23_SPATIAL_OFFICE_DESKTOP.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(office3d),full_page=True,animations='disabled')
    page.locator('#office-view-2d').click()
    assert page.locator('#office-world').is_visible()
    page.locator('#office-view-3d').click()
    assert page.locator('#office-3d-stage').is_visible()
    page.locator('#office-3d-quality').select_option('eco')
    assert page.locator('#office-3d-quality').input_value()=='eco'
    page.locator('#office-3d-quality').select_option('studio')
    page.locator('#office-3d-canvas').focus()
    keyboard_before=page.locator('#office-3d-canvas').evaluate('(c)=>c.toDataURL()')
    page.keyboard.press('ArrowRight');page.wait_for_timeout(200)
    keyboard_after=page.locator('#office-3d-canvas').evaluate('(c)=>c.toDataURL()')
    assert keyboard_before!=keyboard_after, 'keyboard 3D camera failed'
    page.locator('#office-3d-reset').click()
    page.wait_for_timeout(450)
    asset_valid=page.evaluate('''() => {
       const encoded=window.__fixture.assetFiles.ergonomic_chair;
       const raw=atob(encoded);
       const arr=Uint8Array.from(raw,c=>c.charCodeAt(0));
       const mesh=window.WFSOfficeAssets.decode(arr.buffer);
       return mesh.length>100 && mesh[0].verts.length===3;
    }''')
    assert asset_valid, 'local GLB parser failed to decode original asset'
    assert page.locator('#office-3d-stage').get_attribute('data-assets') in ('local-glb','procedural')
    print('Original local GLB library, quality selector, keyboard camera: PASS')
    perf=page.evaluate('window.WFSOffice3D.metrics()')
    assert perf['drawCalls']>0 and perf['geometryTriangles']>0
    print('3D render measurement (fixture device, not Windows GPU):',perf)
    print('3D geometry, orbit, fallback switch: PASS')
    print('Working characters (fixture only):',page.locator('.avatar-working').count())
    output=Path(__file__).resolve().parents[1]/'data'/'ui_fixture_preview.png'
    output.parent.mkdir(parents=True,exist_ok=True)
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(output),full_page=True)
    print('UI fixture screenshot:',output)
    page.locator('[data-visual-floor="2"]').click()
    page.wait_for_timeout(150)
    print('Floor 2 rooms:',page.locator('.world-room').count(),'active characters:',page.locator('.avatar-working').count())
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_SPATIAL_OFFICE_FLOOR2.png'),full_page=True,animations='disabled')
    page.locator('[data-visual-floor="3"]').click();page.wait_for_timeout(160)
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_SPATIAL_OFFICE_FLOOR3.png'),full_page=True,animations='disabled')
    page.locator('[data-page="agents"]').first.click();page.wait_for_timeout(100)
    print('Directory cards:',page.locator('.directory-card').count())
    page.locator('[data-directory-agent]').first.click();page.wait_for_timeout(100)
    print('Agent modal:',page.locator('#agent-dialog').is_visible())
    page.locator('#close-agent').click()
    page.evaluate('window.wfsNavigate("office")')
    page.locator('#office-demo-btn').click()
    assert 'NOT LIVE' in page.locator('#office-live-badge').inner_text()
    page.locator('#office-demo-btn').click()
    page.locator('[data-page="queue"]').first.click();page.wait_for_timeout(220)
    assert page.locator('#page-queue').is_visible()
    assert page.locator('#queue-pending .queue-row').count()==1
    assert page.locator('#queue-paused .queue-row').count()==1
    print('Queue rows:',page.locator('.queue-row').count())
    queue_screenshot=Path(__file__).resolve().parents[1]/'data'/'queue_fixture_preview.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(queue_screenshot),full_page=True)
    print('Queue fixture screenshot:',queue_screenshot)
    page.locator('[data-page="collaboration"]').first.click();page.wait_for_timeout(250)
    assert page.locator('#page-collaboration').is_visible()
    assert page.locator('.collab-task').count()==1
    assert page.locator('.collab-record').count()==2
    collab_screenshot=Path(__file__).resolve().parents[1]/'data'/'collaboration_fixture_preview.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(collab_screenshot),full_page=True)
    print('Collaboration board fixture screenshot:',collab_screenshot)
    page.locator('[data-page="operator"]').first.click();page.wait_for_timeout(190)
    assert page.locator('#page-operator').is_visible()
    assert page.locator('.operator-job').count()==1
    assert page.locator('#op-job-form').count()==1
    print('Operator Hub loaded:',page.locator('.operator-job').count(),'queued jobs')
    page.locator('#op-search').fill('not-a-matching-project')
    assert page.locator('.operator-job').count()==0
    page.locator('#op-search').fill('qa-static')
    assert page.locator('.operator-job').count()==1
    page.locator('.op-detail').first.click()
    page.locator('#operator-detail-dialog').wait_for(state='visible',timeout=5000)
    page.wait_for_timeout(100)
    assert 'Operator request waiting for approval' in page.locator('#op-detail-body').inner_text()
    page.locator('#op-detail-close').click()
    print('Operator job detail, filters, timeline: PASS')

    op_screenshot=Path(__file__).resolve().parents[1]/'data'/'operator_fixture_preview.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(op_screenshot),full_page=True)
    print('Operator Hub fixture screenshot:',op_screenshot)
    page.locator('[data-page="finops"]').first.click();page.wait_for_timeout(300)
    assert page.locator('#page-finops').is_visible()
    assert '$0.017000' in page.locator('#finops-summary').inner_text()
    assert 'fixture-model' in page.locator('#finops-models').inner_text()
    finops_screenshot=Path(__file__).resolve().parents[1]/'docs'/'V19_FINOPS_FIXTURE_DESKTOP.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(finops_screenshot),full_page=True)
    assert page.locator('#finops-budget-form').count()==1
    assert page.locator('#finops-export').get_attribute('href').startswith('/api/finops/export.csv?period=')
    assert 'Cannot load financial estimates' not in page.locator('#finops-note').inner_text()
    print('FinOps & worker capacity fixture: PASS')
    page.locator('[data-page="team"]').first.click();page.wait_for_timeout(300)
    assert page.locator('#page-team').is_visible()
    assert 'frontend-dev' in page.locator('#team-members').inner_text()
    assert 'user_created' in page.locator('#team-audit').inner_text()
    assert 'Private client' not in page.locator('#access-project').inner_text() # fixture projects only
    assert page.locator('#access-project option').count()>1
    page.locator('#access-project').select_option('a'*20)
    page.wait_for_timeout(180)
    assert 'frontend-dev' in page.locator('#access-members').inner_text()
    team_screen=Path(__file__).resolve().parents[1]/'docs'/'V21_ACCESS_FIXTURE_DESKTOP.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(team_screen),full_page=True)
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_TEAM_ACCESS_DESKTOP.png'),full_page=True,animations='disabled')
    print('Team RBAC fixture page: PASS')
    page.locator('[data-page="activity"]').first.click();page.wait_for_timeout(120)
    page.locator('#activity-history-btn').click();page.wait_for_timeout(150)
    assert 'audit events loaded' in page.locator('#activity-page-caption').inner_text()
    page.locator('#activity-history-btn').click();page.wait_for_timeout(110)
    print('Activity audit history mode tested')
    for name in ('quality','deliverables','activity','system','projects','overview'):
        page.locator('[data-page="'+name+'"]').first.click();page.wait_for_timeout(100)
        print(name,'visible',page.locator('#page-'+name).is_visible())
    for name in ('quality','deliverables','activity','system','projects','queue','collaboration','operator','finops','team','agents'):
        page.evaluate('name => window.wfsNavigate(name)',name)
        page.wait_for_timeout(160)
        shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/f'V23_UI_{name.upper()}_DESKTOP.png'),full_page=True,animations='disabled')
    page.evaluate("window.wfsNavigate('overview')")
    page.wait_for_timeout(130)
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_MISSION_CONTROL_DESKTOP.png'),full_page=True,animations='disabled')
    print('JS errors:',errors)
    print('All browser checks used synthetic fixture data; this is NOT real API E2E.')
    assert not errors,errors
    assert page.locator('#page-overview').is_visible()
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate('window.wfsNavigate("team")');page.wait_for_timeout(180)
    assert page.locator('#page-team').is_visible()
    page.evaluate('window.wfsNavigate("overview")');page.wait_for_timeout(100)
    page.evaluate('window.scrollTo(0,0)')
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(Path(__file__).resolve().parents[1]/'docs'/'V23_MISSION_CONTROL_MOBILE.png'),full_page=True,animations='disabled')
    page.evaluate('window.wfsNavigate("office")');page.wait_for_timeout(400)
    assert page.locator('#office-3d-stage').is_visible()
    assert page.locator('#office-3d-rooms button').count() in (3,4)
    page.locator('#office-3d-zoom-in').click()
    page.evaluate('window.scrollTo(0,0)')
    spatial_mobile=Path(__file__).resolve().parents[1]/'docs'/'V23_SPATIAL_OFFICE_MOBILE.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(spatial_mobile),full_page=True,animations='disabled')
    assert page.evaluate('document.documentElement.scrollWidth')<=390
    page.evaluate('window.wfsNavigate("team")')
    team_mobile=Path(__file__).resolve().parents[1]/'docs'/'V21_ACCESS_FIXTURE_MOBILE.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(team_mobile),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth')<=390
    print('Team mobile fixture: PASS')
    page.evaluate('window.wfsNavigate("collaboration")')
    page.wait_for_timeout(220)
    assert page.locator('#page-collaboration').is_visible()
    assert page.locator('.collab-task').count()==1
    collab_mobile=Path(__file__).resolve().parents[1]/'data'/'collaboration_fixture_mobile.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(collab_mobile),full_page=True)
    print('Collaboration board mobile fixture:',collab_mobile)
    page.evaluate('window.wfsNavigate("operator")')
    page.wait_for_timeout(180)
    assert page.locator('#page-operator').is_visible()
    assert page.locator('.operator-job').count()==1
    mobile_operator=Path(__file__).resolve().parents[1]/'data'/'operator_fixture_mobile.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(mobile_operator),full_page=True)
    print('Operator Hub mobile fixture:',mobile_operator)
    page.evaluate('window.wfsNavigate("finops")')
    page.wait_for_timeout(250)
    assert page.locator('#page-finops').is_visible()
    finops_mobile=Path(__file__).resolve().parents[1]/'docs'/'V19_FINOPS_FIXTURE_MOBILE.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(finops_mobile),full_page=True)
    page.evaluate('window.wfsNavigate("queue")')
    page.wait_for_timeout(200)
    assert page.locator('#page-queue').is_visible()
    assert page.locator('#queue-pending .queue-row').count()==1
    page.locator('#mobile-nav-btn').click()
    assert 'menu-open' in page.locator('.sidebar').get_attribute('class')
    page.locator('#mobile-nav-btn').click()
    page.wait_for_timeout(360)
    dimensions=page.evaluate('({scroll:document.documentElement.scrollWidth,viewport:innerWidth})')
    print('Mobile 390px layout:',dimensions)
    assert dimensions['scroll']<=dimensions['viewport']+8,'Unexpected horizontal page overflow'
    mobile_screen=Path(__file__).resolve().parents[1]/'data'/'queue_fixture_mobile.png'
    page.evaluate("document.activeElement?.blur(); window.scrollTo(0,0)")
    shot(page,path=str(mobile_screen),full_page=True)
    print('Mobile queue fixture screenshot:',mobile_screen)
    print('Mobile screenshot: primary pages plus Team / Operator / Queue via fixture')
    if os.environ.get("WFS_FULL_UI_AUDIT", "0") == "1":
        # v2.4 comprehensive route-by-route visual audit, using synthetic fixture data only.
        names=('overview','projects','queue','office','collaboration','operator','agents',
               'quality','deliverables','activity','finops','system','team')
        audit_dir=Path(__file__).resolve().parents[1]/'docs'/'V24_SCREENS'
        audit_dir.mkdir(parents=True,exist_ok=True)
        for width,height,device in ((1440,900,'DESKTOP'),(820,900,'TABLET'),(390,844,'MOBILE')):
            page.set_viewport_size({'width':width,'height':height})
            for i,route in enumerate(names,1):
                page.evaluate('(name)=>window.wfsNavigate(name)',route)
                page.wait_for_timeout(100 if route!='office' else 290)
                assert page.locator('#page-'+route).is_visible(),(device,route)
                overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth + 8')
                assert not overflow,f'{route} overflow at {width}px'
                if device!='TABLET':
                    target=audit_dir/f'{device}_{i:02d}_{route}.png'
                    if not target.exists():shot(page,path=str(target),full_page=device=='DESKTOP',animations='disabled')
            print(f'v2.4 {device} 13-page no-overflow/navigation audit: PASS')
    assert not errors,errors
    browser.close()
