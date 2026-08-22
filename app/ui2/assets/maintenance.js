/* >>> LEXIA UI2 3.3.9 OCR OBSERVABLE */
(function(){
  'use strict';
  document.getElementById('globalTopbar')?.remove();
  document.querySelectorAll('.nav button[data-route="activitypage"],.nav button[data-route="systempage"]').forEach(button=>button.remove());
  const nav=document.querySelector('#globalSidebar .nav');
  if(nav&&!nav.querySelector('[data-route="maintenance"]')){
    const button=document.createElement('button');
    button.dataset.route='maintenance';
    button.innerHTML='<span class="nav-glyph">⚙</span>Mantenimiento';
    nav.appendChild(button);
  }

  /* La tarjeta heredada de Actividad ahora representa el estado del sistema. */
  const homeSystemCard=document.querySelector('#home .hr-metrics article[data-home-target="activitypage"]');
  if(homeSystemCard){
    homeSystemCard.dataset.homeTarget='maintenance';
    const heading=homeSystemCard.querySelector('.hr-mhead');
    if(heading)heading.innerHTML='<i>⚙</i><b>Sistema</b>';
    const value=homeSystemCard.querySelector(':scope > strong');
    if(value)value.textContent='Operativo';
    const line=homeSystemCard.querySelector('.hr-line');
    if(line)line.innerHTML='<span>Mantenimiento</span><em>En línea</em>';
    const progressBar=homeSystemCard.querySelector('.hr-progress i');
    if(progressBar)progressBar.style.width='100%';
    const detailLabel=homeSystemCard.querySelector(':scope > small');
    if(detailLabel)detailLabel.textContent='Estado general';
    const detail=homeSystemCard.querySelector(':scope > p');
    if(detail)detail.textContent='Todo operativo';
    homeSystemCard.addEventListener('click',event=>{
      event.preventDefault();
      event.stopImmediatePropagation();
      window.lexiaMaintenanceOpen?.();
    },true);
  }

  const homeSearchButton=document.getElementById('homeQuickSearchButton');
  if(homeSearchButton){
    const menuIcon=nav?.querySelector('[data-route="searchpage"] .nav-glyph')?.cloneNode(true);
    const label=document.createElement('span');
    label.textContent='Buscar';
    homeSearchButton.replaceChildren(menuIcon||document.createTextNode('⌕'),label);
  }
  document.querySelector('#home .hr-search kbd')?.remove();

  const app=document.querySelector('.app');
  let page=document.getElementById('maintenance');
  if(!page){
    page=document.createElement('section');
    page.id='maintenance';
    (app||document.body).appendChild(page);
  }else if(app&&page.parentElement!==app){
    app.appendChild(page);
  }
  if(!page)return;

  function closeResponsiveNavigation(){
    document.body.classList.remove('lexia-nav-open');
    const toggle=document.getElementById('lexiaNavToggle');
    if(toggle){
      toggle.textContent='☰';
      toggle.setAttribute('aria-expanded','false');
      toggle.setAttribute('aria-label','Abrir menú de navegación');
    }
  }
  const narrowNavigation=window.matchMedia('(max-width: 1199px)');
  narrowNavigation.addEventListener?.('change',closeResponsiveNavigation);
  window.addEventListener('resize',()=>{
    if(narrowNavigation.matches)closeResponsiveNavigation();
  },{passive:true});
  if(narrowNavigation.matches)closeResponsiveNavigation();

  window.addEventListener('click',event=>{
    const target=event.target.closest?.('#home .hr-metrics article[data-home-target="maintenance"]');
    if(!target)return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    window.lexiaMaintenanceOpen?.();
  },true);

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
  const modes={manual:'Manual',automatic:'Automático',scheduled:'Programado'};
  let state=null;
  let tab='activity';
  let pollTimer=null;
  let working=false;
  let refreshing=false;
  let notice='';
  let noticeError=false;
  let keepPollingUntil=0;
  let ocrQueueFilter='';

  const card=(html,extra='')=>'<section class="maint-card '+extra+'">'+html+'</section>';
  const button=(id,label,kind='secondary',disabled=false)=>'<button type="button" class="maint-btn '+kind+'" id="'+id+'" '+(disabled?'disabled':'')+'>'+label+'</button>';
  function kpi(label,value,detail,target=''){
    const attrs=target?' role="button" tabindex="0" data-maint-target="'+target+'"':'';
    return '<section class="maint-card mkpi '+(target?'mkpi-link':'')+'"'+attrs+'><span class="mkpi-label">'+esc(label)+'</span><strong class="mkpi-value">'+esc(value)+'</strong><span class="mkpi-detail">'+esc(detail)+'</span></section>';
  }
  function problems(items){
    return items.length?items.map(item=>'<div class="maint-warn"><b>'+esc(item.kind)+'</b><p>'+esc(item.message)+'</p><small>Cómo corregir: '+esc(item.action)+'</small></div>').join(''):'<p class="maint-empty">No se detectaron incidencias que requieran intervención.</p>';
  }
  function history(items){
    const labels={'autosync-config':'Configuración AutoSync','autosync-scan':'Sincronización manual','autosync-stop-indexing':'Detención de indexación','ocr-start-all':'Inicio de OCR','ocr-stop':'Detención de OCR',diagnostic:'Diagnóstico',backup:'Copia operativa'};
    const rows=(Array.isArray(items)?items:[]).slice(0,8);
    return rows.length?'<div class="maint-history">'+rows.map(item=>'<div class="maint-row"><i class="maint-icon">'+(item.status==='error'?'!':'•')+'</i><div><b>'+esc(labels[item.action]||item.action||'Mantenimiento')+'</b><p>'+esc(item.message||'Operación registrada')+'</p></div><span class="maint-tag '+(item.status==='error'?'maint-bad':'maint-good')+'">'+esc(item.created_at||'')+'</span></div>').join('')+'</div>':'<p class="maint-empty">Todavía no hay acciones registradas desde Mantenimiento.</p>';
  }
  function phaseLabel(phase){
    return ({waiting:'en espera',scanning:'analizando',indexing:'indexando',knowledge:'actualizando Knowledge',ocr:'procesando OCR',idle:'en reposo',error:'con error'})[phase]||phase||'en reposo';
  }
  function progress(processed,total,percentage){
    const safeTotal=Number(total||0),safeProcessed=Number(processed||0);
    const value=Math.max(0,Math.min(100,Number(percentage||0)||(safeTotal?Math.round(100*safeProcessed/safeTotal):0)));
    return '<div class="maint-progress"><i style="width:'+value+'%"></i></div><small class="maint-progress-label">'+esc(safeProcessed)+' de '+esc(safeTotal)+' · '+value+'%</small>';
  }
  function ocrDetails(ocr){
    const stage=({ocr:'Reconocimiento de páginas',indexing:'Indexación del texto',completed:'OCR completado',stopped:'OCR detenido',error:'OCR con error',idle:'En espera'})[ocr.stage]||ocr.stage||'En espera';
    const documentPosition=Number(ocr.documentPosition||ocr.document_position||0);
    const documentTotal=Number(ocr.total||0);
    const currentPage=Number(ocr.currentPage||ocr.current_page||0);
    const totalPages=Number(ocr.totalPages||ocr.total_pages||0);
    const completedPages=Number(ocr.completedPages||ocr.completed_pages||0);
    const pagePercentage=Number(ocr.pagePercentage||ocr.page_percentage||0);
    const name=ocr.documentName||ocr.document_name||'';
    const path=ocr.currentFile||ocr.current_file||'';
    return '<div class="maint-ocr-details"><div><span>Etapa</span><b>'+esc(stage)+'</b></div><div><span>Documento</span><b>'+(documentTotal?esc(documentPosition)+' de '+esc(documentTotal):'—')+'</b></div><div><span>Página actual</span><b>'+(totalPages?esc(currentPage)+' de '+esc(totalPages):'—')+'</b></div><div><span>Páginas completadas</span><b>'+esc(completedPages)+'</b></div></div>'+(name?'<p class="maint-ocr-file"><b>'+esc(name)+'</b><span title="'+esc(path)+'">'+esc(path)+'</span></p>'+progress(completedPages,totalPages,pagePercentage):'');
  }
  function ocrQueuePanel(ocr){
    const items=Array.isArray(ocr.items)?ocr.items:[];
    if(!ocrQueueFilter)return '<p class="maint-ocr-help">Seleccioná un estado para ver los archivos y su ubicación.</p>';
    const selected=items.filter(item=>String(item.status||'').trim().toLowerCase()===ocrQueueFilter);
    const labels={pending:'Pendientes',processing:'En proceso',error:'Con error'};
    const expected=Number(ocr[ocrQueueFilter]||0);
    if(ocr.items_error)return '<div class="maint-ocr-queue maint-ocr-queue-error"><b>'+esc(labels[ocrQueueFilter]||ocrQueueFilter)+'</b><p>'+esc(ocr.items_error)+'</p><small>Usá “Actualizar estado” para reintentar la lectura.</small></div>';
    if(!selected.length)return '<div class="maint-ocr-queue"><b>'+esc(labels[ocrQueueFilter]||ocrQueueFilter)+'</b><p class="maint-empty">'+(expected?'La cola informa '+esc(expected)+' archivo(s), pero el detalle todavía no está disponible. Actualizando…':'No hay archivos en este estado.')+'</p></div>';
    return '<div class="maint-ocr-queue"><b>'+esc(labels[ocrQueueFilter]||ocrQueueFilter)+' · '+selected.length+(expected>selected.length?' de '+esc(expected):'')+'</b>'+selected.map(item=>'<div class="maint-ocr-queue-item"><strong>'+esc(item.name||'Documento')+'</strong><span>'+esc(item.path||'Sin ubicación registrada')+'</span>'+((item.total_pages||item.progress_page)?'<small>Página '+esc(item.progress_page||0)+' de '+esc(item.total_pages||'—')+'</small>':'')+(item.error?'<small class="maint-ocr-item-error">'+esc(item.error)+'</small>':'')+'</div>').join('')+'</div>';
  }
  function ocrStatusButtons(ocr){
    return '<div class="maint-ocr-stats"><button type="button" data-ocr-filter="pending" class="'+(ocrQueueFilter==='pending'?'active':'')+'"><span>Pendientes</span><b>'+esc(ocr.pending||0)+'</b></button><button type="button" data-ocr-filter="processing" class="'+(ocrQueueFilter==='processing'?'active':'')+'"><span>En proceso</span><b>'+esc(ocr.processing||0)+'</b></button><button type="button" data-ocr-filter="error" class="'+(ocrQueueFilter==='error'?'active':'')+'"><span>Con error</span><b>'+esc(ocr.error||0)+'</b></button></div>';
  }
  function diagnosticPanel(diagnostic){
    const d=diagnostic||{};
    if(d.running)return '<div class="maint-running"><span class="maint-spinner"></span>'+esc(d.status||'Diagnóstico en curso…')+'</div>';
    if(d.error)return '<div class="maint-warn"><b>Diagnóstico con error</b><p>'+esc(d.error)+'</p></div>';
    const report=d.report;
    if(!report)return '';
    const label=value=>value===true?'OK':value===false?'No disponible':String(value??'—');
    return '<div class="maint-report">Estado general: '+esc(label(report.healthy))+'\nVersión: '+esc(report.version)+'\nBiblioteca: '+esc(label(report.library_exists))+'\nCatálogo: '+esc(label(report.catalog_exists))+' ('+esc(report.catalog_integrity)+')\nKnowledge/índice: '+esc(label(report.qdrant_exists))+'\nBases de casos: '+esc(report.cases_integrity)+'\nEspacio libre: '+esc(report.free_disk_gb)+' GB\nRuntime escribible: '+esc(label(report.runtime_writable))+'</div>';
  }
  function aboutPanel(platform){
    const p=platform||{},components=p.components||{},settings=p.settings||{};
    const componentRows=Object.entries(components).map(([name,item])=>'<div class="maint-component"><span>'+(item.available?'✅':'❌')+' '+esc(name)+'</span><b>'+esc(item.version||'—')+'</b></div>').join('');
    return '<div class="maint-about">'+card('<p class="maint-eyebrow">PRODUCTO</p><h2>'+esc(p.product||'LexIA Platform')+'</h2><dl><dt>Versión</dt><dd>'+esc(p.version||'2.1.0-dev')+'</dd><dt>Build</dt><dd>'+esc(p.build||'2026.08.03.2101')+'</dd><dt>Canal</dt><dd>'+esc(p.channel||'DEV')+'</dd></dl>')+card('<h3>Componentes</h3><div class="maint-components">'+(componentRows||'<p class="maint-empty">Información de componentes no disponible.</p>')+'</div>')+card('<h3>Configuración activa</h3><dl><dt>Inicio</dt><dd>'+esc(settings.startup_mode||'watch_only')+'</dd><dt>Consultas máximas</dt><dd>'+esc(settings.max_queries||5)+'</dd><dt>Fuentes máximas operativas</dt><dd>'+esc(settings.max_sources||14)+'</dd><dt>Qdrant</dt><dd>'+esc(settings.qdrant_mode||'local_embedded')+'</dd></dl><p class="maint-note">Los componentes esenciales de Platform 2.1 están '+(p.healthy===false?'incompletos.':'disponibles.')+'</p>')+'</div>';
  }

  function render(){
    if(!state){
      page.innerHTML='<div class="maint-wrap"><div class="maint-loading"><span class="maint-spinner"></span>Leyendo estado operativo…</div></div>';
      return;
    }
    const live=state.live||{},sync=live.autosync||{},ocr=live.ocr||{},catalog=live.catalog||{},config=state.autosync_config||{},items=state.problems||[],events=state.history||[],operation=state.operation||{};
    const attention=sync.phase==='error'||Number(ocr.error||0)>0;
    let body='';
    if(tab==='activity'){
      body='<div class="maint-grid">'+card('<h3>Actividad actual</h3><div class="maint-row"><i class="maint-icon">↻</i><div><b>AutoSync</b><p>'+esc(sync.current_file||sync.status||'Biblioteca disponible')+'</p></div><span class="maint-tag">'+esc(phaseLabel(sync.phase))+'</span></div><div class="maint-row"><i class="maint-icon">O</i><div><b>OCR</b><p>'+esc(ocr.running?((ocr.document_name||'Procesando OCR')+(ocr.total_pages?' · página '+ocr.current_page+' de '+ocr.total_pages:'')):(String(ocr.pending||0)+' pendiente(s) en cola.'))+'</p></div><span class="maint-tag '+(ocr.error?'maint-bad':'maint-good')+'">'+(ocr.error?esc(String(ocr.error)+' error(es)'):'OK')+'</span></div>'+((ocr.running||ocr.document_name)?ocrDetails(ocr):'')+'<div class="maint-current"><b>'+esc(operation.engine||'LexIA')+' · '+esc(operation.function||'idle')+'</b><p>'+esc(operation.status||'Biblioteca al día')+'</p>'+progress(operation.processed,operation.total,operation.percentage)+'<small>Cola: '+esc(operation.queued||0)+' tarea(s)</small></div><div class="maint-actions">'+button('mScan','Buscar cambios ahora')+(sync.phase==='indexing'?button('mStopIndex','Detener indexación'): '')+'</div>','maint-activity')+card('<h3>Errores y recuperación</h3>'+problems(items))+card('<h3>Historial operativo</h3><p class="maint-note">Se muestran únicamente las últimas 8 acciones.</p>'+history(events),'maint-history-card')+'</div>';
    }else if(tab==='automation'){
      body='<div class="maint-grid">'+card('<h3>AutoSync</h3><p class="maint-note">Elegí cómo LexIA detecta y procesa los cambios de la biblioteca.</p><div class="maint-form"><label>Modo<select id="mMode" class="maint-select"><option value="manual" '+(config.mode==='manual'?'selected':'')+'>Manual</option><option value="automatic" '+(config.mode==='automatic'?'selected':'')+'>Automático</option><option value="scheduled" '+(config.mode==='scheduled'?'selected':'')+'>Programado</option></select></label><label>Hora programada<input id="mSchedule" class="maint-time" type="time" value="'+esc(config.schedule_time||'03:00')+'" '+(config.mode==='scheduled'?'':'disabled')+'></label>'+button('mSaveMode','Guardar modo','primary',working)+'</div><div class="maint-actions">'+button('mScan','Ejecutar sincronización manual','secondary',working)+'</div>','maint-autosync-card')+card('<h3>OCR</h3><p class="maint-note">'+esc((state.ocr_policy||{}).description||'Los documentos escaneados se procesan desde la cola manual.')+'</p>'+ocrStatusButtons(ocr)+ocrQueuePanel(ocr)+ocrDetails(ocr)+progress(ocr.processed,ocr.total,0)+'<div class="maint-actions">'+button('mOcrStart','Procesar OCR pendiente','primary',working||Boolean(ocr.running))+button('mOcrStop','Detener OCR','secondary',working||!ocr.running)+'</div>','maint-ocr-card')+'</div>';
    }else if(tab==='diagnosis'){
      const diagnostic=state.diagnostic||{};
      body='<div class="maint-grid">'+card('<h3>Incidencias detectadas</h3>'+problems(items))+card('<h3>Diagnóstico bajo demanda</h3><p class="maint-note">Comprueba disco, catálogo, bases y componentes en segundo plano. La pantalla continúa respondiendo.</p><div class="maint-actions">'+button('mDiagnose',diagnostic.running?'Diagnóstico en ejecución':'Ejecutar diagnóstico','primary',working||diagnostic.running)+'</div>'+diagnosticPanel(diagnostic))+'</div>';
    }else if(tab==='backups'){
      const backups=state.backups||[],scope=state.backup_scope||{};
      body='<div class="maint-grid">'+card('<h3>Copias disponibles</h3>'+(backups.length?backups.map(item=>'<div class="maint-row"><i class="maint-icon">▣</i><div><b>'+esc(item.name)+'</b><p>Copia operativa de bases y configuración.</p></div><span class="maint-tag maint-good">Lista</span></div>').join(''):'<p class="maint-empty">Todavía no hay copias creadas desde Mantenimiento.</p>')+'<div class="maint-actions">'+button('mBackup','Crear copia operativa','primary',working)+'</div>')+card('<h3>Alcance de la copia</h3><p class="maint-note">'+esc(scope.note||'Incluye bases internas y configuración.')+'</p><p class="maint-note">Incluye: bases internas y Knowledge. No incluye: biblioteca física ni índice Qdrant.</p>')+'</div>';
    }else if(tab==='monitor'){
      const lines=Array.isArray(state.monitor)?state.monitor:[];
      body=card('<div class="maint-terminal-head"><div><h3>Monitor técnico en vivo</h3><p class="maint-note">Estado, cola, errores y últimas líneas de los registros operativos. Se actualiza cada 2,5 segundos.</p></div><span class="maint-tag maint-good">EN VIVO</span></div><pre class="maint-terminal" id="mTerminal">'+esc(lines.join('\n')||'Sin actividad registrada.')+'</pre>','maint-monitor-card');
    }else{
      body=aboutPanel(state.platform||{});
    }

    const tabs=[['activity','Estado y actividad'],['automation','Automatizaciones'],['diagnosis','Diagnóstico'],['backups','Copias'],['monitor','Monitor técnico'],['about','Acerca de LexIA']].map(([id,label])=>'<button class="maint-tab '+(tab===id?'active':'')+'" data-maint-tab="'+id+'">'+label+'</button>').join('');
    const header='<div class="maint-wrap"><div class="maint-head"><div><h1>Mantenimiento</h1><p>Operación real de AutoSync, OCR, diagnóstico y copias de LexIA.</p></div><div class="maint-actions">'+button('mRefresh',refreshing?'Actualizando…':'Actualizar','secondary',refreshing)+'</div></div><div class="maint-tabs">'+tabs+'</div><div class="maint-kpis">'+kpi('ESTADO GENERAL',attention?'Requiere atención':'Operativo',sync.status||'Biblioteca disponible','activity')+kpi('BIBLIOTECA',Number(catalog.documents||0).toLocaleString('es-AR'),'documentos activos','search')+kpi('OCR',String(ocr.pending||0)+' pendientes',String(ocr.error||0)+' con error','ocr')+kpi('AUTOSYNC',modes[config.mode]||'Automático',config.mode==='scheduled'?(config.schedule_time||'03:00'):(sync.last_sync||'sin registro'),'autosync')+'</div>'+body+'<p id="mToast" class="maint-toast '+(noticeError?'maint-toast-error':'')+'">'+esc(notice)+'</p></div>';
    page.innerHTML=header;
    bind();
    updateSidebar();
  }

  function ensureSidebar(){
    const box=document.querySelector('#globalSidebar .health');
    if(!box)return null;
    let detail=box.querySelector('.lexia-operation-detail');
    if(!detail){
      const paragraph=box.querySelector('p')||document.createElement('p');
      paragraph.innerHTML='<b id="liveAutoSyncLabel">AutoSync activo</b><br><span id="liveAutoSyncDetail">Estado sin actualizar</span><span class="lexia-operation-detail"><span id="liveOperationFunction">En reposo</span><span class="lexia-operation-progress"><i id="liveOperationProgress"></i></span><small id="liveOperationQueue">Cola: 0</small><button type="button" id="liveOperationRefresh" class="lexia-sidebar-refresh">↻ Actualizar estado</button></span>';
      if(!paragraph.parentElement)box.appendChild(paragraph);
      detail=paragraph.querySelector('.lexia-operation-detail');
    }
    const refreshButton=box.querySelector('#liveOperationRefresh');
    if(refreshButton&&!refreshButton.dataset.bound){
      refreshButton.dataset.bound='1';
      refreshButton.addEventListener('click',event=>{
        event.preventDefault();
        refreshGlobalSidebar(true);
      });
    }
    return detail;
  }
  function updateSidebar(){
    ensureSidebar();
    const op=(state||{}).operation||{},live=(state||{}).live||{},sync=live.autosync||{},ocr=live.ocr||{};
    const set=(id,value)=>{const element=document.getElementById(id);if(element)element.textContent=value;};
    set('liveAutoSyncLabel',op.engine==='OCR'?'OCR trabajando':(['waiting','scanning','indexing','knowledge'].includes(sync.phase)?'AutoSync trabajando':'AutoSync activo'));
    set('liveAutoSyncDetail',op.status||sync.status||'Biblioteca al día');
    set('liveOperationFunction',(op.engine||'LexIA')+' · '+phaseLabel(op.function));
    const pageDetail=op.engine==='OCR'&&Number(op.total_pages||0)?' · pág. '+Number(op.current_page||0)+'/'+Number(op.total_pages||0):'';
    set('liveOperationQueue','Cola: '+Number(op.queued||0)+' · '+Number(op.processed||0)+' de '+Number(op.total||0)+pageDetail);
    const bar=document.getElementById('liveOperationProgress');
    if(bar)bar.style.width=Math.max(0,Math.min(100,Number(op.percentage||0)))+'%';
    const title=document.querySelector('#globalSidebar .health h4');
    if(title){
      const healthy=sync.phase!=='error'&&Number(ocr.error||0)===0;
      title.innerHTML='<span class="dot"></span>'+(healthy?'Todo operativo':'Requiere atención');
    }
  }
  window.lexiaUpdateOperationalSidebar=function(payload){
    if(!payload)return;
    const autosync=payload.autosync||payload.live?.autosync||{};
    const ocr=payload.ocr||payload.live?.ocr||{};
    const activeOcr=Boolean(ocr.running);
    const activeSync=['waiting','scanning','indexing','knowledge'].includes(autosync.phase);
    const total=Number((activeOcr?ocr.total:autosync.total)||0),processed=Number((activeOcr?ocr.processed:autosync.processed)||0);
    const op={engine:activeOcr?'OCR':activeSync?'AutoSync':'LexIA',function:activeOcr?(ocr.stage||'ocr'):(autosync.phase||'idle'),status:activeOcr?(ocr.document_name||'Procesando OCR'):(autosync.status||'Biblioteca al día'),processed,total,percentage:Number((activeOcr?0:autosync.percentage)||0)||(total?Math.round(100*processed/total):0),queued:activeOcr?Number(ocr.pending||0):Math.max(0,total-processed),current_page:Number(ocr.current_page||0),total_pages:Number(ocr.total_pages||0)};
    state={...(state||{}),live:{...((state||{}).live||{}),autosync,ocr},operation:op};
    updateSidebar();
  };

  function navigate(target){
    if(target==='search'){
      closeResponsiveNavigation();
      page.style.display='none';
      const searchButton=document.querySelector('#globalSidebar .nav [data-route="searchpage"]');
      if(searchButton)searchButton.click();
      else if(window.lexiaUI2NavigateGlobal)window.lexiaUI2NavigateGlobal('searchpage');
      return;
    }
    if(target==='activity'){tab='activity';render();return;}
    if(target==='ocr'||target==='autosync'){
      tab='automation';
      render();
      requestAnimationFrame(()=>document.querySelector(target==='ocr'?'.maint-ocr-card':'.maint-autosync-card')?.scrollIntoView({behavior:'smooth',block:'center'}));
    }
  }
  function bind(){
    document.querySelectorAll('[data-maint-tab]').forEach(element=>element.onclick=()=>{tab=element.dataset.maintTab;render();schedulePoll();});
    document.querySelectorAll('[data-maint-target]').forEach(element=>{
      const go=()=>navigate(element.dataset.maintTarget);
      element.onclick=go;
      element.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();go();}};
    });
    document.querySelectorAll('[data-ocr-filter]').forEach(element=>element.addEventListener('click',()=>{
      ocrQueueFilter=element.dataset.ocrFilter||'';
      render();
      refresh(false,false);
    }));
    document.getElementById('mRefresh')?.addEventListener('click',()=>refresh(true,true));
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
  function schedulePoll(){
    if(pollTimer){clearTimeout(pollTimer);pollTimer=null;}
    if(page.style.display==='none')return;
    const live=(state||{}).live||{},sync=live.autosync||{},ocr=live.ocr||{},diagnostic=(state||{}).diagnostic||{};
    const shouldPoll=tab==='monitor'||ocr.running||diagnostic.running||['waiting','scanning','indexing','knowledge'].includes(sync.phase)||Date.now()<keepPollingUntil;
    if(shouldPoll)pollTimer=setTimeout(()=>refresh(true,false),2500);
  }
  async function refresh(schedule=true,announce=false){
    if(refreshing)return;
    refreshing=true;
    if(announce){notice='Actualizando estado operativo…';noticeError=false;render();}
    try{
      const response=await fetch('/api/maintenance',{cache:'no-store'});
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'No se pudo leer el estado operativo.');
      state=payload;
      if(announce)notice='Estado actualizado a las '+new Date().toLocaleTimeString('es-AR')+'.';
      noticeError=false;
    }catch(error){
      notice=error.message||String(error);
      noticeError=true;
    }finally{
      refreshing=false;
      render();
      if(schedule)schedulePoll();
    }
  }
  async function requestAction(action,extra={}){
    if(working)return;
    working=true;
    notice='Ejecutando operación…';
    noticeError=false;
    render();
    try{
      const response=await fetch('/api/maintenance-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})});
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'La operación no pudo completarse.');
      notice=payload.message||'Operación completada.';
      noticeError=false;
      keepPollingUntil=Date.now()+15000;
      await refresh(false,false);
    }catch(error){
      notice=error.message||String(error);
      noticeError=true;
    }finally{
      working=false;
      render();
      schedulePoll();
    }
  }
  function hideOtherPages(){
    ['home','library','searchpage','contextpage','activitypage','systempage'].forEach(id=>{
      const element=document.getElementById(id);
      if(element)element.style.display='none';
    });
  }
  window.lexiaMaintenanceOpen=function(){
    closeResponsiveNavigation();
    hideOtherPages();
    page.style.display='block';
    if(!state)render();
    refresh(true,false);
  };

  async function refreshGlobalSidebar(announce=false){
    const refreshButton=document.getElementById('liveOperationRefresh');
    if(announce&&refreshButton){
      refreshButton.disabled=true;
      refreshButton.textContent='Actualizando…';
    }
    try{
      const response=await fetch('/api/maintenance-live',{cache:'no-store'});
      const payload=await response.json();
      if(response.ok&&payload.ok)window.lexiaUpdateOperationalSidebar(payload);
    }catch(_error){
      // El último estado válido permanece visible si falla la consulta.
    }finally{
      if(refreshButton){
        refreshButton.disabled=false;
        refreshButton.textContent='↻ Actualizar estado';
      }
    }
  }

  ensureSidebar();
  refreshGlobalSidebar();
  setInterval(refreshGlobalSidebar,60000);
  if(location.hash==='#maintenance')window.lexiaMaintenanceOpen();
})();
/* <<< LEXIA UI2 3.3.9 OCR OBSERVABLE */
