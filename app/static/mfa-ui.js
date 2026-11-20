/* WFS v2.5 — own-account authenticator enrollment. UI never stores secrets. */
'use strict';
(()=>{
 const $=s=>document.querySelector(s);
 let pending=false;
 const setup=$('#mfa-setup-form'),enroll=$('#mfa-enroll'),recovery=$('#mfa-recovery'),disable=$('#mfa-disable-form');
 const say=message=>{$('#mfa-notice').textContent=message;};
 async function refresh(){
   if(!window.wfsCurrentUser)return;
   try {
     const state=await api('/api/mfa/status');
     $('#mfa-status').textContent=state.enabled?'ENABLED · TOTP':(state.required_by_organization?'ENROLLMENT REQUIRED':'NOT ENABLED');
     setup.hidden=!!state.enabled;
     disable.hidden=!state.enabled||!!state.required_by_organization;
     if(state.enabled && !recovery.hidden)return;
     if(state.enabled)enroll.hidden=true;
   } catch(e){say('Unable to read MFA status: '+e.message);}
 }
 async function refreshSessions(){
   if(!window.wfsCurrentUser)return;
   const target=$('#session-list');
   try{
     const data=await api('/api/sessions');
     target.replaceChildren();
     if(!data.sessions?.length){target.textContent='No active sessions';return;}
     for(const item of data.sessions){
       const line=document.createElement('div');line.className='settings-row';
       const details=document.createElement('span');
       details.textContent=`${item.current?'CURRENT · ':''}${item.device} · ${item.created_at} · expires ${item.expires_at}`;
       line.append(details);
       if(!item.current){
         const button=document.createElement('button');button.type='button';button.className='outline small';
         button.textContent='Revoke';
         button.onclick=async()=>{
           if(!confirm('Sign out this session?'))return;
           try{await api('/api/sessions/'+encodeURIComponent(item.id),{method:'DELETE'});$('#session-notice').textContent='Session revoked';await refreshSessions();}
           catch(e){$('#session-notice').textContent=e.message;}
         };line.append(button);
       }
       target.append(line);
     }
   }catch(e){target.textContent=e.message;}
 }
 $('#session-refresh').onclick=refreshSessions;
 $('#session-revoke-others').onclick=async()=>{
   if(!confirm('Sign out every other browser session for this account?'))return;
   try{const result=await api('/api/sessions/revoke-others',{method:'POST'});$('#session-notice').textContent=result.revoked_count+' session(s) revoked';await refreshSessions();}
   catch(e){$('#session-notice').textContent=e.message;}
 };
 window.wfsMfaOnOpen=()=>{refresh();refreshSessions();};
 window.wfsMfaClear=()=>{
   pending=false;
   $('#mfa-secret').textContent='';$('#mfa-recovery-codes').textContent='';
   for(const id of ['mfa-setup-password','mfa-confirm-code','mfa-disable-password','mfa-disable-code'])$('#'+id).value='';
   enroll.hidden=true;recovery.hidden=true;
   say('');
 };
 setup.addEventListener('submit',async e=>{
   e.preventDefault();
   try{
     const result=await api('/api/mfa/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#mfa-setup-password').value})});
     $('#mfa-setup-password').value='';
     $('#mfa-secret').textContent=result.secret;
     enroll.hidden=false;recovery.hidden=true;pending=true;
     say('Secret ready; enrollment expires in 10 minutes. Confirm a code from the authenticator.');
     $('#mfa-confirm-code').focus();
   }catch(err){say(err.message);}
 });
 $('#mfa-copy-secret').addEventListener('click',async()=>{
   try{await navigator.clipboard.writeText($('#mfa-secret').textContent);say('Secret copied; clear your clipboard after enrollment.');}
   catch{say('Clipboard permission denied; copy the secret manually.');}
 });
 $('#mfa-confirm-form').addEventListener('submit',async e=>{
   e.preventDefault();
   if(!pending)return;
   try{
     const result=await api('/api/mfa/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('#mfa-confirm-code').value})});
     $('#mfa-confirm-code').value='';$('#mfa-secret').textContent='';pending=false;enroll.hidden=true;
     $('#mfa-recovery-codes').textContent=result.recovery_codes.join('\n');recovery.hidden=false;
     say('MFA enabled. Save recovery codes offline before closing this panel.');await refresh();
   }catch(err){say(err.message);}
 });
 $('#mfa-save-recovery').addEventListener('click',async()=>{
   try{await navigator.clipboard.writeText($('#mfa-recovery-codes').textContent);say('Recovery codes copied; store offline and clear the clipboard.');}
   catch{say('Clipboard permission denied; save recovery codes manually.');}
 });
 $('#mfa-recovery-done').addEventListener('click',()=>{
   $('#mfa-recovery-codes').textContent='';recovery.hidden=true;
   say('Recovery codes are no longer displayed.');
   // Finish the setup-only session and load permitted project APIs after MFA enrollment.
   window.location.reload();
 });
 disable.addEventListener('submit',async e=>{
   e.preventDefault();if(!confirm('Disable MFA for this account and revoke ALL sessions?'))return;
   try{
     await api('/api/mfa/disable',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#mfa-disable-password').value,code:$('#mfa-disable-code').value})});
     $('#mfa-disable-password').value='';$('#mfa-disable-code').value='';
     showLogin();
   }catch(err){say(err.message);}
 });
})();
