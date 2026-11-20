/* WFS v1.9: operator-defined cost estimates, project budgets and CSV audit. */
'use strict';
(()=>{
 const $=s=>document.querySelector(s),safe=v=>esc(v);
 let loading=false;
 const money=x=>'$'+Number(x||0).toFixed(6);
 const summary=(label,value,desc)=>`<div class="finops-card"><span>${safe(label)}</span><strong>${safe(value)}</strong><small>${safe(desc)}</small></div>`;
 const line=(x)=>`<div class="finops-line"><span>${safe(x.name)}</span><span>${safe(x.calls)} calls · ${safe(x.input_tokens)} in / ${safe(x.output_tokens)} out · ${money(x.estimated_usd)}${x.unpriced_calls?' · '+safe(x.unpriced_calls)+' unpriced':''}</span></div>`;
 async function refresh(){if(loading||!csrf)return;loading=true;
   try{
     const period=$('#finops-period').value,project=$('#finops-project').value;
     const [report,capacity,prices,budgets,limits]=await Promise.all([
       api('/api/finops/report?period='+encodeURIComponent(period)+(project?'&project_id='+encodeURIComponent(project):'')),
       api('/api/concurrency'),api('/api/finops/prices'),api('/api/finops/budgets'),api('/api/finops/limits')]);
     $('#finops-summary').innerHTML=summary('Estimated USD',money(report.estimated_usd),report.price_coverage_complete?'All reported calls priced':'Partial estimate: '+report.unpriced_calls+' calls unpriced')+
       summary('Input tokens',report.input_tokens.toLocaleString('id-ID'),'As reported by provider')+
       summary('Output tokens',report.output_tokens.toLocaleString('id-ID'),'As reported by provider')+
       summary('Model calls',String(report.calls),JSON.stringify(report.model_attempts));
     $('#finops-concurrency').innerHTML=`<p>${safe(capacity.active_count)} running / ${safe(capacity.max_active_projects)} max · ${safe(capacity.queued_count)} queued · ${safe(capacity.awaiting_approval_count)} awaiting human review · ${safe(capacity.free_slots)} free slots</p>`+
       (capacity.active.map(a=>`<div class="finops-line"><span>${safe(a.title)}</span><span>${safe(a.phase)} · ${safe(a.id)}</span></div>`).join('')||'<p>No active projects.</p>');
     const peak=Math.max(0,...(report.by_day||[]).map(d=>Number(d.estimated_usd)||0));
     $('#finops-daily').innerHTML=(report.by_day||[]).slice(-30).map(d=>`<div class="finops-day" title="${safe(d.calls)} calls · ${safe(d.unpriced_calls)} unpriced"><span>${safe(d.day)}</span><progress value="${safe(d.estimated_usd)}" max="${peak||1}" aria-label="Daily estimated USD"></progress><span>${money(d.estimated_usd)}</span></div>`).join('')||'<p>No usage records in period.</p>';
     $('#finops-models').innerHTML=report.by_model.map(line).join('')||'<p>No model usage in selected period.</p>';
     $('#finops-projects').innerHTML=report.by_project.map(line).join('')||'<p>No project usage in selected period.</p>';
     $('#finops-prices').innerHTML=prices.map(p=>`<div class="finops-line"><span>${safe(p.model)}</span><span>In $${safe(p.input_usd_per_million)} · Out $${safe(p.output_usd_per_million)} / 1M</span></div>`).join('')||'<p>No model rates saved. Estimates will be incomplete until rates are configured.</p>';
     $('#finops-note').textContent=(report.truncated?'WARNING: report is truncated at 30,000 usage records. ':'')+report.disclaimer;
     const selected=project;
     const chosen=budgets.find(b=>b.project_id===selected);
     const budgetText=b=>`${money(b.estimated_usd)} estimated / ${money(b.limit_usd)} limit · ${b.unpriced_calls} calls unpriced · ${b.limit_reached?'ESTIMATE LIMIT REACHED':(b.percent_used??0)+'% estimated usage'}`;
     $('#finops-budget-summary').innerHTML=selected
       ? (chosen?`<div class="finops-line"><span>Project budget</span><span>${safe(budgetText(chosen))}</span></div>`:
          `<div class="finops-line"><span>Selected project</span><span>No estimate limit set · ${safe(selected)}</span></div>`)
       : (budgets.map(b=>`<div class="finops-line"><span>${safe(b.project_id)}</span><span>${safe(budgetText(b))}</span></div>`).join('')||'<p>No project-specific limits. Select a project to create one.</p>');
     $('#finops-scope-limits').innerHTML=limits.map(l=>`<div class="finops-line"><span>${safe(l.scope)} · ${safe(l.scope_id)}</span><span>${money(l.limit_usd)} estimated USD / admission</span></div>`).join('')||'<p>No organization/workspace admission limits configured.</p>';
     $('#finops-budget-limit').value=String(chosen?.limit_usd??0);
     $('#finops-budget-threshold').value=String(chosen?.alert_pct??80);
     const csvParams=new URLSearchParams({period});if(project)csvParams.set('project_id',project);
     $('#finops-export').href='/api/finops/export.csv?'+csvParams.toString();
     const select=$('#finops-project'),old=select.value;
     select.innerHTML='<option value="">Semua proyek</option>'+projects.map(p=>`<option value="${safe(p.id)}">${safe(p.title)} · ${safe(p.id)}</option>`).join('');
     select.value=old;
   }catch(e){$('#finops-note').textContent='Cannot load financial estimates: '+e.message;}
   finally{loading=false;}
 }
 window.wfsFinopsRefresh=refresh;
 $('#finops-refresh').onclick=refresh;
 $('#finops-period').onchange=refresh;
 $('#finops-project').onchange=refresh;
 $('#finops-price-form').onsubmit=async e=>{
   e.preventDefault();
   if(!confirm('Update operator-entered pricing for FUTURE usage only? This is not provider billing data.'))return;
   try{
     await api('/api/finops/prices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:$('#finops-model-id').value,input_usd_per_million:Number($('#finops-input-rate').value),output_usd_per_million:Number($('#finops-output-rate').value)})});
     $('#finops-note').textContent='Model rate saved; historical usage is unchanged.';await refresh();
   }catch(err){$('#finops-note').textContent='Cannot save model rate: '+err.message;}
 };
 $('#finops-scope-form').onsubmit=async e=>{
   e.preventDefault();
   if(!confirm('Change this estimated AI admission limit for your current organization? This does not update your provider invoice or hard spending policy.'))return;
   const kind=$('#finops-scope-kind').value;
   try{
     await api('/api/finops/limits',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:kind,workspace_id:'default',limit_usd:Number($('#finops-scope-amount').value)})});
     $('#finops-scope-message').textContent='Saved '+kind+' estimated admission limit for your organization.';
     await refresh();
   }catch(err){$('#finops-scope-message').textContent='Cannot update admission limit: '+err.message;}
 };
 $('#finops-budget-form').onsubmit=async e=>{
   e.preventDefault();
   const pid=$('#finops-project').value;
   if(!pid){$('#finops-budget-message').textContent='Select a specific project first.';return;}
   if(!confirm('Set a project estimate reservation limit? This is NOT a guaranteed provider billing cap.'))return;
   try{
     const result=await api(`/api/projects/${encodeURIComponent(pid)}/budget`,{method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({limit_usd:Number($('#finops-budget-limit').value),alert_pct:Number($('#finops-budget-threshold').value)})});
     $('#finops-budget-message').textContent=`Saved: ${money(result.limit_usd)} reserved estimate limit for ${pid}.`;
     await refresh();
   }catch(err){$('#finops-budget-message').textContent='Budget update failed: '+err.message;}
 };
})();
