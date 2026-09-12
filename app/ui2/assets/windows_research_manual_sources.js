/* LexIA Windows — fuentes manuales por fragmento + tipo automático de Estudiar. */
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
  const VIEWER_ID='lexiaManualResearchSelectionViewer';
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
      .lexia-manual-source-name{font-size:11px;font-weight:800;line-height:1.25;color:#242048;overflow-wrap:anywhere}
      .lexia-manual-source-meta{font-size:9.5px;color:#655da0}
      .lexia-manual-source-snippet{font-size:10px;line-height:1.35;color:#4e5267;margin:0;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
      .lexia-manual-source-actions{display:flex;justify-content:flex-end;gap:6px;flex-wrap:wrap}
      .lexia-manual-source-actions button{font-size:9.5px;padding:5px 8px}
      #${MODAL_SECTION_ID}{padding:0 18px 14px;display:grid;gap:7px}
      #${MODAL_SECTION_ID}:empty{display:none}
      #${MODAL_SECTION_ID} .lexia-manual-modal-title{font-size:10px;font-weight:900;color:#5146f6;letter-spacing:.04em;text-transform:uppercase;margin:3px 0}
      .lexia-manual-source-choice{border:1px solid #d9d5ff;border-radius:9px;background:#faf9ff;padding:8px 10px;display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:start}
      .lexia-manual-source-choice input{margin-top:3px}
      .lexia-manual-source-choice small{display:block;margin-top:3px;color:#655da0}
      .lexia-manual-source-choice p{margin:5px 0 0;font-size:9.5px;line-height:1.3;color:#555a70;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
      .lexia-manual-source-choice button{font-size:9px;padding:4px 7px}
      #${DIALOG_ID},#${VIEWER_ID}{width:min(820px,calc(100vw - 28px));max-height:88vh;border:0;border-radius:14px;padding:0;box-shadow:0 18px 55px rgba(25,22,67,.28)}
      #${DIALOG_ID}::backdrop,#${VIEWER_ID}::backdrop{background:rgba(18,20,35,.42)}
      .lexia-manual-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid #e5e3f5}
      .lexia-manual-dialog-body{padding:14px 16px;display:grid;gap:10px;overflow:auto;max-height:72vh}
      .lexia-manual-search-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}
      .lexia-manual-search-row input{min-width:0;padding:9px 10px;border:1px solid #cbc8e2;border-radius:8px;font:inherit}
      .lexia-manual-search-results{display:grid;gap:7px}
      .lexia-manual-search-result{border:1px solid #e0deec;border-radius:9px;padding:9px 10px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center}
      .lexia-manual-search-result small{display:block;margin-top:3px;color:#73758a;overflow-wrap:anywhere}
      .lexia-manual-reader{box-sizing:border-box;width:100%;height:52vh;min-height:300px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;border:1px solid #d9dce8;border-radius:10px;background:#fff;padding:14px;font:12px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;color:#252d49;user-select:text;cursor:text}
      .lexia-manual-reader:focus{outline:2px solid rgba(81,70,246,.18);border-color:#8178ec}
      .lexia-manual-selection-status{margin:0;font-size:10px;color:#66708d}
      .lexia-manual-selection-list{display:flex;gap:6px;flex-wrap:wrap}
      .lexia-manual-selection-chip{border:1px solid #d7d2ff;background:#f2f0ff;color:#4036b4;border-radius:999px;padding:5px 8px;font-size:9px;cursor:pointer}
      .lexia-manual-viewer-actions{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}
      @media(max-width:700px){.lexia-manual-search-result{grid-template-columns:1fr}.lexia-manual-search-row{grid-template-columns:1fr}.lexia-manual-reader{height:48vh;min-height:240px}}
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

  function sourcePageLabel(source){
    if(source?.page_label)return String(source.page_label);
    if(source?.page_start&&source?.page_end&&source.page_end!==source.page_start)return 'págs. '+source.page_start+'–'+source.page_end;
    if(source?.page_start)return 'pág. '+source.page_start;
    return 'página no determinada';
  }

  function renderManualSources(){
    installStyle();
    const sidebar=document.getElementById(SIDEBAR_ID);
    if(sidebar){
      sidebar.innerHTML=manualSources.map((source,index)=>`
        <article class="lexia-manual-source" data-manual-index="${index}">
          <div><div class="lexia-manual-source-name">${escapeHtml(source.name)}</div><div class="lexia-manual-source-meta">${escapeHtml(source.category||'Documento')} · ${escapeHtml(sourcePageLabel(source))} · fragmento manual</div></div>
          <p class="lexia-manual-source-snippet">${escapeHtml(source.snippet||'')}</p>
          <div class="lexia-manual-source-actions"><button type="button" data-manual-open="${index}">Abrir archivo</button><button type="button" data-manual-remove="${index}">Quitar</button></div>
        </article>`).join('');
    }

    const modal=document.getElementById(MODAL_SECTION_ID);
    if(modal){
      modal.innerHTML=manualSources.length
        ? '<div class="lexia-manual-modal-title">Fragmentos agregados por el usuario</div>'+manualSources.map((source,index)=>`
          <label class="lexia-manual-source-choice">
            <input type="checkbox" class="lexia-manual-source-check" data-manual-index="${index}" ${source.selected!==false?'checked':''}>
            <span><b>${escapeHtml(source.name)}</b><small>${escapeHtml(source.category||'Documento')} · ${escapeHtml(sourcePageLabel(source))}</small><p>${escapeHtml(source.snippet||'')}</p></span>
            <button type="button" data-manual-remove="${index}" aria-label="Quitar fragmento manual">Quitar</button>
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
        add.title='Buscar un documento conocido y seleccionar sólo el pasaje pertinente';
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

  function closeElementDialog(id){
    const dialog=document.getElementById(id);
    if(!dialog)return;
    try{dialog.close();}catch(_){}
    dialog.remove();
  }

  function openAddDialog(){
    closeElementDialog(DIALOG_ID);
    const dialog=document.createElement('dialog');
    dialog.id=DIALOG_ID;
    dialog.innerHTML=`
      <div class="lexia-manual-dialog-head"><div><b>Agregar fuente manual a la investigación</b><div style="font-size:10px;color:#6b6d80;margin-top:2px">Buscá el archivo y luego seleccioná únicamente el pasaje pertinente.</div></div><button type="button" class="secondary" data-manual-close>Cerrar</button></div>
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
          <button type="button" class="primary" data-manual-select="${index}">Abrir y seleccionar</button>
        </div>`).join('');
      dialog.__lexiaSearchItems=items;
    }catch(error){if(status)status.textContent=error.message||String(error);}
  }

  function selectionOffsets(reader){
    const selection=window.getSelection();
    if(!selection||!selection.rangeCount||!selection.toString().trim())return null;
    const range=selection.getRangeAt(0);
    if(!reader.contains(range.commonAncestorContainer))return null;
    const prefix=range.cloneRange();
    prefix.selectNodeContents(reader);
    prefix.setEnd(range.startContainer,range.startOffset);
    const raw=selection.toString(),leading=raw.length-raw.trimStart().length;
    const text=raw.trim();
    if(!text)return null;
    const start=prefix.toString().length+leading;
    return {text,start,end:start+text.length};
  }

  function mergeRanges(reader,values){
    const source=String(reader.textContent||'');
    const sorted=values.slice().sort((a,b)=>a.start-b.start),merged=[];
    sorted.forEach(item=>{
      const previous=merged[merged.length-1];
      if(previous&&item.start<=previous.end)previous.end=Math.max(previous.end,item.end);
      else merged.push({start:item.start,end:item.end});
    });
    return merged.map(item=>({start:item.start,end:item.end,text:source.slice(item.start,item.end).trim()})).filter(item=>item.text);
  }

  function pagesForRange(preview,range){
    const overlaps=(preview?.segments||[]).filter(item=>range.start<Number(item.end_char||0)&&range.end>Number(item.start_char||0));
    if(!overlaps.length)return {page_start:null,page_end:null};
    const first=overlaps[0],last=overlaps[overlaps.length-1];
    return {
      page_start:Number(first.page_start||first.page||0)||null,
      page_end:Number(last.page_end||last.page_start||last.page||0)||Number(first.page_start||first.page||0)||null,
    };
  }

  async function openSelectionViewer(item){
    if(!item?.document_path)return;
    closeElementDialog(VIEWER_ID);
    closeElementDialog(DIALOG_ID);
    const dialog=document.createElement('dialog');
    dialog.id=VIEWER_ID;
    dialog.innerHTML=`
      <div class="lexia-manual-dialog-head"><div><b>${escapeHtml(item.document_name||'Documento')}</b><div style="font-size:10px;color:#6b6d80;margin-top:2px">${escapeHtml(item.category||'Documento')} · seleccioná uno o más pasajes. Shift permite sumar otro pasaje separado.</div></div><button type="button" class="secondary" data-viewer-close>Cerrar</button></div>
      <div class="lexia-manual-dialog-body">
        <div class="lexia-manual-reader" tabindex="0" contenteditable="true" spellcheck="false" data-manual-reader>Cargando texto indexado…</div>
        <p class="lexia-manual-selection-status" data-selection-status>Seleccioná el pasaje exacto que querés agregar.</p>
        <div class="lexia-manual-selection-list" data-selection-list></div>
        <div class="lexia-manual-viewer-actions"><button type="button" class="secondary" data-clear-selection>Limpiar selección</button><button type="button" class="primary" data-add-selection>Agregar selección a la investigación</button></div>
      </div>`;
    document.body.appendChild(dialog);
    if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','open');

    const reader=dialog.querySelector('[data-manual-reader]');
    const status=dialog.querySelector('[data-selection-status]');
    const list=dialog.querySelector('[data-selection-list]');
    const add=dialog.querySelector('[data-add-selection]');
    let preview=null,selectedRanges=[],selectionStartedWithShift=false;

    const refresh=()=>{
      list.replaceChildren();
      selectedRanges.forEach((range,index)=>{
        const chip=document.createElement('button');
        chip.type='button';
        chip.className='lexia-manual-selection-chip';
        chip.textContent='Pasaje '+(index+1)+' ×';
        chip.title='Quitar: '+range.text.replace(/\s+/g,' ').slice(0,160);
        chip.addEventListener('click',event=>{
          event.preventDefault();event.stopPropagation();selectedRanges.splice(index,1);refresh();reader.focus({preventScroll:true});
        });
        list.appendChild(chip);
      });
      const chars=selectedRanges.reduce((sum,range)=>sum+range.text.length,0);
      status.textContent=selectedRanges.length
        ? selectedRanges.length+' pasaje(s) seleccionado(s), '+chars+' caracteres. Podés agregar otro manteniendo Shift.'
        : 'Seleccioná con el mouse el pasaje exacto que querés agregar. Mantené Shift para sumar otro separado.';
    };

    const capture=append=>{
      const range=selectionOffsets(reader);
      if(!range)return false;
      selectedRanges=mergeRanges(reader,append?selectedRanges.concat(range):[range]);
      const selection=window.getSelection();if(selection)selection.removeAllRanges();
      refresh();return true;
    };

    reader.addEventListener('beforeinput',event=>event.preventDefault());
    reader.addEventListener('paste',event=>event.preventDefault());
    reader.addEventListener('drop',event=>event.preventDefault());
    reader.addEventListener('selectstart',event=>event.stopPropagation());
    reader.addEventListener('mousedown',event=>{selectionStartedWithShift=event.shiftKey;});
    reader.addEventListener('mouseup',event=>capture(event.shiftKey||selectionStartedWithShift));
    reader.addEventListener('keyup',event=>{if(event.shiftKey)capture(true);});
    dialog.querySelector('[data-clear-selection]').addEventListener('click',()=>{selectedRanges=[];const selection=window.getSelection();if(selection)selection.removeAllRanges();refresh();reader.focus({preventScroll:true});});
    dialog.querySelector('[data-viewer-close]').addEventListener('click',()=>{dialog.close();dialog.remove();});
    add.addEventListener('pointerdown',()=>capture(false));
    add.addEventListener('click',async()=>{
      const live=selectionOffsets(reader);if(live)capture(false);
      if(!selectedRanges.length){alert('Seleccioná uno o más pasajes antes de agregarlos a la investigación.');return;}
      add.disabled=true;
      const previous=add.textContent;
      add.textContent='Agregando…';
      try{
        for(const range of selectedRanges){
          const pages=pagesForRange(preview,range);
          await sidecar('/add-fragment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            path:item.document_path,
            selected_text:range.text,
            page_start:pages.page_start,
            page_end:pages.page_end,
          })});
        }
        await refreshManualSources();
        const count=selectedRanges.length;
        selectedRanges=[];
        refresh();
        status.textContent=count+' fragmento(s) agregado(s). El visor queda abierto para que puedas seleccionar otro pasaje del mismo documento.';
        reader.focus({preventScroll:true});
      }catch(error){alert('No se pudo agregar la selección.\n\n'+(error.message||String(error)));}
      finally{add.disabled=false;add.textContent=previous;}
    });

    try{
      const data=await api('/api/catalog-text-preview?path='+encodeURIComponent(item.document_path));
      preview=data;
      reader.textContent=String(data.text||'');
      if(!reader.textContent.trim())throw new Error('El documento no tiene texto indexado utilizable.');
      refresh();
      reader.focus({preventScroll:true});
    }catch(error){preview=null;reader.textContent='';status.textContent='No se pudo cargar texto seleccionable: '+(error.message||String(error));add.disabled=true;}
  }

  async function removeManual(index){
    const source=manualSources[index];
    if(!source?.id)return;
    try{
      const data=await sidecar('/remove-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:source.id})});
      manualSources=Array.isArray(data.sources)?data.sources:[];
      renderManualSources();
    }catch(error){alert('No se pudo quitar el fragmento.\n\n'+(error.message||String(error)));}
  }

  async function setManualSelected(index,selected){
    const source=manualSources[index];
    if(!source?.id)return;
    source.selected=!!selected;
    try{
      const data=await sidecar('/set-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:source.id,selected:!!selected})});
      manualSources=Array.isArray(data.sources)?data.sources:manualSources;
    }catch(error){
      source.selected=!selected;
      renderManualSources();
      alert('No se pudo actualizar la selección.\n\n'+(error.message||String(error)));
    }
  }

  function openManualSource(index){
    const source=manualSources[index];
    if(!source?.path)return;
    const page=Number(source.page_start||0)||1;
    if(typeof window.lexiaQuickViewerOpen==='function')window.lexiaQuickViewerOpen(source.path,page,String(source.snippet||''));
    else window.open('/api/file-preview?path='+encodeURIComponent(source.path),'_blank','noopener');
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;

    const studyButton=target.closest('.study-source');
    if(studyButton){
      const card=studyButton.closest('.source-item,.lexia-source-choice,.result-card');
      setStudyType((card?.textContent||'')+' '+String(card?.dataset?.path||''));
    }
    if(target.closest('#startStudy'))setStudyType(document.getElementById('studyPath')?.value||'');
    if(target.closest('#startContext,#newContext'))clearManualSources();
  },true);

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;
    if(target.closest('#'+ADD_BUTTON_ID)){openAddDialog();return;}
    if(target.closest('[data-manual-close]')){closeElementDialog(DIALOG_ID);return;}
    const dialog=target.closest('#'+DIALOG_ID);
    if(dialog&&target.closest('[data-manual-search]')){searchDocuments(dialog);return;}
    if(dialog&&target.closest('[data-manual-select]')){
      const button=target.closest('[data-manual-select]');
      const item=dialog.__lexiaSearchItems?.[Number(button.dataset.manualSelect)];
      if(item)openSelectionViewer(item);
      return;
    }
    const remove=target.closest('[data-manual-remove]');
    if(remove){removeManual(Number(remove.dataset.manualRemove));return;}
    const open=target.closest('[data-manual-open]');
    if(open){openManualSource(Number(open.dataset.manualOpen));return;}
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
