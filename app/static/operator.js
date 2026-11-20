/* v1.7 Operator Operations. Browser queues/inspects; only the host can execute. */
'use strict';
(() => {
 const $=s=>document.querySelector(s);
 const safe=v=>esc(v);
 let busy=false,last=0,all=[];
 const desc=j=>`${j.kind} · ${j.project_id} · ${j.id}`;
 function choices(){
   const sel=$('#op-project'),old=sel.value;
   const html='<option value="">Choose delivered project</option>'+projects.filter(p=>['completed','review_required'].includes(p.status)).slice(0,250)
    .map(p=>`<option value="${safe(p.id)}">${safe(p.title)} · ${safe(p.stack)} · ${safe(p.status)}</option>`).join('');
   if(sel.dataset.options!==html){sel.innerHTML=html;sel.dataset.options=html;sel.value=old;}
 }
 function linkPreview(outcome){return typeof outcome.url==='string'&&/^http:\/\/127\.0\.0\.1:\d+\/$/.test(outcome.url)
   ? `<a href="${safe(outcome.url)}" target="_blank" rel="noopener noreferrer">Open local preview ↗</a>`:'';}
 function display(){
   const query=$('#op-search').value.trim().toLowerCase(),filter=$('#op-status-filter').value;
   const filtered=all.filter(j=>(filter==='all'||filter===j.status)&&(!query||desc(j).toLowerCase().includes(query)));
   $('#op-count').textContent=`${filtered.length} of ${all.length} operator requests · All execution requires host confirmation`;
   $('#op-jobs').innerHTML=filtered.map(j=>{
     const outcome=j.result||{};
     return `<article class="operator-job"><div class="operator-job-head"><strong>${safe(j.kind)}</strong><span class="collab-status ${safe(j.status)}">${safe(j.status.toUpperCase())}</span></div>
       <p>Project ${safe(j.project_id)} · ${safe(j.created_at)}</p><code>${safe(j.id)}</code>
       ${j.retry_of?`<p>Retry of ${safe(j.retry_of)}</p>`:''}
       ${j.options.repo?`<p>Repo: ${safe(j.options.repo)}</p>`:''}
       ${linkPreview(outcome)}${outcome.note?`<p>${safe(outcome.note)}</p>`:''}${outcome.error?`<p>Error: ${safe(outcome.error)}</p>`:''}
       ${j.status==='queued'?`<p>Host: <code>python scripts/operator-runner.py --job ${safe(j.id)}</code></p>`:''}
       <div class="operator-job-actions"><button type="button" class="outline small op-detail" data-id="${safe(j.id)}">Timeline & result</button>
       ${j.status==='queued'?`<button type="button" class="outline small op-cancel" data-id="${safe(j.id)}">Cancel request</button>`:''}
       ${['failed','rejected'].includes(j.status)?`<button type="button" class="outline small op-retry" data-id="${safe(j.id)}">Requeue with new approval</button>`:''}</div>
     </article>`;
   }).join('')||'<div class="empty-state">No matching operator jobs.</div>';
   $('#op-jobs').querySelectorAll('.op-detail').forEach(b=>b.onclick=()=>showDetail(b.dataset.id));
   $('#op-jobs').querySelectorAll('.op-cancel').forEach(b=>b.onclick=async()=>{
      if(!confirm('Cancel this queued operator request?'))return;
      b.disabled=true;
      try {await api(`/api/operator/jobs/${b.dataset.id}/cancel`,{method:'POST'});await load(true);}
      catch(e){$('#op-notice').textContent='Cannot cancel: '+e.message;b.disabled=false;}
   });
   $('#op-jobs').querySelectorAll('.op-retry').forEach(b=>b.onclick=async()=>{
      if(!confirm('Create a NEW queued request? The host operator must inspect the source and approve again.'))return;
      b.disabled=true;
      try{const r=await api(`/api/operator/jobs/${b.dataset.id}/retry`,{method:'POST'});
        $('#op-notice').textContent=`New request ${r.job_id} queued. No execution has occurred.`;await load(true);
      }catch(e){$('#op-notice').textContent='Requeue failed: '+e.message;b.disabled=false;}
   });
 }
 async function showDetail(id){
   const body=$('#op-detail-body'),dialog=$('#operator-detail-dialog');
   $('#op-detail-title').textContent=id;
   body.textContent='Loading authenticated job history…';dialog.showModal();
   try{
     const j=await api(`/api/operator/jobs/${id}`),result=j.result||{};
     const steps=j.steps||[];
     body.innerHTML=`<p><strong>${safe(j.kind)}</strong> · ${safe(j.status.toUpperCase())} · Project ${safe(j.project_id)}</p>
       ${j.possibly_stalled?'<p class="job-warning">Host heartbeat is stale. Confirm state on Windows; WFS will not automatically rerun external commands.</p>':''}
       <p>Created: ${safe(j.created_at)} · Last update: ${safe(j.updated_at)}</p>
       <div class="op-step-list">${steps.map(s=>`<div class="op-step"><span class="collab-status">${safe(s.stage)}</span><span>${safe(s.summary)}</span><small>${safe(s.created_at)}</small></div>`).join('')||'<p>Legacy job: no structured timeline recorded.</p>'}</div>
       <h3>Saved result</h3>${linkPreview(result)}<pre class="operator-result">${safe(JSON.stringify(result,null,2))}</pre>
       <p class="grounded-note">A timeline proves the runner recorded transitions, not that generated code is safe for production.</p>`;
   }catch(e){body.textContent='Unable to open job detail: '+e.message;}
 }
 async function load(force=false){
   choices();if(busy||(!force&&Date.now()-last<2000))return;
   busy=true;
   try{all=await api('/api/operator/jobs');display();last=Date.now();}
   catch(e){$('#op-notice').textContent='Cannot retrieve jobs: '+e.message;}
   finally{busy=false;}
 }
 window.wfsOperatorOnOpen=(force=false)=>load(force);
 window.wfsOperatorRefresh=()=>{if(location.hash==='#operator')load(true);};
 $('#op-refresh').onclick=()=>load(true);
 $('#op-status-filter').addEventListener('change',display);
 $('#op-search').addEventListener('input',display);
 $('#op-detail-close').onclick=()=>$('#operator-detail-dialog').close();
 $('#op-job-form').addEventListener('submit',async e=>{
   e.preventDefault();const pid=$('#op-project').value,kind=$('#op-kind').value,repo=$('#op-repo').value.trim();
   if(!pid){$('#op-notice').textContent='Choose a delivered project.';return;}
   if(kind==='github-draft'&&!/^[A-Za-z0-9_.-]{1,80}\/[A-Za-z0-9_.-]{1,100}$/.test(repo)){
       $('#op-notice').textContent='GitHub repository must be owner/repo.';return;
   }
   if(!confirm('Queue '+kind+' for operator review? No Docker/GitHub action is executed by this click.'))return;
   const btn=$('#op-submit');btn.disabled=true;
   try{
     const job=await api(`/api/projects/${pid}/operator-jobs`,{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({kind,...(kind==='github-draft'?{repo}:{})})});
     $('#op-notice').textContent='Queued '+job.job_id+' — requires fresh host-side typed approval.';
     await load(true);
   }catch(err){$('#op-notice').textContent='Request failed: '+err.message;}
   finally{btn.disabled=false;}
 });
})();
