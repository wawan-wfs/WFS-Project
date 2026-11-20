/* WFS PROJECT v2.3 accessible navigation and contextual command palette. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const pages=[
    ['overview','Mission Control','Dashboard dan mission intake','⌂'],
    ['projects','Projects & Missions','Riwayat proyek dan deliverables','▤'],
    ['queue','Queue Manager','Prioritas dan status antrean','☷'],
    ['office','AI Office 3D','Ruang kerja agent berbasis telemetry','◈'],
    ['collaboration','Collaboration Board','Tugas, handoff dan review','⇄'],
    ['operator','Operator Command Hub','Runner lokal dan approval','⬡'],
    ['agents','Agent Directory','10 divisi dan spesialis','♧'],
    ['quality','QA & Audit Center','Review dan kualitas pengujian','✓'],
    ['deliverables','Deliverables','File dan arsip hasil proyek','◇'],
    ['activity','Activity Feed','Log pekerjaan dan keputusan','≋'],
    ['finops','AI Cost Center','Token dan estimasi biaya','◉'],
    ['system','System & Settings','Kesehatan worker dan preferensi','⚙'],
    ['team','Team & Access','Akun dan perizinan proyek','♙']
  ];
  const dialog=$('command-dialog'), search=$('command-search'), results=$('command-results');
  if(!dialog||!search||!results)return;
  let matches=pages,active=0;
  const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function render(){
    const q=search.value.trim().toLowerCase();
    matches=pages.filter(p=>(p[1]+' '+p[2]).toLowerCase().includes(q));
    active=Math.min(active,Math.max(0,matches.length-1));
    results.innerHTML=matches.map((p,i)=>`<button type="button" role="option" aria-selected="${i===active}" class="command-result ${i===active?'is-selected':''}" data-command-page="${p[0]}"><span class="command-icon">${escape(p[3])}</span><span><strong>${escape(p[1])}</strong><small>${escape(p[2])}</small></span><span class="command-jump" aria-hidden="true">↗</span></button>`).join('')||'<p class="command-empty">Tidak ada halaman yang cocok.</p>';
    for(const button of results.querySelectorAll('[data-command-page]')){
      button.onclick=()=>openPage(button.dataset.commandPage);
      button.onmouseenter=()=>{active=matches.findIndex(p=>p[0]===button.dataset.commandPage);refreshSelection();};
    }
  }
  function refreshSelection(){
    results.querySelectorAll('[data-command-page]').forEach((b,i)=>{
      b.classList.toggle('is-selected',i===active);b.setAttribute('aria-selected',String(i===active));
    });
  }
  function openPage(page){
    dialog.close();
    if(typeof window.wfsNavigate==='function')window.wfsNavigate(page);
  }
  function open(){
    if(dialog.open)return;
    search.value='';active=0;render();dialog.showModal();search.focus();
  }
  $('command-trigger')?.addEventListener('click',open);
  $('command-close')?.addEventListener('click',()=>dialog.close());
  search.addEventListener('input',()=>{active=0;render();});
  search.addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();active=(active+(e.key==='ArrowDown'?1:-1)+matches.length)%Math.max(1,matches.length);refreshSelection();
      results.querySelector('.is-selected')?.scrollIntoView({block:'nearest'});
    }
    if(e.key==='Enter'&&matches[active]){e.preventDefault();openPage(matches[active][0]);}
  });
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){
      e.preventDefault();if(dialog.open)dialog.close();else open();
    }
  });
  $('welcome-new-mission')?.addEventListener('click',()=>{
    $('project-title')?.focus();
    $('mission-form')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
  });
  $('welcome-enter-office')?.addEventListener('click',()=>window.wfsNavigate?.('office'));
})();
