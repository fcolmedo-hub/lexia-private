/* LexIA Windows — retorno explícito de fuentes de Investigación al bloque de origen. */
(function(){
  'use strict';

  if(window.__lexiaWindowsCaseResearchReturn)return;
  window.__lexiaWindowsCaseResearchReturn=true;

  const STORAGE_KEY='lexia.case.research.context.v2';
  const BUTTON_ID='lexiaCaseReturnSelectedSources';
  const ACTIONS_ID='lexiaCaseReturnActions';
  const STYLE_ID='lexiaCaseReturnStyle';
  const MANUAL_SOURCES_URL='http://127.0.0.1:8516/sources';

  function loadContext(){
    try{return JSON.parse(sessionStorage.getItem(STORAGE_KEY)||'null');}
    catch(_){return null;}
  }

  function saveContext(ctx){
    sessionStorage.setItem(STORAGE_KEY,JSON.stringify(ctx));
  }

  function clearContext(){
    sessionStorage.removeItem(STORAGE_KEY);
    try{window.lexiaCaseResearchBridge?.clear?.();}catch(_){}
  }

  async function jsonFetch(url,options){
    const response=await fetch(url,Object.assign({
      cache:'no-store',
      headers:{'Content-Type':'application/json'}
    },options||{}));
    let data={};
    try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false){
      throw new Error(data.detail||data.error||data.message||('HTTP '+response.status));
    }
    return data;
  }

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${ACTIONS_ID}{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}
      #${BUTTON_ID}{
        min-height:34px;padding:7px 11px;border:1px solid #5146f6;border-radius:8px;
        background:#5146f6;color:#fff;font:800 10px/1.15 system-ui,-apple-system,"Segoe UI",sans-serif;
        cursor:pointer;white-space:normal
      }
      #${BUTTON_ID}:hover{background:#4338e8;border-color:#4338e8}
      #${BUTTON_ID}:disabled{opacity:.5;cursor:default}
      @media(max-width:700px){#${ACTIONS_ID}{width:100%}#${ACTIONS_ID}>button{flex:1 1 180px}}
    `;
    document.head.appendChild(style);
  }

  function selectedIndices(){
    return [...document.querySelectorAll('#researchSourcesModalList .research-source-check:checked')]
      .map(box=>Number(box.dataset.sourceIndex))
      .filter(Number.isFinite);
  }

  async function selectedManualSources(){
    try{
      const data=await jsonFetch(MANUAL_SOURCES_URL);
      return (Array.isArray(data.sources)?data.sources:[]).filter(source=>source.selected!==false);
    }catch(_){return [];}
  }

  function pageOf(source){
    const direct=Number(source?.page_start||source?.page||0);
    if(direct>0)return direct;
    const match=String(source?.page_label||'').match(/\d+/);
    return match?Math.max(1,Number(match[0])):1;
  }

  function sourceName(source){
    const fromPath=String(source?.path||'').split(/[\\/]/).pop();
    return String(source?.name||fromPath||'Fuente de investigación').trim();
  }

  function setHelp(message){
    const help=document.getElementById('sourceSelectionHelp');
    if(help)help.textContent=String(message||'');
  }

  function casesNavButton(){
    const norm=value=>String(value||'')
      .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
      .replace(/\s+/g,' ').trim().toLowerCase();
    return [...document.querySelectorAll('#globalSidebar .nav button,.global-sidebar .nav button')]
      .find(button=>norm(button.textContent)==='casos');
  }

  function navigateToCases(){
    document.getElementById('researchSourcesModal')?.classList.remove('open');
    document.getElementById('researchSourcesModal')?.setAttribute('aria-hidden','true');
    const button=casesNavButton();
    if(!button)return false;
    button.click();
    [100,300,700].forEach(delay=>window.setTimeout(()=>{
      try{window.lexiaCaseResearchBridge?.sync?.();}catch(_){}
    },delay));
    return true;
  }

  async function resultSources(){
    const data=await jsonFetch('/api/research-candidates-result');
    return Array.isArray(data?.result?.sources)?data.result.sources:[];
  }

  async function addSourceToCase(source,ctx,linkIds){
    const path=String(source?.path||'').trim();
    if(!path)throw new Error('La fuente “'+sourceName(source)+'” no conserva una ruta utilizable.');

    let caseDocumentId=linkIds.get(path);
    if(!caseDocumentId){
      const linked=await jsonFetch('/api/cases/link-document',{
        method:'POST',
        body:JSON.stringify({
          case_id:Number(ctx.caseId),
          document_id:source.document_id||null,
          document_name:sourceName(source),
          document_path:path,
          category:String(source.category||''),
          relation_kind:'fuente de investigación',
          note:'Fuente incorporada desde Investigación · '+String(ctx.nodeTitle||'bloque del caso')
        })
      });
      caseDocumentId=Number(linked.link_id||0);
      if(!caseDocumentId)throw new Error('No se pudo vincular “'+sourceName(source)+'” a Archivos del caso.');
      linkIds.set(path,caseDocumentId);
    }

    const page=pageOf(source);
    const selectedText=String(source.snippet||'').trim()||sourceName(source);
    await jsonFetch('/api/cases/block/highlight',{
      method:'POST',
      body:JSON.stringify({
        case_id:Number(ctx.caseId),
        block_id:Number(ctx.blockId),
        case_document_id:caseDocumentId,
        page_start:page,
        page_end:page,
        selected_text:selectedText,
        anchor_data:''
      })
    });
  }

  async function incorporateSelected(button){
    const ctx=loadContext();
    if(!ctx?.caseId||!ctx?.blockId){
      alert('Esta investigación ya no conserva el vínculo con el bloque de origen.');
      ensureButton();
      return;
    }

    const indices=selectedIndices();
    const manual=await selectedManualSources();
    if(!indices.length&&!manual.length){
      alert('Seleccioná al menos una fuente antes de incorporarla al caso.');
      return;
    }

    const previous=button.textContent;
    button.disabled=true;
    button.textContent='Incorporando…';
    setHelp('Incorporando las fuentes seleccionadas al bloque del caso…');

    let done=0;
    const already=new Set((ctx.incorporatedSourceIndexes||[]).map(Number));
    const alreadyManual=new Set((ctx.incorporatedManualPaths||[]).map(value=>String(value).casefold?.()||String(value).toLowerCase()));

    try{
      const sources=indices.length?await resultSources():[];
      const byIndex=new Map(sources.map(source=>[Number(source.index),source]));
      const linkIds=new Map();

      for(const index of indices){
        if(already.has(index))continue;
        const source=byIndex.get(index);
        if(!source)throw new Error('No se pudo recuperar la fuente '+(index+1)+' de la investigación.');
        await addSourceToCase(source,ctx,linkIds);
        already.add(index);
        ctx.incorporatedSourceIndexes=[...already];
        saveContext(ctx);
        done+=1;
      }

      for(const source of manual){
        const path=String(source?.path||'').trim();
        const key=path.toLowerCase();
        if(!path||alreadyManual.has(key))continue;
        await addSourceToCase(source,ctx,linkIds);
        alreadyManual.add(key);
        ctx.incorporatedManualPaths=[...alreadyManual];
        saveContext(ctx);
        done+=1;
      }

      if(!done){
        setHelp('Las fuentes seleccionadas ya estaban incorporadas al bloque.');
      }else{
        setHelp('Fuentes incorporadas correctamente. Volviendo al caso…');
      }

      clearContext();
      if(!navigateToCases()){
        alert('Las fuentes se incorporaron correctamente, pero no se pudo abrir el menú Casos.');
        return;
      }
    }catch(error){
      setHelp('No se pudo completar la incorporación al caso.');
      alert((done?'Se incorporaron '+done+' fuente(s). ':'')+(error.message||String(error)));
    }finally{
      button.textContent=previous;
      button.disabled=false;
    }
  }

  function ensureButton(){
    installStyle();
    const footer=document.querySelector('#researchSourcesModal .lexia-sources-foot');
    const build=document.getElementById('buildResearchPackage');
    if(!footer||!build)return false;

    let actions=document.getElementById(ACTIONS_ID);
    if(!actions){
      actions=document.createElement('div');
      actions.id=ACTIONS_ID;
      footer.insertBefore(actions,build);
      actions.appendChild(build);
    }

    let button=document.getElementById(BUTTON_ID);
    if(!button){
      button=document.createElement('button');
      button.type='button';
      button.id=BUTTON_ID;
      button.textContent='Incorporar al caso y volver';
      button.addEventListener('click',()=>incorporateSelected(button));
      actions.appendChild(button);
    }

    const ctx=loadContext();
    button.hidden=!(ctx?.caseId&&ctx?.blockId);
    return true;
  }

  function syncBurst(){
    [0,100,350,900,1700,3000,5000].forEach(delay=>window.setTimeout(ensureButton,delay));
  }

  function isResearchAction(target){
    if(!target)return false;
    if(target.closest('.lexia-case-investigate,#researchTab,#startContext,#reviewResearchSources'))return true;
    const button=target.closest('#contextpage button');
    const label=String(button?.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();
    return label==='investigar'||label==='revisar fuentes';
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(isResearchAction(target))syncBurst();
  },true);

  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(target?.matches('.research-source-check,.lexia-manual-source-check'))ensureButton();
  },true);

  window.lexiaCaseResearchReturn={sync:ensureButton,burst:syncBurst};

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',syncBurst,{once:true});
  else syncBurst();
})();
