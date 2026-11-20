/* WFS v2.0 team directory. Owner-only actions are enforced on the server. */
'use strict';
(()=>{
 const $=s=>document.querySelector(s);
 const escapeHTML=s=>esc(s);
 let loading=false;
 async function refresh(){
   if(loading)return;
   loading=true;
   const box=$('#team-members'),audit=$('#team-audit');
   if(window.wfsCurrentUser?.role!=='owner'){
     box.textContent='Account administration is reserved for Owner. You can manage access to projects you created in the panel below.';
     audit.textContent='Only Owner can view account-level audit events.';
     $('#team-create-form').hidden=true;loading=false;return;
   }
   $('#team-create-form').hidden=false;
   try{
     const response=await api('/api/users');
     box.innerHTML=response.users.map(user=>`<div class="team-member"><div><strong>${escapeHTML(user.username)}</strong><small>${escapeHTML(user.role.toUpperCase())} · ${user.disabled?'DISABLED':'ACTIVE'} · ${escapeHTML(user.created_at)}</small></div>
       ${user.id==='owner'?'<span class="nav-new">OWNER</span>':`<div class="operator-actions"><select class="team-change-role" data-id="${escapeHTML(user.id)}" aria-label="Change role ${escapeHTML(user.username)}"><option value="manager" ${user.role==='manager'?'selected':''}>Manager</option><option value="developer" ${user.role==='developer'?'selected':''}>Developer</option><option value="viewer" ${user.role==='viewer'?'selected':''}>Viewer</option></select><button type="button" class="outline small team-toggle" data-id="${escapeHTML(user.id)}" data-disabled="${user.disabled?'false':'true'}">${user.disabled?'Enable':'Disable'}</button><button type="button" class="outline small team-reset" data-id="${escapeHTML(user.id)}">Reset password</button></div>`}</div>`).join('');
     audit.innerHTML=response.audit.map(x=>`<div><span>${escapeHTML(x.action)} · ${escapeHTML(x.actor_id)} / ${escapeHTML(x.subject_id)}</span><small>${escapeHTML(x.created_at)}</small></div>`).join('')||'<p>No access changes yet.</p>';
     document.querySelectorAll('.team-change-role').forEach(el=>el.addEventListener('change',async()=>{
       if(!confirm(`Set selected user role to ${el.value}? All of their sessions will be revoked.`)){refresh();return;}
       try{await api('/api/users/'+el.dataset.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:el.value})});await refresh();}catch(e){$('#team-notice').textContent=e.message;}
     }));
     document.querySelectorAll('.team-reset').forEach(el=>el.addEventListener('click',async()=>{
       const password=prompt('Enter a NEW password (minimum 12 characters) for the selected user. All existing sessions will be revoked.');
       if(password===null)return;
       if(password.length<12){$('#team-notice').textContent='Password must have at least 12 characters.';return;}
       try{await api('/api/users/'+el.dataset.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_password:password})});
         $('#team-notice').textContent='Password reset. Share it through a secure channel.';await refresh();
       }catch(e){$('#team-notice').textContent='Reset failed: '+e.message;}
     }));
     document.querySelectorAll('.team-toggle').forEach(el=>el.addEventListener('click',async()=>{
       if(!confirm('Change account access and revoke its active sessions?'))return;
       try{await api('/api/users/'+el.dataset.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({disabled:el.dataset.disabled==='true'})});await refresh();}catch(e){$('#team-notice').textContent=e.message;}
     }));
   }catch(e){box.textContent=e.message;audit.textContent='Only the Owner can manage team accounts.';}
   finally{loading=false;}
 }
 window.wfsTeamOnOpen=refresh;
 $('#team-refresh').onclick=refresh;
 $('#team-create-form').onsubmit=async event=>{
   event.preventDefault();
   const body={username:$('#team-username').value.trim(),password:$('#team-password').value,role:$('#team-role').value};
   if(!confirm(`Create ${body.username} (${body.role})?`))return;
   try{await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
     $('#team-notice').textContent='User created. Share the temporary password using a secure channel.';
     $('#team-password').value='';await refresh();
   }catch(e){$('#team-notice').textContent='Account creation failed: '+e.message;}
 };
})();
