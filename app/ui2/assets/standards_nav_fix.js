/* LexIA UI2 — integración nativa del menú Estándares y mejoras de producto. */
(function(){
  'use strict';

  const API_PORT=(window.LEXIA_STANDARDS_PORT||'8515');
  const API=`http://127.0.0.1:${API_PORT}`;
  const RECENT_KEY='lexia_standards_recent_searches_v1';
  let recentMemory=[];
  let recentStorageAvailable=true;

  function standardsShell(){return document.getElementById('lexiaStandardsShell');}
  function norm(value){return String(value||'').replace(/\s+/g,' ').trim().toLowerCase();}
  function setText(node,value){if(node&&node.textContent!==value)node.textContent=value;}

  function installVisualFixes(){
    if(document.getElementById('lexiaStandardsNativeVisualFix'))return;
    const style=document.createElement('style');
    style.id='lexiaStandardsNativeVisualFix';
    style.textContent=`
      #lexiaStandardsShell .std-kicker{display:none!important}
      #lexiaStandardsShell .std-wrap{max-width:none!important;margin:0!important;padding:22px 18px 38px!important}
      #lexiaStandardsShell .std-head{margin-bottom:14px!important}
      #lexiaStandardsShell .std-title{margin-top:0!important}
      #lexiaStandardsShell .std-grid.std-primary-row{grid-template-columns:minmax(280px,1fr) auto auto auto!important}
      #lexiaStandardsShell .std-grid.secondary{grid-template-columns:repeat(6,minmax(110px,1fr))!important;margin-top:10px!important}
      #lexiaStandardsShell #stdSummary:empty{display:none}
      #lexiaStandardsShell .std-query-wrap{position:relative;min-width:0}
      #lexiaStandardsShell .std-query-wrap #stdQ{padding-right:38px}
      #lexiaStandardsShell .std-history-toggle{position:absolute;z-index:2;top:4px;right:5px;width:30px;height:32px;border:0;border-radius:8px;background:transparent;color:#6258d8;font-size:14px;cursor:pointer}
      #lexiaStandardsShell .std-history-toggle:hover{background:#f0efff}
      #lexiaStandardsShell .std-history-menu{position:absolute;z-index:40;top:calc(100% + 6px);left:0;right:0;display:none;max-height:260px;overflow:auto;padding:6px;background:#fff;border:1px solid #d8d3ff;border-radius:11px;box-shadow:0 14px 32px rgba(45,36,120,.16)}
      #lexiaStandardsShell .std-history-menu.open{display:grid;gap:3px}
      #lexiaStandardsShell .std-history-item{width:100%;border:0;border-radius:8px;padding:9px 10px;background:#fff;color:#252b4b;font:inherit;font-size:12px;line-height:1.35;text-align:left;cursor:pointer}
      #lexiaStandardsShell .std-history-item:hover,#lexiaStandardsShell .std-history-item:focus{background:#f0efff;color:#5146f6;outline:none}
      #lexiaStandardsShell .std-history-empty{padding:9px 10px;color:#7b829b;font-size:12px}
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
      [data-lexia-standards-home]:hover{transform:translateY(-2px);border-color:#d8d3ff!important;box-shadow:0 10px 24px rgba(81,70,246,.12)!important}
      @media(max-width:1100px){#lexiaStandardsShell .std-wrap{padding:18px 14px!important}#lexiaStandardsShell .std-grid.secondary{grid-template-columns:repeat(3,1fr)!important}}
      @media(max-width:680px){#lexiaStandardsShell .std-wrap{padding:12px!important}#lexiaStandardsShell .std-grid.std-primary-row{grid-template-columns:repeat(3,1fr)!important}#lexiaStandardsShell .std-grid.std-primary-row .std-query-wrap{grid-column:1/-1}#lexiaStandardsShell .std-grid.secondary{grid-template-columns:1fr!important}}
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

  function clearFields(){
    ['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'].forEach(id=>{const node=document.getElementById(id);if(node)node.value='';});
  }

  function readCriteria(){
    const ids={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'};
    const out={};for(const [key,id] of Object.entries(ids)){const value=String(document.getElementById(id)?.value||'').trim();if(value)out[key]=value;}return out;
  }

  function recentSearches(){if(!recentStorageAvailable)return recentMemory;try{const raw=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');if(Array.isArray(raw)){recentMemory=raw;return raw;}}catch(_){recentStorageAvailable=false;}return recentMemory;}
  function recentLabel(criteria){return [criteria.q,criteria.court,criteria.speaker,criteria.treatment,criteria.from&&('desde '+criteria.from),criteria.to&&('hasta '+criteria.to),criteria.tag&&('#'+criteria.tag)].filter(Boolean).join(' · ')||'Todos los estándares';}
  function saveRecentSearch(){
    const criteria=readCriteria();
    const label=recentLabel(criteria);let items=recentSearches().filter(item=>JSON.stringify(item.criteria)!==JSON.stringify(criteria));
    items.unshift({label,criteria,at:Date.now()});items=items.slice(0,12);recentMemory=items;
    if(recentStorageAvailable){try{localStorage.setItem(RECENT_KEY,JSON.stringify(items));}catch(_){recentStorageAvailable=false;}}
    refreshRecentMenu();
  }
  function setHistoryOpen(open){
    const menu=document.getElementById('stdHistoryMenu'),input=document.getElementById('stdQ'),toggle=document.getElementById('stdHistoryToggle');
    if(!menu)return;
    const visible=Boolean(open&&menu.childElementCount);
    menu.classList.toggle('open',visible);input?.setAttribute('aria-expanded',String(visible));toggle?.setAttribute('aria-expanded',String(visible));
  }
  function refreshRecentMenu(){
    const menu=document.getElementById('stdHistoryMenu'),toggle=document.getElementById('stdHistoryToggle');if(!menu)return;
    menu.replaceChildren();
    const items=recentSearches();items.forEach((item,index)=>{
      const button=document.createElement('button');button.type='button';button.className='std-history-item';button.textContent=item.label;button.dataset.recentIndex=String(index);
      button.setAttribute('role','option');
      button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();setHistoryOpen(false);applyRecent(index);});
      menu.appendChild(button);
    });
    if(!items.length){const empty=document.createElement('div');empty.className='std-history-empty';empty.textContent='Sin búsquedas recientes';menu.appendChild(empty);}
    if(toggle)toggle.hidden=false;
  }
  function applyRecent(index){
    const item=recentSearches()[Number(index)];if(!item)return;
    clearFields();for(const [key,value] of Object.entries(item.criteria||{})){const id={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'}[key];const node=document.getElementById(id);if(node)node.value=value;}
    saveRecentSearch();setHistoryOpen(false);
    if(typeof window.lexiaStandardsSearch==='function')window.lexiaStandardsSearch();
  }

  function installActionRouter(){
    if(window.__lexiaStandardsActionRouter)return;window.__lexiaStandardsActionRouter=true;
    document.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target:null;if(!target)return;
      const recent=target.closest('.std-history-item[data-recent-index]');
      if(recent){event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();applyRecent(recent.dataset.recentIndex);return;}
      if(target.closest('#stdHistoryToggle,#stdQ')){
        if(target.closest('#stdHistoryToggle'))event.preventDefault();
        event.stopPropagation();event.stopImmediatePropagation();refreshRecentMenu();
        const menu=document.getElementById('stdHistoryMenu');setHistoryOpen(!menu?.classList.contains('open'));return;
      }
      if(target.closest('#stdSearch')){
        event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();saveRecentSearch();setHistoryOpen(false);
        if(typeof window.lexiaStandardsSearch==='function')window.lexiaStandardsSearch();return;
      }
      if(target.closest('#stdClear')){
        event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();setHistoryOpen(false);
        if(typeof window.lexiaStandardsResetSearch==='function')window.lexiaStandardsResetSearch();return;
      }
      if(!target.closest('.std-query-wrap'))setHistoryOpen(false);
    },true);
    document.addEventListener('input',event=>{if(event.target?.id==='stdQ')setHistoryOpen(false);},true);
  }

  function installSearchUx(){
    const shell=standardsShell();if(!shell||shell.dataset.lexiaSearchUx==='1')return;
    shell.dataset.lexiaSearchUx='1';
    const q=document.getElementById('stdQ'),court=document.getElementById('stdCourt'),speaker=document.getElementById('stdSpeaker'),treatment=document.getElementById('stdTreatment'),from=document.getElementById('stdFrom'),to=document.getElementById('stdTo'),clear=document.getElementById('stdClear'),search=document.getElementById('stdSearch');
    if(from){from.type='date';from.removeAttribute('placeholder');}
    if(to){to.type='date';to.removeAttribute('placeholder');}

    const firstGrid=shell.querySelector('.std-search .std-grid');
    const secondary=shell.querySelector('.std-grid.secondary');
    if(firstGrid){
      firstGrid.classList.remove('primary');
      firstGrid.classList.add('std-primary-row');
      if(secondary)secondary.prepend(...[court,speaker,treatment].filter(Boolean));
      shell.querySelector('.std-recent-row')?.remove();
      let queryWrap=q?.closest('.std-query-wrap');
      if(q&&!queryWrap){
        queryWrap=document.createElement('div');queryWrap.className='std-query-wrap';q.replaceWith(queryWrap);queryWrap.appendChild(q);
      }
      if(queryWrap&&!document.getElementById('stdHistoryMenu')){
        const toggle=document.createElement('button');toggle.type='button';toggle.id='stdHistoryToggle';toggle.className='std-history-toggle';toggle.setAttribute('aria-label','Mostrar últimas búsquedas');toggle.setAttribute('aria-haspopup','listbox');toggle.textContent='▾';
        const menu=document.createElement('div');menu.id='stdHistoryMenu';menu.className='std-history-menu';menu.setAttribute('role','listbox');
        queryWrap.append(toggle,menu);q.setAttribute('aria-haspopup','listbox');q.setAttribute('aria-expanded','false');
        const toggleHistory=event=>{event.preventDefault();event.stopPropagation();refreshRecentMenu();setHistoryOpen(!menu.classList.contains('open'));};
        q.addEventListener('click',toggleHistory);toggle.addEventListener('click',toggleHistory);q.addEventListener('input',()=>setHistoryOpen(false));
        document.addEventListener('click',event=>{if(!queryWrap.contains(event.target))setHistoryOpen(false);});
        refreshRecentMenu();
      }
      let add=document.getElementById('stdManualAdd');
      if(!add){add=document.createElement('button');add.type='button';add.id='stdManualAdd';add.className='std-btn ghost';}
      add.textContent='Nuevo estándar';
      if(add.dataset.lexiaManualHandler!=='1'){
        add.dataset.lexiaManualHandler='1';
        add.addEventListener('click',openManualModal);
      }
      firstGrid.append(...[queryWrap,clear,search,add].filter(Boolean));
    }

    if(search)search.addEventListener('click',()=>saveRecentSearch(),true);

    const results=document.getElementById('stdResults');
    if(results&&['buscando estándares','ingresá criterios'].some(text=>norm(results.textContent).includes(text)))results.replaceChildren();
    installActionRouter();
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
    modal.innerHTML=`<div class="std-modal"><div class="std-modal-head"><h2>Nuevo estándar</h2><button class="std-modal-close" type="button" data-close>✕</button></div><div class="std-manual-grid">
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

  function homeStandardsCard(){
    const card=document.querySelector('#home [data-lexia-standards-home]')||document.querySelector('#home .hr-metrics article[data-home-target="search-fragments"]');
    if(!card)return null;
    if(card.hasAttribute('data-home-target'))card.removeAttribute('data-home-target');
    if(card.dataset.lexiaStandardsHome!=='1')card.dataset.lexiaStandardsHome='1';
    setText(card.querySelector('.hr-mhead b'),'Estándares');
    const count=card.querySelector('#liveStandards')||card.querySelector('#liveFragments')||card.querySelector('strong');
    if(count&&count.id!=='liveStandards')count.id='liveStandards';
    setText(card.querySelector('.hr-line span'),'Disponibles');
    card.querySelector('.hr-line em')?.remove();
    setText(card.querySelector('small'),'Diccionario jurídico');
    setText(card.querySelector('p'),'Jurisprudencia estructurada');
    return card;
  }

  async function updateHomeStandardsCard(){
    try{
      const card=homeStandardsCard();if(!card)return;
      const response=await fetch(API+'/api/stats',{headers:{Accept:'application/json'}});if(!response.ok)return;
      const data=await response.json(),total=Number(data.standards||0);
      setText(card.querySelector('#liveStandards')||card.querySelector('strong'),total.toLocaleString('es-AR'));
    }catch(_){}
  }

  function installHomeCardHandler(){
    if(window.__lexiaStandardsHomeHandler)return;window.__lexiaStandardsHomeHandler=true;
    homeStandardsCard();
    window.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(!target?.closest('#home [data-lexia-standards-home]'))return;
      event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();openStandards();
    },true);
  }

  function installExitHandler(){
    if(window.__lexiaStandardsNativeExit)return;window.__lexiaStandardsNativeExit=true;
    window.addEventListener('click',event=>{const target=event.target instanceof Element?event.target:null;const destination=target&&target.closest('#globalSidebar .nav button');if(destination&&!destination.matches('[data-lexia-standards-nav]'))closeStandards();},true);
  }

  function boot(){
    install();installExitHandler();installHomeCardHandler();installSearchUx();adjustDetail();updateHomeStandardsCard();
    window.addEventListener('resize',syncStandardsInset,{passive:true});
    const observer=new MutationObserver(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();});observer.observe(document.body,{childList:true,subtree:true});
    window.setTimeout(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();},150);
    window.setTimeout(()=>{install();installSearchUx();adjustDetail();updateHomeStandardsCard();},700);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
