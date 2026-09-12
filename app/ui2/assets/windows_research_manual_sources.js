/* LexIA Windows — fuentes manuales de Investigación + tipo automático de Estudiar. */
(function(){
  'use strict';

  if(window.__lexiaWindowsResearchManualSources)return;
  window.__lexiaWindowsResearchManualSources=true;

  const SIDECAR='http://127.0.0.1:8516';
  const STYLE_ID='lexiaWindowsResearchManualSourcesStyle';
  const ADD_BUTTON_ID='lexiaAddManualResearchSource';
  const SIDEBAR_ID='lexiaManualResearchSources';
  const MODAL_SECTION_ID='lexiaManualResearchModalSources';
  const DIALOG_ID='lexiaManualResearchDialog';
  let manualSources=[];

  const normalize=value=>String(value||'')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ').trim().toLowerCase();
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,ch=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[ch]));

  async function sidecar(path,options){
    const response=await fetch(SIDECAR+path,Object.assign({cache:'no-store'},options||{}));
    let data={};
    try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  }

  async function api(path,options){
    const response=await fetch(path,Object.assign({cache:'no-store'},options||{}));
    let data={};
    try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  }

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${ADD_BUTTON_ID}{width:100%;margin-top:8px;border:1px solid #8178ec;background:#f4f3ff;color:#312a9f}
      #${SIDEBAR_ID}{margin-top:10px;display:grid;gap:8px}
      #${SIDEBAR_ID}:empty{display:none}
      .lexia-manual-source{border:1px solid #d9d5ff;border-radius:9px;background:#faf9ff;padding:9px 10px;display:grid;gap:5px}
      .lexia-manual-source-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
      .lexia-manual-source-name{font-size:11px;font-weight:800;line-height:1.25;color:#242048;overflow-wrap:anywhere}
      .lexia-manual-source-meta{font-size:9.5px;color:#655da0}
      .lexia-manual-source-snippet{font-size:10px;line-height:1.35;color:#4e5267;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
      .lexia-manual-source-actions{display:flex;justify-content:flex-end;gap:6px;flex-wrap:wrap}
      .lexia-manual-source-actions button{font-size:9.5px;padding:5px 8px}
      #${MODAL_SECTION_ID}{padding:0 18px 14px;display:grid;gap:7px}
      #${MODAL_SECTION_ID}:empty{display:none}
      #${MODAL_SECTION_ID} .lexia-manual-modal-title{font-size:10px;font-weight:900;color:#5146f6;letter-spacing:.04em;text-transform:uppercase;margin:3px 0}
      .lexia-manual-source-choice{border:1px solid #d9d5ff;border-radius:9px;background:#faf9ff;padding:8px 10px;display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:start}
      .lexia-manual-source-choice input{margin-top:3px}
      .lexia-manual-source-choice button{font-size:9px;padding:4px 7px}
      #${DIALOG_ID}{width:min(720px,calc(100vw - 28px));max-height:82vh;border:0;border-radius:14px;padding:0;box-shadow:0 18px 55px rgba(25,22,67,.28)}
      #${DIALOG_ID}::backdrop{background:rgba(18,20,35,.42)}
      .lexia-manual-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid #e5e3f5}
      .lexia-manual-dialog-body{padding:14px 16px;display:grid;gap:10px;overflow:auto;max-height:68vh}
      .lexia-manual-search-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}
      .lexia-manual-search-row input{min-width:0;padding:9px 10px;border:1px solid #cbc8e2;border-radius:8px;font:inherit}
      .lexia-manual-search-results{display:grid;gap:7px}
      .lexia-manual-search-result{border:1px solid #e0deec;border-radius:9px;padding:9px 10px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center}
      .lexia-manual-search-result small{display:block;margin-top:3px;color:#73758a;overflow-wrap:anywhere}
      @media(max-width:700px){.lexia-manual-search-result{grid-template-columns:1fr}.lexia-manual-search-row{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function ensureStudyTypes(){
    const select=document.getElementById('studyType');
    if(!select)return false;
    ['Doctrina','Legislación'].forEach(label=>{
      if(![...select.options].some(option=>normalize(option.value||option.textContent)===normalize(label))){
        const option=document.createElement('option');
        option.value=label;
        option.textContent=label;
        select.appendChild(option);
      }
    });
    return true;
  }

  function inferredStudyType(value){
    const text=normalize(value);
    if(!text)return '';
    if(/(^|[\\/\s])doctrina([\\/\s]|$)/.test(text))return 'Doctrina';
    if(/(^|[\\/\s])(jurisprudencia|fallos?|sentencias?)([\\/\s]|$)/.test(text))return 'Fallo judicial';
    if(/(^|[\\/\s])legislacion([\\/\s]|$)/.test(text))return 'Legislación';
    return '';
  }

  function setStudyType(value){
    ensureStudyTypes();
    const detected=inferredStudyType(value);
    const select=document.getElementById('studyType');
    if(detected&&select&&[...select.options].some(option=>option.value===detected))select.value=detected;
    return detected;
  }

  function studyManualSource(source){
    const path=document.getElementById('studyPath');
    if(path)path.value=String(source.path||'');
    setStudyType(String(source.category||'')+' '+String(source.path||''));
    document.getElementById('studyTab')?.click();
    document.getElementById('researchSourcesModal')?.classList.remove('open');
    document.getElementById('researchSourcesModal')?.setAttribute('aria-hidden','true');
  }

  function renderManualSources(){
    installStyle();
    const sidebar=document.getElementById(SIDEBAR_ID);
    if(sidebar){
      sidebar.innerHTML=manualSources.map((source,index)=>`
        <article class="lexia-manual-source" data-manual-index="${index}">
          <div class="lexia-manual-source-head"><div><div class="lexia-manual-source-name">${escapeHtml(source.name)}</div><div class="lexia-manual-source-meta">${escapeHtml(source.category||'Documento')} · agregada manualmente</div></div></div>
          <p class="lexia-manual-source-snippet">${escapeHtml(source.snippet||'')}</p>
          <div class="lexia-manual-source-actions"><button type="button" data-manual-study="${index}">Estudiar</button><button type="button" data-manual-remove="${index}">Quitar</button></div>
        </article>`).join('');
    }

    const modal=document.getElementById(MODAL_SECTION_ID);
    if(modal){
      modal.innerHTML=manualSources.length
        ? '<div class="lexia-manual-modal-title">Documentos agregados por el usuario</div>'+manualSources.map((source,index)=>`
          <label class="lexia-manual-source-choice">
            <input type="checkbox" class="lexia-manual-source-check" data-manual-index="${index}" ${source.selected!==false?'checked':''}>
            <span><b>${escapeHtml(source.name)}</b><small>${escapeHtml(source.category||'Documento')} · ${escapeHtml(source.page_label||'Documento completo')}</small></span>
            <button type="button" data-manual-remove="${index}" aria-label="Quitar documento manual">Quitar</button>
          </label>`).join('')
        : '';
    }
  }

  async function refreshManualSources(){
    try{
      const data=await sidecar('/sources');
      manualSources=Array.isArray(data.sources)?data.sources:[];
      renderManualSources();
    }catch(_){
      manualSources=[];
      renderManualSources();
    }
  }

  async function clearManualSources(){
    manualSources=[];
    renderManualSources();
    try{await sidecar('/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(_){}
  }

  function ensureContainers(){
    installStyle();
    ensureStudyTypes();
    const view=document.getElementById('viewSources');
    if(view){
      let add=document.getElementById(ADD_BUTTON_ID);
      if(!add){
        add=document.createElement('button');
        add.type='button';
        add.id=ADD_BUTTON_ID;
        add.className='secondary';
        add.textContent='Agregar documento conocido';
        add.title='Agregar a la investigación un documento pertinente que LexIA no recuperó';
        view.insertAdjacentElement('afterend',add);
      }
      let sidebar=document.getElementById(SIDEBAR_ID);
      if(!sidebar){
        sidebar=document.createElement('div');
        sidebar.id=SIDEBAR_ID;
        add.insertAdjacentElement('afterend',sidebar);
      }
    }

    const modalList=document.getElementById('researchSourcesModalList');
    if(modalList&&!document.getElementById(MODAL_SECTION_ID)){
      const section=document.createElement('div');
      section.id=MODAL_SECTION_ID;
      modalList.insertAdjacentElement('afterend',section);
    }
    renderManualSources();
    return !!view;
  }

  function closeDialog(){
    const dialog=document.getElementById(DIALOG_ID);
    if(!dialog)return;
    try{dialog.close();}catch(_){}
    dialog.remove();
  }

  function openAddDialog(){
    closeDialog();
    const dialog=document.createElement('dialog');
    dialog.id=DIALOG_ID;
    dialog.innerHTML=`
      <div class="lexia-manual-dialog-head"><div><b>Agregar documento a la investigación</b><div style="font-size:10px;color:#6b6d80;margin-top:2px">Buscá por nombre dentro de la biblioteca de LexIA.</div></div><button type="button" class="secondary" data-manual-close>Cerrar</button></div>
      <div class="lexia-manual-dialog-body">
        <div class="lexia-manual-search-row"><input type="search" data-manual-query placeholder="Nombre o parte del nombre del archivo" autocomplete="off"><button type="button" class="primary" data-manual-search>Buscar</button></div>
        <div data-manual-status style="font-size:10px;color:#6b6d80"></div>
        <div class="lexia-manual-search-results" data-manual-results></div>
      </div>`;
    document.body.appendChild(dialog);
    if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','open');
    dialog.querySelector('[data-manual-query]')?.focus();
  }

  async function searchDocuments(dialog){
    const input=dialog.querySelector('[data-manual-query]');
    const status=dialog.querySelector('[data-manual-status]');
    const results=dialog.querySelector('[data-manual-results]');
    const query=String(input?.value||'').trim();
    if(!query){if(status)status.textContent='Ingresá al menos una parte del nombre del archivo.';return;}
    if(status)status.textContent='Buscando en la biblioteca…';
    if(results)results.innerHTML='';
    try{
      const data=await api('/api/search-filename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,limit:40})});
      const items=Array.isArray(data.results)?data.results:[];
      if(status)status.textContent=items.length?items.length+' documento(s) encontrado(s).':'No se encontraron archivos con ese nombre.';
      if(results)results.innerHTML=items.map((item,index)=>`
        <div class="lexia-manual-search-result" data-search-index="${index}">
          <div><b>${escapeHtml(item.document_name||'Documento')}</b><small>${escapeHtml(item.category||'Documento')} · ${escapeHtml(item.document_path||'')}</small></div>
          <button type="button" class="primary" data-manual-add="${index}">Agregar</button>
        </div>`).join('');
      dialog.__lexiaSearchItems=items;
    }catch(error){if(status)status.textContent=error.message||String(error);}
  }

  async function addSearchResult(dialog,index,button){
    const item=dialog.__lexiaSearchItems?.[index];
    if(!item?.document_path)return;
    const previous=button.textContent;
    button.disabled=true;
    button.textContent='Agregando…';
    try{
      const data=await sidecar('/add-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:item.document_path})});
      manualSources=Array.isArray(data.sources)?data.sources:manualSources;
      renderManualSources();
      button.textContent='Agregado';
      const status=dialog.querySelector('[data-manual-status]');
      if(status)status.textContent='Documento agregado. Quedará incluido si permanece seleccionado al crear el paquete.';
    }catch(error){
      button.textContent=previous;
      button.disabled=false;
      const status=dialog.querySelector('[data-manual-status]');
      if(status)status.textContent=error.message||String(error);
    }
  }

  async function removeManual(index){
    const source=manualSources[index];
    if(!source)return;
    try{
      const data=await sidecar('/remove-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:source.path})});
      manualSources=Array.isArray(data.sources)?data.sources:[];
      renderManualSources();
    }catch(error){alert('No se pudo quitar el documento.\n\n'+(error.message||String(error)));}
  }

  async function setManualSelected(index,selected){
    const source=manualSources[index];
    if(!source)return;
    source.selected=!!selected;
    try{
      const data=await sidecar('/set-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:source.path,selected:!!selected})});
      manualSources=Array.isArray(data.sources)?data.sources:manualSources;
    }catch(error){
      source.selected=!selected;
      renderManualSources();
      alert('No se pudo actualizar la selección.\n\n'+(error.message||String(error)));
    }
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;

    const studyButton=target.closest('.study-source');
    if(studyButton){
      const card=studyButton.closest('.source-item,.lexia-source-choice,.result-card');
      setStudyType((card?.textContent||'')+' '+String(card?.dataset?.path||''));
    }

    if(target.closest('#startStudy')){
      const path=document.getElementById('studyPath')?.value||'';
      setStudyType(path);
    }

    if(target.closest('#startContext,#newContext')){
      clearManualSources();
    }
  },true);

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;
    if(target.closest('#'+ADD_BUTTON_ID)){openAddDialog();return;}
    if(target.closest('[data-manual-close]')){closeDialog();return;}
    const dialog=target.closest('#'+DIALOG_ID);
    if(dialog&&target.closest('[data-manual-search]')){searchDocuments(dialog);return;}
    if(dialog&&target.closest('[data-manual-add]')){
      const button=target.closest('[data-manual-add]');
      addSearchResult(dialog,Number(button.dataset.manualAdd),button);
      return;
    }
    const remove=target.closest('[data-manual-remove]');
    if(remove){removeManual(Number(remove.dataset.manualRemove));return;}
    const study=target.closest('[data-manual-study]');
    if(study){const source=manualSources[Number(study.dataset.manualStudy)];if(source)studyManualSource(source);return;}
    if(target.closest('#viewSources'))window.setTimeout(()=>{ensureContainers();refreshManualSources();},0);
  });

  document.addEventListener('keydown',event=>{
    const dialog=document.getElementById(DIALOG_ID);
    if(dialog&&event.key==='Enter'&&event.target?.matches('[data-manual-query]')){
      event.preventDefault();searchDocuments(dialog);
    }
  });

  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(target?.matches('.lexia-manual-source-check'))setManualSelected(Number(target.dataset.manualIndex),target.checked);
    if(target?.matches('#studyPath'))setStudyType(target.value);
  },true);

  [0,120,450,1200].forEach(delay=>window.setTimeout(()=>{ensureContainers();refreshManualSources();},delay));
  window.lexiaResearchManualSources={refresh:refreshManualSources,clear:clearManualSources,list:()=>manualSources.slice()};
})();
