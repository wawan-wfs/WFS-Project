/* WFS v2.1 private project access, all mutations verified by the server. */
'use strict';
(()=>{
 const $=s=>document.querySelector(s),safe=v=>esc(v);
 let users=[];
 let busy=false;
 async function load(){
   if(busy||!csrf)return;busy=true;
   try{
     const select=$('#access-project'),old=select.value;
     select.innerHTML='<option value="">Select mission</option>'+projects.map(p=>`<option value="${safe(p.id)}">${safe(p.title)} · ${safe(p.visibility||'workspace')}</option>`).join('');
     select.value=old;
     users=await api('/api/team/directory');
     $('#access-user').innerHTML='<option value="">Select user</option>'+users.filter(x=>x.id!=='owner').map(x=>`<option value="${safe(x.id)}">${safe(x.username)} · ${safe(x.role)}</option>`).join('');
     await detail();
   }catch(e){$('#access-notice').textContent=e.message;}
   finally{busy=false;}
 }
 async function detail(){
   const pid=$('#access-project').value;
   $('#access-members').textContent='';$('#access-audit').textContent='';
   if(!pid){$('#access-mode').textContent='Select a project to inspect permissions.';return;}
   try{
     const data=await api('/api/projects/'+pid+'/access');
     $('#access-mode').textContent='Visibility: '+data.visibility+' · Creator ID: '+data.created_by;
     $('#access-visibility').value=data.visibility;
     $('#access-members').innerHTML=data.members.map(m=>`<div class="team-member"><div><strong>${safe(m.username)}</strong><small>${safe(m.permission)} · ${safe(m.granted_at)}</small></div><button type="button" class="outline small access-remove" data-id="${safe(m.user_id)}">Revoke</button></div>`).join('')||'<p>No explicit members. Creator and Owner retain access.</p>';
     $('#access-audit').innerHTML=(data.audit||[]).slice(0,15).map(m=>`<div><span>${safe(m.action)} · ${safe(m.actor_id)}</span><small>${safe(m.at)}</small></div>`).join('');
     document.querySelectorAll('.access-remove').forEach(el=>el.onclick=async()=>{
       if(!confirm('Immediately revoke project access for this member?'))return;
       try{await api('/api/projects/'+pid+'/members/'+encodeURIComponent(el.dataset.id),{method:'DELETE'});await detail();}
       catch(e){$('#access-notice').textContent=e.message;}
     });
   }catch(e){$('#access-mode').textContent='Cannot inspect project access: '+e.message;}
 }
 window.wfsAccessOnOpen=load;
 $('#access-project').onchange=detail;
 $('#access-save-visibility').onclick=async()=>{
   const pid=$('#access-project').value,visibility=$('#access-visibility').value;
   if(!pid||!confirm('Set this project visibility to '+visibility+'?'))return;
   try{await api('/api/projects/'+pid+'/access',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({visibility})});await detail();}
   catch(e){$('#access-notice').textContent=e.message;}
 };
 $('#access-grant').onclick=async()=>{
   const pid=$('#access-project').value,user_id=$('#access-user').value,permission=$('#access-permission').value;
   if(!pid||!user_id)return;
   if(!confirm('Grant '+permission+' access to the selected user?'))return;
   try{await api('/api/projects/'+pid+'/members',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id,permission})});await detail();}
   catch(e){$('#access-notice').textContent=e.message;}
 };
})();
