/* >>> LEXIA UI2 3.3.3v MANTENIMIENTO OPERATIVO */
(function(){
  const page=document.getElementById('maintenance');
  if(!page)return;
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
  let state=null,tab='activity',pollTimer=null,working=false;
  const modes={manual:'Manual',automatic:'Automático',scheduled:'Programado'};
  const card=html=>'<section class="maint-card">'+html+'</section>';
  const button=(id,label,kind='secondary',disabled=false)=>'<button type="button" class="maint-btn '+kind+'" id="'+id+'" '+(disabled?'disabled':'')+'>'+label+'</button>';
  function toast(message,isError=false){const target=document.getElementById('mToast');if(target){target.textContent=message||'';target.style.color=isError?'#a63b28':'#4f5f82';}}
  function kpi(label,value,detail){return '<section class="maint-card mkpi"><span class="mkpi-label">'+esc(label)+'</span><strong class="mkpi-value">'+esc(value)+'</strong><span class="mkpi-detail">'+esc(detail)+'</span></section>';}
  function problems(items){return items.length?items.map(item=>'<div class="maint-warn"><b>'+esc(item.kind)+'</b><p>'+esc(item.message)+'</p><small>Cómo corregir: '+esc(item.action)+'</small></div>').join(''):'<p class="maint-empty">No se detectaron incidencias que requieran intervención.</p>';}
  function phaseLabel(phase){return ({waiting:'en espera',scanning:'analizando',indexing:'indexando',knowledge:'actualizando Knowledge',idle:'en reposo',error:'con error'})[phase]||phase||'en reposo';}
  function render(){
    if(!state)return;
    const live=state.live||{},sync=live.autosync||{},ocr=live.ocr||{},catalog=live.catalog||{},config=state.autosync_config||{},items=state.problems||[];
    const attention=sync.phase==='error'||Number(ocr.error||0)>0;
    let body='';
    if(tab==='activity'){
      body='<div class="maint-grid">'+card('<h3>Actividad actual</h3><div class="maint-row"><i class="maint-icon">↻</i><div><b>AutoSync</b><p>'+esc(sync.current_file||sync.status||'Biblioteca disponible')+'</p></div><span class="maint-tag">'+esc(phaseLabel(sync.phase))+'</span></div><div class="maint-row"><i class="maint-icon">O</i><div><b>OCR</b><p>'+esc(ocr.running?(ocr.current_file||'Procesando OCR en segundo plano'):(String(ocr.pending||0)+' pendiente(s) en cola.'))+'</p></div><span class="maint-tag '+(ocr.error?'maint-bad':'')+'">'+(ocr.error?esc(String(ocr.error)+' error(es)'):'OK')+'</span></div><div class="maint-row"><i class="maint-icon">K</i><div><b>Knowledge e índice</b><p>Estado asociado al catálogo activo. El monitor no inicia indexaciones.</p></div><span class="maint-tag maint-good">Disponible</span></div><div class="maint-actions">'+button('mScan','Buscar cambios ahora')+(sync.phase==='indexing'?button('mStopIndex','Detener indexación','secondary'): '')+'</div>')+card('<h3>Errores y recuperación</h3>'+problems(items))+'</div>';
    }else if(tab==='automation'){
      body='<div class="maint-grid">'+card('<h3>AutoSync</h3><p class="maint-note">Elegí cómo LexIA detecta y procesa los cambios de la biblioteca. El modo se aplica al servicio ya activo.</p><div class="maint-form"><label>Modo<select id="mMode" class="maint-select"><option value="manual" '+(config.mode==='manual'?'selected':'')+'>Manual</option><option value="automatic" '+(config.mode==='automatic'?'selected':'')+'>Automático</option><option value="scheduled" '+(config.mode==='scheduled'?'selected':'')+'>Programado</option></select></label><label>Hora programada<input id="mSchedule" class="maint-time" type="time" value="'+esc(config.schedule_time||'03:00')+'" '+(config.mode==='scheduled'?'':'disabled')+'></label>'+button('mSaveMode','Guardar modo','primary')+'</div><div class="maint-actions">'+button('mScan','Ejecutar sincronización manual')+'</div>')+card('<h3>OCR</h3><p class="maint-note">'+esc((state.ocr_policy||{}).description||'Los documentos escaneados se procesan desde la cola manual.')+'</p><p class="maint-note">Pendientes: <b>'+esc(ocr.pending||0)+'</b> · En proceso: <b>'+esc(ocr.processing||0)+'</b> · Con error: <b>'+esc(ocr.error||0)+'</b></p><div class="maint-actions">'+button('mOcrStart','Procesar OCR pendiente','primary',Boolean(ocr.running))+button('mOcrStop','Detener OCR','secondary',!ocr.running)+'</div>')+'</div>';
    }else if(tab==='diagnosis'){
      body='<div class="maint-grid">'+card('<h3>Incidencias detectadas</h3>'+problems(items))+card('<h3>Diagnóstico bajo demanda</h3><p class="maint-note">Comprueba disco, catálogo, bases y componentes. No se ejecuta al abrir Inicio ni al actualizar el monitor.</p><div class="maint-actions">'+button('mDiagnose','Ejecutar diagnóstico','primary')+'</div><div id="mDiagnosticReport"></div>')+'</div>';
    }else{
      const backups=(state.backups||[]);
      const scope=state.backup_scope||{};
      body='<div class="maint-grid">'+card('<h3>Copias disponibles</h3>'+(backups.length?backups.map(item=>'<div class="maint-row"><i class="maint-icon">▣</i><div><b>'+esc(item.name)+'</b><p>Copia operativa de bases y configuración.</p></div><span class="maint-tag maint-good">Lista</span></div>').join(''):'<p class="maint-empty">Todavía no hay copias creadas desde Mantenimiento.</p>')+'<div class="maint-actions">'+button('mBackup','Crear copia operativa','primary')+'</div>')+card('<h3>Alcance de la copia</h3><p class="maint-note">'+esc(scope.note||'Incluye bases internas y configuración.')+'</p><p class="maint-note">Incluye: bases internas y Knowledge. No incluye: biblioteca física ni índice Qdrant.</p>')+'</div>';
    }
    const header='<div class="maint-wrap"><div class="maint-head"><div><h1>Mantenimiento</h1><p>Operación real de AutoSync, OCR, diagnóstico y copias de LexIA.</p></div><div class="maint-actions">'+button('mRefresh','Actualizar')+'</div></div><div class="maint-tabs"><button class="maint-tab '+(tab==='activity'?'active':'')+'" data-maint-tab="activity">Estado y actividad</button><button class="maint-tab '+(tab==='automation'?'active':'')+'" data-maint-tab="automation">Automatizaciones</button><button class="maint-tab '+(tab==='diagnosis'?'active':'')+'" data-maint-tab="diagnosis">Diagnóstico</button><button class="maint-tab '+(tab==='backups'?'active':'')+'" data-maint-tab="backups">Copias</button></div><div class="maint-kpis">'+kpi('ESTADO GENERAL',attention?'Requiere atención':'Operativo',sync.status||'Biblioteca disponible')+kpi('BIBLIOTECA',Number(catalog.documents||0).toLocaleString('es-AR'),'documentos activos')+kpi('OCR',String(ocr.pending||0)+' pendientes',String(ocr.error||0)+' con error')+kpi('AUTOSYNC',modes[config.mode]||'Automático',config.mode==='scheduled'?(config.schedule_time||'03:00'):(sync.last_sync||'sin registro'))+'</div>'+body+'<p id="mToast" class="maint-toast"></p></div>';
    page.innerHTML=header;
    bind();
  }
  async function requestAction(action,extra={}){
    if(working)return;
    working=true;
    toast('Ejecutando…');
    try{
      const response=await fetch('/api/maintenance-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})});
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'La operación no pudo completarse.');
      toast(payload.message||'Operación completada.');
      await refresh(false);
      if(action==='diagnostic')showDiagnostic(payload.report||{});
    }catch(error){toast(error.message||String(error),true);}finally{working=false;}
  }
  function showDiagnostic(report){
    const target=document.getElementById('mDiagnosticReport');
    if(!target)return;
    const label=value=>value===true?'OK':value===false?'No disponible':String(value??'—');
    target.innerHTML='<div class="maint-report">Estado general: '+label(report.healthy)+'\nVersión: '+esc(report.version)+'\nBiblioteca: '+label(report.library_exists)+'\nCatálogo: '+label(report.catalog_exists)+' ('+esc(report.catalog_integrity)+')\nKnowledge/índice: '+label(report.qdrant_exists)+'\nBases de casos: '+esc(report.cases_integrity)+'\nEspacio libre: '+esc(report.free_disk_gb)+' GB\nRuntime escribible: '+label(report.runtime_writable)+'</div>';
  }
  function bind(){
    document.querySelectorAll('[data-maint-tab]').forEach(element=>element.onclick=()=>{tab=element.dataset.maintTab;render();});
    document.getElementById('mRefresh')?.addEventListener('click',()=>refresh());
    document.getElementById('mScan')?.addEventListener('click',()=>requestAction('autosync-scan'));
    document.getElementById('mStopIndex')?.addEventListener('click',()=>requestAction('autosync-stop-indexing'));
    document.getElementById('mOcrStart')?.addEventListener('click',()=>requestAction('ocr-start-all'));
    document.getElementById('mOcrStop')?.addEventListener('click',()=>requestAction('ocr-stop'));
    document.getElementById('mBackup')?.addEventListener('click',()=>requestAction('backup'));
    document.getElementById('mDiagnose')?.addEventListener('click',()=>requestAction('diagnostic'));
    const mode=document.getElementById('mMode'),schedule=document.getElementById('mSchedule');
    mode?.addEventListener('change',()=>{if(schedule)schedule.disabled=mode.value!=='scheduled';});
    document.getElementById('mSaveMode')?.addEventListener('click',()=>requestAction('autosync-config',{mode:mode?.value||'automatic',schedule_time:schedule?.value||'03:00'}));
  }
  async function refresh(schedule=true){
    if(pollTimer){clearTimeout(pollTimer);pollTimer=null;}
    try{
      const response=await fetch('/api/maintenance',{cache:'no-store'});
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'No se pudo leer el estado operativo.');
      state=payload;render();
      const live=state.live||{},sync=live.autosync||{},ocr=live.ocr||{};
      if(schedule&&page.style.display!=='none'&&(ocr.running||['waiting','scanning','indexing','knowledge'].includes(sync.phase))){pollTimer=setTimeout(()=>refresh(true),5000);}
    }catch(error){toast(error.message||String(error),true);}
  }
  window.lexiaMaintenanceOpen=function(){page.style.display='block';refresh(true);};
  render();
  if(location.hash==='#maintenance')window.lexiaMaintenanceOpen();
})();
/* <<< LEXIA UI2 3.3.3v MANTENIMIENTO OPERATIVO */
