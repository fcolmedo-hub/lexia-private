/* LexIA — respuestas de ChatGPT e historial persistente de Investigación. */
(function(){
  'use strict';

  const $=id=>document.getElementById(id);
  const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));
  const request=async(url,options={})=>{
    const response=await fetch(url,{cache:'no-store',...options});
    const data=await response.json().catch(()=>({}));
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  };
  const watching={research:false,file:false};
  const resultWatchToken={research:0,file:0};
  let watchingCandidates=false;
  let candidateWatchToken=0;

  function installStyle(){
    if($('lexiaResearchResultsStyle'))return;
    const style=document.createElement('style');
    style.id='lexiaResearchResultsStyle';
    style.textContent=`
      #contextpage .output-card{display:none!important}
      #contextpage #aiResultsPanel[hidden]{display:none!important}
      #contextpage #aiResultsPanel{margin-top:0;padding:16px}
      #contextpage .ai-results-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}
      #contextpage .ai-results-head h3{margin:0 0 4px;color:#252d48;font-size:16px}
      #contextpage .ai-results-head p{margin:0;color:#747d97;font-size:12px}
      #contextpage .ai-results-tools{display:flex;align-items:center;gap:8px;margin-bottom:14px}
      #contextpage .ai-results-search{flex:1;min-width:0;height:38px;padding:0 12px;border:1px solid #dfe2ec;border-radius:9px;background:#fff;color:#29314d;font-size:12px;outline:0}
      #contextpage .ai-results-search:focus{border-color:#8178ff;box-shadow:0 0 0 3px rgba(81,70,246,.10)}
      #contextpage .ai-results-list{display:flex;flex-direction:column;gap:10px}
      #contextpage .ai-result-card{width:100%;display:grid;grid-template-columns:128px minmax(0,1fr) auto;gap:14px;align-items:start;text-align:left;padding:13px;border:1px solid #e1e4ee;border-radius:11px;background:#fff}
      #contextpage .ai-result-card:hover{border-color:#b9b3ff;background:#faf9ff;box-shadow:0 5px 16px rgba(71,62,177,.08)}
      #contextpage .ai-result-badge{display:inline-flex;width:max-content;padding:5px 8px;border-radius:999px;background:#eceaff;color:#4036c4;font-size:10px;font-weight:800}
      #contextpage .ai-result-card[data-kind="file"] .ai-result-badge{background:#e8f4ff;color:#17649b}
      #contextpage .ai-result-date{display:block;margin-top:8px;color:#8790a8;font-size:10px}
      #contextpage .ai-result-copy b{display:block;margin-bottom:5px;color:#29314d;font-size:13px;line-height:1.35}
      #contextpage .ai-result-copy p{margin:0;color:#68728d;font-size:11.5px;line-height:1.45}
      #contextpage .ai-result-open{display:block;width:100%;padding:0;border:0;background:transparent;text-align:left;cursor:pointer}
      #contextpage .ai-result-actions{display:flex;flex-direction:column;gap:6px}
      #contextpage .ai-result-actions button{min-width:78px;height:30px;padding:0 10px;border-radius:7px;font-size:10px;font-weight:700;cursor:pointer}
      #contextpage .ai-result-delete{border:1px solid #efc7cd;background:#fff;color:#b52c3c}
      #contextpage .ai-results-empty{padding:26px;text-align:center;color:#7b849d;border:1px dashed #d9dce7;border-radius:10px}
      #researchSourcesModal{display:none!important}
      #contextpage #aiProcessCard[hidden]{display:none!important}
      #contextpage #aiProcessCard{position:relative;margin:0;padding:13px 15px;border:1px solid #dddafe;background:#faf9ff}
      #contextpage #aiProcessCard .job-top h3{margin:0;color:#252d48;font-size:12px!important}
      #contextpage #aiProcessCard .job-top p{margin:4px 0 0;color:#687294;font-size:10px}
      html[data-lexia-app="1"] #contextpage:not(.lexia-source-review) #researchPanel:not([hidden]){display:block!important;grid-template-columns:none!important;width:100%!important}
      html[data-lexia-app="1"] #contextpage:not(.lexia-source-review) #researchPanel>.research-main-column{display:flex!important;width:100%!important;max-width:none!important}
      html[data-lexia-app="1"] #contextpage:not(.lexia-source-review) #researchPanel>.context-side{display:none!important}
      html[data-lexia-app="1"] #contextpage.lexia-source-review #researchPanel:not([hidden]){display:flex!important;flex-direction:column!important;gap:10px!important;height:calc(100dvh - 172px)!important;min-height:430px!important;max-height:none!important;overflow:hidden!important;width:100%!important}
      html[data-lexia-app="1"] #contextpage.lexia-source-review #researchPanel>.research-main-column{display:none!important}
      html[data-lexia-app="1"] #contextpage.lexia-source-review #researchPanel>.context-side{order:1!important;display:flex!important;flex:1 1 auto!important;flex-direction:column!important;width:100%!important;max-width:none!important;height:auto!important;min-height:0!important;margin:0!important;padding:14px!important;position:relative!important;top:auto!important;overflow:hidden!important}
      html[data-lexia-app="1"] #contextpage.lexia-source-review #researchPanel>#aiProcessCard{order:2!important;display:block!important;flex:0 0 auto!important;width:100%!important;min-height:0!important;height:auto!important}
      #contextpage #researchSourcesModalList{display:none}
      #contextpage.lexia-source-review #researchSourceList{display:none!important}
      html[data-lexia-app="1"] #contextpage.lexia-source-review #researchSourcesModalList{display:grid!important;flex:1 1 auto!important;height:auto!important;max-height:none!important;min-height:0!important;overflow-y:auto!important;padding:6px 3px 8px!important}
      #contextpage.lexia-source-review #viewSources{display:none!important}
      #contextpage.lexia-source-review #lexiaAddManualResearchSource{display:inline-flex!important;align-items:center;justify-content:center;flex:0 0 210px!important;width:210px!important;min-width:210px!important;max-width:100%!important;min-height:34px;padding:7px 12px;margin-left:auto!important;align-self:center!important;border:1px solid #17864f!important;border-radius:8px;background:#1b9c5a!important;color:#fff!important;font-weight:800;cursor:pointer}
      #contextpage.lexia-source-review #lexiaAddManualResearchSource:hover{background:#17864f!important;border-color:#147543!important}
      #contextpage.lexia-source-review .lexia-sources-foot{align-items:center!important;gap:8px!important}
      #contextpage .context-side>.lexia-sources-foot{display:none}
      #contextpage.lexia-source-review .context-side>.lexia-sources-foot{display:flex;flex:0 0 auto;margin-top:8px;padding:12px 2px 0;border-top:1px solid #e8e9f1;border-bottom:0}
      .lexia-ai-modal{display:none;position:fixed;inset:0;z-index:12000;background:rgba(20,25,43,.5);padding:30px;align-items:center;justify-content:center}
      .lexia-ai-modal.open{display:flex}
      .lexia-ai-dialog{display:flex;flex-direction:column;width:min(920px,96vw);max-height:90vh;background:#fff;border-radius:14px;box-shadow:0 24px 70px rgba(10,15,35,.3);overflow:hidden}
      .lexia-ai-dialog-head{display:flex;justify-content:space-between;gap:16px;padding:17px 20px;border-bottom:1px solid #e7e9f1}
      .lexia-ai-dialog-head h2{margin:0 0 5px;color:#222a46;font-size:18px}
      .lexia-ai-dialog-head p{margin:0;color:#747e98;font-size:11px}
      .lexia-ai-dialog-close{width:34px;height:34px;border:0;border-radius:8px;background:#f1f0ff;color:#4036c4;font-size:21px;cursor:pointer}
      .lexia-ai-result{padding:20px;overflow:auto;white-space:pre-wrap;color:#28314e;font:13px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif}
      @media(max-width:700px){#contextpage .ai-results-head,#contextpage .ai-results-tools{flex-direction:column}#contextpage .ai-results-tools>*{width:100%}#contextpage .ai-result-card{grid-template-columns:1fr}#contextpage .ai-result-actions{flex-direction:row}.lexia-ai-modal{padding:10px}.lexia-ai-dialog{max-height:94vh}html[data-lexia-app="1"] #contextpage.lexia-source-review #researchPanel:not([hidden]){height:calc(100dvh - 155px)!important;min-height:360px!important}}
    `;
    document.head.appendChild(style);
  }

  function ensureModal(){
    let modal=$('lexiaAiResultModal');
    if(modal)return modal;
    modal=document.createElement('div');
    modal.id='lexiaAiResultModal';
    modal.className='lexia-ai-modal';
    modal.setAttribute('aria-hidden','true');
    modal.innerHTML=`<section class="lexia-ai-dialog" role="dialog" aria-modal="true" aria-labelledby="lexiaAiResultTitle"><header class="lexia-ai-dialog-head"><div><h2 id="lexiaAiResultTitle">Resultado</h2><p id="lexiaAiResultMeta"></p></div><button class="lexia-ai-dialog-close" type="button" aria-label="Cerrar">×</button></header><div class="lexia-ai-result" id="lexiaAiResultText"></div></section>`;
    modal.addEventListener('click',event=>{
      if(event.target===modal||event.target.closest('.lexia-ai-dialog-close'))closeModal();
    });
    document.addEventListener('keydown',event=>{if(event.key==='Escape')closeModal();});
    document.body.appendChild(modal);
    return modal;
  }

  function closeModal(){
    const modal=$('lexiaAiResultModal');
    if(!modal)return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden','true');
  }

  function showResult(result){
    const modal=ensureModal();
    $('lexiaAiResultTitle').textContent=result.title||result.query||'Resultado de la investigación';
    const date=result.created_at?new Date(result.created_at).toLocaleString('es-AR'):'';
    const tokens=Number(result.total_tokens||result.usage?.total_tokens||0);
    $('lexiaAiResultMeta').textContent=[result.type_label,date,result.model,tokens?tokens.toLocaleString('es-AR')+' tokens':''].filter(Boolean).join(' · ');
    $('lexiaAiResultText').textContent=String(result.result||result.content||'Sin contenido.');
    modal.classList.add('open');
    modal.setAttribute('aria-hidden','false');
    $('lexiaAiResultText').scrollTop=0;
  }

  function ensureHistoryPanel(){
    const tabs=$('contextpage')?.querySelector('.investigation-tabs');
    const studyPanel=$('studyPanel');
    if(!tabs||!studyPanel)return false;
    if(!$('aiResultsTab')){
      const tab=document.createElement('button');
      tab.type='button';tab.id='aiResultsTab';tab.className='investigation-tab';
      tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');
      tab.textContent='Últimos resultados';
      tabs.appendChild(tab);
    }
    if(!$('aiResultsPanel')){
      const panel=document.createElement('section');
      panel.id='aiResultsPanel';panel.className='card investigation-panel';panel.hidden=true;
      panel.innerHTML=`<div class="ai-results-head"><div><h3>Últimos resultados de ChatGPT</h3><p>Investigaciones y estudios guardados para volver a consultarlos sin consumir créditos.</p></div><button class="secondary" id="refreshAiResults" type="button">Actualizar</button></div><form class="ai-results-tools" id="aiResultsSearchForm"><input class="ai-results-search" id="aiResultsSearch" type="search" autocomplete="off" placeholder="Buscar por nombre, consulta o contenido"><button class="secondary" type="submit">Buscar</button><button class="secondary" id="clearAiResultsSearch" type="button">Limpiar</button></form><div class="ai-results-list" id="aiResultsList"><div class="ai-results-empty">Todavía no hay resultados guardados.</div></div>`;
      studyPanel.insertAdjacentElement('afterend',panel);
    }
    return true;
  }

  function activateHistory(active){
    const panel=$('aiResultsPanel'),tab=$('aiResultsTab');
    if(!panel||!tab)return;
    panel.hidden=!active;
    tab.classList.toggle('active',active);
    tab.setAttribute('aria-selected',String(active));
    if(active){
      if($('researchPanel'))$('researchPanel').hidden=true;
      if($('studyPanel'))$('studyPanel').hidden=true;
      $('researchTab')?.classList.remove('active');
      $('studyTab')?.classList.remove('active');
      $('researchTab')?.setAttribute('aria-selected','false');
      $('studyTab')?.setAttribute('aria-selected','false');
      loadHistory();
    }
  }

  function formatDate(raw){
    if(!raw)return '';
    const date=new Date(raw);
    return Number.isNaN(date.getTime())?String(raw):date.toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});
  }

  async function loadHistory(){
    const list=$('aiResultsList');if(!list)return;
    list.innerHTML='<div class="ai-results-empty">Cargando resultados…</div>';
    try{
      const query=String($('aiResultsSearch')?.value||'').trim();
      const data=await request('/api/ai-results'+(query?'?query='+encodeURIComponent(query):''));
      const items=data.results||[];
      list.innerHTML=items.length?items.map(item=>`<article class="ai-result-card" data-result-id="${Number(item.id)}" data-kind="${escapeHtml(item.kind)}"><span><span class="ai-result-badge">${escapeHtml(item.type_label)}</span><small class="ai-result-date">${escapeHtml(formatDate(item.created_at))}</small></span><button class="ai-result-open" data-open-result type="button"><span class="ai-result-copy"><b>${escapeHtml(item.query||item.title||'Consulta sin título')}</b><p>${escapeHtml(item.preview||'')}</p></span></button><span class="ai-result-actions"><button class="secondary" data-open-result type="button">Consultar</button><button class="ai-result-delete" data-delete-result type="button">Eliminar</button></span></article>`).join(''):`<div class="ai-results-empty">${query?'No se encontraron resultados para esa búsqueda.':'Todavía no hay resultados guardados.'}</div>`;
    }catch(error){list.innerHTML='<div class="ai-results-empty">No se pudo cargar el historial: '+escapeHtml(error.message||error)+'</div>';}
  }

  async function openArchived(id){
    try{const data=await request('/api/ai-results/'+encodeURIComponent(id));showResult(data.result||{});}
    catch(error){window.alert(error.message||String(error));}
  }

  async function deleteArchived(card){
    const id=Number(card?.dataset.resultId||0);if(!id)return;
    const title=card.querySelector('.ai-result-copy b')?.textContent||'este resultado';
    if(!window.confirm('¿Eliminar “'+title+'” del historial?\n\nEsta acción no se puede deshacer.'))return;
    try{
      await request('/api/ai-results-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
      await loadHistory();
    }catch(error){window.alert(error.message||String(error));}
  }

  function ensureAiProcess(){
    let card=$('aiProcessCard');if(card)return card;
    const panel=$('researchPanel');if(!panel)return null;
    card=document.createElement('section');card.id='aiProcessCard';card.className='card job-card';card.hidden=true;
    card.innerHTML=`<div class="job-top"><div><h3>Proceso de IA</h3><p id="aiProcessDetail">Esperando la selección de fuentes.</p></div><span class="job-state" id="aiProcessStep">0%</span></div><div class="research-progress-track"><i id="aiProcessBar"></i></div><div class="research-progress-foot"><span id="aiProcessState">Fuentes listas para revisar</span><span id="aiProcessPercent">0%</span></div>`;
    panel.appendChild(card);return card;
  }

  function showAiProcess(state={}){
    const card=ensureAiProcess();if(!card)return;
    card.hidden=false;
    const percent=Math.max(0,Math.min(100,Number(state.percentage||0)));
    const status=String(state.status||'Fuentes listas. Revisá la selección antes de generar el resultado.');
    if($('aiProcessDetail'))$('aiProcessDetail').textContent=status;
    if($('aiProcessState'))$('aiProcessState').textContent=state.phase==='completed'?'Resultado listo':state.phase==='error'?'Error en el proceso':'Proceso de IA';
    if($('aiProcessStep'))$('aiProcessStep').textContent=percent+'%';
    if($('aiProcessPercent'))$('aiProcessPercent').textContent=percent+'%';
    if($('aiProcessBar'))$('aiProcessBar').style.width=percent+'%';
  }

  function enterSourceReview(){
    const page=$('contextpage'),side=$('researchPanel')?.querySelector('.context-side');
    const allSources=$('researchSourcesModalList'),footer=document.querySelector('#researchSourcesModal .lexia-sources-foot')||side?.querySelector('.lexia-sources-foot');
    if(!page||!side)return;
    if(allSources&&allSources.parentElement!==side)side.appendChild(allSources);
    if(footer&&footer.parentElement!==side)side.appendChild(footer);
    const addManual=$('lexiaAddManualResearchSource');
    if(addManual&&footer&&addManual.parentElement!==footer){
      const actions=footer.querySelector('#lexiaCaseReturnActions,#buildResearchPackage');
      footer.insertBefore(addManual,actions||null);
    }
    page.classList.add('lexia-source-review');
    const panel=$('researchPanel');if(panel)panel.hidden=false;
    showAiProcess({percentage:0,status:'Fuentes listas. Revisá la selección y elegí cuáles analizará ChatGPT.'});
  }

  function resetResearchLayout(){
    $('contextpage')?.classList.remove('lexia-source-review');
    const card=$('aiProcessCard');if(card)card.hidden=true;
    const list=$('researchSourceList');if(list)list.innerHTML='<p class="source-empty">Todavía no se recuperaron fuentes.</p>';
    const all=$('researchSourcesModalList');if(all)all.innerHTML='';
    candidateWatchToken+=1;
    watchingCandidates=false;
    for(const kind of ['research','file']){
      resultWatchToken[kind]+=1;
      watching[kind]=false;
    }
  }

  function watchCandidates(){
    if(watchingCandidates)return;watchingCandidates=true;
    const token=++candidateWatchToken;
    let attempts=0;
    const poll=async()=>{
      if(token!==candidateWatchToken)return;
      attempts+=1;
      try{
        const data=await request('/api/research-candidates-status'),state=data.state||{};
        if(token!==candidateWatchToken)return;
        if(state.phase==='completed'){watchingCandidates=false;enterSourceReview();return;}
        if(state.phase==='error'||state.phase==='cancelled'||attempts>=900){watchingCandidates=false;return;}
      }catch(_){if(attempts>=900){watchingCandidates=false;return;}}
      window.setTimeout(poll,750);
    };
    window.setTimeout(poll,500);
  }

  function watchResult(kind){
    if(watching[kind])return;
    watching[kind]=true;
    const token=++resultWatchToken[kind];
    const statusUrl=kind==='research'?'/api/research-package-status':'/api/study-status';
    const resultUrl=kind==='research'?'/api/research-package-result':'/api/study-result';
    let attempts=0;
    const poll=async()=>{
      if(token!==resultWatchToken[kind])return;
      attempts+=1;
      try{
        const status=await request(statusUrl),phase=status.state?.phase;
        if(token!==resultWatchToken[kind])return;
        if(kind==='research')showAiProcess(status.state||{});
        if(phase==='completed'){
          const data=await request(resultUrl);
          if(token!==resultWatchToken[kind])return;
          watching[kind]=false;
          if(kind==='research'&&$('buildResearchPackage'))$('buildResearchPackage').textContent='Generar resultado con IA';
          if(kind==='research')showAiProcess({phase:'completed',percentage:100,status:'Resultado generado y guardado en Últimos resultados.'});
          showResult(data.result||{});
          loadHistory();
          return;
        }
        if(phase==='error'||attempts>=900){if(kind==='research')showAiProcess({phase:'error',percentage:100,status:status.state?.error||status.state?.status||'No se pudo generar el resultado.'});watching[kind]=false;return;}
      }catch(_){if(attempts>=900){watching[kind]=false;return;}}
      window.setTimeout(poll,800);
    };
    window.setTimeout(poll,800);
  }

  function install(){
    installStyle();ensureModal();
    // El paquete es un insumo técnico no editable. No debe ocupar espacio ni
    // quedar visible después de obtener la respuesta final de ChatGPT.
    const packageCard=$('investigationOutput')?.closest('.output-card')
      ||document.querySelector('#contextpage .output-card');
    packageCard?.remove();
    if(!ensureHistoryPanel())return;
    const build=$('buildResearchPackage');
    if(build){
      build.textContent='Generar resultado con IA';
      build.title='Enviar las fuentes seleccionadas a ChatGPT';
    }
    $('aiResultsTab')?.addEventListener('click',event=>{event.preventDefault();activateHistory(true);});
    ['researchTab','studyTab'].forEach(id=>$(id)?.addEventListener('click',()=>activateHistory(false)));
    $('refreshAiResults')?.addEventListener('click',loadHistory);
    $('aiResultsSearchForm')?.addEventListener('submit',event=>{event.preventDefault();loadHistory();});
    $('clearAiResultsSearch')?.addEventListener('click',()=>{if($('aiResultsSearch'))$('aiResultsSearch').value='';loadHistory();});
    $('aiResultsList')?.addEventListener('click',event=>{
      const card=event.target.closest('[data-result-id]');if(!card)return;
      if(event.target.closest('[data-delete-result]')){deleteArchived(card);return;}
      if(event.target.closest('[data-open-result]'))openArchived(card.dataset.resultId);
    });
    document.addEventListener('click',event=>{
      if(event.target.closest('#startContext')&&String($('researchQuery')?.value||'').trim())watchCandidates();
      if(event.target.closest('#buildResearchPackage')){
        showAiProcess({percentage:5,status:'Preparando las fuentes seleccionadas para el análisis de ChatGPT…'});
        watchResult('research');
      }
      if(event.target.closest('#startStudy'))watchResult('file');
      if(event.target.closest('#newContext'))resetResearchLayout();
    });
    ensureAiProcess();
    window.lexiaEnterResearchSourceReview=enterSourceReview;
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
