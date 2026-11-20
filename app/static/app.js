'use strict';
const $ = (s)=>document.querySelector(s);
const floorMeta={
  1:{name:'Strategy Floor',description:'Kepemimpinan, analisis kebutuhan, arsitektur dan delivery.',divisions:['Management','Architecture','Operations']},
  2:{name:'Production Floor',description:'Engineering, UI/UX, AI, data dan dokumentasi.',divisions:['Engineering','Creative Studio','AI & Data','Documentation']},
  3:{name:'Reliability Floor',description:'Security, pengujian statis, infrastruktur dan reliability.',divisions:['Quality Lab','Infrastructure','Security']}
};
const icons={'Management':'♔','Architecture':'⌘','Operations':'◧','Engineering':'</>','Creative Studio':'✧','AI & Data':'◎','Documentation':'▤','Quality Lab':'✓','Infrastructure':'⬡','Security':'⬢'};
let projects=[],meta=null,selectedId=null,csrf=null,refreshing=false,selectedDetail=null,officeState={},selectedFloor=1;
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(path,options={}){
  const o={credentials:'same-origin',...options};
  if(o.method && o.method.toUpperCase()!=='GET'){
    o.headers={'X-WFS-CSRF':csrf||'',...o.headers};
  }
  const r=await fetch(path,o);
  if(r.status===401 && path!=='/api/login'){showLogin();throw new Error('Sesi berakhir, silakan login lagi');}
  if(!r.ok){let m='HTTP '+r.status;try{const data=await r.json();m=typeof data.detail==='string'?data.detail:m;}catch{}throw new Error(m);}
  return r.json();
}
function showLogin(){window.wfsMfaClear?.();stopLive();csrf=null;window.wfsCurrentUser=null;delete document.body.dataset.role;$('#login-screen').hidden=false;$('#login-otp').value='';$('#login-otp-wrap').hidden=true;$('#admin-password').focus();}
function hideLogin(){$('#login-screen').hidden=true;$('#admin-password').value='';$('#login-otp').value='';$('#login-otp-wrap').hidden=true;$('#login-error').textContent='';}
function floorSelect(n){
  selectedFloor=n;
  const f=floorMeta[n];$('#floor-number').textContent='FLOOR 0'+n;$('#floor-name').textContent=f.name;$('#floor-description').textContent=f.description;
  document.querySelectorAll('[data-floor]').forEach(el=>el.classList.toggle(el.classList.contains('chip')?'active':'active-floor',Number(el.dataset.floor)===n));
  $('#division-cards').innerHTML=f.divisions.map(name=>{
    const d=meta?.divisions.find(x=>x.name===name);
    const activity=officeState[name]||{active:0,finished:0};
    return `<div class="division-card"><div class="row"><div class="iconbox">${esc(icons[name]||'✧')}</div><strong>${esc(name)}</strong></div><p>${esc(d?.description||'Specialist division')}</p><div class="division-activity"><span class="${activity.active?'division-active':''}">${Number(activity.active)} active</span><span>${Number(activity.finished)} finished</span></div></div>`;
  }).join('');
}
function renderProjects(){
  $('#stat-active').textContent=projects.filter(p=>!p.archived_at && ['queued','paused','running','cancel_requested'].includes(p.status)).length;
  $('#stat-done').textContent=projects.filter(p=>!p.archived_at && ['completed','review_required'].includes(p.status)).length;
  $('#project-count').textContent=projects.length+' total';
  const keyword=$('#project-search').value.toLowerCase().trim();
  const statusFilter=$('#project-status-filter').value;
  const shown=projects.filter(p=>(statusFilter==='all'||p.status===statusFilter) && (!keyword || [p.title,p.status,p.stack,p.id].some(v=>String(v||'').toLowerCase().includes(keyword))));
  const empty='<div class="empty-state">Belum ada proyek. Buat misi pada Mission Intake.</div>';
  $('#project-list').innerHTML=shown.length?shown.map(p=>`<button class="project-row" data-id="${esc(p.id)}"><div class="file-icon">◈</div><div class="project-identity"><strong>${esc(p.title)}</strong><small>${esc(p.stack)} · ${esc(p.mode.toUpperCase())}${p.parent_id?' · ↳ Revision':''}${p.archived_at?' · ARCHIVED':''} · ${esc(new Date(p.created_at).toLocaleString('id-ID'))}</small></div><span class="status-label ${esc(p.status)}">${esc(p.status.toUpperCase())}</span></button>`).join(''):empty;
  $('#side-projects').innerHTML=projects.length?projects.slice(0,8).map(p=>`<button class="side-project" data-id="${esc(p.id)}">◇ ${esc(p.title)}</button>`).join(''):'<div class="empty-sidebar">Belum ada proyek.</div>';
  // Scope project click handlers to their own lists. Never override data-id controls in other pages (Operator job detail, etc).
  document.querySelectorAll('#project-list [data-id], #side-projects [data-id]').forEach(el=>el.onclick=()=>selectProject(el.dataset.id));
}
async function selectProject(id){selectedId=id;window.wfsNavigate?.('projects');await loadDetail();document.querySelector('.lower-grid').scrollIntoView({behavior:'smooth',block:'start'});}
async function loadDetail(){
  if(!selectedId)return;
  const selected=projects.find(p=>p.id===selectedId);if(!selected)return;
  $('#selected-label').textContent=selected.title.slice(0,40);
  try{
    const [events,agents,artifacts,detail]=await Promise.all([
      api(`/api/projects/${selectedId}/events`),api(`/api/projects/${selectedId}/agents`),
      api(`/api/projects/${selectedId}/files`),api(`/api/projects/${selectedId}`)]);
    $('#timeline').innerHTML=events.length?events.map(e=>`<div class="event"><div class="event-line"><div class="event-dot"></div></div><div class="event-body"><strong>${esc(e.agent)}</strong><p>${esc(e.message)}</p><small>${esc(e.state.toUpperCase())} · ${esc(new Date(e.created_at).toLocaleTimeString('id-ID'))}</small></div></div>`).join(''):'<div class="empty-state">Belum ada aktivitas</div>';
    selectedDetail=detail;
    $('#mission-detail').hidden=false;
    $('#mission-stats').innerHTML=`<strong>PHASE: ${esc(detail.phase.toUpperCase())}</strong> · ${esc(detail.stack)} · ${esc(detail.mode.toUpperCase())} · Priority ${Number(detail.priority??1)}${detail.queue_position?' · Queue #'+Number(detail.queue_position):''} · ${esc(detail.usage.calls)} successful model calls · ${esc(detail.usage.attempts)} attempts · ${esc(detail.usage.input_tokens+detail.usage.output_tokens)} provider tokens${detail.cost_estimate?.price_coverage_complete?' · Estimated $'+Number(detail.cost_estimate.estimated_usd).toFixed(5):' · Cost partially unpriced'}${detail.parent_id?' · Parent: '+esc(detail.parent_id):''}`+(detail.error?`<p>ERROR: ${esc(detail.error)}</p>`:'');
    const qa=detail.qa_reports||[];
    $('#qa-summary').innerHTML=qa.length?`<strong>OPERATOR SANDBOX QA</strong><p>${esc(qa[0].status)} · ${esc(qa[0].created_at||'')} · ${qa.length} recorded runs</p><p>${(qa[0].checks||[]).map(x=>esc(x.name)+': '+esc(x.status)).join(' · ')}</p>`:'<strong>RUNTIME QA</strong><p>Belum ada QA Docker dari operator. Static review ≠ runtime testing.</p>';
    $('#agent-roster').innerHTML=agents.length?agents.map(a=>`<span class="agent-chip" title="${esc(a.task)}">${esc(a.agent)} · ${esc(a.status)}</span>`).join(''):'<span>Belum ada subagent aktif</span>';
    $('#artifact-list').innerHTML=artifacts.length?artifacts.map(f=>`<button class="artifact-item" data-file="${esc(f.name)}"><span>▤ ${esc(f.name)}</span><small>${esc(f.bytes)} bytes</small></button>`).join(''):'<span>Artefak belum tersedia</span>';
    document.querySelectorAll('[data-file]').forEach(el=>el.onclick=()=>readFile(el.dataset.file));
    const hasFiles=artifacts.length>0;
    $('#actions').hidden=!hasFiles;
    $('#preview-btn').hidden=!(hasFiles && detail.preview_ready);
    if(hasFiles)$('#download-link').href=`/api/projects/${selectedId}/download`;
    $('#mission-controls').hidden=false;
    $('#trace-download-link').href=`/api/projects/${selectedId}/trace/download`;
    const waiting=['queued','paused'].includes(detail.status);
    $('#hold-btn').hidden=detail.status!=='queued';
    $('#resume-btn').hidden=detail.status!=='paused';
    $('#priority-control').hidden=!waiting;
    $('#priority-save-btn').hidden=!waiting;
    $('#mission-priority').value=String(detail.priority??1);
    $('#cancel-btn').hidden=!['queued','paused','running','awaiting_approval'].includes(detail.status);
    $('#retry-btn').hidden=!['failed','interrupted','cancelled'].includes(detail.status);
    $('#resume-tasks-btn').hidden=!detail.resumable_tasks;
    $('#approve-btn').hidden=detail.status!=='review_required';
    $('#revision-btn').hidden=detail.status!=='completed' || !meta.capabilities.real_ai;
    $('#archive-btn').hidden=['queued','paused','running','awaiting_approval','cancel_requested'].includes(detail.status);
    $('#observe-btn').hidden=false;$('#metadata-btn').hidden=false;
    $('#archive-btn').textContent=detail.archived_at?'Restore from archive':'Archive mission';
    $('#delete-btn').hidden=['queued','paused','running','awaiting_approval','cancel_requested'].includes(detail.status) || (detail.revisions||[]).length>0;
  }catch(e){$('#timeline').textContent=e.message;}
}
async function readFile(path){
  try{
    const file=await api(`/api/projects/${selectedId}/files/${path.split('/').map(encodeURIComponent).join('/')}`);
    $('#file-title').textContent=file.name;$('#file-content').textContent=file.content;
    $('#file-dialog').showModal();
  }catch(e){alert(e.message);}
}
async function refresh(){if(refreshing||!csrf)return;refreshing=true;try{
    const [list,diagnostics,office]=await Promise.all([api('/api/projects?include_archived='+($('#archived-toggle').checked?'true':'false')),api('/api/diagnostics'),api('/api/office')]);
    projects=list;officeState=office;floorSelect(selectedFloor);
    const ready=diagnostics.workers_online>0;
    $('#system-health').textContent=ready?`Worker online (${diagnostics.workers_online})`:'Worker offline · check Docker logs';
    $('.status-point').style.background=ready?'#5abb98':'#e3a758';
    renderProjects();if(selectedId)await loadDetail();window.wfsStudioRefresh?.();}
catch(e){console.warn('Refresh:',e.message);}finally{refreshing=false;}}
async function unlocked(){
  hideLogin();
  const session=await api('/api/session');
  const user=session.user||{username:'admin',role:'owner'};
  window.wfsCurrentUser=user;
  document.body.dataset.role=user.role;
  $('#nav-team').hidden=false;
  $('.sidebar-person strong').textContent=user.username;
  $('.sidebar-person small').textContent=user.role.toUpperCase()+' · Local workspace';
  meta=await api('/api/meta');
  const connected=meta.capabilities.real_ai;
  $('#mode-pill').textContent=connected?'● API KEY CONFIGURED':'◌ DEMO AVAILABLE';
  $('#model-description').textContent=connected?'API key diatur (belum diverifikasi); biaya model terpisah.':'Belum ada OPENAI_API_KEY — hanya template demo yang tersedia.';
  $('#project-mode').value=connected?'ai':'demo';
  floorSelect(1);
  if(session.mfa_setup_required){
    // Server permits only self-enrollment; take the user directly to that panel.
    window.wfsNavigate?.('team');
    const notice=document.querySelector('#mfa-notice');
    if(notice)notice.textContent='Your organization requires Authenticator MFA. Enroll now to unlock missions.';
  }else{await refresh();startLive();}
}
let liveSource=null,liveConnected=false,liveRefreshTimer=null,liveGeneration=0;
function liveStatus(value){const label=$('#live-event-status');if(label)label.textContent=value;}
function stopLive(){
  ++liveGeneration;
  if(liveSource){liveSource.close();liveSource=null;}
  clearTimeout(liveRefreshTimer);liveConnected=false;
  liveStatus('EVENTS: OFFLINE');
}
async function startLive(){
  stopLive();if(!csrf||!window.EventSource)return;
  const generation=liveGeneration;
  try{
    const cursor=await api('/api/live/cursor');
    if(generation!==liveGeneration||!csrf)return;
    const source=new EventSource(`/api/live/events?after_id=${Number(cursor.cursor)||0}`);
    liveSource=source;
    source.onopen=()=>{if(generation!==liveGeneration)return;liveConnected=true;liveStatus('EVENTS: LIVE');};
    source.onerror=()=>{if(generation!==liveGeneration)return;liveConnected=false;liveStatus('EVENTS: RECONNECTING');};
    source.addEventListener('wfs-event',()=>{
      if(generation!==liveGeneration||!csrf)return;
      clearTimeout(liveRefreshTimer);
      liveRefreshTimer=setTimeout(()=>{refresh();window.wfsCollabRefresh?.();window.wfsOperatorRefresh?.();},450);
    });
  }catch(e){liveStatus('EVENTS: POLLING');}
}
async function boot(){
  document.querySelectorAll('[data-floor]').forEach(el=>el.onclick=()=>{const n=Number(el.dataset.floor);floorSelect(n);if(el.classList.contains('floor-link')){window.wfsVisualFloor?.(n);window.wfsNavigate?.('office');}});
  try{const s=await api('/api/session');if(s.authenticated){csrf=s.csrf;await unlocked();}else{showLogin();}}catch(e){showLogin();}
  let lastRefreshAt=Date.now();
  setInterval(()=>{const desired=Number(window.wfsAutoRefreshMs||3000);if(Date.now()-lastRefreshAt>= (liveConnected?Math.max(desired,12000):desired)){lastRefreshAt=Date.now();refresh();}},1000);
}
$('#project-search').addEventListener('input',renderProjects);
$('#project-status-filter').addEventListener('change',renderProjects);
$('#archived-toggle').addEventListener('change',refresh);
$('#login-form').addEventListener('submit',async(e)=>{
  e.preventDefault();const btn=$('#login-form button');btn.disabled=true;
  try{const data=await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#admin-password').value,username:$('#login-username').value,otp:$('#login-otp').value||null})});csrf=data.csrf;await unlocked();}
  catch(err){$('#login-error').textContent=err.message;if(err.message.includes('autentikator')||err.message.includes('recovery code')){$('#login-otp-wrap').hidden=false;$('#login-otp').focus();}}
  finally{btn.disabled=false;}
});
$('#logout-btn').onclick=async()=>{stopLive();try{await api('/api/logout',{method:'POST'});}catch{}showLogin();};
$('#mission-form').addEventListener('submit',async(e)=>{
  e.preventDefault();const btn=$('#create-btn');btn.disabled=true;btn.textContent='Submitting mission…';
  try{
    const payload={title:$('#project-title').value,prompt:$('#project-prompt').value,
      stack:$('#project-stack').value,mode:$('#project-mode').value,task_review_mode:$('#task-review-mode').value,visibility:$('#project-visibility').value};
    const r=await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json',
      'Idempotency-Key':(globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`)},body:JSON.stringify(payload)});
    await refresh();await selectProject(r.id);
  }catch(err){alert('Gagal membuat misi: '+err.message);}
  finally{btn.disabled=false;btn.innerHTML='Launch Mission <span>↗</span>';}
});
async function queueAction(operation){
  if(!selectedId)return;
  try{await api(`/api/projects/${selectedId}/${operation}`,{method:'POST'});await refresh();}
  catch(e){alert(e.message);}
}
$('#hold-btn').onclick=()=>queueAction('pause');
$('#resume-btn').onclick=()=>queueAction('resume');
$('#priority-save-btn').onclick=async()=>{
  if(!selectedId)return;
  try{await api(`/api/projects/${selectedId}/priority`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({priority:Number($('#mission-priority').value)})});await refresh();}
  catch(e){alert(e.message);}
};
$('#cancel-btn').onclick=async()=>{if(selectedId && confirm('Batalkan misi ini?')){try{await api(`/api/projects/${selectedId}/cancel`,{method:'POST'});await refresh();}catch(e){alert(e.message);}}};
$('#retry-btn').onclick=async()=>{if(selectedId){try{await api(`/api/projects/${selectedId}/retry`,{method:'POST'});await refresh();}catch(e){alert(e.message);}}};
$('#resume-tasks-btn').onclick=async()=>{if(!selectedId)return;if(!confirm('Resume from verified specialist task checkpoints? In-flight AI calls may have to be retried.'))return;try{const r=await api(`/api/projects/${selectedId}/resume-tasks`,{method:'POST'});alert(`Requeued with ${r.preserved_results} saved task output(s).`);await refresh();}catch(e){alert(e.message);}};
$('#approve-btn').onclick=async()=>{if(selectedId && confirm('Temuan QA high/critical masih ada. Anda sudah meninjau source dan menerima risikonya?')){try{await api(`/api/projects/${selectedId}/approve`,{method:'POST'});await refresh();}catch(e){alert(e.message);}}};
$('#revision-btn').onclick=()=>{if(!selectedId)return;$('#revision-prompt').value='';$('#revision-dialog').showModal();$('#revision-prompt').focus();};
$('#revision-close').onclick=()=>$('#revision-dialog').close();
$('#revision-form').addEventListener('submit',async e=>{
  e.preventDefault(); if(!selectedId)return;
  const button=$('#revision-form button[type=submit]');button.disabled=true;
  try{const r=await api(`/api/projects/${selectedId}/revisions`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':(crypto.randomUUID?.()||`${Date.now()}-revision`)},body:JSON.stringify({prompt:$('#revision-prompt').value})});$('#revision-dialog').close();await refresh();await selectProject(r.id);}
  catch(err){alert('Revisi gagal: '+err.message);}finally{button.disabled=false;}
});
$('#collaboration-btn').onclick=()=>{if(selectedId)window.wfsCollabFocus?.(selectedId);};
$('#observe-btn').onclick=()=>{if(selectedId){$('#office-project-filter').value=selectedId;window.wfsOfficeFocus?.(selectedId);window.wfsNavigate?.('office');}};
$('#metadata-btn').onclick=()=>{if(!selectedDetail)return;$('#metadata-title').value=selectedDetail.title;$('#metadata-notes').value=selectedDetail.notes||'';$('#metadata-dialog').showModal();};
$('#metadata-close').onclick=()=>$('#metadata-dialog').close();
$('#metadata-form').addEventListener('submit',async e=>{e.preventDefault();if(!selectedId)return;const b=$('#metadata-form button[type=submit]');b.disabled=true;try{await api(`/api/projects/${selectedId}/metadata`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('#metadata-title').value,notes:$('#metadata-notes').value})});$('#metadata-dialog').close();await refresh();}catch(err){alert('Gagal menyimpan metadata: '+err.message);}finally{b.disabled=false;}});
$('#archive-btn').onclick=async()=>{if(!selectedId||!selectedDetail)return;const archive=!selectedDetail.archived_at;if(!confirm(archive?'Arsipkan proyek ini?':'Kembalikan proyek dari arsip?'))return;try{await api(`/api/projects/${selectedId}/archive`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({archive})});if(archive && !$('#archived-toggle').checked){selectedId=null;$('#mission-detail').hidden=true;$('#actions').hidden=true;$('#mission-controls').hidden=true;}await refresh();}catch(e){alert(e.message);}};
$('#delete-btn').onclick=async()=>{if(!selectedId)return;const id=selectedId;if(!confirm('Hapus permanen source, file, dan seluruh data proyek ini? Tidak bisa dibatalkan.'))return;const typed=prompt('Ketik project ID berikut untuk mengonfirmasi penghapusan permanen: '+id);if(typed!==id)return;try{await api(`/api/projects/${id}/delete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_id:id})});selectedId=null;selectedDetail=null;$('#mission-detail').hidden=true;$('#actions').hidden=true;$('#mission-controls').hidden=true;$('#timeline').textContent='Proyek dihapus';await refresh();}catch(e){alert(e.message);}};
$('#preview-btn').onclick=()=>{if(!selectedId)return;const p=projects.find(x=>x.id===selectedId);$('#preview-title').textContent=p?.title||'Preview';$('#preview-frame').src=`/preview/${selectedId}/index.html`;$('#preview-dialog').showModal();};
$('#close-preview').onclick=()=>$('#preview-dialog').close();
$('#preview-dialog').addEventListener('close',()=>$('#preview-frame').src='about:blank');
$('#close-file').onclick=()=>$('#file-dialog').close();
boot();
