/* WFS Visual AI Office. Client-side presentation of authenticated server telemetry. */
'use strict';
(() => {
  const pages = ['overview','projects','queue','office','collaboration','operator','finops','agents','quality','deliverables','activity','system','team'];
  const pageNames = {overview:'Mission Control',projects:'Projects & Missions',queue:'Queue Manager',office:'Virtual AI Office',collaboration:'Collaboration Board',operator:'Operator Command Hub',finops:'AI Cost Center',
    agents:'Agent Directory',quality:'QA & Audit Center',deliverables:'Deliverables',
    activity:'Activity Feed',system:'System & Settings',team:'Team & Access'};
  const divIcons = {'Management':'♛','Architecture':'⌘','Operations':'◈','Engineering':'⌨',
    'Creative Studio':'✧','AI & Data':'◉','Documentation':'▤','Quality Lab':'✓',
    'Infrastructure':'⬡','Security':'⛨'};
  const divColors = {'Management':'#d9b47d','Architecture':'#c7b0e9','Operations':'#94a9e6',
    'Engineering':'#72bdcf','Creative Studio':'#e6a5c5','AI & Data':'#ba9cf0',
    'Documentation':'#c2c7d4','Quality Lab':'#7ed3ac','Infrastructure':'#b1c57c','Security':'#edaa90'};
  const $s = selector => document.querySelector(selector);
  const $all = selector => [...document.querySelectorAll(selector)];
  const safe = v => esc(v);
  const divisionClass = name => 'div-'+String(name||'').toLowerCase().replace(/[^a-z0-9]+/g,'-');
  const brief = (s,n=115) => String(s ?? '').length>n ? String(s).slice(0,n-1)+'…' : String(s??'');
  const dateText = value => {try {return new Date(value).toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short'});}catch{return value||'-';}};
  const statusText = {working:'Working',done:'Finished',failed:'Failed',interrupted:'Interrupted',
    completed:'Delivered',review_required:'Needs review',queued:'Queued',paused:'On hold',awaiting_approval:'Waiting for approval',running:'Running',cancelled:'Cancelled'};
  const state = {page:'overview',floor:1,officeProject:'',zoom:100,motion:true,demoTour:false,live:null,
    agents:[],activity:[],artifacts:[],queue:{queued:[],paused:[]},stats:null,diagnostics:null,capabilities:null,auditMode:false,auditCursor:0,auditHasMore:false,
    lastFetch:{},loading:false,selectedAgent:null};
  const defaultPrefs={motion:true,zoom:100,floor:1,refresh:3000};
  function readPrefs(){try{
      const v=JSON.parse(localStorage.getItem('wfs-v13-visual-prefs')||'{}');
      return {motion:typeof v.motion==='boolean'?v.motion:true,
        zoom:[70,80,90,100,110,120,130,140].includes(v.zoom)?v.zoom:100,
        floor:[1,2,3].includes(v.floor)?v.floor:1,
        refresh:[3000,6000,12000].includes(v.refresh)?v.refresh:3000};
    }catch{return {...defaultPrefs};}}
  function applyPrefs(v){
    state.motion=v.motion;state.zoom=v.zoom;state.floor=v.floor;
    window.wfsAutoRefreshMs=v.refresh;
    $s('#pref-motion').value=v.motion?'on':'off';
    $s('#pref-zoom').value=String(v.zoom);
    $s('#pref-floor').value=String(v.floor);
    $s('#pref-refresh').value=String(v.refresh);
  }
  applyPrefs(readPrefs());
  window.wfsOfficeFocus = id => {state.officeProject=id;$s('#office-project-filter').value=id;};
  window.wfsVisualFloor = n => floor(n);
  window.wfsOfficeSelectAgent = id => showAgent(id);
  const demoNames={
    'Management':['Product Manager','Menyiapkan product roadmap'],
    'Architecture':['Software Architect','Merancang komponen sistem'],
    'Operations':['Delivery Manager','Menyusun release checklist'],
    'Engineering':['Frontend Engineer','Membangun komponen antarmuka'],
    'Creative Studio':['UI/UX Designer','Menyempurnakan design system'],
    'AI & Data':['AI Engineer','Merancang AI workflow'],
    'Documentation':['Technical Writer','Menyusun dokumentasi produk'],
    'Quality Lab':['QA Engineer','Menguji acceptance criteria'],
    'Infrastructure':['DevOps Engineer','Mengevaluasi deployment pipeline'],
    'Security':['Security Engineer','Melakukan threat modeling']};
  function mockOffice(){
    const divisions=floorMeta[state.floor].divisions;
    const agents=divisions.map((name,index)=>({id:90000+state.floor*100+index,
      project_id:'demo-only',project_title:'DEMO TOUR · contoh visual',agent:demoNames[name][0],
      division:name,task:demoNames[name][1],status:'working',state:'working',
      live:true,demo:true,created_at:new Date().toISOString(),finished_at:null}));
    return {floor:state.floor,agents,workers_online:0,
      project:{title:'DEMO TOUR — bukan proyek nyata',status:'sample-only',phase:'visual demonstration'},events:[],
      divisions:Object.fromEntries(divisions.map(x=>[x,{working:1,done:0,failed:0}]))};
  }
  function currentOffice(){return state.demoTour?mockOffice():state.live;}
  const fresh = (key,ms) => (Date.now()-(state.lastFetch[key]||0))<ms;
  let toastTimeout;
  function toast(message){let el=$s('#toast');el.textContent=message;el.hidden=false;
    clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>el.hidden=true,3500);}
  function updateNav(){
    $all('.nav-item[data-page]').forEach(x=>x.classList.toggle('active',x.dataset.page===state.page));
    $all('.page-view').forEach(x=>x.hidden=x.dataset.pageView!==state.page);
    $s('#breadcrumb-title').textContent=pageNames[state.page];
    $s('.sidebar').classList.remove('menu-open');
    $s('#mobile-nav-btn').setAttribute('aria-expanded','false');
    if(state.page==='office')$all('[data-visual-floor]').forEach(x=>x.classList.toggle('selected',Number(x.dataset.visualFloor)===state.floor));
  }
  function navigate(page,{hash=true}={}){
    if(!pages.includes(page))return;
    state.page=page;
    if(page==='office')floorSelect(state.floor);
    if(page==='finops')window.wfsFinopsRefresh?.();
    updateNav();
    window.WFSOffice3D?.setVisible(page==='office' && document.getElementById('office-3d-stage')?.dataset.mode!=='2d');
    if(hash && location.hash!=='#'+page)history.replaceState(null,'','#'+page);
    window.scrollTo({top:0,behavior:'instant'});
    loadPage(true).catch(err=>console.warn('Page load:',err.message));
  }
  window.wfsNavigate = navigate;
  function floor(n){
    if(![1,2,3].includes(n))return;
    state.floor=n;
    floorSelect(n);
    $all('[data-visual-floor]').forEach(x=>x.classList.toggle('selected',Number(x.dataset.visualFloor)===n));
    loadPage(true).catch(err=>toast(err.message));
  }
  function syncProjectOptions(){
    const active=projects.filter(p=>!p.archived_at);
    const options='<option value="">Semua proyek</option>'+active.slice(0,150).map(p=>
      `<option value="${safe(p.id)}">${safe(brief(p.title,55))} · ${safe(p.status)}</option>`).join('');
    for(const id of ['office-project-filter','artifact-project-filter']){
      const sel=$s('#'+id), previous=sel.value;
      if(sel.dataset.lastOptions!==options){sel.innerHTML=options;sel.dataset.lastOptions=options;sel.value=previous;}
    }
    if(state.officeProject && !active.some(p=>p.id===state.officeProject)){state.officeProject='';$s('#office-project-filter').value='';}
  }
  function dashboardSnapshot(){
    syncProjectOptions();
    $s('#queue-nav-count').textContent=String(projects.filter(p=>p.status==='queued').length);
    if(state.stats){
      const sum=state.stats.usage||{};
      const total=(sum.input_tokens||0)+(sum.output_tokens||0);
      $s('#system-refresh-btn').title=`Provider tokens recorded: ${total}`;
    }
  }
  function room(division,index){
    const agents=(currentOffice()?.agents||[]).filter(a=>a.division===division);
    const ongoing=agents.filter(a=>a.live);
    const chosen=ongoing[0]||agents[0];
    const active=ongoing.length>0;
    const icon=divIcons[division]||'✦';
    const accent=divColors[division]||'#b9c0cf';
    const stateName=active?'working':chosen?.state==='done'?'done':chosen?'interrupted':'idle';
    const avatar=chosen?`<button type="button" class="office-character ${active?'avatar-working':'avatar-resting'}" data-agent-run="${Number(chosen.id)}" title="${safe(chosen.agent)}: ${safe(brief(chosen.task,110))}" aria-label="Lihat ${safe(chosen.agent)}">
       <span class="character-shadow"></span><span class="character-head"><i class="character-hair"></i><i class="character-eye left"></i><i class="character-eye right"></i></span><span class="character-body"><span class="character-arm left"></span><span class="character-arm right"></span></span><span class="character-feet"></span>
       <span class="character-caption">${safe(brief(chosen.agent,23))}</span></button>`:'<div class="empty-chair" aria-hidden="true"></div>';
    return `<div class="world-room ${active?'room-active':''} room-${index+1} ${divisionClass(division)}">
      <div class="room-top"><span class="room-number">0${index+1} / ${safe(division.toUpperCase())}</span><span class="room-state ${stateName}">${active?'● LIVE':chosen?'● '+safe(statusText[chosen.state]||chosen.state):'○ IDLE'}</span></div>
      <div class="room-content"><div class="room-icon" aria-hidden="true">${safe(icon)}</div><div class="desk-scene"><div class="monitor"><div class="monitor-screen ${active?'screen-active':''}"><i></i><i></i><i></i></div><div class="monitor-neck"></div></div><div class="desk-surface"></div><div class="desk-legs"></div>${avatar}</div></div>
      <div class="room-bottom"><strong>${safe(division)}</strong><span>${active?safe(brief(chosen.task,51)):chosen?safe(brief(chosen.agent,36)):'Waiting for assignment'}</span></div>
      ${ongoing.length>1?`<span class="team-count">+${ongoing.length-1} active</span>`:''}
    </div>`;
  }
  function renderOffice(){
    const f=floorMeta[state.floor];if(!f)return;
    const live=currentOffice()||{agents:[],events:[],workers_online:0,project:null};
    const working=live.agents.filter(a=>a.live);
    const texts={1:'Executive & planning wing',2:'Product engineering & creative wing',3:'Quality, security & release wing'};
    $s('#visual-floor-code').textContent=`FLOOR 0${state.floor} / ${f.name.toUpperCase()}`;
    $s('#visual-floor-title').textContent=texts[state.floor];
    $s('#visual-occupancy').textContent=state.demoTour?`${working.length} sample avatars`: `${working.length} agent working`;
    $s('#vis-active').textContent=working.length;
    $s('#vis-total').textContent=live.agents.length;
    $s('#vis-workers').textContent=live.workers_online;
    $s('#vis-agent-count').textContent=working.length;
    $s('#office-current-mission').textContent=live.project?.title||'No active mission';
    $s('#office-current-phase').textContent=live.project?`${live.project.status.toUpperCase()} · Phase: ${live.project.phase}`:'Buat misi baru untuk menugaskan para agent.';
    // Checkpoints are real phase labels, NOT estimated completion percentages.
    const stages=['intake','planning','architecture','implementation','quality','delivered'];
    const phase=live.project?.phase||'';
    const currentStage=stages.indexOf(phase);
    $s('#office-phase-rail').innerHTML=stages.map((step,index)=>`<span class="phase-step ${currentStage===index?'current':currentStage>index?'passed':''}">${safe(step)}</span>`).join('')+(live.project && currentStage<0?`<span class="phase-step current">${safe(live.project.phase)}</span>`:'');
    const queue=state.queue||{queued:[],paused:[]};
    $s('#vis-queue-count').textContent=String(queue.queued.length);
    $s('#office-queue-peek').innerHTML=queue.queued.length?queue.queued.slice(0,3).map(q=>
      `<button class="queue-peek-item" data-open-project="${safe(q.id)}"><b>#${Number(q.position)} · ${safe(brief(q.title,38))}</b><small>${safe(['Low','Normal','High','Urgent'][q.priority]||'Normal')} priority</small></button>`).join(''):'<div class="empty-small">Antrean sedang kosong.</div>';

    const online=live.workers_online>0;
    $s('#office-live-badge').className=`live-status ${state.demoTour?'demo-mode':online?'online':'offline'}`;
    $s('#office-live-badge').textContent=state.demoTour?'◈ DEMO SCENE · NOT LIVE':online?`● ${live.workers_online} worker online`:'○ Worker offline';
    $s('#office-demo-btn').textContent=state.demoTour?'Exit demo tour':'Preview demo tour';
    $s('#office-demo-btn').setAttribute('aria-pressed',String(state.demoTour));
    $s('#office-truth-note').textContent=state.demoTour?'MODE DEMO: seluruh agent, tugas, dan animasi pada layar ini adalah contoh lokal, bukan aktivitas AI nyata. Tekan Exit demo tour untuk kembali ke telemetry worker.':'Agent bergerak/mengetik hanya saat ada eksekusi dan heartbeat worker aktif. Ruang kosong bukan simulasi aktivitas.';
    const roomGrid=$s('#world-room-grid');
    const markup=f.divisions.map((name,i)=>room(name,i)).join('');
    // Updating only on changes prevents characters from resetting animation every poll.
    if(roomGrid.dataset.rendered!==markup){roomGrid.innerHTML=markup;roomGrid.dataset.rendered=markup;}
    roomGrid.classList.toggle('four-rooms',f.divisions.length===4);
    $s('#office-agent-list').innerHTML=live.agents.length?live.agents.slice(0,12).map(a=>`
      <button class="inspector-agent" data-agent-run="${Number(a.id)}"><span class="agent-glyph ${divisionClass(a.division)}">${safe(divIcons[a.division]||'✦')}</span><span><strong>${safe(a.agent)}</strong><small>${safe(brief(a.task,63))}</small></span><i class="inspector-indicator ${a.live?'pulse':'muted'}" title="${safe(a.state)}"></i></button>`).join(''):'<div class="empty-small">Belum ada aktivitas agent pada lantai ini. Buat misi untuk melihat aktivitas nyata.</div>';
    const hostJobs=state.demoTour?[]:(live.operator_jobs||[]);
    $s('#office-operator-jobs').innerHTML=state.demoTour?'<div class="empty-small">DEMO SCENE · NO LIVE OPERATOR JOBS</div>':
      hostJobs.length?hostJobs.slice(0,5).map(j=>`<div class="operator-office-item"><strong>${safe(j.kind)}</strong><span class="collab-status ${safe(j.status)}">${safe(j.status)}</span></div>`).join(''):
      '<div class="empty-small">Belum ada host operator jobs pada proyek/ruang kerja ini.</div>';
    $s('#office-event-stream').innerHTML=live.events.length?live.events.slice(0,8).map(e=>`
      <button class="stream-item" data-open-project="${safe(e.project_id)}"><span class="stream-dot ${safe(e.state)}"></span><span><b>${safe(e.agent)}</b><small>${safe(brief(e.message,110))}</small><em>${safe(dateText(e.created_at))}</em></span></button>`).join(''):'<div class="empty-small">Tidak ada aktivitas yang tercatat.</div>';
    window.WFSOffice3D?.update(live,{floor:state.floor,demo:state.demoTour,motion:state.motion});
    $s('#office-world').classList.toggle('motion-paused',!state.motion);
    $s('#office-world').style.setProperty('--zoom',String(state.zoom/100));
    $s('#zoom-label').textContent=state.zoom+'%';
    $s('#office-motion-btn').textContent=state.motion?'Pause motion':'Resume motion';
    $s('#office-motion-btn').setAttribute('aria-pressed',String(!state.motion));
    $all('[data-agent-run]').forEach(x=>x.onclick=()=>showAgent(Number(x.dataset.agentRun)));
    $all('.stream-item, .queue-peek-item').forEach(x=>x.onclick=()=>openProject(x.dataset.openProject));
  }
  async function showAgent(runId){
    const snapshot=[...(currentOffice()?.agents||[]),...state.agents].find(a=>a.id===runId);
    let item=snapshot;
    if(snapshot && !snapshot.demo){try{const current=await api('/api/agents/runs/'+Number(runId));item=current && current.id===runId?current:snapshot;}catch{item=snapshot;}}
    if(!item){toast('Data agent tidak tersedia pada snapshot ini.');return;}
    $s('#agent-dialog-title').textContent=item.agent;
    $s('#agent-dialog-body').innerHTML=`<div class="agent-profile"><span class="agent-profile-icon ${divisionClass(item.division)}">${safe(divIcons[item.division]||'✦')}</span><div><strong>${safe(item.agent)}</strong><span>${safe(item.division)}</span></div><span class="state-pill ${safe(item.state)}">${safe(statusText[item.state]||item.state)}</span></div>
       <dl class="agent-details"><dt>Project</dt><dd>${safe(item.project_title)}</dd><dt>Task</dt><dd>${safe(item.task)}</dd><dt>Started</dt><dd>${safe(dateText(item.created_at))}</dd><dt>Finished</dt><dd>${item.finished_at?safe(dateText(item.finished_at)):'—'}</dd><dt>Execution</dt><dd>${item.live?'Verified running with recent worker heartbeat':'No current live execution confirmed'}</dd></dl>
       <button class="primary" id="agent-project-link">Open project ↗</button>`;
    if(item.demo){$s('#agent-project-link').textContent='Sample agent · no project';$s('#agent-project-link').disabled=true;}else{$s('#agent-project-link').onclick=()=>{$s('#agent-dialog').close();openProject(item.project_id);};}
    $s('#agent-dialog').showModal();
  }
  function renderAgents(){
    const keyword=$s('#agent-search').value.toLowerCase().trim();
    const filter=$s('#agent-filter').value;
    const agents=state.agents;
    const divisions=meta?.divisions||[];
    const shown=divisions.map((d,index)=>{
      let records=agents.filter(a=>a.division===d.name);
      if(filter!=='all')records=records.filter(a=>filter==='failed'?['failed','interrupted'].includes(a.state):a.state===filter);
      if(keyword){records=records.filter(a=>[a.agent,a.task,a.project_title,d.name].some(v=>String(v||'').toLowerCase().includes(keyword)));
        if(!d.name.toLowerCase().includes(keyword)&&!records.length)return '';
      }
      const working=records.filter(a=>a.live);
      return `<article class="directory-card"><div class="directory-card-top"><div class="directory-symbol ${divisionClass(d.name)}">${safe(divIcons[d.name]||'✦')}</div><div><small>DIVISION ${String(index+1).padStart(2,'0')}</small><h3>${safe(d.name)}</h3></div><span class="mini-status ${working.length?'online':''}">${working.length?`${working.length} live`:'Idle'}</span></div><p>${safe(d.description)}</p><div class="directory-members">${records.length?records.slice(0,4).map(a=>`<button data-directory-agent="${Number(a.id)}"><span class="member-point ${a.live?'online':''}"></span><span><strong>${safe(a.agent)}</strong><small>${safe(brief(a.project_title,28))} · ${safe(a.state)}</small></span></button>`).join(''):'<div class="empty-members">Belum ada run agent yang cocok.</div>'}</div><div class="directory-footer"><span>${records.length} recorded runs</span><button data-agent-floor="${Object.entries(floorMeta).find(([,v])=>v.divisions.includes(d.name))?.[0]||'1'}">View office →</button></div></article>`;
    }).filter(Boolean);
    $s('#agent-directory').innerHTML=shown.length?shown.join(''):'<div class="empty-state">Tidak ada agent yang sesuai filter.</div>';
    $all('[data-directory-agent]').forEach(x=>x.onclick=()=>showAgent(Number(x.dataset.directoryAgent)));
    $all('[data-agent-floor]').forEach(x=>x.onclick=()=>{floor(Number(x.dataset.agentFloor));navigate('office');});
  }
  async function queueOperation(id, operation, priority=null){
    try{
      const options={method:'POST'};
      if(operation==='priority'){
        options.headers={'Content-Type':'application/json'};
        options.body=JSON.stringify({priority:Number(priority)});
      }
      await api(`/api/projects/${id}/${operation}`,options);
      toast(operation==='pause'?'Mission ditahan.':operation==='resume'?'Mission masuk kembali ke antrean.':'Prioritas disimpan.');
      await refresh();
      await loadPage(true);
    }catch(err){toast('Queue: '+err.message);}
  }
  function renderQueue(){
    const queue=state.queue||{queued:[],paused:[]};
    const totalQueued=queue.queued.length,totalPaused=queue.paused.length;
    const running=projects.filter(p=>p.status==='running').length;
    $s('#queue-kpis').innerHTML=`<div><span>AWAITING WORKER</span><strong>${totalQueued}</strong><small>Ordered by priority and queue time</small></div>
      <div><span>ON HOLD</span><strong>${totalPaused}</strong><small>No worker can claim these missions</small></div>
      <div><span>EXECUTING</span><strong>${running}</strong><small>Running agents cannot be paused mid-call</small></div>`;
    function buildRow(q){
      return `<article class="queue-row"><span class="queue-order">${q.position?'#'+Number(q.position):'Ⅱ'}</span>
        <div class="queue-identity"><strong>${safe(q.title)}</strong><small>${safe(q.stack)} · ${safe(q.mode.toUpperCase())} · ${safe(dateText(q.queued_at||q.created_at))}</small></div>
        <label class="queue-priority-label">PRIORITY<select data-queue-priority="${safe(q.id)}" aria-label="Prioritas ${safe(q.title)}">
          ${['Low','Normal','High','Urgent'].map((label,i)=>`<option value="${i}" ${Number(q.priority)===i?'selected':''}>${label}</option>`).join('')}
        </select></label>
        <div class="queue-buttons"><button class="outline small" data-queue-save="${safe(q.id)}">Save</button>
          <button class="outline small" data-queue-${q.status==='queued'?'pause':'resume'}="${safe(q.id)}">${q.status==='queued'?'Hold':'Resume'}</button>
          <button class="outline small" data-queue-open="${safe(q.id)}">Details ↗</button></div></article>`;
    }
    $s('#queue-pending').innerHTML=queue.queued.length?queue.queued.map(buildRow).join(''):'<div class="empty-state">Tidak ada misi yang menunggu worker.</div>';
    $s('#queue-paused').innerHTML=queue.paused.length?queue.paused.map(buildRow).join(''):'<div class="empty-state">Tidak ada misi yang ditahan.</div>';
    $all('[data-queue-save]').forEach(x=>x.onclick=()=>queueOperation(x.dataset.queueSave,'priority',$s(`[data-queue-priority="${x.dataset.queueSave}"]`).value));
    $all('[data-queue-pause]').forEach(x=>x.onclick=()=>queueOperation(x.dataset.queuePause,'pause'));
    $all('[data-queue-resume]').forEach(x=>x.onclick=()=>queueOperation(x.dataset.queueResume,'resume'));
    $all('[data-queue-open]').forEach(x=>x.onclick=()=>openProject(x.dataset.queueOpen));
  }

  function renderQuality(){
    const count={review:0,delivered:0,failed:0};
    projects.forEach(p=>{if(p.status==='review_required')count.review++;else if(p.status==='completed')count.delivered++;else if(['failed','interrupted'].includes(p.status))count.failed++;});
    $s('#qa-overview').innerHTML=`<div><span>NEEDS HUMAN REVIEW</span><strong>${count.review}</strong><small>AI advisory findings pending</small></div><div><span>DELIVERED SOURCE</span><strong>${count.delivered}</strong><small>Not runtime certified</small></div><div><span>FAILED / INTERRUPTED</span><strong>${count.failed}</strong><small>Requires investigation</small></div>`;
    const list=projects.filter(p=>!p.archived_at).slice(0,100);
    $s('#qa-board').innerHTML=list.length?list.map(p=>`<article class="quality-row"><div class="quality-dot ${safe(p.status)}">${p.status==='review_required'?'!':p.status==='completed'?'✓':'·'}</div><div><strong>${safe(p.title)}</strong><small>${safe(p.stack)} · ${safe(p.phase)} · ${safe(dateText(p.updated_at))}</small></div><span class="state-pill ${safe(p.status)}">${safe(statusText[p.status]||p.status)}</span><button class="outline small" data-quality-project="${safe(p.id)}">Inspect →</button></article>`).join(''):'<div class="empty-state">Belum ada proyek yang dapat diperiksa.</div>';
    $all('[data-quality-project]').forEach(x=>x.onclick=()=>openProject(x.dataset.qualityProject));
  }
  function renderArtifacts(){
    const keyword=$s('#artifact-search').value.toLowerCase().trim();
    const filter=$s('#artifact-project-filter').value;
    const list=state.artifacts.filter(a=>(!filter||a.project_id===filter)&&(!keyword||[a.project_title,a.name].some(s=>s.toLowerCase().includes(keyword))));
    $s('#artifact-overview').textContent=`${state.artifacts.length} indexed files`;
    $s('#deliverable-list').innerHTML=list.length?list.map(a=>`<div class="deliverable-row"><span class="file-square">${safe(a.name.toLowerCase().endsWith('.md')?'M':a.name.toLowerCase().endsWith('.py')?'Py':a.name.toLowerCase().endsWith('.js')?'JS':'▤')}</span><div class="deliverable-main"><strong>${safe(a.name)}</strong><small>${safe(a.project_title)} · ${Number(a.bytes).toLocaleString('id-ID')} bytes</small><code title="SHA256">SHA-256: ${safe(a.sha256.slice(0,16))}…</code></div><div class="deliverable-buttons"><button data-open-artifact="${safe(a.project_id)}" data-file-path="${safe(a.name)}" class="outline small">View</button><a href="/api/projects/${safe(a.project_id)}/download" class="outline small">ZIP ↓</a></div></div>`).join(''):'<div class="empty-state">Belum ada berkas hasil proyek yang cocok.</div>';
    $all('[data-open-artifact]').forEach(x=>x.onclick=()=>{selectedId=x.dataset.openArtifact;readFile(x.dataset.filePath);});
  }
  function renderActivity(){
    const keyword=$s('#activity-search').value.toLowerCase().trim();
    const filter=$s('#activity-state-filter').value;
    const items=state.activity.filter(e=>(filter==='all'||e.state===filter)&&(!keyword||[e.agent,e.message,e.project_title,e.state].some(v=>String(v).toLowerCase().includes(keyword))));
    $s('#activity-feed').innerHTML=items.length?items.map(e=>`<button class="activity-row" data-event-project="${safe(e.project_id)}"><span class="activity-bullet ${safe(e.state)}"></span><div><span class="activity-heading"><strong>${safe(e.agent)}</strong><em>${safe(e.state.toUpperCase())}</em></span><p>${safe(e.message)}</p><small>${safe(e.project_title)} · ${safe(dateText(e.created_at))}</small></div><span class="activity-arrow">↗</span></button>`).join(''):'<div class="empty-state">Tidak ada aktivitas sesuai filter.</div>';
    $all('[data-event-project]').forEach(x=>x.onclick=()=>openProject(x.dataset.eventProject));
    $s('#activity-page-caption').textContent=state.auditMode?`${state.activity.length} audit events loaded · chronological`: 'Showing recent activity (last 80 records)';
    $s('#activity-next-btn').hidden=!state.auditMode||!state.auditHasMore;
    $s('#activity-history-btn').textContent=state.auditMode?'Back to latest':'Browse full history';
  }
  function renderSystem(){
    const diag=state.diagnostics||{};
    const cap=state.capabilities||{model_routing:{},limits:{},security:{}};
    const tokens=(state.stats?.usage?.input_tokens||0)+(state.stats?.usage?.output_tokens||0);
    const services=[{name:'Database',value:diag.database==='ready'?'READY':'UNAVAILABLE',ok:diag.database==='ready',desc:'SQLite persistent storage'},
      {name:'Workers',value:String(diag.workers_online||0)+' ONLINE',ok:!!diag.workers_online,desc:`${diag.queued||0} queued · ${diag.running||0} running`},
      {name:'AI Provider',value:cap.real_ai_configured?'CONFIGURED':'DEMO MODE',ok:!!cap.real_ai_configured,desc:'Configured does not mean API verified'},
      {name:'Usage',value:tokens.toLocaleString('id-ID'),ok:true,desc:'Recorded provider tokens'}];
    $s('#system-health-cards').innerHTML=services.map(v=>`<div class="system-stat"><span class="system-light ${v.ok?'ok':'warning'}"></span><span>${v.name}</span><strong>${safe(v.value)}</strong><small>${safe(v.desc)}</small></div>`).join('');
    const pairs=[['Master model',cap.model_routing?.master],['Worker model',cap.model_routing?.worker],['QA model',cap.model_routing?.qa],
       ['Maximum parallel',cap.limits?.max_parallel],['Maximum tasks',cap.limits?.max_tasks],
       ['Maximum model calls',cap.limits?.max_model_calls],['Token limit (not cost)',cap.limits?.max_total_tokens]];
    $s('#model-routing').innerHTML=pairs.map(([k,v])=>`<div><span>${safe(k)}</span><strong>${safe(v??'—')}</strong></div>`).join('');
    $s('#security-summary').innerHTML=[['CSRF protection',true],['Session login',true],['Docker socket attached to AI',false],
      ['Public SaaS ready',false],['Runtime QA needs operator',true]].map(([k,v])=>`<div><span>${safe(k)}</span><strong class="${v?'positive':'caution'}">${v?'YES':'NO'}</strong></div>`).join('');
  }
  async function loadPage(force=false){
    if(!csrf||!meta)return;
    const page=state.page;
    try{
      if(page==='queue'){
        state.queue=await api('/api/queue');renderQueue();
      }else if(page==='office'){
        if(force||!fresh('queue',3500)){
          state.queue=await api('/api/queue');state.lastFetch.queue=Date.now();
        }

        const key=`office-${state.floor}-${state.officeProject}`;
        if(force||!fresh(key,2200)){
          const query=new URLSearchParams({floor:String(state.floor)});
          if(state.officeProject)query.set('project_id',state.officeProject);
          state.live=await api('/api/office/live?'+query.toString());state.lastFetch[key]=Date.now();
        }
        renderOffice();
      }else if(page==='collaboration'){
        window.wfsCollabOnOpen?.(force);
      }else if(page==='operator'){
        window.wfsOperatorOnOpen?.(force);
      }else if(page==='agents'){
        if(force||!fresh('agents',3600)){state.agents=await api('/api/agents/directory');state.lastFetch.agents=Date.now();}
        renderAgents();
      }else if(page==='quality'){renderQuality();}
      else if(page==='deliverables'){
        if(force||!fresh('artifacts',7000)){state.artifacts=await api('/api/workspace/artifacts');state.lastFetch.artifacts=Date.now();}
        renderArtifacts();
      }else if(page==='activity'){
        if(!state.auditMode && (force||!fresh('activity',3600))){state.activity=await api('/api/workspace/activity');state.lastFetch.activity=Date.now();}
        renderActivity();
      }else if(page==='team'){window.wfsTeamOnOpen?.(force);window.wfsAccessOnOpen?.();window.wfsMfaOnOpen?.();
      }else if(page==='system'){
        if(force||!fresh('system',7000)){
          [state.diagnostics,state.stats,state.capabilities]=await Promise.all([
            api('/api/diagnostics'),api('/api/dashboard-stats'),api('/api/workspace/capabilities')]);
          state.lastFetch.system=Date.now();
        }
        renderSystem();
      }
    }catch(err){console.warn('WFS studio refresh:',err); if(force)toast('Gagal memuat halaman: '+err.message);}
  }
  function openProject(id){if(!id)return;navigate('projects');selectProject(id);}
  // Existing Mission Control refresh drives live pages while remaining non-blocking.
  window.wfsStudioRefresh=()=>{dashboardSnapshot();loadPage().catch(e=>console.warn(e));};
  $all('[data-page]').forEach(x=>x.addEventListener('click',()=>navigate(x.dataset.page)));
  $s('#go-visual-office').onclick=()=>navigate('office');
  $all('[data-visual-floor]').forEach(x=>x.onclick=()=>floor(Number(x.dataset.visualFloor)));
  $s('#office-project-filter').onchange=e=>{state.officeProject=e.target.value;loadPage(true);};
  $s('#office-refresh-btn').onclick=()=>loadPage(true);
  $s('#office-open-operator').onclick=()=>navigate('operator');
  const switchView = (use3d) => {
    const available = window.WFSOffice3D?.supported === true;
    const active = Boolean(use3d && available);
    const stage = $s('#office-3d-stage');
    stage.dataset.mode = active?'3d':'2d';
    $s('#office-world').classList.toggle('office2d-hidden',active);
    $s('#office-3d-rooms').hidden = !active;
    $s('#office-view-3d').classList.toggle('selected',active);
    $s('#office-view-2d').classList.toggle('selected',!active);
    $s('#office-view-3d').setAttribute('aria-pressed',String(active));
    $s('#office-view-2d').setAttribute('aria-pressed',String(!active));
    window.WFSOffice3D?.setVisible(active && state.page==='office');
    try{localStorage.setItem('wfs-office-renderer',active?'3d':'2d');}catch{}
  };
  $s('#office-view-3d').onclick=()=>switchView(true);
  $s('#office-view-2d').onclick=()=>switchView(false);
  let useSaved3d=true;try{useSaved3d=localStorage.getItem('wfs-office-renderer')!=='2d';}catch{}
  switchView(useSaved3d);
  $s('#office-demo-btn').onclick=()=>{state.demoTour=!state.demoTour;renderOffice();};
  $s('#office-motion-btn').onclick=()=>{state.motion=!state.motion;renderOffice();};
  $s('#zoom-in').onclick=()=>{state.zoom=Math.min(140,state.zoom+10);renderOffice();};
  $s('#zoom-out').onclick=()=>{state.zoom=Math.max(70,state.zoom-10);renderOffice();};
  for(const id of ['agent-search','artifact-search','activity-search']){
    $s('#'+id).addEventListener('input',()=>{if(id==='agent-search')renderAgents();else if(id==='artifact-search')renderArtifacts();else renderActivity();});
  }
  $s('#agent-filter').onchange=renderAgents;
  $s('#artifact-project-filter').onchange=renderArtifacts;
  $s('#activity-state-filter').onchange=renderActivity;
  $s('#queue-refresh-btn').onclick=()=>loadPage(true);
  $s('#activity-refresh').onclick=()=>{state.auditMode=false;state.auditCursor=0;state.auditHasMore=false;loadPage(true);};
  async function loadAuditPage(reset=false){
    if(reset){state.auditCursor=0;state.activity=[];}
    try{
      const page=await api('/api/workspace/events?after_id='+Number(state.auditCursor)+'&limit=50');
      state.auditMode=true;state.activity=[...state.activity,...page.events];
      state.auditCursor=page.next_cursor;state.auditHasMore=page.has_more;
      renderActivity();
    }catch(err){toast('Audit history: '+err.message);}
  }
  $s('#activity-history-btn').onclick=()=>state.auditMode?($s('#activity-refresh').click()):loadAuditPage(true);
  $s('#activity-next-btn').onclick=()=>loadAuditPage();
  $s('#system-refresh-btn').onclick=()=>loadPage(true);
  $s('#pref-save').onclick=()=>{
    const v={motion:$s('#pref-motion').value==='on',zoom:Number($s('#pref-zoom').value),
      floor:Number($s('#pref-floor').value),refresh:Number($s('#pref-refresh').value)};
    if(![70,80,90,100,110,120,130,140].includes(v.zoom)||![1,2,3].includes(v.floor)||![3000,6000,12000].includes(v.refresh)){
      toast('Preferensi tidak valid.');return;
    }
    try{localStorage.setItem('wfs-v13-visual-prefs',JSON.stringify(v));}catch{}
    applyPrefs(v);if(state.page==='office'){floorSelect(v.floor);loadPage(true);}
    toast('Preferensi visual disimpan di browser ini.');
  };
  $s('#pref-reset').onclick=()=>{
    try{localStorage.removeItem('wfs-v13-visual-prefs');}catch{}
    applyPrefs(defaultPrefs);
    toast('Preferensi visual dikembalikan ke default.');
  };
  $s('#close-agent').onclick=()=>$s('#agent-dialog').close();
  $s('#projects-new-btn').onclick=()=>{navigate('overview');$s('#project-title').focus();};
  $s('#mobile-nav-btn').onclick=()=>{
    const sidebar=$s('.sidebar');const opened=sidebar.classList.toggle('menu-open');
    $s('#mobile-nav-btn').setAttribute('aria-expanded',String(opened));
  };
  $all('.copy-command').forEach(x=>x.onclick=async()=>{try{
    await navigator.clipboard.writeText(x.dataset.command);toast('Perintah berhasil disalin.');
  }catch{window.prompt('Salin perintah:',x.dataset.command);}});
  window.addEventListener('hashchange',()=>navigate(pages.includes(location.hash.slice(1))?location.hash.slice(1):'overview',{hash:false}));
  const startup=location.hash.slice(1);
  if(pages.includes(startup))navigate(startup,{hash:false});
  else updateNav();
})();
