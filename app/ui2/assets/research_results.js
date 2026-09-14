/* LexIA — respuestas de ChatGPT e historial persistente de Investigación. */
(function(){
  'use strict';

  const $=id=>document.getElementById(id);
  const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));
  const request=async url=>{
    const response=await fetch(url,{cache:'no-store'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  };
  const watching={research:false,file:false};

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
      #contextpage .ai-results-list{display:flex;flex-direction:column;gap:10px}
      #contextpage .ai-result-card{width:100%;display:grid;grid-template-columns:128px minmax(0,1fr);gap:14px;text-align:left;padding:13px;border:1px solid #e1e4ee;border-radius:11px;background:#fff;cursor:pointer}
      #contextpage .ai-result-card:hover{border-color:#b9b3ff;background:#faf9ff;box-shadow:0 5px 16px rgba(71,62,177,.08)}
      #contextpage .ai-result-badge{display:inline-flex;width:max-content;padding:5px 8px;border-radius:999px;background:#eceaff;color:#4036c4;font-size:10px;font-weight:800}
      #contextpage .ai-result-card[data-kind="file"] .ai-result-badge{background:#e8f4ff;color:#17649b}
      #contextpage .ai-result-date{display:block;margin-top:8px;color:#8790a8;font-size:10px}
      #contextpage .ai-result-copy b{display:block;margin-bottom:5px;color:#29314d;font-size:13px;line-height:1.35}
      #contextpage .ai-result-copy p{margin:0;color:#68728d;font-size:11.5px;line-height:1.45}
      #contextpage .ai-results-empty{padding:26px;text-align:center;color:#7b849d;border:1px dashed #d9dce7;border-radius:10px}
      .lexia-ai-modal{display:none;position:fixed;inset:0;z-index:12000;background:rgba(20,25,43,.5);padding:30px;align-items:center;justify-content:center}
      .lexia-ai-modal.open{display:flex}
      .lexia-ai-dialog{display:flex;flex-direction:column;width:min(920px,96vw);max-height:90vh;background:#fff;border-radius:14px;box-shadow:0 24px 70px rgba(10,15,35,.3);overflow:hidden}
      .lexia-ai-dialog-head{display:flex;justify-content:space-between;gap:16px;padding:17px 20px;border-bottom:1px solid #e7e9f1}
      .lexia-ai-dialog-head h2{margin:0 0 5px;color:#222a46;font-size:18px}
      .lexia-ai-dialog-head p{margin:0;color:#747e98;font-size:11px}
      .lexia-ai-dialog-close{width:34px;height:34px;border:0;border-radius:8px;background:#f1f0ff;color:#4036c4;font-size:21px;cursor:pointer}
      .lexia-ai-result{padding:20px;overflow:auto;white-space:pre-wrap;color:#28314e;font:13px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif}
      @media(max-width:700px){#contextpage .ai-result-card{grid-template-columns:1fr}.lexia-ai-modal{padding:10px}.lexia-ai-dialog{max-height:94vh}}
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
      panel.innerHTML=`<div class="ai-results-head"><div><h3>Últimos resultados de ChatGPT</h3><p>Investigaciones y estudios guardados para volver a consultarlos sin consumir créditos.</p></div><button class="secondary" id="refreshAiResults" type="button">Actualizar</button></div><div class="ai-results-list" id="aiResultsList"><div class="ai-results-empty">Todavía no hay resultados guardados.</div></div>`;
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
      const data=await request('/api/ai-results');
      const items=data.results||[];
      list.innerHTML=items.length?items.map(item=>`<button class="ai-result-card" data-result-id="${Number(item.id)}" data-kind="${escapeHtml(item.kind)}" type="button"><span><span class="ai-result-badge">${escapeHtml(item.type_label)}</span><small class="ai-result-date">${escapeHtml(formatDate(item.created_at))}</small></span><span class="ai-result-copy"><b>${escapeHtml(item.query||item.title||'Consulta sin título')}</b><p>${escapeHtml(item.preview||'')}</p></span></button>`).join(''):'<div class="ai-results-empty">Todavía no hay resultados guardados.</div>';
    }catch(error){list.innerHTML='<div class="ai-results-empty">No se pudo cargar el historial: '+escapeHtml(error.message||error)+'</div>';}
  }

  async function openArchived(id){
    try{const data=await request('/api/ai-results/'+encodeURIComponent(id));showResult(data.result||{});}
    catch(error){window.alert(error.message||String(error));}
  }

  function watchResult(kind){
    if(watching[kind])return;
    watching[kind]=true;
    const statusUrl=kind==='research'?'/api/research-package-status':'/api/study-status';
    const resultUrl=kind==='research'?'/api/research-package-result':'/api/study-result';
    let attempts=0;
    const poll=async()=>{
      attempts+=1;
      try{
        const status=await request(statusUrl),phase=status.state?.phase;
        if(phase==='completed'){
          const data=await request(resultUrl);
          watching[kind]=false;
          if(kind==='research'&&$('buildResearchPackage'))$('buildResearchPackage').textContent='Generar resultado con IA';
          showResult(data.result||{});
          loadHistory();
          return;
        }
        if(phase==='error'||attempts>=900){watching[kind]=false;return;}
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
    $('aiResultsList')?.addEventListener('click',event=>{
      const card=event.target.closest('[data-result-id]');if(card)openArchived(card.dataset.resultId);
    });
    document.addEventListener('click',event=>{
      if(event.target.closest('#buildResearchPackage'))watchResult('research');
      if(event.target.closest('#startStudy'))watchResult('file');
    });
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
