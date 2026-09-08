/* LexIA UI2 — integración nativa del menú Estándares y mejoras de producto. */
(function(){
  'use strict';

  const API_PORT=(window.LEXIA_STANDARDS_PORT||'8515');
  const API=`http://127.0.0.1:${API_PORT}`;
  const RECENT_KEY='lexia_standards_recent_searches_v1';

  function standardsShell(){return document.getElementById('lexiaStandardsShell');}
  function norm(value){return String(value||'').replace(/\s+/g,' ').trim().toLowerCase();}
  function esc(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}

  function installVisualFixes(){
    if(document.getElementById('lexiaStandardsNativeVisualFix'))return;
    const style=document.createElement('style');
    style.id='lexiaStandardsNativeVisualFix';
    style.textContent=`
      #lexiaStandardsShell .std-kicker{display:none!important}
      #lexiaStandardsShell .std-wrap{max-width:none!important;margin:0!important;padding:22px 18px 38px!important}
      #lexiaStandardsShell .std-head{margin-bottom:14px!important}
      #lexiaStandardsShell .std-title{margin-top:0!important}
      #lexiaStandardsShell .std-grid.secondary{grid-template-columns:repeat(3,minmax(150px,1fr)) auto auto auto!important}
      #lexiaStandardsShell .std-recent-row{display:flex;align-items:center;gap:8px;margin-top:10px}
      #lexiaStandardsShell .std-recent-label{font-size:11px;font-weight:800;color:#687492;white-space:nowrap}
      #lexiaStandardsShell #stdRecent{max-width:420px}
      #lexiaStandardsShell .std-detail-actions{display:flex;justify-content:flex-end;margin-bottom:10px}
      #lexiaStandardsShell .std-notice[data-lexia-strong-relations]{display:none!important}
      #lexiaStandardsManualModal .std-manual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:16px}
      #lexiaStandardsManualModal .std-manual-field{display:grid;gap:5px}
      #lexiaStandardsManualModal .std-manual-field.wide{grid-column:1/-1}
      #lexiaStandardsManualModal label{font-size:10px;font-weight:850;color:#687492;text-transform:uppercase;letter-spacing:.04em}
      #lexiaStandardsManualModal input,#lexiaStandardsManualModal select,#lexiaStandardsManualModal textarea{box-sizing:border-box;width:100%;border:1px solid #d8d7e9;border-radius:9px;padding:9px 10px;font:inherit;color:#1a2140;background:#fff}
      #lexiaStandardsManualModal textarea{min-height:100px;resize:vertical}
      #lexiaStandardsManualModal .std-manual-actions{display:flex;justify-content:flex-end;gap:8px;padding:0 16px 16px}
      #lexiaStandardsManualModal .std-manual-status{margin:0 16px 12px;padding:9px 10px;border-radius:9px;background:#f7f5ff;color:#625c7b;font-size:11px;display:none}
      [data-lexia-standards-home]{cursor:pointer!important}
      @media(max-width:1100px){#lexiaStandardsShell .std-wrap{padding:18px 14px!important}#lexiaStandardsShell .std-grid.secondary{grid-template-columns:1fr 1fr!important}}
      @media(max-width:680px){#lexiaStandardsShell .std-wrap{padding:12px!important}#lexiaStandardsShell .std-recent-row{display:grid}}
    `;
    document.head.appendChild(style);
  }

  function syncStandardsInset(){
    const sidebar=document.getElementById('globalSidebar'),shell=standardsShell();
    if(!sidebar||!shell)return;
    const rect=sidebar.getBoundingClientRect();
    shell.style.setProperty('left',Math.max(0,Math.round(rect.right))+'px','important');
    shell.style.setProperty('right','0','important');
    shell.style.setProperty('top','0','important');
    shell.style.setProperty('bottom','0','important');
    shell.style.setProperty('width','auto','important');
  }

  function openStandards(){
    const shell=standardsShell();if(!shell)return;
    installVisualFixes();syncStandardsInset();
    const nav=document.querySelector('#globalSidebar .nav');
    if(nav)nav.querySelectorAll('button').forEach(item=>item.classList.remove('active'));
    const button=nav&&nav.querySelector('[data-lexia-standards-nav]');
    if(button){button.classList.add('active');button.setAttribute('aria-current','page');}
    shell.classList.add('open');
  }

  function closeStandards(){
    standardsShell()?.classList.remove('open');
    document.getElementById('stdGraphModal')?.remove();
    document.getElementById('lexiaStandardsManualModal')?.remove();
    const button=document.querySelector('#globalSidebar .nav [data-lexia-standards-nav]');
    if(button){button.classList.remove('active');button.removeAttribute('aria-current');}
  }

  function buildButton(){
    const button=document.createElement('button');button.type='button';button.dataset.lexiaStandardsNav='1';button.setAttribute('aria-label','Estándares');
    const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');
    icon.innerHTML='<path d="M12 3v18"></path><path d="M5 6h14"></path><path d="M7 6 3.5 12h7L7 6Z"></path><path d="M17 6 13.5 12h7L17 6Z"></path><path d="M8 21h8"></path>';
    button.append(icon,document.createTextNode('Estándares'));
    button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();openStandards();},true);
    return button;
  }

  function install(){
    installVisualFixes();
    const nav=document.querySelector('#globalSidebar .nav');if(!nav)return false;
    if(nav.querySelector('[data-lexia-standards-nav]')){syncStandardsInset();return true;}
    const button=buildButton();const buttons=[...nav.querySelectorAll(':scope > button')];
    const maintenance=buttons.find(item=>norm(item.textContent)==='mantenimiento');
    const investigation=nav.querySelector('button[data-route="contextpage"]')||buttons.find(item=>['investigación','investigacion'].includes(norm(item.textContent)));
    if(maintenance)maintenance.insertAdjacentElement('beforebegin',button);else if(investigation)investigation.insertAdjacentElement('afterend',button);else nav.append(button);
    syncStandardsInset();return true;
  }

  function cloneWithoutListeners(id){
    const old=document.getElementById(id);if(!old||old.dataset.lexiaCleanClone==='1')return old;
    const fresh=old.cloneNode(true);fresh.dataset.lexiaCleanClone='1';old.replaceWith(fresh);return fresh;
  }

  function clearFields(){
    ['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'].forEach(id=>{const node=document.getElementById(id);if(node)node.value='';});
  }

  function readCriteria(){
    const ids={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'};
    const out={};for(const [key,id] of Object.entries(ids)){const value=String(document.getElementById(id)?.value||'').trim();if(value)out[key]=value;}return out;
  }

  function recentSearches(){try{const raw=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');return Array.isArray(raw)?raw:[];}catch(_){return [];}}
  function recentLabel(criteria){return [criteria.q,criteria.court,criteria.speaker,criteria.treatment,criteria.from&&('desde '+criteria.from),criteria.to&&('hasta '+criteria.to),criteria.tag&&('#'+criteria.tag)].filter(Boolean).join(' · ');}
  function saveRecentSearch(){
    const criteria=readCriteria();if(!Object.keys(criteria).length)return;
    const label=recentLabel(criteria);let items=recentSearches().filter(item=>JSON.stringify(item.criteria)!==JSON.stringify(criteria));
    items.unshift({label,criteria,at:Date.now()});items=items.slice(0,12);localStorage.setItem(RECENT_KEY,JSON.stringify(items));refreshRecentSelect();
  }
  function refreshRecentSelect(){
    const select=document.getElementById('stdRecent');if(!select)return;
    select.innerHTML='<option value="">Últimas búsquedas…</option>'+recentSearches().map((item,index)=>`<option value="${index}">${esc(item.label)}</option>`).join('');
  }
  function applyRecent(index){
    const item=recentSearches()[Number(index)];if(!item)return;
    clearFields();for(const [key,value] of Object.entries(item.criteria||{})){const id={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'}[key];const node=document.getElementById(id);if(node)node.value=value;}
    document.getElementById('stdSearch')?.click();
  }

  function installSearchUx(){
    const shell=standardsShell();if(!shell||shell.dataset.lexiaSearchUx==='1')return;
    shell.dataset.lexiaSearchUx='1';
    const q=cloneWithoutListeners('stdQ'),court=cloneWithoutListeners('stdCourt'),speaker=cloneWithoutListeners('stdSpeaker'),treatment=cloneWithoutListeners('stdTreatment'),from=cloneWithoutListeners('stdFrom'),to=cloneWithoutListeners('stdTo'),tag=cloneWithoutListeners('stdTag'),clear=cloneWithoutListeners('stdClear');
    if(from){from.type='date';from.removeAttribute('placeholder');}
    if(to){to.type='date';to.removeAttribute('placeholder');}
    if(clear)clear.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();clearFields();});
    if(q)q.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();document.getElementById('stdSearch')?.click();}});

    const firstGrid=shell.querySelector('.std-search .std-grid');
    if(firstGrid&&!document.getElementById('stdRecent')){
      const row=document.createElement('div');row.className='std-recent-row';
      row.innerHTML='<span class="std-recent-label">Últimas búsquedas</span><select class="std-select" id="stdRecent"><option value="">Últimas búsquedas…</option></select>';
      firstGrid.insertAdjacentElement('afterend',row);
      row.querySelector('#stdRecent').addEventListener('change',event=>{if(event.target.value!=='')applyRecent(event.target.value);});
      refreshRecentSelect();
    }

    const secondary=shell.querySelector('.std-grid.secondary');
    if(secondary&&!document.getElementById('stdManualAdd')){
      const add=document.createElement('button');add.type='button';add.id='stdManualAdd';add.className='std-btn ghost';add.textContent='Agregar estándar';add.addEventListener('click',openManualModal);secondary.appendChild(add);
    }

    const search=document.getElementById('stdSearch');
    if(search)search.addEventListener('click',()=>saveRecentSearch(),true);

    const results=document.getElementById('stdResults');
    if(results&&norm(results.textContent).includes('buscando estándares'))results.innerHTML='<div class="std-empty">Ingresá criterios o dejá los campos vacíos y presioná Buscar para ver todos los estándares.</div>';
  }

  function adjustDetail(){
    const detail=document.getElementById('stdDetail');if(!detail)return;
    [...detail.querySelectorAll('.std-notice')].forEach(node=>{
      if(norm(node.textContent).includes('relaciones propuestas de tipo fuerte')){node.dataset.lexiaStrongRelations='1';node.remove();}
    });
    const graph=document.getElementById('stdGraphBtn');if(!graph||graph.dataset.lexiaMoved==='1')return;
    graph.dataset.lexiaMoved='1';
    let actions=detail.querySelector('.std-detail-actions');
    if(!actions){actions=document.createElement('div');actions.className='std-detail-actions';detail.prepend(actions);}
    actions.appendChild(graph);
  }

  function openManualModal(){
    document.getElementById('lexiaStandardsManualModal')?.remove();
    const modal=document.createElement('div');modal.id='lexiaStandardsManualModal';modal.className='std-modal-backdrop';
    modal.innerHTML=`<div class="std-modal"><div class="std-modal-head"><h2>Agregar estándar</h2><button class="std-modal-close" type="button" data-close>✕</button></div><div class="std-manual-grid">
      <div class="std-manual-field wide"><label>Estándar jurídico</label><textarea id="stdMStatement" required></textarea></div>
      <div class="std-manual-field"><label>Documento fuente</label><input id="stdMDocument" placeholder="Nombre del archivo" required></div>
      <div class="std-manual-field"><label>Ruta local (opcional)</label><input id="stdMPath" placeholder="/ruta/al/documento.pdf"></div>
      <div class="std-manual-field"><label>Tribunal</label><input id="stdMCourt"></div>
      <div class="std-manual-field"><label>Fecha</label><input id="stdMDate" type="date"></div>
      <div class="std-manual-field"><label>Voz</label><select id="stdMSpeaker"><option value="mayoria">mayoria</option><option value="disidencia">disidencia</option><option value="procurador">procurador</option><option value="tribunal_anterior">tribunal_anterior</option></select></div>
      <div class="std-manual-field"><label>Tratamiento</label><select id="stdMTreatment"><option value="adopta">adopta</option><option value="propone">propone</option><option value="cita">cita</option><option value="rechaza">rechaza</option></select></div>
      <div class="std-manual-field wide"><label>Cita literal</label><textarea id="stdMQuote"></textarea></div>
      <div class="std-manual-field"><label>Página</label><input id="stdMPage" inputmode="numeric"></div>
      <div class="std-manual-field"><label>Tags</label><input id="stdMTags" placeholder="tributario, prescripción"></div>
    </div><div class="std-manual-status" id="stdMStatus"></div><div class="std-manual-actions"><button class="std-btn secondary" type="button" data-close>Cancelar</button><button class="std-btn" type="button" id="stdMSave">Guardar estándar</button></div></div>`;
    document.body.appendChild(modal);
    modal.querySelectorAll('[data-close]').forEach(btn=>btn.addEventListener('click',()=>modal.remove()));
    modal.addEventListener('click',event=>{if(event.target===modal)modal.remove();});
    modal.querySelector('#stdMSave').addEventListener('click',()=>saveManualStandard(modal));
  }

  async function saveManualStandard(modal){
    const status=modal.querySelector('#stdMStatus'),button=modal.querySelector('#stdMSave');
    const payload={
      statement:modal.querySelector('#stdMStatement').value.trim(),document_name:modal.querySelector('#stdMDocument').value.trim(),document_path:modal.querySelector('#stdMPath').value.trim(),court:modal.querySelector('#stdMCourt').value.trim(),judgment_date:modal.querySelector('#stdMDate').value,speaker:modal.querySelector('#stdMSpeaker').value,source_speaker:modal.querySelector('#stdMSpeaker').value,treatment:modal.querySelector('#stdMTreatment').value,quote:modal.querySelector('#stdMQuote').value.trim(),page:modal.querySelector('#stdMPage').value.trim(),tags:modal.querySelector('#stdMTags').value.split(',').map(x=>x.trim()).filter(Boolean)
    };
    if(!payload.statement||!payload.document_name){status.style.display='block';status.textContent='Completá el estándar y el documento fuente.';return;}
    button.disabled=true;status.style.display='block';status.textContent='Guardando…';
    try{
      const response=await fetch(API+'/api/manual-standard',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(payload)});
      const data=await response.json();if(!response.ok||data.ok===false)throw new Error(data.error||'No se pudo guardar.');
      status.textContent=data.message||'Estándar guardado.';updateHomeStandardsCard();
      window.setTimeout(()=>modal.remove(),1400);
    }catch(error){status.textContent=String(error.message||error);}
    finally{button.disabled=false;}
  }

  async function updateHomeStandardsCard(){
    try{
      const response=await fetch(API+'/api/search?limit=1',{headers:{Accept:'application/json'}});if(!response.ok)return;
      const data=await response.json(),total=Number(data.total||0);
      const labels=[...document.querySelectorAll('body *')].filter(node=>node.children.length===0&&norm(node.textContent)==='fragmentos');
      const label=labels[0];if(!label)return;
      label.textContent='Estándares';
      let card=label.closest('button,a,[role="button"],.card,.stat,.metric,.home-card,.summary-card')||label.parentElement;
      for(let i=0;i<3&&card&&card.parentElement&&!card.querySelector('button,a');i+=1){if(card.querySelectorAll('*').length>12)break;card=card.parentElement;}
      if(!card)return;card.dataset.lexiaStandardsHome='1';
      const nums=[...card.querySelectorAll('*')].filter(node=>node.children.length===0&&/^\s*\d[\d.,]*\s*$/.test(node.textContent||''));
      if(nums[0])nums[0].textContent=String(total);
      if(!card.dataset.lexiaStandardsClick){card.dataset.lexiaStandardsClick='1';card.addEventListener('click',event=>{event.preventDefault();document.querySelector('#globalSidebar .nav [data-lexia-standards-nav]')?.click();},true);}
    }catch(_){}
  }

  function installExitHandler(){
    if(window.__lexiaStandardsNativeExit)return;window.__lexiaStandardsNativeExit=true;
    window.addEventListener('click',event=>{const target=event.target instanceof Element?event.target:null;const destination=target&&target.closest('#globalSidebar .nav button');if(destination&&!destination.matches('[data-lexia-standards-nav]'))closeStandards();},true);
  }

  function boot(){
    install();installExitHandler();installSearchUx();adjustDetail();updateHomeStandardsCard();
    window.addEventListener('resize',syncStandardsInset,{passive:true});
    const observer=new MutationObserver(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();});observer.observe(document.body,{childList:true,subtree:true});
    window.setTimeout(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();},150);
    window.setTimeout(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();},700);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();