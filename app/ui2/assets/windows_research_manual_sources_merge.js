/* LexIA Windows — integra fragmentos manuales con las fuentes nativas sin reflujo. */
(function(){
  'use strict';
  if(window.__lexiaWindowsResearchManualSourcesMergeV5)return;
  window.__lexiaWindowsResearchManualSourcesMergeV5=true;

  const STYLE_ID='lexiaWindowsResearchManualSourcesMergeStyleV5';
  const MODAL_LIST_ID='researchSourcesModalList';
  const SOURCE_SECTION_ID='lexiaManualResearchModalSources';
  const SIDEBAR_ID='lexiaManualResearchSources';
  const LEGACY_MAIN_LIST_ID='lexiaManualSourcesMainList';
  const ADD_BUTTON_ID='lexiaAddManualResearchSource';
  const SIDECAR='http://127.0.0.1:8516';
  let requestSerial=0;
  let lastModalSignature='';
  let lastMainSignature='';

  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const pageLabel=source=>{
    if(source?.page_label)return String(source.page_label);
    const start=Number(source?.page_start||0),end=Number(source?.page_end||0);
    if(start&&end&&end!==start)return 'Páginas '+start+'-'+end;
    if(start)return 'Página '+start;
    return 'Página no determinada';
  };
  const signature=sources=>JSON.stringify((sources||[]).map(source=>[
    String(source.id||''),String(source.name||''),String(source.category||''),
    String(source.page_start||''),String(source.page_end||''),
    String(source.snippet||source.selected_text||''),source.selected!==false
  ]));

  async function sidecar(path,options){
    const response=await fetch(SIDECAR+path,Object.assign({cache:'no-store'},options||{}));
    let data={};try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  }

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${SOURCE_SECTION_ID},#${SIDEBAR_ID},#${LEGACY_MAIN_LIST_ID}{display:none!important}

      #contextpage #viewSources,#contextpage #${ADD_BUTTON_ID}{
        width:100%!important;min-height:30px!important;height:30px!important;
        margin-top:7px!important;padding:5px 10px!important;border-radius:8px!important;
        font-size:10.5px!important;line-height:1!important;font-weight:700!important;
        box-sizing:border-box!important;
      }
      #contextpage #viewSources{border:1px solid #ddd9f2!important;background:#fff!important;color:#3f3a62!important}
      #contextpage #${ADD_BUTTON_ID}{border:1px solid #bcb6ff!important;background:#f7f6ff!important;color:#352bc7!important}
      #contextpage #${ADD_BUTTON_ID}:hover{background:#efedff!important;border-color:#9f97ff!important}

      /* El contenido de toda fuente debe permanecer dentro de su tarjeta. */
      #${MODAL_LIST_ID},#${MODAL_LIST_ID} *,#contextpage .research-source-check~*{box-sizing:border-box;min-width:0}
      #${MODAL_LIST_ID} a,#${MODAL_LIST_ID} b,#${MODAL_LIST_ID} p,#${MODAL_LIST_ID} small,#${MODAL_LIST_ID} span,
      #contextpage .research-source-check~*{max-width:100%;overflow-wrap:anywhere;word-break:normal}
      #${MODAL_LIST_ID} .research-source-check{accent-color:#5146f6}

      /* La tarjeta manual replica proporciones, tipografía y espaciado de la nativa.
         Sólo cambian los acentos verdes y la acción Quitar en púrpura. */
      .lexia-manual-native-card{
        width:100%!important;border:1px solid #d9ddea!important;border-radius:10px!important;background:#fff!important;
        padding:10px 12px!important;display:grid!important;
        grid-template-columns:18px 28px minmax(0,1fr) auto!important;
        gap:9px!important;align-items:start!important;box-shadow:none!important;min-width:0!important;
        font-family:inherit!important;color:#42506b!important;
      }
      .lexia-manual-native-card+.lexia-manual-native-card{margin-top:8px!important}
      .lexia-manual-native-check{accent-color:#169b62!important;margin:3px 0 0!important;width:14px!important;height:14px!important}
      .lexia-manual-native-number{
        width:25px;height:25px;border-radius:6px;background:#e7f6ed!important;color:#168054!important;
        display:flex;align-items:center;justify-content:center;font-size:10px!important;font-weight:800!important;line-height:1!important;
      }
      .lexia-manual-native-body{min-width:0!important;overflow:hidden!important}
      .lexia-manual-native-name{
        display:block!important;color:#168054!important;font-size:12px!important;font-weight:700!important;
        line-height:1.25!important;text-decoration:underline!important;cursor:pointer!important;
        overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;max-width:100%!important;
      }
      .lexia-manual-native-meta{
        display:block!important;margin-top:5px!important;color:#68738f!important;
        font-size:10px!important;line-height:1.25!important;font-weight:400!important;
      }
      .lexia-manual-native-snippet{
        margin:8px 0 0!important;color:#42506b!important;font-size:11px!important;line-height:1.45!important;font-weight:400!important;
        display:-webkit-box!important;-webkit-box-orient:vertical!important;-webkit-line-clamp:3!important;
        overflow:hidden!important;overflow-wrap:anywhere!important;max-width:100%!important;
      }
      .lexia-manual-native-tag{
        display:block!important;margin-top:5px!important;color:#168054!important;
        font-size:9px!important;line-height:1.2!important;font-weight:800!important;letter-spacing:.02em!important;
      }
      .lexia-manual-native-remove{
        border:1px solid #9a3b8f!important;background:#9a3b8f!important;color:#fff!important;
        border-radius:6px!important;padding:6px 10px!important;font-size:10px!important;font-weight:700!important;
        line-height:1!important;cursor:pointer!important;white-space:nowrap!important;
      }
      .lexia-manual-native-remove:hover{background:#84317b!important;border-color:#84317b!important}

      body.lexia-manual-search-open #searchpage{display:none!important}
      body.lexia-manual-search-open #contextpage{display:block!important}
      #lexiaManualResearchDialog::backdrop,#lexiaManualResearchSelectionViewer::backdrop{background:rgba(246,247,252,.96)!important}
      @media(max-width:700px){
        .lexia-manual-native-card{grid-template-columns:18px 26px minmax(0,1fr)!important}
        .lexia-manual-native-remove{grid-column:3;justify-self:end}
      }
    `;
    document.head.appendChild(style);
  }

  function keepInvestigationBackground(){
    document.body.classList.add('lexia-manual-search-open');
    const context=document.getElementById('contextpage');
    const search=document.getElementById('searchpage');
    if(context)context.style.setProperty('display','block','important');
    if(search)search.style.setProperty('display','none','important');
  }

  function releaseInvestigationGuard(){
    if(document.getElementById('lexiaManualResearchDialog')||document.getElementById('lexiaManualResearchSelectionViewer'))return;
    document.body.classList.remove('lexia-manual-search-open');
    document.getElementById('contextpage')?.style.removeProperty('display');
    document.getElementById('searchpage')?.style.removeProperty('display');
  }

  function nativeSourceCount(){
    const modal=document.getElementById(MODAL_LIST_ID);
    const modalChecks=modal?[...modal.querySelectorAll('.research-source-check')]:[];
    const indexes=modalChecks.map(check=>Number(check.dataset.sourceIndex)).filter(Number.isFinite);
    if(indexes.length)return Math.max(...indexes)+1;
    if(modalChecks.length)return modalChecks.length;
    const context=document.getElementById('contextpage');
    const text=String(context?.textContent||'');
    const match=text.match(/FUENTES\s+DISPONIBLES\s+(\d+)/i);
    if(match)return Number(match[1])||0;
    return [...document.querySelectorAll('#contextpage .research-source-check')]
      .filter(check=>!check.closest('#'+MODAL_LIST_ID)&&!check.closest('.lexia-manual-native-card')).length;
  }

  function cardHtml(source,number){
    return `
      <input type="checkbox" class="lexia-manual-source-check lexia-manual-native-check" data-manual-id="${esc(source.id||'')}" ${source.selected!==false?'checked':''}>
      <span class="lexia-manual-native-number">${number}</span>
      <span class="lexia-manual-native-body">
        <span class="lexia-manual-native-name" data-manual-open-id="${esc(source.id||'')}" title="Abrir ${esc(source.name||'Documento')}">${esc(source.name||'Documento')}</span>
        <small class="lexia-manual-native-meta">${esc(source.category||'Documento')} · ${esc(pageLabel(source))}</small>
        <p class="lexia-manual-native-snippet">${esc(source.snippet||source.selected_text||'')}</p>
        <span class="lexia-manual-native-tag">AGREGADA POR EL USUARIO</span>
      </span>
      <button type="button" class="lexia-manual-native-remove" data-manual-inline-remove="${esc(source.id||'')}" aria-label="Quitar fragmento manual">Quitar</button>`;
  }

  function renderInto(container,sources,startNumber,kind){
    if(!container)return;
    const sig=kind+'|'+startNumber+'|'+signature(sources);
    const previous=kind==='modal'?lastModalSignature:lastMainSignature;
    if(previous===sig&&container.querySelectorAll(':scope > .lexia-manual-native-card').length===sources.length)return;

    container.querySelectorAll(':scope > .lexia-manual-native-card').forEach(node=>node.remove());
    sources.forEach((source,index)=>{
      const card=document.createElement('label');
      card.className='lexia-manual-native-card';
      card.dataset.manualId=String(source.id||'');
      card.dataset.manualPlacement=kind;
      card.innerHTML=cardHtml(source,startNumber+index);
      container.appendChild(card);
    });
    if(kind==='modal')lastModalSignature=sig;else lastMainSignature=sig;
  }

  function nativeMainChecks(){
    return [...document.querySelectorAll('#contextpage .research-source-check')]
      .filter(check=>!check.closest('#'+MODAL_LIST_ID)&&!check.closest('.lexia-manual-native-card'));
  }

  function findMainNativeContainer(){
    const checks=nativeMainChecks();
    if(!checks.length)return null;
    const view=document.getElementById('viewSources');
    let node=checks[0].parentElement;
    let fallback=null;
    while(node&&node.id!=='contextpage'){
      if(checks.every(check=>node.contains(check))){
        fallback=node;
        const style=window.getComputedStyle(node);
        const scrollable=/(auto|scroll)/.test(String(style.overflowY||''));
        if(scrollable&&(!view||!node.contains(view)))return node;
      }
      node=node.parentElement;
    }
    if(fallback&&(!view||!fallback.contains(view)))return fallback;
    return null;
  }

  function cleanupLegacyMainContainer(){
    const legacy=document.getElementById(LEGACY_MAIN_LIST_ID);
    if(legacy)legacy.remove();
  }

  async function merge(){
    installStyle();
    cleanupLegacyMainContainer();
    const current=++requestSerial;
    let sources=[];
    try{
      const data=await sidecar('/sources');
      if(current!==requestSerial)return false;
      sources=Array.isArray(data.sources)?data.sources:[];
    }catch(_){return false;}

    const start=nativeSourceCount()+1;
    renderInto(document.getElementById(MODAL_LIST_ID),sources,start,'modal');
    const mainContainer=findMainNativeContainer();
    if(mainContainer)renderInto(mainContainer,sources,start,'main');
    return true;
  }

  function refreshSoon(){window.setTimeout(()=>merge(),0);}

  function openManualById(id){
    const sources=window.lexiaResearchManualSources?.list?.()||[];
    const source=sources.find(item=>String(item.id||'')===String(id||''));
    if(!source?.path)return;
    const page=Number(source.page_start||0)||1;
    if(typeof window.lexiaQuickViewerOpen==='function')window.lexiaQuickViewerOpen(source.path,page,String(source.snippet||source.selected_text||''));
    else window.open('/api/file-preview?path='+encodeURIComponent(source.path),'_blank','noopener');
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;

    if(target.closest('#'+ADD_BUTTON_ID)){
      keepInvestigationBackground();
      window.setTimeout(keepInvestigationBackground,60);
      return;
    }
    if(target.closest('[data-manual-close],[data-viewer-close]'))window.setTimeout(releaseInvestigationGuard,80);
    if(target.closest('#reviewResearchSources,#viewSources'))refreshSoon();

    const open=target.closest('[data-manual-open-id]');
    if(open){event.preventDefault();event.stopPropagation();openManualById(open.dataset.manualOpenId);return;}

    const remove=target.closest('[data-manual-inline-remove]');
    if(remove){
      event.preventDefault();event.stopPropagation();
      const id=String(remove.dataset.manualInlineRemove||'');
      sidecar('/remove-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})
        .then(()=>{lastModalSignature='';lastMainSignature='';return merge();})
        .catch(error=>alert('No se pudo quitar el fragmento.\n\n'+(error.message||String(error))));
    }
  },true);

  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(target?.matches('.lexia-manual-source-check[data-manual-id]')){
      const id=String(target.dataset.manualId||'');
      const checked=target.checked;
      document.querySelectorAll('.lexia-manual-source-check[data-manual-id="'+CSS.escape(id)+'"]').forEach(box=>{box.checked=checked;});
      sidecar('/set-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,selected:checked})})
        .catch(error=>{target.checked=!checked;alert('No se pudo actualizar la selección.\n\n'+(error.message||String(error)));});
    }
  },true);

  [0,250,800].forEach(delay=>window.setTimeout(()=>merge(),delay));
  window.lexiaMergeManualResearchSources=merge;
})();
