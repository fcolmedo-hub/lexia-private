/* LexIA UI2 — integración nativa del menú Estándares y ajustes de producto. */
(function(){
  'use strict';

  const API_PORT=(window.LEXIA_STANDARDS_PORT||'8515');
  const API=`http://127.0.0.1:${API_PORT}`;

  function standardsShell(){
    return document.getElementById('lexiaStandardsShell');
  }

  function installVisualFixes(){
    if(document.getElementById('lexiaStandardsNativeVisualFix'))return;
    const style=document.createElement('style');
    style.id='lexiaStandardsNativeVisualFix';
    style.textContent=`
      #lexiaStandardsShell .std-kicker{display:none!important}
      #lexiaStandardsShell .std-wrap{max-width:none!important;margin:0!important;padding:22px 18px 38px!important}
      #lexiaStandardsShell .std-head{margin-bottom:14px!important}
      #lexiaStandardsShell .std-title{margin-top:0!important}
      #lexiaStandardsShell .std-source-link{color:#5146f6;text-decoration:underline;text-underline-offset:2px;font-weight:800;cursor:pointer}
      #lexiaStandardsShell .std-source-link:hover{color:#3f34d8}
      #lexiaStandardsShell .std-source-error{display:block;margin-top:6px;color:#9a3456;font-size:11px}
      #lexiaStandardsShell .std-visual-graph{margin-top:12px;padding:14px;border:1px solid #e3e2f3;border-radius:14px;background:#fafaff}
      #lexiaStandardsShell .std-visual-graph-title{font-size:13px;font-weight:850;color:#273153;margin-bottom:12px}
      #lexiaStandardsShell .std-graph-root{max-width:720px;margin:0 auto 14px;padding:12px 14px;border:2px solid #8178ff;border-radius:12px;background:#f3f1ff;box-shadow:0 4px 12px rgba(81,70,246,.08)}
      #lexiaStandardsShell .std-graph-root .std-graph-node-title{font-weight:850;color:#2a245f}
      #lexiaStandardsShell .std-graph-edges{display:grid;gap:10px}
      #lexiaStandardsShell .std-graph-edge{display:grid;grid-template-columns:minmax(0,1fr) 110px minmax(0,1fr);align-items:center;gap:10px}
      #lexiaStandardsShell .std-graph-node{padding:10px 11px;border:1px solid #e1e3ef;border-radius:10px;background:#fff;min-width:0}
      #lexiaStandardsShell .std-graph-node-title{font-size:12px;line-height:1.38;font-weight:750;color:#273153}
      #lexiaStandardsShell .std-graph-node-meta{margin-top:5px;font-size:10px;color:#7a84a0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      #lexiaStandardsShell .std-graph-connector{text-align:center;position:relative;padding:4px 2px}
      #lexiaStandardsShell .std-graph-arrow{display:block;font-size:18px;line-height:1;color:#756bff;margin-top:3px}
      #lexiaStandardsShell .std-graph-rel{display:inline-block;padding:3px 7px;border-radius:999px;background:#eeeaff;color:#5548ef;font-size:10px;font-weight:850}
      #lexiaStandardsShell .std-graph-second{margin:14px 0 6px;font-size:10px;font-weight:850;letter-spacing:.04em;text-transform:uppercase;color:#707a97}
      @media(max-width:900px){#lexiaStandardsShell .std-graph-edge{grid-template-columns:1fr}#lexiaStandardsShell .std-graph-connector{padding:0}#lexiaStandardsShell .std-graph-arrow{transform:rotate(90deg)}}
      @media(max-width:1100px){#lexiaStandardsShell .std-wrap{padding:18px 14px!important}}
      @media(max-width:680px){#lexiaStandardsShell .std-wrap{padding:12px!important}}
    `;
    document.head.appendChild(style);
  }

  function syncStandardsInset(){
    const sidebar=document.getElementById('globalSidebar');
    const shell=standardsShell();
    if(!sidebar||!shell)return;
    const rect=sidebar.getBoundingClientRect();
    const left=Math.max(0,Math.round(rect.right));
    shell.style.setProperty('left',left+'px','important');
    shell.style.setProperty('right','0','important');
    shell.style.setProperty('top','0','important');
    shell.style.setProperty('bottom','0','important');
    shell.style.setProperty('width','auto','important');
  }

  function openStandards(){
    const shell=standardsShell();
    if(!shell)return;
    installVisualFixes();
    syncStandardsInset();
    const nav=document.querySelector('#globalSidebar .nav');
    if(nav)nav.querySelectorAll('button').forEach(item=>item.classList.remove('active'));
    const button=nav&&nav.querySelector('[data-lexia-standards-nav]');
    if(button){button.classList.add('active');button.setAttribute('aria-current','page');}
    shell.classList.add('open');
    document.getElementById('stdSearch')?.click();
  }

  function closeStandards(){
    const shell=standardsShell();
    if(shell)shell.classList.remove('open');
    const button=document.querySelector('#globalSidebar .nav [data-lexia-standards-nav]');
    if(button){button.classList.remove('active');button.removeAttribute('aria-current');}
  }

  function buildButton(){
    const button=document.createElement('button');
    button.type='button';
    button.dataset.lexiaStandardsNav='1';
    button.setAttribute('aria-label','Estándares');
    const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');
    icon.setAttribute('viewBox','0 0 24 24');
    icon.setAttribute('aria-hidden','true');
    icon.innerHTML='<path d="M12 3v18"></path><path d="M5 6h14"></path><path d="M7 6 3.5 12h7L7 6Z"></path><path d="M17 6 13.5 12h7L17 6Z"></path><path d="M8 21h8"></path>';
    button.append(icon,document.createTextNode('Estándares'));
    button.addEventListener('click',event=>{
      event.preventDefault();event.stopPropagation();openStandards();
    },true);
    return button;
  }

  function install(){
    installVisualFixes();
    const nav=document.querySelector('#globalSidebar .nav');
    if(!nav)return false;
    if(nav.querySelector('[data-lexia-standards-nav]')){syncStandardsInset();return true;}
    const button=buildButton();
    const buttons=[...nav.querySelectorAll(':scope > button')];
    const maintenance=buttons.find(item=>String(item.textContent||'').trim().toLowerCase()==='mantenimiento');
    const investigation=nav.querySelector('button[data-route="contextpage"]') ||
      buttons.find(item=>['investigación','investigacion'].includes(String(item.textContent||'').trim().toLowerCase()));
    if(maintenance)maintenance.insertAdjacentElement('beforebegin',button);
    else if(investigation)investigation.insertAdjacentElement('afterend',button);
    else nav.append(button);
    syncStandardsInset();
    return true;
  }

  function allSearchFieldsBlank(){
    return ['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'].every(id=>{
      const node=document.getElementById(id);
      return !node || !String(node.value||'').trim();
    });
  }

  let blankSearchTimer=null;
  function scheduleShowAllIfBlank(){
    clearTimeout(blankSearchTimer);
    blankSearchTimer=window.setTimeout(()=>{
      const shell=standardsShell();
      if(!shell||!shell.classList.contains('open')||!allSearchFieldsBlank())return;
      document.getElementById('stdSearch')?.click();
    },60);
  }

  function esc(value){
    return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }

  function shortMeta(node){
    return [node?.document_name,node?.court,node?.judgment_date].filter(Boolean).join(' · ');
  }

  function graphNode(node,extraClass=''){
    if(!node)return '<div class="std-graph-node"><div class="std-graph-node-title">Estándar no disponible</div></div>';
    return `<div class="std-graph-node ${extraClass}"><div class="std-graph-node-title">${esc(node.statement||node.standard_uid||'')}</div><div class="std-graph-node-meta">${esc(shortMeta(node))}</div></div>`;
  }

  async function renderVisualGraph(button){
    const graph=document.getElementById('stdGraph');
    if(!graph)return;
    if(graph.dataset.lexiaGraphOpen==='1'){
      graph.innerHTML='';graph.className='';graph.dataset.lexiaGraphOpen='0';
      button.textContent='Ver grafo';button.setAttribute('aria-expanded','false');
      return;
    }
    const uid=document.querySelector('#stdDetail .std-uid')?.textContent?.trim();
    if(!uid)return;
    graph.dataset.lexiaGraphOpen='1';
    graph.className='std-visual-graph';
    graph.innerHTML='<div class="std-empty">Cargando grafo…</div>';
    button.textContent='Cerrar grafo';button.setAttribute('aria-expanded','true');
    try{
      const response=await fetch(API+'/api/graph?uid='+encodeURIComponent(uid)+'&depth=2',{headers:{Accept:'application/json'}});
      if(!response.ok)throw new Error('HTTP '+response.status);
      const data=await response.json();
      const nodes=new Map((data.nodes||[]).map(node=>[node.standard_uid,node]));
      const root=nodes.get(data.root)||nodes.get(uid);
      const direct=[];const second=[];
      for(const edge of (data.edges||[])){
        if(edge.from===uid||edge.to===uid)direct.push(edge);else second.push(edge);
      }
      const edgeHtml=edge=>{
        const from=nodes.get(edge.from);const to=nodes.get(edge.to);
        const label=({duplicate_of:'Duplica',specializes:'Especializa',generalizes:'Generaliza',exception_to:'Excepción',related_to:'Relacionado',supports:'Apoya',contradicts:'Contradice'})[edge.relation_type]||edge.relation_type;
        return `<div class="std-graph-edge">${graphNode(from)}<div class="std-graph-connector"><span class="std-graph-rel">${esc(label)} · ${esc(edge.status||'')}</span><span class="std-graph-arrow">→</span></div>${graphNode(to)}</div>`;
      };
      graph.innerHTML=`<div class="std-visual-graph-title">Mapa de relaciones</div><div class="std-graph-root"><div class="std-graph-node-title">${esc(root?.statement||uid)}</div><div class="std-graph-node-meta">${esc(shortMeta(root))}</div></div><div class="std-graph-edges">${direct.map(edgeHtml).join('')||'<div class="std-empty">Sin relaciones visibles.</div>'}${second.length?'<div class="std-graph-second">Relaciones de segundo nivel</div>'+second.map(edgeHtml).join(''):''}</div>`;
    }catch(error){
      graph.innerHTML=`<div class="std-error">No fue posible cargar el grafo. ${esc(error.message)}</div>`;
    }
  }

  function installDocumentLink(){
    const doc=document.querySelector('#stdDetail .std-doc');
    if(!doc||doc.querySelector('[data-lexia-open-source]'))return;
    const uid=doc.querySelector('.std-uid')?.textContent?.trim();
    const title=doc.querySelector('b');
    if(!uid||!title)return;
    const link=document.createElement('a');
    link.href='#';
    link.dataset.lexiaOpenSource='1';
    link.dataset.uid=uid;
    link.className='std-source-link';
    link.textContent=title.textContent||'Abrir documento fuente';
    title.replaceWith(link);
  }

  async function openSourceDocument(link){
    const uid=String(link.dataset.uid||'').trim();
    if(!uid)return;
    let errorNode=link.parentElement?.querySelector('.std-source-error');
    if(errorNode)errorNode.remove();
    try{
      const response=await fetch(API+'/api/open-document?uid='+encodeURIComponent(uid),{headers:{Accept:'application/json'}});
      const data=await response.json();
      if(!response.ok||data.ok===false)throw new Error(data.error==='document_not_found'?'No se encontró el archivo fuente en esta computadora.':(data.error||'No se pudo abrir el archivo.'));
    }catch(error){
      errorNode=document.createElement('span');
      errorNode.className='std-source-error';
      errorNode.textContent=String(error.message||error);
      link.parentElement?.appendChild(errorNode);
    }
  }

  function installStandardsInteractionFixes(){
    if(window.__lexiaStandardsInteractionFixesV2)return;
    window.__lexiaStandardsInteractionFixesV2=true;

    document.addEventListener('click',event=>{
      const el=event.target instanceof Element?event.target:null;
      const graphButton=el?.closest('#stdGraphBtn');
      if(graphButton){
        event.preventDefault();event.stopImmediatePropagation();renderVisualGraph(graphButton);return;
      }
      const sourceLink=el?.closest('[data-lexia-open-source]');
      if(sourceLink){
        event.preventDefault();event.stopImmediatePropagation();openSourceDocument(sourceLink);return;
      }
    },true);

    document.addEventListener('input',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(target?.matches('#stdQ,#stdFrom,#stdTo,#stdTag'))scheduleShowAllIfBlank();
    },true);
    document.addEventListener('change',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(target?.matches('#stdCourt,#stdSpeaker,#stdTreatment,#stdFrom,#stdTo,#stdTag'))scheduleShowAllIfBlank();
    },true);

    const observer=new MutationObserver(()=>installDocumentLink());
    observer.observe(document.body,{childList:true,subtree:true});
    installDocumentLink();
  }

  function installExitHandler(){
    if(window.__lexiaStandardsNativeExit)return;
    window.__lexiaStandardsNativeExit=true;
    window.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target:null;
      const destination=target&&target.closest('#globalSidebar .nav button');
      if(destination&&!destination.matches('[data-lexia-standards-nav]'))closeStandards();
    },true);
  }

  function boot(){
    install();
    installExitHandler();
    installStandardsInteractionFixes();
    window.addEventListener('resize',syncStandardsInset,{passive:true});
    const observer=new MutationObserver(()=>install());
    observer.observe(document.body,{childList:true,subtree:true});
    window.setTimeout(install,100);
    window.setTimeout(install,500);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
