/* WFS v1.5: persisted task/handoff board; operator annotations are not AI instructions. */
'use strict';
(() => {
  const q = s => document.querySelector(s);
  const clean = value => esc(value);
  const status = {planned:'PLANNED',working:'WORKING',done:'DONE',failed:'FAILED',blocked:'BLOCKED'};
  let current='',lastFetch=0,busy=false;

  function fillProjects(){
    const box=q('#collab-project-filter');if(!box)return;
    const previous=box.value||current;
    const html='<option value="">Select a project…</option>'+projects.filter(x=>!x.archived_at).slice(0,200)
      .map(x=>`<option value="${clean(x.id)}">${clean(x.title.slice(0,65))} · ${clean(x.status)}</option>`).join('');
    if(box.dataset.options!==html){box.innerHTML=html;box.dataset.options=html;}
    const ids=projects.map(x=>x.id);
    current=ids.includes(previous)?previous:(ids.includes(selectedId)?selectedId:(ids[0]||''));
    box.value=current;
  }
  function recordDate(value){return value?new Date(value).toLocaleString('id-ID'):'—';}
  function render(result){
    q('#collab-phase').textContent=`${result.status.toUpperCase()} · ${result.phase} · Attempt ${result.attempt}`;
    const counts=result.task_counts;
    const total=result.tasks.length,done=counts.done||0;
    q('#collab-progress').textContent=`${done}/${total} specialist tasks completed (recorded)`;
    q('#collab-task-count').textContent=String(total);
    const cards=result.tasks.map(t=>`<article class="collab-task ${clean(t.status)}">
      <div class="collab-task-top"><span class="collab-task-id">${clean(t.task_key)}</span><span class="collab-status ${clean(t.status)}">${status[t.status]||clean(t.status)}</span></div>
      <h3>${clean(t.role)}</h3><div class="collab-dept">${clean(t.division)}</div>
      <p>${clean(t.description)}</p><div class="collab-files">${(t.files||[]).map(f=>`<code>${clean(f)}</code>`).join('')}</div>
      <small>Start: ${clean(recordDate(t.started_at))} · Finish: ${clean(recordDate(t.finished_at))}</small>
      ${result.task_review_mode==='manual' ? `<div class="task-review"><span>Approval: ${clean(t.decision||'pending')}</span>${t.feedback?`<p>Reviewer: ${clean(t.feedback)}</p>`:''}
      ${(t.status==='planned'&&['running','awaiting_approval'].includes(result.status)&&result.phase==='task_approval')?`<button type="button" class="outline small task-action" data-task-id="${clean(t.task_key)}" data-decision="approved" data-attempt="${Number(result.attempt)}">Approve</button><button type="button" class="outline small task-action" data-task-id="${clean(t.task_key)}" data-decision="blocked" data-attempt="${Number(result.attempt)}">Block</button>`:''}</div>`:''}
    </article>`).join('');
    q('#collab-tasks').innerHTML=cards||'<div class="empty-state">Belum ada task yang dihasilkan oleh Master Orchestrator pada attempt ini. Mode demo tidak memanggil AI coding agents.</div>';
    q('#collab-handoff-count').textContent=String(result.handoffs.length);
    q('#collab-handoffs').innerHTML=result.handoffs.map(h=>`<article class="collab-record">
      <div class="collab-record-icon">⇄</div><div><strong>${clean(h.source)} <span>→</span> ${clean(h.destination)}</strong>
      <p>${clean(h.summary)}</p><small>Attempt ${Number(h.attempt)} · ${clean(recordDate(h.created_at))}</small></div></article>`).join('')||
      '<div class="empty-state">Serah-terima agent akan tercatat setelah tahap terkait benar-benar menghasilkan output.</div>';
    q('#collab-notes').innerHTML=result.notes.map(n=>`<article class="collab-record">
      <div class="collab-record-icon">✎</div><div><strong>${clean(n.category.toUpperCase())} · Human Operator</strong>
      <p>${clean(n.message)}</p><small>${clean(recordDate(n.created_at))}</small></div></article>`).join('')||
      '<div class="empty-state">Belum ada catatan operator untuk proyek ini.</div>';
    q('#collab-note-submit').disabled=false;
    const pending=result.tasks.filter(t=>t.decision==='pending'&&t.status==='planned').length;
    const bulk=q('#collab-approve-pending');
    bulk.hidden=!(result.task_review_mode==='manual'&&result.phase==='task_approval'&&['running','awaiting_approval'].includes(result.status)&&pending>0);
    bulk.textContent=`Approve ${pending} pending task${pending===1?'':'s'}`;
    bulk.dataset.attempt=String(result.attempt);
    bulk.dataset.count=String(pending);
    q('#task-gate-notice').textContent=result.task_review_mode==='manual'
      ? 'Human gate: '+result.tasks.filter(t=>t.decision==='approved').length+'/'+total+' tasks approved. Worker is released while awaiting approvals. All approved tasks are automatically requeued; feedback is supplied to the matching AI agent.'
      : 'Auto mode: tasks are executed without a manual approval gate. Create an AI project with Human gate to control each planned task.';
    q('#collab-tasks').querySelectorAll('.task-action').forEach(b=>b.onclick=async()=>{
      const decision=b.dataset.decision,task=b.dataset.taskId,attempt=Number(b.dataset.attempt);
      const feedback=prompt(`Review ${task} — optional feedback for its assigned AI agent:`, '') ;
      if(feedback===null)return;
      if(feedback.length>1000){alert('Feedback must be under 1000 characters');return;}
      if(!confirm(`Confirm ${decision.toUpperCase()} ${task}?`))return;
      b.disabled=true;
      try {await api(`/api/projects/${current}/tasks/${task}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,feedback,attempt})});lastFetch=0;await load(true);}
      catch(e){alert('Task review failed: '+e.message);b.disabled=false;}
    });
  }
  async function load(force=false){
    fillProjects();if(!current){q('#collab-phase').textContent='No project selected';q('#collab-tasks').innerHTML='<div class="empty-state">Buat misi lebih dahulu untuk menampilkan kolaborasi agent.</div>';q('#collab-handoffs').innerHTML='';q('#collab-notes').innerHTML='';q('#collab-note-submit').disabled=true;return;}
    if(busy||(!force&&Date.now()-lastFetch<2600))return;
    busy=true;
    try {const result=await api(`/api/projects/${current}/collaboration`);render(result);lastFetch=Date.now();}
    catch(err){q('#collab-phase').textContent='Cannot load collaboration: '+err.message;}
    finally{busy=false;}
  }
  window.wfsCollabOnOpen=(force=false)=>load(force);
  window.wfsCollabRefresh=()=>{if(location.hash==='#collaboration')load();};
  window.wfsCollabFocus=pid=>{current=pid;q('#collab-project-filter').value=pid;window.wfsNavigate?.('collaboration');};
  q('#collab-project-filter').addEventListener('change',e=>{current=e.target.value;lastFetch=0;load(true);});
  q('#collab-refresh').addEventListener('click',()=>load(true));
  q('#collab-approve-pending').addEventListener('click',async()=>{
    const btn=q('#collab-approve-pending');
    const count=Number(btn.dataset.count),attempt=Number(btn.dataset.attempt);
    if(!count||!current)return;
    const feedback=prompt(`Shared feedback for ${count} pending tasks (optional):`,'');
    if(feedback===null)return;
    if(feedback.length>1000){alert('Feedback must be under 1000 characters');return;}
    if(!confirm(`Approve ${count} pending tasks in this project? Previously BLOCKED tasks will remain blocked.`))return;
    btn.disabled=true;
    try{
      const result=await api(`/api/projects/${current}/tasks/approve-pending`,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({attempt,feedback})});
      q('#collab-note-error').textContent=`Approved ${result.approved} tasks; pending review updated.`;
      lastFetch=0;await load(true);
    }catch(e){q('#collab-note-error').textContent='Bulk approval failed: '+e.message;}
    finally{btn.disabled=false;}
  });
  q('#collab-note-form').addEventListener('submit',async e=>{
    e.preventDefault();if(!current)return;
    const button=q('#collab-note-submit');button.disabled=true;
    try{
      await api(`/api/projects/${current}/notes`,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({category:q('#collab-note-type').value,message:q('#collab-note-text').value})});
      q('#collab-note-text').value='';lastFetch=0;await load(true);
    }catch(err){q('#collab-note-error').textContent=err.message;}
    finally{button.disabled=false;}
  });
})();
