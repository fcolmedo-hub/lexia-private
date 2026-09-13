/* LexIA Windows — fusiona fuentes automáticas y manuales en el renderer nativo. */
(function(){
  'use strict';
  if(window.__lexiaWindowsResearchManualSourcesMergeV6)return;
  window.__lexiaWindowsResearchManualSourcesMergeV6=true;

  const STYLE_ID='lexiaWindowsResearchManualSourcesMergeStyleV6';
  const MODAL_LIST_ID='researchSourcesModalList';
  const MAIN_LIST_ID='researchSourceList';
  const SOURCE_SECTION_ID='lexiaManualResearchModalSources';
  const SIDEBAR_ID='lexiaManualResearchSources';
  const LEGACY_MAIN_LIST_ID='lexiaManualSourcesMainList';
  const ADD_BUTTON_ID='lexiaAddManualResearchSource';
  const SIDECAR='http://127.0.0.1:8516';
  let requestSerial=0;
  let refreshQueued=false;
  let manualSourcesCache=[];
  let automaticSelectionOverride=null;
  let automaticSourceSignature='';
  let investigationBackgroundSnapshot=null;
  const nativeFetch=window.fetch.bind(window);

  window.fetch=function(input,options){
    const url=typeof input==='string'?input:String(input?.url||'');
    if(automaticSelectionOverride&&url.includes('/api/research-package-start')&&typeof options?.body==='string'){
      try{
        const payload=JSON.parse(options.body);
        payload.selected_indices=[...automaticSelectionOverride].sort((a,b)=>a-b);
        options=Object.assign({},options,{body:JSON.stringify(payload)});
      }catch(_){/* conserva la solicitud original si el cuerpo no es JSON */}
    }
    return nativeFetch(input,options);
  };

  const pageLabel=source=>{
    if(source?.page_label)return String(source.page_label);
    const start=Number(source?.page_start||0),end=Number(source?.page_end||0);
    if(start&&end&&end!==start)return 'Páginas '+start+'-'+end;
    if(start)return 'Página '+start;
    return 'Página no determinada';
  };

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

      /* Un único esqueleto de tarjeta para automáticas y manuales, en ambas listas. */
      .lexia-unified-source-card{
        box-sizing:border-box!important;width:100%!important;height:116px!important;min-height:116px!important;
        display:grid!important;grid-template-columns:18px 26px minmax(0,1fr) 76px!important;
        gap:9px!important;align-items:start!important;padding:10px!important;
        border:1px solid #dfe3ed!important;border-radius:9px!important;background:#fff!important;
        box-shadow:none!important;font-family:inherit!important;color:#3f4a6c!important;overflow:hidden!important;
      }
      .lexia-unified-source-card,.lexia-unified-source-card *{box-sizing:border-box;min-width:0}
      .lexia-unified-source-check{width:14px!important;height:14px!important;margin:3px 0 0!important}
      .lexia-source-automatic .lexia-unified-source-check{accent-color:#5146f6!important}
      .lexia-source-manual .lexia-unified-source-check{accent-color:#169b62!important}
      .lexia-unified-source-number{
        width:25px!important;height:25px!important;margin:0!important;border-radius:7px!important;
        display:grid!important;place-items:center!important;font-size:10px!important;font-weight:800!important;line-height:1!important;
      }
      .lexia-source-automatic .lexia-unified-source-number{background:#eeecff!important;color:#5146f6!important}
      .lexia-source-manual .lexia-unified-source-number{background:#e7f6ed!important;color:#168054!important}
      .lexia-unified-source-details{min-width:0!important;height:94px!important;overflow:hidden!important}
      .lexia-unified-source-title-row{display:flex!important;align-items:center!important;min-height:16px!important;overflow:hidden!important}
      .lexia-unified-source-card .source-name-link{
        display:block!important;width:100%!important;max-width:100%!important;margin:0!important;padding:0!important;border:0!important;
        background:transparent!important;font-family:inherit!important;font-size:10.5px!important;font-weight:800!important;
        line-height:1.35!important;text-align:left!important;text-decoration:underline!important;text-underline-offset:2px!important;
        white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;cursor:pointer!important;
      }
      .lexia-source-automatic .source-name-link{color:#5146f6!important}
      .lexia-source-manual .source-name-link{color:#168054!important}
      .lexia-unified-source-meta{
        display:flex!important;align-items:center!important;justify-content:space-between!important;gap:7px!important;
        min-height:14px!important;margin-top:3px!important;color:#687294!important;
      }
      .lexia-unified-source-meta small{
        display:block!important;margin:0!important;max-width:100%!important;color:#687294!important;
        font-size:8.5px!important;line-height:1.25!important;font-weight:400!important;
        white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
      }
      .lexia-unified-source-card .source-score{font-size:7.5px!important;padding:2px 4px!important;white-space:nowrap!important}
      .lexia-unified-source-snippet{
        margin:5px 0 0!important;max-width:100%!important;color:#3e496b!important;
        font-size:9.5px!important;line-height:1.35!important;font-weight:400!important;
        display:-webkit-box!important;-webkit-box-orient:vertical!important;-webkit-line-clamp:3!important;
        overflow:hidden!important;overflow-wrap:anywhere!important;word-break:normal!important;
      }
      .lexia-source-user-tag{
        display:block!important;height:11px!important;margin-top:3px!important;color:#168054!important;
        font-size:8px!important;line-height:11px!important;font-weight:800!important;letter-spacing:.02em!important;
        white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
      }
      .lexia-source-automatic .lexia-source-user-tag{visibility:hidden!important}
      .lexia-unified-source-card .source-actions{
        display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:4px!important;
        width:76px!important;margin:0!important;padding:1px 0 0!important;
      }
      .lexia-unified-source-card .source-actions button{
        box-sizing:border-box!important;width:76px!important;min-width:76px!important;height:24px!important;min-height:24px!important;
        margin:0!important;padding:0 7px!important;border-radius:6px!important;
        font-family:inherit!important;font-size:8.5px!important;line-height:1!important;font-weight:700!important;white-space:nowrap!important;
      }
      .lexia-source-automatic .study-source{border:1px solid #5146f6!important;background:#5146f6!important;color:#fff!important}
      .lexia-source-automatic .study-source:hover{border-color:#4338e8!important;background:#4338e8!important}
      .lexia-manual-native-remove{border:1px solid #9a3b8f!important;background:#9a3b8f!important;color:#fff!important;cursor:pointer!important}
      .lexia-manual-native-remove:hover{border-color:#84317b!important;background:#84317b!important}

      body.lexia-manual-search-open #searchpage{display:none!important}
      body.lexia-manual-search-open #contextpage{display:block!important}
      #lexiaManualResearchDialog::backdrop,#lexiaManualResearchSelectionViewer::backdrop{background:rgba(246,247,252,.96)!important}
      @media(max-width:700px){
        .lexia-unified-source-card{grid-template-columns:18px 24px minmax(0,1fr) 70px!important;gap:7px!important}
        .lexia-unified-source-card .source-actions{width:70px!important}
        .lexia-unified-source-card .source-actions button{width:70px!important;min-width:70px!important}
      }
    `;
    document.head.appendChild(style);
  }

  function keepInvestigationBackground(){
    if(!investigationBackgroundSnapshot){
      const context=document.getElementById('contextpage');
      const search=document.getElementById('searchpage');
      investigationBackgroundSnapshot={
        contextValue:context?.style.getPropertyValue('display')||'',
        contextPriority:context?.style.getPropertyPriority('display')||'',
        searchValue:search?.style.getPropertyValue('display')||'',
        searchPriority:search?.style.getPropertyPriority('display')||'',
      };
    }
    document.body.classList.add('lexia-manual-search-open');
    const context=document.getElementById('contextpage');
    const search=document.getElementById('searchpage');
    if(context)context.style.setProperty('display','block','important');
    if(search)search.style.setProperty('display','none','important');
  }

  function releaseInvestigationGuard(){
    if(document.getElementById('lexiaManualResearchDialog')||document.getElementById('lexiaManualResearchSelectionViewer'))return;
    document.body.classList.remove('lexia-manual-search-open');
    const snapshot=investigationBackgroundSnapshot;
    investigationBackgroundSnapshot=null;
    const restore=(node,value,priority)=>{
      if(!node)return;
      if(value)node.style.setProperty('display',value,priority);else node.style.removeProperty('display');
    };
    restore(document.getElementById('contextpage'),snapshot?.contextValue||'',snapshot?.contextPriority||'');
    restore(document.getElementById('searchpage'),snapshot?.searchValue||'',snapshot?.searchPriority||'');
  }

  function automaticIndicesFromDom(changed){
    const boxes=[...document.querySelectorAll('#'+MODAL_LIST_ID+' .research-source-check')];
    const selected=new Set(boxes.filter(box=>box.checked).map(box=>Number(box.dataset.sourceIndex)).filter(Number.isFinite));
    if(changed){
      const index=Number(changed.dataset.sourceIndex);
      if(Number.isFinite(index)){if(changed.checked)selected.add(index);else selected.delete(index);}
    }
    return selected;
  }

  function applyAutomaticSelectionOverride(){
    if(!automaticSelectionOverride)return;
    document.querySelectorAll('.research-source-check').forEach(box=>{
      box.checked=automaticSelectionOverride.has(Number(box.dataset.sourceIndex));
    });
    const count=automaticSelectionOverride.size;
    const setText=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value;};
    setText('researchSourceNote',count+' fuente'+(count===1?' seleccionada.':'s seleccionadas. Revisá el texto y ajustá la selección.'));
    setText('selectedSourcesSummary',count+' fuente'+(count===1?' seleccionada':'s seleccionadas')+' para el paquete');
    setText('outputSourceCount',count||'—');
  }

  function actionBox(button){
    const actions=document.createElement('div');
    actions.className='source-actions';
    if(button)actions.appendChild(button);
    return actions;
  }

  function renderUnifiedCard(parts,number,kind){
    const manual=kind==='manual';
    const card=parts.card||document.createElement('div');
    card.className=(parts.nativeClass||'')+' lexia-unified-source-card '+(manual?'lexia-source-manual':'lexia-source-automatic');
    card.dataset.sourcePlacement=parts.placement||'';
    if(manual)card.dataset.manualId=String(parts.source?.id||'');

    const check=parts.check||document.createElement('input');
    check.type='checkbox';
    check.classList.add('lexia-unified-source-check');

    const badge=document.createElement('span');
    badge.className='source-num lexia-unified-source-number';
    badge.textContent=String(number);

    const details=document.createElement('div');
    details.className='source-details lexia-unified-source-details';
    const titleRow=document.createElement('div');
    titleRow.className='lexia-unified-source-title-row';
    titleRow.appendChild(parts.nameButton);
    const meta=document.createElement('div');
    meta.className='source-meta lexia-unified-source-meta';
    const metaText=document.createElement('small');
    metaText.textContent=parts.metaText||'';
    meta.appendChild(metaText);
    if(parts.score)meta.appendChild(parts.score);
    const snippet=document.createElement('p');
    snippet.className='source-snippet lexia-unified-source-snippet';
    snippet.textContent=parts.snippetText||'Sin texto relevante recuperado.';
    const tag=document.createElement('span');
    tag.className='lexia-source-user-tag';
    tag.textContent=manual?'AGREGADA POR EL USUARIO':'FUENTE AUTOMÁTICA';
    if(!manual)tag.setAttribute('aria-hidden','true');
    details.append(titleRow,meta,snippet,tag);

    card.replaceChildren(check,badge,details,parts.actions);
    return card;
  }

  function automaticDescriptor(card,placement){
    const check=card.querySelector('.research-source-check');
    const nameButton=card.querySelector('.view-source');
    const actions=card.querySelector('.source-actions');
    if(!check||!nameButton||!actions)return null;
    const metaNode=card.querySelector('.source-meta small')||card.querySelector('.meta');
    const snippet=card.querySelector('.source-snippet')||card.querySelector('p');
    return {
      card,
      nativeClass:placement==='modal'?'lexia-source-choice':'source-item',
      placement,
      check,
      nameButton,
      metaText:String(metaNode?.textContent||'').trim(),
      snippetText:String(snippet?.textContent||'').trim(),
      score:card.querySelector('.source-score'),
      actions
    };
  }

  function manualDescriptor(source,placement){
    const check=document.createElement('input');
    check.className='lexia-manual-source-check';
    check.dataset.manualId=String(source.id||'');
    check.checked=source.selected!==false;

    const nameButton=document.createElement('button');
    nameButton.type='button';
    nameButton.className='source-name-link';
    nameButton.dataset.manualOpenId=String(source.id||'');
    nameButton.title='Abrir '+String(source.name||'Documento');
    nameButton.textContent=String(source.name||'Documento');

    const remove=document.createElement('button');
    remove.type='button';
    remove.className='lexia-manual-native-remove';
    remove.dataset.manualInlineRemove=String(source.id||'');
    remove.setAttribute('aria-label','Quitar fragmento manual');
    remove.textContent='Quitar';

    return {
      /* Evita que el módulo Casos agregue acciones ajenas: la geometría la da el renderer unificado. */
      nativeClass:'lexia-source-choice',
      placement,
      source,
      check,
      nameButton,
      metaText:String(source.category||'Documento')+' · '+pageLabel(source),
      snippetText:String(source.snippet||source.selected_text||''),
      score:null,
      actions:actionBox(remove)
    };
  }

  function directAutomaticCards(container){
    if(!container)return [];
    return [...container.children].filter(card=>
      card instanceof Element&&
      !card.classList.contains('lexia-source-manual')&&
      Boolean(card.querySelector('.research-source-check'))
    );
  }

  function renderPlacement(container,sources,placement){
    if(!container)return;
    container.querySelectorAll(':scope > .lexia-source-manual').forEach(card=>card.remove());

    const automaticSources=directAutomaticCards(container)
      .map(card=>automaticDescriptor(card,placement))
      .filter(Boolean)
      .map(parts=>({kind:'automatic',parts}));
    if(placement==='modal'){
      const signature=automaticSources.map(entry=>String(entry.parts.check?.dataset?.sourceIndex||'')+'|'+String(entry.parts.nameButton?.textContent||'')).join('\n');
      if(automaticSourceSignature&&signature&&signature!==automaticSourceSignature)automaticSelectionOverride=null;
      if(signature)automaticSourceSignature=signature;
    }
    const manualSources=(sources||[])
      .map(source=>({kind:'manual',parts:manualDescriptor(source,placement)}));
    const finalSources=automaticSources.concat(manualSources);

    if(finalSources.length)container.querySelectorAll(':scope > .source-empty').forEach(node=>node.remove());
    finalSources.forEach((entry,index)=>{
      const card=renderUnifiedCard(entry.parts,index+1,entry.kind);
      container.appendChild(card);
    });
    applyAutomaticSelectionOverride();
  }

  function renderMergedLists(sources){
    renderPlacement(document.getElementById(MODAL_LIST_ID),sources,'modal');
    renderPlacement(document.getElementById(MAIN_LIST_ID),sources,'main');
  }

  function cleanupLegacyMainContainer(){
    const legacy=document.getElementById(LEGACY_MAIN_LIST_ID);
    if(legacy)legacy.remove();
  }

  async function merge(){
    installStyle();
    cleanupLegacyMainContainer();
    renderMergedLists(manualSourcesCache);
    const current=++requestSerial;
    try{
      const data=await sidecar('/sources');
      if(current!==requestSerial)return false;
      manualSourcesCache=Array.isArray(data.sources)?data.sources:[];
      renderMergedLists(manualSourcesCache);
      return true;
    }catch(_){return false;}
  }

  function refreshSoon(){
    if(refreshQueued)return;
    refreshQueued=true;
    window.setTimeout(()=>{refreshQueued=false;merge();},0);
  }

  function openManualById(id){
    const sources=manualSourcesCache.length?manualSourcesCache:(window.lexiaResearchManualSources?.list?.()||[]);
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
    if(target.closest('#newContext')||(target.closest('#startContext')&&/investigar/i.test(String(target.closest('#startContext').textContent||'')))){
      automaticSelectionOverride=null;
      automaticSourceSignature='';
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
        .then(()=>{
          manualSourcesCache=manualSourcesCache.filter(source=>String(source.id||'')!==id);
          renderMergedLists(manualSourcesCache);
          return merge();
        })
        .catch(error=>alert('No se pudo quitar el fragmento.\n\n'+(error.message||String(error))));
    }
  },true);

  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;
    if(target.matches('.research-source-check')){
      automaticSelectionOverride=automaticIndicesFromDom(target);
      /* El renderer nativo sustituye tarjetas y altera tipografía/selección.
         La capa Windows conserva el DOM estable y aplica el estado explícito. */
      event.stopImmediatePropagation();
      applyAutomaticSelectionOverride();
      return;
    }
    if(target.matches('.lexia-manual-source-check[data-manual-id]')){
      const id=String(target.dataset.manualId||'');
      const checked=target.checked;
      document.querySelectorAll('.lexia-manual-source-check[data-manual-id="'+CSS.escape(id)+'"]').forEach(box=>{box.checked=checked;});
      const cached=manualSourcesCache.find(source=>String(source.id||'')===id);
      if(cached)cached.selected=checked;
      sidecar('/set-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,selected:checked})})
        .catch(error=>{
          target.checked=!checked;
          if(cached)cached.selected=!checked;
          alert('No se pudo actualizar la selección.\n\n'+(error.message||String(error)));
        });
    }
  },true);

  document.addEventListener('cancel',event=>{
    if(event.target?.matches?.('#lexiaManualResearchDialog,#lexiaManualResearchSelectionViewer'))window.setTimeout(releaseInvestigationGuard,0);
  },true);

  [0,250,800].forEach(delay=>window.setTimeout(()=>merge(),delay));
  window.lexiaMergeManualResearchSources=merge;
  window.lexiaReleaseManualResearchGuard=releaseInvestigationGuard;
})();
