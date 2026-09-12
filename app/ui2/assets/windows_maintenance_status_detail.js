/* LexIA Windows — explica qué está haciendo AutoSync en la tarjeta lateral. */
(function(){
  'use strict';
  if(window.__lexiaWindowsMaintenanceStatusDetail)return;
  window.__lexiaWindowsMaintenanceStatusDetail=true;

  const shortName=value=>{
    const parts=String(value||'').replace(/\\/g,'/').split('/').filter(Boolean);
    return parts[parts.length-1]||'';
  };

  function detailFor(autosync){
    const phase=String(autosync?.phase||'idle');
    const file=shortName(autosync?.current_file||'');
    const status=String(autosync?.status||'').trim();
    if(phase==='waiting')return status||'Esperando que finalice la operación anterior.';
    if(phase==='scanning')return file?'Analizando cambios · '+file:'Analizando cambios: comparando la biblioteca con el catálogo.';
    if(phase==='indexing')return file?'Indexando texto y vectores · '+file:'Indexando los documentos modificados.';
    if(phase==='knowledge')return file?'Actualizando Knowledge · '+file:'Actualizando el Knowledge Engine con los cambios detectados.';
    if(phase==='error')return status||'AutoSync encontró un error. Abrí Mantenimiento para ver el detalle.';
    return status||'Biblioteca al día.';
  }

  function paint(payload){
    const autosync=payload?.autosync||payload?.live?.autosync||{};
    const ocr=payload?.ocr||payload?.live?.ocr||{};
    if(ocr?.running)return;
    const detail=document.getElementById('liveAutoSyncDetail');
    if(detail)detail.textContent=detailFor(autosync);
    const fn=document.getElementById('liveOperationFunction');
    if(fn&&['waiting','scanning','indexing','knowledge'].includes(String(autosync.phase||''))){
      const labels={waiting:'en espera',scanning:'analizando cambios',indexing:'indexando documentos',knowledge:'actualizando Knowledge'};
      fn.textContent='AutoSync · '+labels[autosync.phase];
    }
  }

  function install(){
    const original=window.lexiaUpdateOperationalSidebar;
    if(typeof original!=='function'||original.__lexiaDetailed)return false;
    const wrapped=function(payload){
      const result=original.apply(this,arguments);
      paint(payload);
      return result;
    };
    wrapped.__lexiaDetailed=true;
    window.lexiaUpdateOperationalSidebar=wrapped;
    return true;
  }

  [0,120,450,1000,2200].forEach(delay=>window.setTimeout(install,delay));
  document.addEventListener('click',event=>{
    if(event.target?.closest?.('#liveOperationRefresh,[data-route="maintenance"],#mRefresh')){
      [0,120,400,900].forEach(delay=>window.setTimeout(install,delay));
    }
  },true);
})();
