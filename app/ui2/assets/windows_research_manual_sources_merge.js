/* LexIA Windows — integra fragmentos manuales directamente en la lista nativa de fuentes. */
(function(){
  'use strict';
  if(window.__lexiaWindowsResearchManualSourcesMergeV3)return;
  window.__lexiaWindowsResearchManualSourcesMergeV3=true;

  const STYLE_ID='lexiaWindowsResearchManualSourcesMergeStyleV3';
  const LIST_ID='researchSourcesModalList';
  const SOURCE_SECTION_ID='lexiaManualResearchModalSources';
  const SIDEBAR_ID='lexiaManualResearchSources';
  const ADD_BUTTON_ID='lexiaAddManualResearchSource';
  const SIDECAR='http://127.0.0.1:8516';
  let serial=0;

  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const pageLabel=source=>{
    if(source?.page_label)return String(source.page_label);
    const start=Number(source?.page_start||0),end=Number(source?.page_end||0);
    if(start&&end&&end!==start)return 'págs. '+start+'–'+end;
    if(start)return 'pág. '+start;
    return 'página no determinada';
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
      #${SOURCE_SECTION_ID},#${SIDEBAR_ID}{display:none!important}

      #contextpage #viewSources,
      #contextpage #${ADD_BUTTON_ID}{
        width:100%!important;min-height:30px!important;height:30px!important;
        margin-top:7px!important;padding:5px 10px!important;border-radius:8px!important;
        font-size:10.5px!important;line-height:1!important;font-weight:700!important;
        box-sizing:border-box!important;
      }
      #contextpage #viewSources{border:1px solid #ddd9f2!important;background:#fff!important;color:#3f3a62!important}
      #contextpage #${ADD_BUTTON_ID}{border:1px solid #bcb6ff!important;background:#f7f6ff!important;color:#352bc7!important}
      #contextpage #${ADD_BUTTON_ID}:hover{background:#efedff!important;border-color:#9f97ff!important}

      #${LIST_ID} .research-source-check{accent-color:#5146f6}
      #${LIST_ID} .lexia-manual-source-inline{
        border:1px solid #bfe5cf!important;background:#f4fbf7!important;
        box-shadow:none!important;border-radius:9px!important;padding:8px 10px!important;
        display:grid!important;grid-template-columns:auto minmax(0,1fr) auto!important;
        gap:9px!important;align-items:start!important;
      }
      #${LIST_ID} .lexia-manual-source-inline .lexia-manual-source-check{accent-color:#169b62!important;margin-top:3px!important}
      #${LIST_ID} .lexia-manual-source-inline .lexia-manual-inline-number{
        display:block;margin:0 0 3px;font-size:9px;line-height:1.1;font-weight:900;
        letter-spacing:.035em;color:#168054!important;
      }
      #${LIST_ID} .lexia-manual-source-inline b{color:#177245!important}
      #${LIST_ID} .lexia-manual-source-inline small{display:block;margin-top:3px;color:#3f7d60!important}
      #${LIST_ID} .lexia-manual-source-inline p{margin:5px 0 0;font-size:9.5px;line-height:1.3;color:#475c50!important;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
      #${LIST_ID} .lexia-manual-source-inline button[data-manual-inline-remove]{
        border:1px solid #b8ddc7!important;background:#fff!important;color:#177245!important;
        border-radius:6px!important;padding:4px 7px!important;font-size:9px!important;cursor:pointer!important;
      }

      /* El buscador manual debe quedar sobre Investigación, nunca sobre Buscar. */
      body.lexia-manual-search-open #searchpage{display:none!important}
      body.lexia-manual-search-open #contextpage{display:block!important}
      #lexiaManualResearchDialog::backdrop,#lexiaManualResearchSelectionViewer::backdrop{background:rgba(246,247,252,.96)!important}
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
    const context=document.getElementById('contextpage');
    const search=document.getElementById('searchpage');
    context?.style.removeProperty('display');
    search?.style.removeProperty('display');
  }

  async function merge(){
    installStyle();
    const list=document.getElementById(LIST_ID);
    if(!list)return false;
    const current=++serial;

    /* Sólo retiramos tarjetas manuales creadas por este módulo. Las fuentes
       nativas halladas por LexIA permanecen intactas. */
    list.querySelectorAll('.lexia-manual-source-inline').forEach(node=>node.remove());

    let sources=[];
    try{
      const data=await sidecar('/sources');
      if(current!==serial)return false;
      sources=Array.isArray(data.sources)?data.sources:[];
    }catch(_){return false;}

    const nativeCount=[...list.querySelectorAll('.research-source-check')]
      .filter(check=>!check.closest('.lexia-manual-source-inline')).length;

    sources.forEach((source,index)=>{
      const label=document.createElement('label');
      label.className='lexia-manual-source-inline';
      label.dataset.manualId=String(source.id||'');
      label.innerHTML=`
        <input type="checkbox" class="lexia-manual-source-check" data-manual-id="${esc(source.id||'')}" ${source.selected!==false?'checked':''}>
        <span>
          <span class="lexia-manual-inline-number">FUENTE ${nativeCount+index+1} · AGREGADA POR EL USUARIO</span>
          <b>${esc(source.name||'Documento')}</b>
          <small>${esc(source.category||'Documento')} · ${esc(pageLabel(source))}</small>
          <p>${esc(source.snippet||source.selected_text||'')}</p>
        </span>
        <button type="button" data-manual-inline-remove="${esc(source.id||'')}" aria-label="Quitar fragmento manual">Quitar</button>`;
      list.appendChild(label);
    });
    return true;
  }

  function burst(){[0,80,220,520,1000,1800,3000].forEach(delay=>window.setTimeout(()=>merge(),delay));}

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;

    if(target.closest('#'+ADD_BUTTON_ID)){
      keepInvestigationBackground();
      [0,60,180,500].forEach(delay=>window.setTimeout(keepInvestigationBackground,delay));
      return;
    }

    if(target.closest('[data-manual-close],[data-viewer-close]')){
      [0,80,220].forEach(delay=>window.setTimeout(releaseInvestigationGuard,delay));
    }

    if(target.closest('#reviewResearchSources,#viewSources,[data-add-selection]'))burst();

    const remove=target.closest('[data-manual-inline-remove]');
    if(remove){
      event.preventDefault();event.stopPropagation();
      const id=String(remove.dataset.manualInlineRemove||'');
      sidecar('/remove-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})
        .then(()=>burst()).catch(error=>alert('No se pudo quitar el fragmento.\n\n'+(error.message||String(error))));
    }
  },true);

  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(target?.matches('.lexia-manual-source-check[data-manual-id]')){
      const id=String(target.dataset.manualId||'');
      sidecar('/set-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,selected:target.checked})})
        .catch(error=>{target.checked=!target.checked;alert('No se pudo actualizar la selección.\n\n'+(error.message||String(error)));});
    }
  },true);

  [0,200,700,1500].forEach(delay=>window.setTimeout(()=>merge(),delay));
  window.lexiaMergeManualResearchSources=merge;
})();
