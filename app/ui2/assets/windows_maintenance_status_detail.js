/* LexIA Windows — explica qué está haciendo AutoSync en la tarjeta lateral. */
(function(){
  'use strict';
  if(window.__lexiaWindowsMaintenanceStatusDetailV2)return;
  window.__lexiaWindowsMaintenanceStatusDetailV2=true;

  const shortName=value=>{
    const parts=String(value||'').replace(/\\/g,'/').split('/').filter(Boolean);
    return parts[parts.length-1]||'';
  };

  function detailFor(autosync){
    const phase=String(autosync?.phase||'idle');
    const file=shortName(autosync?.current_file||'');
    const status=String(autosync?.status||'').trim();
    const lastStage=String(autosync?.last_stage||'').trim();
    const changed=Number(autosync?.snapshot_changed||0);
    const deleted=Number(autosync?.snapshot_deleted||0);
    const files=Number(autosync?.snapshot_files||0);

    if(phase==='waiting')return status||'Esperando el fin del período de estabilización antes de procesar los cambios.';
    if(phase==='scanning'){
      if(lastStage==='smart_snapshot'){
        return files
          ? `Comparando biblioteca y catálogo · ${files.toLocaleString('es-AR')} archivos revisados · ${changed} cambio(s) · ${deleted} eliminado(s).`
          : 'Comparando la biblioteca física con el catálogo para detectar altas, cambios, movimientos y eliminaciones.';
      }
      return file
        ? 'Analizando cambios · '+file
        : 'Comparando la biblioteca física con el catálogo para detectar qué cambió.';
    }
    if(phase==='indexing')return file?'Indexando texto y vectores · '+file:'Indexando los documentos modificados y actualizando sus vectores.';
    if(phase==='knowledge')return file?'Actualizando Knowledge · '+file:'Actualizando el Knowledge Engine con los documentos procesados.';
    if(phase==='error')return status||'AutoSync encontró un error. Abrí Mantenimiento para ver el detalle.';
    return status||'Biblioteca al día.';
  }

  function paint(payload){
    const autosync=payload?.autosync||payload?.live?.autosync||{};
    const ocr=payload?.ocr||payload?.live?.ocr||{};
    if(ocr?.running)return;

    const phase=String(autosync.phase||'idle');
    const active=['waiting','scanning','indexing','knowledge'].includes(phase);
    const detail=document.getElementById('liveAutoSyncDetail');
    if(detail)detail.textContent=detailFor(autosync);

    const fn=document.getElementById('liveOperationFunction');
    if(fn&&active){
      const labels={waiting:'en espera',scanning:'comparando biblioteca y catálogo',indexing:'indexando documentos',knowledge:'actualizando Knowledge'};
      fn.textContent='AutoSync · '+labels[phase];
    }

    const processed=Number(autosync.processed||0);
    const total=Number(autosync.total||0);
    const label=document.getElementById('liveOperationProgressLabel');
    const queue=document.getElementById('liveOperationQueue');
    const bar=document.getElementById('liveOperationProgress');

    /* Durante scanning no existe un porcentaje lineal fiable: el snapshot recorre
       el árbol completo y recién al terminar conoce el trabajo real. Mostrar 50%
       en esa fase era un dato artificial y confundía al usuario. */
    if(phase==='scanning'){
      if(label)label.textContent='Analizando biblioteca…';
      if(queue)queue.textContent='Fase: detección y comparación de cambios';
      if(bar)bar.style.width='100%';
      if(bar)bar.style.opacity='.35';
    }else{
      if(bar)bar.style.opacity='1';
      if(label&&active&&total>0)label.textContent=Math.max(0,Math.min(100,Math.round(100*processed/total)))+'%';
    }
  }

  function install(){
    const original=window.lexiaUpdateOperationalSidebar;
    if(typeof original!=='function'||original.__lexiaDetailedV2)return false;
    const wrapped=function(payload){
      const result=original.apply(this,arguments);
      paint(payload);
      /* maintenance.js puede repintar la tarjeta al finalizar la misma vuelta.
         Reaplicamos el detalle de forma acotada, sin observadores ni intervalos. */
      [0,40,140].forEach(delay=>window.setTimeout(()=>paint(payload),delay));
      return result;
    };
    wrapped.__lexiaDetailedV2=true;
    window.lexiaUpdateOperationalSidebar=wrapped;
    return true;
  }

  [0,120,450,1000,2200,4500].forEach(delay=>window.setTimeout(install,delay));
  document.addEventListener('click',event=>{
    if(event.target?.closest?.('#liveOperationRefresh,[data-route="maintenance"],#mRefresh')){
      [0,120,400,900].forEach(delay=>window.setTimeout(install,delay));
    }
  },true);
})();
