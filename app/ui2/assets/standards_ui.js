/* LexIA UI2 — Diccionario de Estándares Jurídicos. */
(function(){
  'use strict';

  const API_PORT=(window.LEXIA_STANDARDS_PORT||'8515');
  const API=`http://127.0.0.1:${API_PORT}`;
  const state={installed:false,open:false,filtersLoaded:false,currentUid:null};
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
      .std-search-status{margin-top:10px;padding:9px 11px;border-radius:9px;background:#f7f5ff;color:#625c7b;font-size:12px;border:1px solid #e9e5ff}.std-search-status.error{background:#fff4f8;color:#7d2a56;border-color:#f0dce6}.std-search-status[hidden]{display:none!important}
      .std-layout{display:none;grid-template-columns:minmax(0,1.1fr) minmax(390px,.9fr);gap:16px;align-items:start}.std-layout.has-results{display:grid}.std-list,.std-detail{padding:16px}.std-summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:2px 2px 12px;border-bottom:1px solid #ecebf5;margin-bottom:4px}.std-summary-title{font-size:15px;font-weight:800;color:#202846}.std-summary-count{font-size:11px;font-weight:800;color:#5146f6;background:#f0efff;padding:5px 9px;border-radius:999px}
      .std-item{display:grid;grid-template-columns:30px 1fr;gap:10px;padding:14px 12px;border:1px solid transparent;border-bottom-color:#ecebf5;border-radius:10px;cursor:pointer;transition:.14s}.std-item:hover{background:var(--std-lav2);border-color:#e4e0ff}.std-item.active{background:var(--std-lav);border-color:#d8d3ff}.std-number{width:26px;height:26px;border-radius:8px;background:#f0efff;color:#5146f6;display:grid;place-items:center;font-size:11px;font-weight:900}.std-statement{font-size:14px;line-height:1.48;font-weight:700;color:#171d38}.std-meta{margin-top:7px;font-size:11.5px;color:var(--std-muted);display:flex;gap:6px;flex-wrap:wrap}.std-uid{font:10.5px ui-monospace,SFMono-Regular,Consolas,monospace;color:#8a91a8;margin-top:5px}
      .std-empty{padding:30px 10px;text-align:center;color:var(--std-muted)}.std-detail h2{font-size:20px;line-height:1.38;margin:2px 0 8px}.std-detail h3{font-size:13px;text-transform:uppercase;letter-spacing:.055em;color:#555e7d;margin:20px 0 8px}.std-badges{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.std-badge{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#f1f0fb;color:#4f478f;font-size:11px;font-weight:750}.std-badge.proposed{background:#f5f2ff;color:#6b5bcc;border:1px solid #ded8ff}.std-badge.confirmed{background:#edf1ff;color:#4056ae}.std-badge.rel-contradicts{background:#eeeaff;color:#4d3ac3}.std-badge.rel-specializes{background:#edf2ff;color:#3958b7}.std-badge.rel-exception_to{background:#f4efff;color:#6a45a9}.std-badge.rel-supports{background:#eef5ff;color:#4770aa}.std-badge.rel-related_to{background:#f5f3fb;color:#77708f}
      .std-quote{margin:9px 0;padding:12px 13px;border-left:4px solid #8d83ff;border-radius:8px;background:#faf9ff;font-size:13px;line-height:1.48}.std-relation{padding:10px 0;border-bottom:1px solid #eeedf6}.std-rel-title{font-size:13px;line-height:1.4;margin-top:5px;cursor:pointer}.std-rel-title:hover{color:var(--std-brand)}.std-doc{padding:10px 12px;border-radius:10px;background:#fafaff;border:1px solid #eceaff;font-size:12px;line-height:1.5}.std-doc-link{appearance:none;border:0;background:none;padding:0;color:#5146f6;text-decoration:underline;font:inherit;font-weight:800;cursor:pointer;text-align:left}.std-notice{padding:10px 12px;border-radius:10px;background:#f7f5ff;color:#625c7b;font-size:12px;border:1px solid #e9e5ff;margin-bottom:12px}.std-error{padding:18px;color:#7d2a56;background:#fff4f8;border:1px solid #f0dce6;border-radius:12px}
      .std-modal-backdrop{position:fixed;z-index:2000;inset:0;background:rgba(21,24,48,.38);display:grid;place-items:center;padding:28px}.std-modal{width:min(980px,94vw);max-height:88vh;overflow:auto;background:#fff;border:1px solid #dedcf0;border-radius:18px;box-shadow:0 24px 70px rgba(24,20,68,.24)}.std-modal-head{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;background:#fff;border-bottom:1px solid #ecebf5}.std-modal-head h2{margin:0;font-size:18px}.std-modal-close{border:0;background:#f0efff;color:#5146f6;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}.std-graph-body{padding:16px}.std-graph-nodes{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:16px}.std-graph-node{border:1px solid #dedcf0;background:#faf9ff;border-radius:12px;padding:11px;cursor:pointer;text-align:left}.std-graph-node:hover{border-color:#8178ff;background:#f4f1ff}.std-graph-node.root{box-shadow:inset 0 0 0 2px #8178ff}.std-graph-node b{display:block;font-size:12px;line-height:1.35;color:#202846}.std-graph-node small{display:block;margin-top:6px;color:#747d99}.std-graph-edge{padding:10px 0;border-top:1px solid #ecebf5}.std-graph-edge-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.std-graph-link{border:0;background:none;padding:0;color:#5146f6;font-weight:750;cursor:pointer;text-decoration:underline;text-align:left}.std-graph-arrow{color:#8b91a8}
      @media(max-width:1100px){#lexiaStandardsShell{left:0;top:54px}.std-layout{grid-template-columns:1fr}.std-grid{grid-template-columns:1fr 1fr}.std-grid.secondary{grid-template-columns:1fr 1fr}.std-wrap{padding:18px}}@media(max-width:680px){.std-grid,.std-grid.secondary{grid-template-columns:1fr}.std-title{font-size:23px}.std-wrap{padding:12px}.std-list,.std-detail,.std-search{padding:12px}}
    `;
    document.head.appendChild(style);
  }

  async function api(path){const response=await fetch(API+path,{headers:{Accept:'application/json'}});if(!response.ok){let msg=`HTTP ${response.status}`;try{const data=await response.json();if(data.error)msg=data.error;}catch(_){}throw new Error(msg);}return response.json();}
  function shell(){
    let node=document.getElementById('lexiaStandardsShell');if(node)return node;
    node=document.createElement('section');node.id='lexiaStandardsShell';node.setAttribute('aria-label','Estándares jurídicos');
    node.innerHTML=`<div class="std-wrap"><div class="std-head"><div><div class="std-kicker">LEXIA · JURISPRUDENCIA ESTRUCTURADA</div><h1 class="std-title">Estándares jurídicos</h1><p class="std-sub">Reglas extraídas de jurisprudencia con cita literal, voz judicial y relaciones jurídicas trazables.</p></div></div><div class="std-panel std-search"><div class="std-grid"><input class="std-input" id="stdQ" placeholder="Buscar estándar por texto jurídico…"><select class="std-select" id="stdCourt"><option value="">Todos los tribunales</option></select><select class="std-select" id="stdSpeaker"><option value="">Todas las voces</option></select><select class="std-select" id="stdTreatment"><option value="">Todos los tratamientos</option></select></div><div class="std-grid secondary"><input class="std-input" id="stdFrom" placeholder="Fecha desde"><input class="std-input" id="stdTo" placeholder="Fecha hasta"><input class="std-input" id="stdTag" placeholder="Tag"><button class="std-btn secondary" id="stdClear" type="button">Limpiar</button><button class="std-btn" id="stdSearch" type="button">Buscar</button></div><div id="stdSearchStatus" class="std-search-status" hidden></div></div><div class="std-layout" id="stdLayout"><section class="std-panel std-list"><div id="stdSummary" class="std-summary"></div><div id="stdResults"></div></section><section class="std-panel std-detail"><div id="stdDetail"><div class="std-notice">Seleccioná un estándar para ver la cita literal, el documento fuente y sus relaciones.</div></div></section></div></div>`;
    document.body.appendChild(node);
    node.querySelector('#stdSearch').addEventListener('click',event=>{event.preventDefault();search();});
    node.querySelector('#stdClear').addEventListener('click',event=>{event.preventDefault();resetSearch();});
    node.querySelector('#stdQ').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();search();}});
    return node;
  }

  function fillSelect(id,values){const select=document.getElementById(id);if(!select)return;for(const value of values||[]){if([...select.options].some(o=>o.value===value))continue;const option=document.createElement('option');option.value=value;option.textContent=value;select.appendChild(option);}}

  function resetSearch(){
    const node=shell();
    ['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'].forEach(id=>{const field=node.querySelector('#'+id);if(field)field.value='';});
    state.currentUid=null;
    node.querySelector('#stdSummary')?.replaceChildren();
    node.querySelector('#stdResults')?.replaceChildren();
    node.querySelector('#stdLayout')?.classList.remove('has-results');
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
    for(const [id,key] of map){const value=String(node.querySelector('#'+id)?.value||'').trim();if(value)p.set(key,value);}p.set('limit','200');
    document.getElementById('stdHistoryMenu')?.classList.remove('open');
    node.querySelector('#stdQ')?.setAttribute('aria-expanded','false');
    document.getElementById('stdHistoryToggle')?.setAttribute('aria-expanded','false');
    const layout=node.querySelector('#stdLayout'),status=node.querySelector('#stdSearchStatus'),results=node.querySelector('#stdResults');
    layout?.classList.remove('has-results');node.querySelector('#stdSummary')?.replaceChildren();results.replaceChildren();
    if(status){status.hidden=false;status.classList.remove('error');status.textContent='Buscando estándares…';}
    try{
      const data=await api('/api/search?'+p.toString()),items=Array.isArray(data.items)?data.items:[],total=Number(data.total||0);
      if(!state.filtersLoaded&&data.filters){fillSelect('stdCourt',data.filters.courts);fillSelect('stdSpeaker',data.filters.speakers);fillSelect('stdTreatment',data.filters.treatments);state.filtersLoaded=true;}
      if(!items.length){if(status)status.textContent='No se encontraron estándares con esos filtros.';return;}
      if(status){status.hidden=true;status.textContent='';}layout?.classList.add('has-results');
      node.querySelector('#stdSummary').innerHTML=`<div><div class="std-summary-title">Resultados</div><div class="std-meta">Estándares jurídicos que coinciden con la consulta actual</div></div><span class="std-summary-count">${total} ${total===1?'estándar':'estándares'}</span>`;
      results.innerHTML=items.map((item,index)=>`<article class="std-item" data-uid="${esc(item.standard_uid)}"><div class="std-number">${index+1}</div><div><div class="std-statement">${esc(item.statement)}</div><div class="std-meta"><span>${esc(item.court||'Tribunal no informado')}</span><span>·</span><span>${esc(item.judgment_date||'')}</span><span>·</span><span>${esc(item.speaker)}</span><span>·</span><span>${esc(item.treatment)}</span></div><div class="std-uid">${esc(item.standard_uid)}</div></div></article>`).join('');
      results.querySelectorAll('.std-item').forEach(item=>item.addEventListener('click',()=>detail(item.dataset.uid)));
    }catch(error){if(status){status.hidden=false;status.classList.add('error');status.textContent='No fue posible consultar el diccionario. '+String(error.message||error);}}
  }

  async function openDocument(uid){try{await api('/api/open-document?uid='+encodeURIComponent(uid));}catch(error){alert(error.message==='document_not_found'?'No se encontró el archivo fuente en esta computadora.':'No fue posible abrir el documento fuente: '+error.message);}}

  async function detail(uid){
    state.currentUid=uid;document.querySelectorAll('.std-item').forEach(item=>item.classList.toggle('active',item.dataset.uid===uid));
    const target=document.getElementById('stdDetail');if(!target)return;target.innerHTML='<div class="std-empty">Cargando estándar…</div>';
    try{
      const data=await api('/api/standard?uid='+encodeURIComponent(uid));if(!data){target.innerHTML='<div class="std-empty">Estándar no encontrado.</div>';return;}
      const quotes=(data.quotes||[]).map(q=>`<div class="std-quote">${esc(q.quote_text)}<div class="std-meta">Página ${esc(q.page_start||'—')}${q.page_end&&q.page_end!==q.page_start?'–'+esc(q.page_end):''} · ${esc(q.validation||'')}</div></div>`).join('')||'<div class="std-empty">Sin citas registradas.</div>';
      const relations=(data.relations||[]).map(rel=>`<div class="std-relation"><div><span class="std-badge rel-${esc(rel.relation_type)}">${esc(relLabels[rel.relation_type]||rel.relation_type)}</span><span class="std-badge ${esc(rel.status)}">${esc(rel.status)}</span></div><div class="std-rel-title" data-related-uid="${esc(rel.other?.standard_uid||'')}">${esc(rel.other?.statement||'')}</div><div class="std-meta">${esc(rel.other?.document_name||'')} · ${esc(rel.other?.speaker||'')}</div></div>`).join('')||'<div class="std-empty">Sin relaciones visibles.</div>';
      target.innerHTML=`<div class="std-notice">Las relaciones propuestas de tipo fuerte no se muestran como criterio consolidado hasta su confirmación.</div><h2>${esc(data.statement)}</h2><div class="std-badges"><span class="std-badge">${esc(data.speaker)}</span><span class="std-badge">${esc(data.treatment)}</span>${(data.tags||[]).map(tag=>`<span class="std-badge">${esc(tag)}</span>`).join('')}</div><div class="std-doc"><button class="std-doc-link" id="stdOpenDoc">${esc(data.document_name||'Documento fuente')}</button><br>${esc(data.court||'Tribunal no informado')}${data.judgment_date?' · '+esc(data.judgment_date):''}<br><span class="std-uid">${esc(data.standard_uid)}</span></div><h3>Cita literal</h3>${quotes}<h3>Relaciones</h3>${relations}<div style="margin-top:12px"><button class="std-btn ghost small" id="stdGraphBtn">Ver grafo</button></div>`;
      target.querySelectorAll('[data-related-uid]').forEach(node=>node.addEventListener('click',()=>detail(node.dataset.relatedUid)));
      target.querySelector('#stdOpenDoc')?.addEventListener('click',()=>openDocument(uid));
      target.querySelector('#stdGraphBtn')?.addEventListener('click',()=>openGraph(uid));
    }catch(error){target.innerHTML=`<div class="std-error">No fue posible abrir el estándar. ${esc(error.message)}</div>`;}
  }

  async function openGraph(uid){
    closeGraph();
    const backdrop=document.createElement('div');backdrop.className='std-modal-backdrop';backdrop.id='stdGraphModal';backdrop.innerHTML='<div class="std-modal"><div class="std-modal-head"><h2>Grafo de relaciones</h2><button class="std-modal-close">Cerrar</button></div><div class="std-graph-body"><div class="std-empty">Cargando grafo…</div></div></div>';document.body.appendChild(backdrop);
    backdrop.querySelector('.std-modal-close').addEventListener('click',closeGraph);backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeGraph();});
    try{
      const data=await api('/api/graph?uid='+encodeURIComponent(uid)+'&depth=2');const body=backdrop.querySelector('.std-graph-body');const nodes=data.nodes||[],edges=data.edges||[];const byId=new Map(nodes.map(n=>[n.standard_uid,n]));
      const nodesHtml=nodes.map(n=>`<button class="std-graph-node ${n.standard_uid===uid?'root':''}" data-graph-uid="${esc(n.standard_uid)}"><b>${esc(n.statement||n.standard_uid)}</b><small>${esc(n.document_name||'')} ${n.court?'· '+esc(n.court):''}</small></button>`).join('');
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
  function boot(){installStyles();shell();installNav();watchOtherNavigation();if(!state.installed){state.installed=true;const observer=new MutationObserver(()=>installNav());observer.observe(document.body,{childList:true,subtree:true});}}
  window.lexiaStandardsSearch=search;window.lexiaStandardsResetSearch=resetSearch;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
