/* LexIA Windows — corrección de selección manual de fuentes de Investigación. */
(function(){
  'use strict';

  if(window.__lexiaWindowsResearchManualSelectionFix)return;
  window.__lexiaWindowsResearchManualSelectionFix=true;

  const DIALOG_ID='lexiaManualResearchDialog';
  const VIEWER_ID='lexiaManualResearchSelectionViewer';
  const SIDECAR='http://127.0.0.1:8516';
  const STYLE_ID='lexiaManualResearchSelectionFixStyle';
  let activeItem=null;
  const states=new WeakMap();

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${VIEWER_ID} .lexia-manual-reader mark.lexia-manual-selected-mark{
        background:#fff0a8!important;
        color:inherit!important;
        border-radius:2px;
        box-shadow:inset 0 -1px 0 rgba(185,145,0,.18);
      }
      #${VIEWER_ID} .lexia-manual-reader{
        -webkit-user-select:text!important;
        user-select:text!important;
        cursor:text!important;
      }
    `;
    document.head.appendChild(style);
  }

  async function jsonFetch(url,options){
    const response=await fetch(url,Object.assign({cache:'no-store'},options||{}));
    let data={};
    try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false)throw new Error(data.error||data.detail||('HTTP '+response.status));
    return data;
  }

  function selectionOffsets(reader){
    const selection=window.getSelection();
    if(!selection||!selection.rangeCount||!selection.toString().trim())return null;
    const range=selection.getRangeAt(0);
    if(!reader.contains(range.commonAncestorContainer))return null;
    const prefix=range.cloneRange();
    prefix.selectNodeContents(reader);
    prefix.setEnd(range.startContainer,range.startOffset);
    const raw=selection.toString();
    const leading=raw.length-raw.trimStart().length;
    const text=raw.trim();
    if(!text)return null;
    const start=prefix.toString().length+leading;
    return {start,end:start+text.length,text};
  }

  function normalizedRanges(source,values){
    const sorted=values
      .map(item=>({start:Math.max(0,Number(item.start)||0),end:Math.min(source.length,Number(item.end)||0)}))
      .filter(item=>item.end>item.start)
      .sort((a,b)=>a.start-b.start);
    const merged=[];
    sorted.forEach(item=>{
      const previous=merged[merged.length-1];
      if(previous&&item.start<=previous.end)previous.end=Math.max(previous.end,item.end);
      else merged.push({...item});
    });
    return merged.map(item=>({
      start:item.start,
      end:item.end,
      text:source.slice(item.start,item.end).trim(),
    })).filter(item=>item.text);
  }

  function paint(reader,state){
    const source=state.sourceText||String(reader.textContent||'');
    state.sourceText=source;
    const scrollTop=reader.scrollTop;
    const ranges=state.ranges;
    if(!ranges.length){
      reader.replaceChildren(document.createTextNode(source));
      reader.scrollTop=scrollTop;
      return;
    }
    const boundaries=[...new Set([0,source.length,...ranges.flatMap(item=>[item.start,item.end])])]
      .filter(value=>value>=0&&value<=source.length)
      .sort((a,b)=>a-b);
    const nodes=[];
    for(let index=0;index<boundaries.length-1;index+=1){
      const start=boundaries[index],end=boundaries[index+1];
      const text=source.slice(start,end);
      if(!text)continue;
      const selected=ranges.some(item=>item.start<end&&item.end>start);
      if(selected){
        const mark=document.createElement('mark');
        mark.className='lexia-manual-selected-mark';
        mark.textContent=text;
        nodes.push(mark);
      }else nodes.push(document.createTextNode(text));
    }
    reader.replaceChildren(...nodes);
    reader.scrollTop=scrollTop;
  }

  function updateStatus(dialog,state,message){
    const status=dialog.querySelector('[data-selection-status]');
    if(!status)return;
    if(message){status.textContent=message;return;}
    const chars=state.ranges.reduce((sum,item)=>sum+item.text.length,0);
    status.textContent=state.ranges.length
      ? state.ranges.length+' pasaje(s) seleccionado(s), '+chars+' caracteres. Cada nueva selección se suma y queda marcada en amarillo.'
      : 'Seleccioná uno o más párrafos con el mouse. Cada nueva selección se suma automáticamente.';
  }

  function renderChips(dialog,reader,state){
    const list=dialog.querySelector('[data-selection-list]');
    if(!list)return;
    list.replaceChildren();
    state.ranges.forEach((range,index)=>{
      const chip=document.createElement('button');
      chip.type='button';
      chip.className='lexia-manual-selection-chip';
      chip.textContent='Pasaje '+(index+1)+' ×';
      chip.title='Quitar: '+range.text.replace(/\s+/g,' ').slice(0,180);
      chip.addEventListener('click',event=>{
        event.preventDefault();
        event.stopPropagation();
        state.ranges.splice(index,1);
        paint(reader,state);
        renderChips(dialog,reader,state);
        updateStatus(dialog,state);
      });
      list.appendChild(chip);
    });
  }

  function redraw(dialog,reader,state,message){
    paint(reader,state);
    renderChips(dialog,reader,state);
    updateStatus(dialog,state,message);
  }

  function captureSelection(dialog,reader,state){
    if(!reader||!document.body.contains(reader))return false;
    const selected=selectionOffsets(reader);
    if(!selected)return false;
    state.sourceText=String(reader.textContent||'');
    state.ranges=normalizedRanges(state.sourceText,state.ranges.concat(selected));
    const selection=window.getSelection();
    if(selection)selection.removeAllRanges();
    redraw(dialog,reader,state);
    return true;
  }

  function pagesForRange(preview,range){
    const overlaps=(preview?.segments||[]).filter(item=>
      range.start<Number(item.end_char||0)&&range.end>Number(item.start_char||0)
    );
    if(!overlaps.length)return {page_start:null,page_end:null};
    const first=overlaps[0],last=overlaps[overlaps.length-1];
    const firstPage=Number(first.page_start||first.page||0)||null;
    const lastPage=Number(last.page_end||last.page_start||last.page||0)||firstPage;
    return {page_start:firstPage,page_end:lastPage};
  }

  async function ensurePreview(state){
    if(state.preview)return state.preview;
    if(!state.item?.document_path)return null;
    state.preview=await jsonFetch('/api/catalog-text-preview?path='+encodeURIComponent(state.item.document_path));
    return state.preview;
  }

  function setupViewer(){
    installStyle();
    const dialog=document.getElementById(VIEWER_ID);
    const reader=dialog?.querySelector('[data-manual-reader]');
    if(!dialog||!reader)return false;
    let state=states.get(dialog);
    if(!state){
      state={item:activeItem,ranges:[],sourceText:'',preview:null,busy:false};
      states.set(dialog,state);
    }else if(activeItem)state.item=activeItem;
    reader.setAttribute('contenteditable','false');
    return true;
  }

  function scheduleViewerSetup(){
    [0,50,150,350,700].forEach(delay=>window.setTimeout(setupViewer,delay));
  }

  async function addSelections(dialog,button){
    const reader=dialog.querySelector('[data-manual-reader]');
    const state=states.get(dialog);
    if(!reader||!state)return;
    if(!state.ranges.length){
      alert('Seleccioná uno o más párrafos antes de agregarlos a la investigación.');
      return;
    }
    if(!state.item?.document_path){
      alert('No se pudo identificar el archivo seleccionado. Cerrá el visor y volvé a abrirlo desde el buscador.');
      return;
    }
    if(state.busy)return;
    state.busy=true;
    const previous=button.textContent;
    button.disabled=true;
    button.textContent='Agregando…';
    let added=0;
    try{
      const preview=await ensurePreview(state);
      for(const range of state.ranges){
        const pages=pagesForRange(preview,range);
        await jsonFetch(SIDECAR+'/add-fragment',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({
            path:state.item.document_path,
            selected_text:range.text,
            page_start:pages.page_start,
            page_end:pages.page_end,
          }),
        });
        added+=1;
      }
      try{await window.lexiaResearchManualSources?.refresh?.();}catch(_){}
      state.ranges=[];
      redraw(dialog,reader,state,added+' fragmento(s) agregado(s). Podés seguir seleccionando otros párrafos del mismo documento.');
    }catch(error){
      try{await window.lexiaResearchManualSources?.refresh?.();}catch(_){}
      alert((added?'Se agregaron '+added+' fragmento(s). ':'')+'No se pudo completar la selección.\n\n'+(error.message||String(error)));
    }finally{
      state.busy=false;
      button.disabled=false;
      button.textContent=previous;
    }
  }

  /*
   * El buscador manual vive dentro de un <dialog>. Con consulta vacía no debe
   * propagarse al buscador principal de LexIA que está detrás del modal.
   */
  window.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    const button=target?.closest?.('#'+DIALOG_ID+' [data-manual-search]');
    if(!button)return;
    const dialog=button.closest('#'+DIALOG_ID);
    const input=dialog?.querySelector('[data-manual-query]');
    if(String(input?.value||'').trim())return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const status=dialog.querySelector('[data-manual-status]');
    if(status)status.textContent='Escribí el nombre o una parte del nombre del archivo para buscarlo en la biblioteca.';
    input?.focus();
  },true);

  window.addEventListener('keydown',event=>{
    const input=event.target instanceof Element?event.target.closest?.('#'+DIALOG_ID+' [data-manual-query]'):null;
    if(!input||event.key!=='Enter'||String(input.value||'').trim())return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const dialog=input.closest('#'+DIALOG_ID);
    const status=dialog?.querySelector('[data-manual-status]');
    if(status)status.textContent='Escribí el nombre o una parte del nombre del archivo para buscarlo en la biblioteca.';
  },true);

  /* Guardamos el archivo antes de que el módulo original cierre el buscador. */
  window.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    const button=target?.closest?.('#'+DIALOG_ID+' [data-manual-select]');
    if(!button)return;
    const dialog=button.closest('#'+DIALOG_ID);
    const item=dialog?.__lexiaSearchItems?.[Number(button.dataset.manualSelect)];
    if(item?.document_path)activeItem=item;
    scheduleViewerSetup();
  },true);

  /*
   * El módulo anterior quitaba inmediatamente la selección nativa y sólo
   * mostraba chips. Aquí interceptamos el mouseup, acumulamos cada pasaje y lo
   * pintamos en amarillo. Una selección posterior se SUMA por defecto: no hace
   * falta mantener Shift para conservar párrafos anteriores.
   */
  window.addEventListener('mouseup',event=>{
    const target=event.target instanceof Element?event.target:null;
    const reader=target?.closest?.('#'+VIEWER_ID+' [data-manual-reader]');
    if(!reader)return;
    event.stopPropagation();
    const dialog=reader.closest('#'+VIEWER_ID);
    setupViewer();
    const state=states.get(dialog);
    window.setTimeout(()=>captureSelection(dialog,reader,state),0);
  },true);

  window.addEventListener('keyup',event=>{
    const target=event.target instanceof Element?event.target:null;
    const reader=target?.closest?.('#'+VIEWER_ID+' [data-manual-reader]');
    if(!reader)return;
    event.stopPropagation();
  },true);

  window.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    const clear=target?.closest?.('#'+VIEWER_ID+' [data-clear-selection]');
    if(clear){
      event.preventDefault();
      event.stopImmediatePropagation();
      const dialog=clear.closest('#'+VIEWER_ID);
      const reader=dialog.querySelector('[data-manual-reader]');
      setupViewer();
      const state=states.get(dialog);
      state.sourceText=String(reader.textContent||state.sourceText||'');
      state.ranges=[];
      const selection=window.getSelection();if(selection)selection.removeAllRanges();
      redraw(dialog,reader,state);
      return;
    }
    const add=target?.closest?.('#'+VIEWER_ID+' [data-add-selection]');
    if(!add)return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const dialog=add.closest('#'+VIEWER_ID);
    setupViewer();
    addSelections(dialog,add);
  },true);

  installStyle();
})();
