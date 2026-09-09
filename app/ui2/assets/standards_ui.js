/* LexIA UI2 — Diccionario de Estándares Jurídicos. */
(function(){
  'use strict';

  const API_PORT=(window.LEXIA_STANDARDS_PORT||'8515');
  const API=`http://127.0.0.1:${API_PORT}`;
  const state={installed:false,open:false,filtersLoaded:false,currentUid:null};
  const RECENT_KEY='lexia_standards_recent_searches_v1';
  let recentMemory=[];
  let recentStorageAvailable=true;
  const relLabels={duplicate_of:'Duplica',specializes:'Especializa',generalizes:'Generaliza',exception_to:'Excepción',related_to:'Relacionado',supports:'Apoya',contradicts:'Contradice'};
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const norm=value=>String(value||'').replace(/\s+/g,' ').trim().toLowerCase();

  function installStyles(){
    if(document.getElementById('lexiaStandardsStyle'))return;
    const style=document.createElement('style');
    style.id='lexiaStandardsStyle';
    style.textContent=`
      :root{--std-brand:#5146f6;--std-brand2:#6258ff;--std-lav:#f0efff;--std-lav2:#f7f5ff;--std-ink:#131a35;--std-muted:#69728e;--std-line:#e4e3f3;--std-panel:#fff}
      #lexiaStandardsShell{position:fixed;z-index:850;top:0;right:0;bottom:0;left:224px;background:#fbfcff;overflow:auto;display:none;color:var(--std-ink)}#lexiaStandardsShell.open{display:block}#lexiaStandardsShell *{box-sizing:border-box}
      .std-wrap{max-width:1320px;margin:0 auto;padding:28px 30px 46px}.std-head{margin-bottom:18px}.std-title{font-size:28px;font-weight:800;letter-spacing:-.02em;margin:0;color:#111936}.std-sub{margin:6px 0 0;color:var(--std-muted);font-size:14px}.std-kicker{display:inline-flex;padding:5px 10px;border-radius:999px;background:var(--std-lav);color:var(--std-brand);font-size:12px;font-weight:800;margin-bottom:8px}
      .std-panel{background:#fff;border:1px solid var(--std-line);border-radius:16px;box-shadow:0 8px 24px rgba(45,36,120,.05)}.std-search{padding:16px;margin-bottom:16px}.std-grid{display:grid;grid-template-columns:minmax(280px,2fr) repeat(3,minmax(150px,1fr));gap:10px}.std-grid.secondary{grid-template-columns:repeat(3,minmax(160px,1fr)) auto auto;margin-top:10px}.std-input,.std-select{width:100%;height:40px;border:1px solid #d8d7e9;border-radius:10px;padding:0 11px;background:white;color:#1a2140;outline:none}.std-input:focus,.std-select:focus{border-color:#8178ff;box-shadow:0 0 0 3px rgba(98,88,255,.12)}
      .std-btn{height:40px;border:0;border-radius:10px;padding:0 16px;background:linear-gradient(135deg,var(--std-brand),var(--std-brand2));color:white;font-weight:750;cursor:pointer;box-shadow:0 5px 14px rgba(81,70,246,.18)}.std-btn.ghost{background:var(--std-lav);color:var(--std-brand);box-shadow:none}.std-btn.secondary{background:#fff;color:#5146f6;border:1px solid #d8d3ff;box-shadow:none}.std-btn.small{height:32px;padding:0 11px;font-size:12px}
      .std-search-status{margin-top:10px;padding:9px 11px;border-radius:9px;background:#f7f5ff;color:#625c7b;font-size:12px;border:1px solid #e9e5ff}.std-search-status.error{background:#fff4f8;color:#7d2a56;border-color:#f0dce6}.std-search-status[hidden]{display:none!important}.std-query-wrap{position:relative;min-width:0}.std-query-wrap #stdQ{padding-right:40px}.std-history-toggle{position:absolute;z-index:2;top:4px;right:5px;width:31px;height:32px;border:0;border-radius:8px;background:transparent;color:#6258d8;font-size:14px;cursor:pointer}.std-history-toggle:hover,.std-history-toggle[aria-expanded="true"]{background:var(--std-lav)}.std-history-menu{position:absolute;z-index:40;top:calc(100% + 6px);left:0;right:0;display:none;max-height:260px;overflow:auto;padding:6px;background:#fff;border:1px solid #d8d3ff;border-radius:11px;box-shadow:0 14px 32px rgba(45,36,120,.16)}.std-history-menu.open{display:grid;gap:3px}.std-history-item{width:100%;border:0;border-radius:8px;padding:9px 10px;background:#fff;color:#252b4b;font:inherit;font-size:12px;line-height:1.35;text-align:left;cursor:pointer}.std-history-item:hover,.std-history-item:focus{background:var(--std-lav);color:var(--std-brand);outline:none}.std-history-empty{padding:9px 10px;color:#7b829b;font-size:12px}
      .std-layout{display:none;grid-template-columns:minmax(0,1.1fr) minmax(390px,.9fr);gap:16px;align-items:start}.std-layout.has-results{display:grid}.std-list,.std-detail{padding:16px}.std-summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:2px 2px 12px;border-bottom:1px solid #ecebf5;margin-bottom:4px}.std-summary-title{font-size:15px;font-weight:800;color:#202846}.std-summary-count{font-size:11px;font-weight:800;color:#5146f6;background:#f0efff;padding:5px 9px;border-radius:999px}
      .std-item{display:grid;grid-template-columns:30px 1fr;gap:10px;padding:14px 12px;border:1px solid transparent;border-bottom-color:#ecebf5;border-radius:10px;cursor:pointer;transition:.14s}.std-item:hover{background:var(--std-lav2);border-color:#e4e0ff}.std-item.active{background:var(--std-lav);border-color:#d8d3ff}.std-number{width:26px;height:26px;border-radius:8px;background:#f0efff;color:#5146f6;display:grid;place-items:center;font-size:11px;font-weight:900}.std-statement{font-size:14px;line-height:1.48;font-weight:700;color:#171d38}.std-meta{margin-top:7px;font-size:11.5px;color:var(--std-muted);display:flex;gap:6px;flex-wrap:wrap}.std-uid{font:10.5px ui-monospace,SFMono-Regular,Consolas,monospace;color:#8a91a8;margin-top:5px}
      .std-empty{padding:30px 10px;text-align:center;color:var(--std-muted)}.std-detail h2{font-size:20px;line-height:1.38;margin:2px 0 8px}.std-detail h3{font-size:13px;text-transform:uppercase;letter-spacing:.055em;color:#555e7d;margin:20px 0 8px}.std-badges{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.std-badge{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#f1f0fb;color:#4f478f;font-size:11px;font-weight:750}.std-badge.proposed{background:#f5f2ff;color:#6b5bcc;border:1px solid #ded8ff}.std-badge.confirmed{background:#edf1ff;color:#4056ae}.std-badge.rel-contradicts{background:#eeeaff;color:#4d3ac3}.std-badge.rel-specializes{background:#edf2ff;color:#3958b7}.std-badge.rel-exception_to{background:#f4efff;color:#6a45a9}.std-badge.rel-supports{background:#eef5ff;color:#4770aa}.std-badge.rel-related_to{background:#f5f3fb;color:#77708f}
      .std-quote{margin:9px 0;padding:12px 13px;border-left:4px solid #8d83ff;border-radius:8px;background:#faf9ff;font-size:13px;line-height:1.48}.std-relation{padding:10px 0;border-bottom:1px solid #eeedf6}.std-rel-title{font-size:13px;line-height:1.4;margin-top:5px;cursor:pointer}.std-rel-title:hover{color:var(--std-brand)}.std-doc{padding:10px 12px;border-radius:10px;background:#fafaff;border:1px solid #eceaff;font-size:12px;line-height:1.5}.std-doc-link{appearance:none;border:0;background:none;padding:0;color:#5146f6;text-decoration:underline;font:inherit;font-weight:800;cursor:pointer;text-align:left}.std-notice{padding:10px 12px;border-radius:10px;background:#f7f5ff;color:#625c7b;font-size:12px;border:1px solid #e9e5ff;margin-bottom:12px}.std-error{padding:18px;color:#7d2a56;background:#fff4f8;border:1px solid #f0dce6;border-radius:12px}
      .std-occurrences{display:grid;gap:10px}.std-occurrence{padding:12px;border:1px solid #e7e5f3;border-radius:12px;background:#fcfcff}.std-occurrence-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.std-wording{margin:9px 0 2px;font-size:12.5px;line-height:1.45;color:#353d5d}.std-wording b{color:#202846}.std-source-count{white-space:nowrap;background:#edf1ff;color:#4056ae;border-radius:999px;padding:4px 8px;font-size:10.5px;font-weight:800}.std-suggestion{padding:11px 12px;margin-top:8px;border:1px dashed #cfc8ff;border-radius:11px;background:#faf8ff}.std-suggestion .std-rel-title{font-weight:700}
      .std-modal-backdrop{position:fixed;z-index:2000;inset:0;background:rgba(21,24,48,.38);display:grid;place-items:center;padding:28px}.std-modal{width:min(980px,94vw);max-height:88vh;overflow:auto;background:#fff;border:1px solid #dedcf0;border-radius:18px;box-shadow:0 24px 70px rgba(24,20,68,.24)}.std-modal-head{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;background:#fff;border-bottom:1px solid #ecebf5}.std-modal-head h2{margin:0;font-size:18px}.std-modal-close{border:0;background:#f0efff;color:#5146f6;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}.std-graph-body{padding:16px}.std-graph-nodes{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:16px}.std-graph-node{border:1px solid #dedcf0;background:#faf9ff;border-radius:12px;padding:11px;cursor:pointer;text-align:left}.std-graph-node:hover{border-color:#8178ff;background:#f4f1ff}.std-graph-node.root{box-shadow:inset 0 0 0 2px #8178ff}.std-graph-node b{display:block;font-size:12px;line-height:1.35;color:#202846}.std-graph-node small{display:block;margin-top:6px;color:#747d99}.std-graph-edge{padding:10px 0;border-top:1px solid #ecebf5}.std-graph-edge-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.std-graph-link{border:0;background:none;padding:0;color:#5146f6;font-weight:750;cursor:pointer;text-decoration:underline;text-align:left}.std-graph-arrow{color:#8b91a8}
      @media(max-width:1100px){#lexiaStandardsShell{left:0;top:54px}.std-layout{grid-template-columns:1fr}.std-grid{grid-template-columns:1fr 1fr}.std-grid.secondary{grid-template-columns:1fr 1fr}.std-wrap{padding:18px}}@media(max-width:680px){.std-grid,.std-grid.secondary{grid-template-columns:1fr}.std-title{font-size:23px}.std-wrap{padding:12px}.std-list,.std-detail,.std-search{padding:12px}}
    `;
    document.head.appendChild(style);
  }

  async function api(path,options={}){const headers={Accept:'application/json',...(options.headers||{})};const response=await fetch(API+path,{cache:'no-store',...options,headers});if(!response.ok){let msg=`HTTP ${response.status}`;try{const data=await response.json();if(data.error)msg=data.error;}catch(_){}throw new Error(msg);}return response.json();}
  async function canonicalDecision(relationId,decision,uid){const action=decision==='confirm'?'confirmar que ambas formulaciones expresan la misma regla':'rechazar esta equivalencia';if(!window.confirm(`¿Querés ${action}?`))return;try{await api('/api/canonical-decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({relation_id:Number(relationId),decision})});await search();await detail(uid);}catch(error){alert('No fue posible registrar la decisión: '+error.message);}}
  function shell(){
    let node=document.getElementById('lexiaStandardsShell');if(node)return node;
    node=document.createElement('section');node.id='lexiaStandardsShell';node.dataset.lexiaNativeSearch='2';node.setAttribute('aria-label','Estándares jurídicos');
    node.innerHTML=`<div class="std-wrap"><div class="std-head"><div><div class="std-kicker">LEXIA · JURISPRUDENCIA ESTRUCTURADA</div><h1 class="std-title">Estándares jurídicos</h1><p class="std-sub">Reglas extraídas de jurisprudencia con cita literal, voz judicial y relaciones jurídicas trazables.</p></div></div><div class="std-panel std-search"><div class="std-grid"><div class="std-query-wrap"><input class="std-input" id="stdQ" placeholder="Buscar estándar por texto jurídico…" aria-haspopup="listbox" aria-expanded="false"><button class="std-history-toggle" id="stdHistoryToggle" type="button" aria-label="Mostrar últimas búsquedas" aria-haspopup="listbox" aria-expanded="false">▾</button><div class="std-history-menu" id="stdHistoryMenu" role="listbox"></div></div><select class="std-select" id="stdCourt"><option value="">Todos los tribunales</option></select><select class="std-select" id="stdSpeaker"><option value="">Todas las voces</option></select><select class="std-select" id="stdTreatment"><option value="">Todos los tratamientos</option></select></div><div class="std-grid secondary"><input class="std-input" id="stdFrom" placeholder="Fecha desde"><input class="std-input" id="stdTo" placeholder="Fecha hasta"><input class="std-input" id="stdTag" placeholder="Tag"><button class="std-btn secondary" id="stdClear" type="button">Limpiar</button><button class="std-btn" id="stdSearch" type="button">Buscar</button></div><div id="stdSearchStatus" class="std-search-status" hidden></div></div><div class="std-layout" id="stdLayout"><section class="std-panel std-list"><div id="stdSummary" class="std-summary"></div><div id="stdResults"></div></section><section class="std-panel std-detail"><div id="stdDetail"><div class="std-notice">Seleccioná un estándar para ver la cita literal, el documento fuente y sus relaciones.</div></div></section></div></div>`;
    document.body.appendChild(node);
    const query=node.querySelector('#stdQ'),toggle=node.querySelector('#stdHistoryToggle'),searchButton=node.querySelector('#stdSearch');
    let lastPointerSearchAt=0;
    searchButton.addEventListener('pointerdown',event=>{if(event.button!==undefined&&event.button!==0)return;event.preventDefault();event.stopPropagation();lastPointerSearchAt=Date.now();search();});
    searchButton.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(Date.now()-lastPointerSearchAt<700)return;search();});
    node.querySelector('#stdClear').addEventListener('click',event=>{event.preventDefault();event.stopPropagation();resetSearch();});
    query.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();event.stopPropagation();search();}});
    query.addEventListener('click',event=>{event.stopPropagation();toggleRecentMenu();});
    query.addEventListener('input',()=>setRecentMenuOpen(false));
    toggle.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();toggleRecentMenu();});
    ['stdFrom','stdTo'].forEach(id=>{const field=node.querySelector('#'+id);field?.addEventListener('input',()=>{field.dataset.lexiaUserEdited='1';});field?.addEventListener('change',()=>{field.dataset.lexiaUserEdited='1';});});
    refreshRecentMenu();
    return node;
  }

  function fillSelect(id,values){const select=document.getElementById(id);if(!select)return;for(const value of values||[]){if([...select.options].some(o=>o.value===value))continue;const option=document.createElement('option');option.value=value;option.textContent=value;select.appendChild(option);}}

  function readCriteria(){
    const node=shell(),ids={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'},criteria={};
    for(const [key,id] of Object.entries(ids)){const field=node.querySelector('#'+id);if((id==='stdFrom'||id==='stdTo')&&field?.dataset.lexiaUserEdited!=='1')continue;const value=String(field?.value||'').trim();if(value)criteria[key]=value;}
    return criteria;
  }
  function recentSearches(){
    if(!recentStorageAvailable)return recentMemory;
    try{const parsed=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');if(Array.isArray(parsed)){recentMemory=parsed;return parsed;}}
    catch(_){recentStorageAvailable=false;}
    return recentMemory;
  }
  function criteriaLabel(criteria){return [criteria.q,criteria.court,criteria.speaker,criteria.treatment,criteria.from&&('desde '+criteria.from),criteria.to&&('hasta '+criteria.to),criteria.tag&&('#'+criteria.tag)].filter(Boolean).join(' · ')||'Todos los estándares';}
  function saveRecentSearch(criteria=readCriteria()){
    const signature=JSON.stringify(criteria),items=recentSearches().filter(item=>JSON.stringify(item.criteria||{})!==signature);
    items.unshift({label:criteriaLabel(criteria),criteria,at:Date.now()});recentMemory=items.slice(0,12);
    if(recentStorageAvailable){try{localStorage.setItem(RECENT_KEY,JSON.stringify(recentMemory));}catch(_){recentStorageAvailable=false;}}
    refreshRecentMenu();
  }
  function setRecentMenuOpen(open){
    const node=shell(),menu=node.querySelector('#stdHistoryMenu'),expanded=Boolean(open);
    menu?.classList.toggle('open',expanded);node.querySelector('#stdQ')?.setAttribute('aria-expanded',String(expanded));node.querySelector('#stdHistoryToggle')?.setAttribute('aria-expanded',String(expanded));
  }
  function toggleRecentMenu(){refreshRecentMenu();setRecentMenuOpen(!shell().querySelector('#stdHistoryMenu')?.classList.contains('open'));}
  function applyRecentSearch(index){
    const item=recentSearches()[Number(index)];if(!item)return;
    const ids={q:'stdQ',court:'stdCourt',speaker:'stdSpeaker',treatment:'stdTreatment',from:'stdFrom',to:'stdTo',tag:'stdTag'},node=shell();
    Object.values(ids).forEach(id=>{const field=node.querySelector('#'+id);if(field){field.value='';delete field.dataset.lexiaUserEdited;}});
    for(const [key,value] of Object.entries(item.criteria||{})){const field=node.querySelector('#'+ids[key]);if(field){field.value=String(value||'');if(key==='from'||key==='to')field.dataset.lexiaUserEdited='1';}}
    setRecentMenuOpen(false);search();
  }
  function refreshRecentMenu(){
    const menu=document.getElementById('stdHistoryMenu');if(!menu)return;menu.replaceChildren();
    const items=recentSearches();
    if(!items.length){const empty=document.createElement('div');empty.className='std-history-empty';empty.textContent='Sin búsquedas recientes';menu.appendChild(empty);return;}
    items.forEach((item,index)=>{const button=document.createElement('button');button.type='button';button.className='std-history-item';button.dataset.recentIndex=String(index);button.setAttribute('role','option');button.textContent=String(item.label||criteriaLabel(item.criteria||{}));button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();applyRecentSearch(index);});menu.appendChild(button);});
  }

  function resetSearch(){
    const node=shell();
    ['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'].forEach(id=>{const field=node.querySelector('#'+id);if(field){field.value='';delete field.dataset.lexiaUserEdited;}});
    state.currentUid=null;
    node.querySelector('#stdSummary')?.replaceChildren();
    node.querySelector('#stdResults')?.replaceChildren();
    node.querySelector('#stdLayout')?.classList.remove('has-results');node.querySelector('#stdLayout')?.style.removeProperty('display');
    const status=node.querySelector('#stdSearchStatus');if(status){status.hidden=true;status.classList.remove('error');status.textContent='';}
    const detail=node.querySelector('#stdDetail');
    if(detail)detail.innerHTML='<div class="std-notice">Seleccioná un estándar para ver la cita literal, el documento fuente y sus relaciones.</div>';
    document.getElementById('stdHistoryMenu')?.classList.remove('open');
    node.querySelector('#stdQ')?.setAttribute('aria-expanded','false');
    document.getElementById('stdHistoryToggle')?.setAttribute('aria-expanded','false');
  }

  async function search(){
    const node=shell(),p=new URLSearchParams();
    const map=[['stdQ','q'],['stdCourt','court'],['stdSpeaker','speaker'],['stdTreatment','treatment'],['stdFrom','from'],['stdTo','to'],['stdTag','tag']];
    for(const [id,key] of map){const field=node.querySelector('#'+id);if((id==='stdFrom'||id==='stdTo')&&field?.dataset.lexiaUserEdited!=='1')continue;const value=String(field?.value||'').trim();if(value)p.set(key,value);}p.set('limit','200');
    saveRecentSearch();setRecentMenuOpen(false);
    const layout=node.querySelector('#stdLayout'),status=node.querySelector('#stdSearchStatus'),results=node.querySelector('#stdResults');
    layout?.classList.remove('has-results');layout?.style.removeProperty('display');node.querySelector('#stdSummary')?.replaceChildren();results.replaceChildren();
    if(status){status.hidden=false;status.classList.remove('error');status.textContent='Buscando estándares…';}
    try{
      const data=await api('/api/search?'+p.toString()),items=Array.isArray(data.items)?data.items:[],total=Number(data.total||0);
      if(!state.filtersLoaded&&data.filters){fillSelect('stdCourt',data.filters.courts);fillSelect('stdSpeaker',data.filters.speakers);fillSelect('stdTreatment',data.filters.treatments);state.filtersLoaded=true;}
      if(!items.length){if(status)status.textContent='No se encontraron estándares con esos filtros.';return;}
      if(status){status.hidden=true;status.textContent='';}layout?.classList.add('has-results');layout?.style.setProperty('display','grid','important');
      node.querySelector('#stdSummary').innerHTML=`<div><div class="std-summary-title">Resultados</div><div class="std-meta">Estándares jurídicos que coinciden con la consulta actual</div></div><span class="std-summary-count">${total} ${total===1?'estándar':'estándares'}</span>`;
      results.innerHTML=items.map((item,index)=>{const sourceMeta=Number(item.occurrence_count||0)>1?`${Number(item.document_count||0)} fallos · ${Number(item.occurrence_count||0)} apariciones`:`${esc(item.court||'Tribunal no informado')} · ${esc(item.judgment_date||'')} · ${esc(item.speaker)} · ${esc(item.treatment)}`;return `<article class="std-item" data-uid="${esc(item.canonical_uid||item.standard_uid)}"><div class="std-number">${index+1}</div><div><div class="std-statement">${esc(item.statement)}</div><div class="std-meta"><span>${sourceMeta}</span></div><div class="std-uid">${esc(item.canonical_uid||item.standard_uid)}</div></div></article>`;}).join('');
      results.querySelectorAll('.std-item').forEach(item=>item.addEventListener('click',()=>detail(item.dataset.uid)));
    }catch(error){if(status){status.hidden=false;status.classList.add('error');status.textContent='No fue posible consultar el diccionario. '+String(error.message||error);}}
  }

  async function openDocument(uid){try{await api('/api/open-document?uid='+encodeURIComponent(uid));}catch(error){alert(error.message==='document_not_found'?'No se encontró el archivo fuente en esta computadora.':'No fue posible abrir el documento fuente: '+error.message);}}

  async function detail(uid){
    state.currentUid=uid;document.querySelectorAll('.std-item').forEach(item=>item.classList.toggle('active',item.dataset.uid===uid));
    const target=document.getElementById('stdDetail');if(!target)return;target.innerHTML='<div class="std-empty">Cargando estándar…</div>';
    try{
      const data=await api('/api/standard?uid='+encodeURIComponent(uid));if(!data){target.innerHTML='<div class="std-empty">Estándar no encontrado.</div>';return;}
      const renderQuotes=quotes=>(quotes||[]).map(q=>`<div class="std-quote">${esc(q.quote_text)}<div class="std-meta">Página ${esc(q.page_start||'—')}${q.page_end&&q.page_end!==q.page_start?'–'+esc(q.page_end):''} · ${esc(q.validation||'')}</div></div>`).join('')||'<div class="std-empty">Sin citas registradas.</div>';
      const occurrences=(data.occurrences||[data]).map((occ,index)=>{const different=norm(occ.statement)!==norm(data.statement);return `<article class="std-occurrence"><div class="std-occurrence-head"><div><button class="std-doc-link" data-open-occurrence="${esc(occ.standard_uid)}">${esc(occ.document_name||'Documento fuente')}</button><div class="std-meta">${esc(occ.court||'Tribunal no informado')}${occ.judgment_date?' · '+esc(occ.judgment_date):''} · ${esc(occ.speaker||'')} · ${esc(occ.treatment||'')}</div></div><span class="std-source-count">Fuente ${index+1}</span></div>${different?`<div class="std-wording"><b>Formulación del fallo:</b> ${esc(occ.statement)}</div>`:''}${renderQuotes(occ.quotes)}</article>`;}).join('');
      const relations=(data.relations||[]).map(rel=>{const count=Number(rel.other?.document_count||0);return `<div class="std-relation"><div><span class="std-badge rel-${esc(rel.relation_type)}">${esc(relLabels[rel.relation_type]||rel.relation_type)}</span><span class="std-badge ${esc(rel.status)}">${esc(rel.status)}</span></div><div class="std-rel-title" data-related-uid="${esc(rel.other?.standard_uid||'')}">${esc(rel.other?.statement||'')}</div><div class="std-meta">${count>1?count+' fallos':esc(rel.other?.document_name||'')} · ${esc(rel.other?.speaker||'')}</div></div>`;}).join('')||'<div class="std-empty">Sin relaciones visibles.</div>';
      const suggestions=(data.canonical_suggestions||[]).map(item=>`<div class="std-suggestion"><div><span class="std-badge proposed">Posible misma regla</span>${item.confidence?`<span class="std-badge">Confianza ${esc(item.confidence)}</span>`:''}</div><div class="std-rel-title" data-related-uid="${esc(item.other?.standard_uid||'')}">${esc(item.other?.statement||'')}</div><div class="std-meta">Requiere confirmación antes de consolidarse.</div><div class="std-badges"><button class="std-btn small" data-confirm-relation="${esc(item.relation_id)}">Confirmar</button><button class="std-btn ghost small" data-reject-relation="${esc(item.relation_id)}">Rechazar</button></div></div>`).join('');
      const occurrenceCount=Number(data.occurrence_count||1),documentCount=Number(data.document_count||1);const notice=occurrenceCount>1?`Estándar canónico confirmado: ${occurrenceCount} apariciones en ${documentCount} fallos, conservadas con su propia redacción y cita.`:'Estándar canónico con una aparición validada. Las nuevas equivalencias se agregarán sin perder su fallo ni su redacción.';
      target.innerHTML=`<div class="std-notice">${esc(notice)}</div><h2>${esc(data.statement)}</h2><div class="std-badges"><span class="std-badge confirmed">Canónico confirmado</span><span class="std-badge">${documentCount} ${documentCount===1?'fallo':'fallos'}</span>${(data.tags||[]).map(tag=>`<span class="std-badge">${esc(tag)}</span>`).join('')}</div><div class="std-uid">${esc(data.canonical_uid||data.standard_uid)}</div><h3>Fallos, formulaciones y citas</h3><div class="std-occurrences">${occurrences}</div>${suggestions?`<h3>Equivalencias pendientes</h3>${suggestions}`:''}<h3>Relaciones con otros estándares</h3>${relations}<div style="margin-top:12px"><button class="std-btn ghost small" id="stdGraphBtn">Ver grafo</button></div>`;
      target.querySelectorAll('[data-related-uid]').forEach(node=>node.addEventListener('click',()=>detail(node.dataset.relatedUid)));
      target.querySelectorAll('[data-open-occurrence]').forEach(node=>node.addEventListener('click',()=>openDocument(node.dataset.openOccurrence)));
      target.querySelectorAll('[data-confirm-relation]').forEach(node=>node.addEventListener('click',event=>{event.stopPropagation();canonicalDecision(node.dataset.confirmRelation,'confirm',uid);}));
      target.querySelectorAll('[data-reject-relation]').forEach(node=>node.addEventListener('click',event=>{event.stopPropagation();canonicalDecision(node.dataset.rejectRelation,'reject',uid);}));
      target.querySelector('#stdGraphBtn')?.addEventListener('click',()=>openGraph(uid));
    }catch(error){target.innerHTML=`<div class="std-error">No fue posible abrir el estándar. ${esc(error.message)}</div>`;}
  }

  async function openGraph(uid){
    closeGraph();
    const backdrop=document.createElement('div');backdrop.className='std-modal-backdrop';backdrop.id='stdGraphModal';backdrop.innerHTML='<div class="std-modal"><div class="std-modal-head"><h2>Grafo de relaciones</h2><button class="std-modal-close">Cerrar</button></div><div class="std-graph-body"><div class="std-empty">Cargando grafo…</div></div></div>';document.body.appendChild(backdrop);
    backdrop.querySelector('.std-modal-close').addEventListener('click',closeGraph);backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeGraph();});
    try{
      const data=await api('/api/graph?uid='+encodeURIComponent(uid)+'&depth=2');const body=backdrop.querySelector('.std-graph-body');const nodes=data.nodes||[],edges=data.edges||[];const byId=new Map(nodes.map(n=>[n.standard_uid,n]));
      const nodesHtml=nodes.map(n=>`<button class="std-graph-node ${n.standard_uid===(data.root||uid)?'root':''}" data-graph-uid="${esc(n.standard_uid)}"><b>${esc(n.statement||n.standard_uid)}</b><small>${Number(n.document_count||0)>1?Number(n.document_count)+' fallos':esc(n.document_name||'')+(n.court?' · '+esc(n.court):'')}</small></button>`).join('');
      const edgesHtml=edges.map(e=>{const a=byId.get(e.from)||{},b=byId.get(e.to)||{};return `<div class="std-graph-edge"><div class="std-graph-edge-row"><button class="std-graph-link" data-graph-uid="${esc(e.from)}">${esc(a.statement||e.from)}</button><span class="std-graph-arrow">→</span><span class="std-badge rel-${esc(e.relation_type)}">${esc(relLabels[e.relation_type]||e.relation_type)}</span><span class="std-badge ${esc(e.status)}">${esc(e.status)}</span><span class="std-graph-arrow">→</span><button class="std-graph-link" data-graph-uid="${esc(e.to)}">${esc(b.statement||e.to)}</button></div></div>`;}).join('');
      body.innerHTML=`<div class="std-graph-nodes">${nodesHtml||'<div class="std-empty">Sin nodos visibles.</div>'}</div><div>${edgesHtml||'<div class="std-empty">Sin relaciones visibles.</div>'}</div>`;
      body.querySelectorAll('[data-graph-uid]').forEach(el=>el.addEventListener('click',()=>{const targetUid=el.dataset.graphUid;closeGraph();detail(targetUid);document.getElementById('stdDetail')?.scrollIntoView({behavior:'smooth',block:'start'});}));
    }catch(error){backdrop.querySelector('.std-graph-body').innerHTML=`<div class="std-error">No fue posible cargar el grafo. ${esc(error.message)}</div>`;}
  }
  function closeGraph(){document.getElementById('stdGraphModal')?.remove();}

  function findMaintenanceNav(){const candidates=[...document.querySelectorAll('button,a,[role="button"],li,div')];return candidates.find(node=>norm(node.textContent)==='mantenimiento'&&node.children.length<8)||null;}
  function installNav(){if(document.querySelector('[data-lexia-standards-nav="1"]'))return true;const maintenance=findMaintenanceNav();if(!maintenance)return false;const button=maintenance.cloneNode(true);button.dataset.lexiaStandardsNav='1';button.removeAttribute('id');button.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));const walker=document.createTreeWalker(button,NodeFilter.SHOW_TEXT);let textNode=null;while(walker.nextNode()){if(norm(walker.currentNode.nodeValue)==='mantenimiento'){textNode=walker.currentNode;break;}}if(textNode)textNode.nodeValue=textNode.nodeValue.replace(/Mantenimiento/i,'Estándares');else button.textContent='Estándares';button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();open();},true);maintenance.parentNode.insertBefore(button,maintenance);return true;}
  function setNavActive(active){const nav=document.querySelector('[data-lexia-standards-nav="1"]');if(!nav)return;nav.classList.toggle('active',active);nav.setAttribute('aria-current',active?'page':'false');}
  function open(){state.open=true;setNavActive(true);shell().classList.add('open');}
  function close(){if(!state.open)return;state.open=false;setNavActive(false);closeGraph();document.getElementById('lexiaStandardsShell')?.classList.remove('open');}
  function watchOtherNavigation(){document.addEventListener('click',event=>{if(!state.open)return;const nav=event.target.closest?.('#globalSidebar .nav button,.sidebar .nav button');if(!nav||nav.matches('[data-lexia-standards-nav="1"]'))return;close();},true);}
  function boot(){installStyles();shell();installNav();watchOtherNavigation();document.addEventListener('click',event=>{if(!event.target.closest?.('#lexiaStandardsShell .std-query-wrap'))setRecentMenuOpen(false);});if(!state.installed){state.installed=true;const observer=new MutationObserver(()=>installNav());observer.observe(document.body,{childList:true,subtree:true});}}
  window.lexiaStandardsSearch=search;window.lexiaStandardsResetSearch=resetSearch;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
