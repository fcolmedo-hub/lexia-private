/* LexIA Windows — puente estable Casos -> Investigación.
   Diseño deliberadamente dirigido por eventos: sin observación continua del DOM,
   sin timers recurrentes y sin alterar el motor de Investigación. */
(function(){
  'use strict';

  const CASE_PAGE='#casespage';
  const RESEARCH_PAGE='#contextpage';
  const STORAGE_KEY='lexia.case.research.context.v2';
  const STYLE_ID='lexiaWindowsCaseResearchBridgeStyle';

  const norm=value=>String(value||'')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ').trim().toLowerCase();

  function jsonFetch(url,options){
    return fetch(url,Object.assign({
      cache:'no-store',
      headers:{'Content-Type':'application/json'}
    },options||{})).then(async response=>{
      let data={};
      try{data=await response.json();}catch(_){/* respuesta sin JSON */}
      if(!response.ok||data.ok===false){
        throw new Error(data.detail||data.error||data.message||('HTTP '+response.status));
      }
      return data;
    });
  }

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      ${CASE_PAGE} .argument-block .argument-block-actions{
        position:static!important;inset:auto!important;transform:none!important;
        display:flex!important;flex-direction:row!important;align-items:flex-start!important;
        justify-content:flex-end!important;gap:2px!important;width:auto!important;
        margin:1px 0 0!important;align-self:start!important
      }
      ${CASE_PAGE} .argument-block .argument-block-actions .cases-icon{
        box-sizing:border-box!important;width:24px!important;min-width:24px!important;
        height:24px!important;min-height:24px!important;padding:0!important;
        display:grid!important;place-items:center!important
      }
      ${CASE_PAGE} .lexia-case-investigate{color:#5146f6!important}
      ${CASE_PAGE} .lexia-case-investigate:hover{background:#eceaff!important;color:#352ac7!important}
      ${CASE_PAGE} .lexia-case-block-warning{
        margin:5px 0 0;color:#a43b45;font-size:10px;font-weight:750
      }
      ${CASE_PAGE} .lexia-case-evidence-row{position:relative;display:block;min-width:0}
      ${CASE_PAGE} .lexia-case-evidence-row>.argument-evidence{
        box-sizing:border-box;min-width:0;margin-right:0!important;padding-right:30px!important
      }
      ${CASE_PAGE} .lexia-case-evidence-delete{
        position:absolute;z-index:2;top:5px;right:4px;box-sizing:border-box;
        width:20px;height:20px;padding:0;border:0;border-radius:5px;
        display:grid;place-items:center;background:transparent;color:#b23848;
        cursor:pointer;opacity:.76
      }
      ${CASE_PAGE} .lexia-case-evidence-delete:hover{
        background:#fff0f2;color:#982b3a;opacity:1
      }
      ${RESEARCH_PAGE} #lexiaCaseResearchOrigin{
        box-sizing:border-box;width:100%;margin:0 0 10px;padding:8px 10px;
        border:1px solid #d9d5ff;border-radius:9px;background:#f8f7ff;
        color:#525d7c;font-size:10px;line-height:1.35
      }
      ${RESEARCH_PAGE} #lexiaCaseResearchOrigin b{color:#4137c9}
      ${RESEARCH_PAGE} [data-lexia-case-link],
      ${RESEARCH_PAGE} .lexia-case-link{display:none!important}
    `;
    document.head.appendChild(style);
  }

  function svgSearch(){
    return '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="6"></circle><path d="m16 16 4 4"></path></svg>';
  }
  function svgTrash(){
    return '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5M14 11v5"></path></svg>';
  }

  function saveContext(ctx){sessionStorage.setItem(STORAGE_KEY,JSON.stringify(ctx));}
  function loadContext(){
    try{return JSON.parse(sessionStorage.getItem(STORAGE_KEY)||'null');}
    catch(_){return null;}
  }
  function clearContext(){sessionStorage.removeItem(STORAGE_KEY);}

  function currentCaseName(){
    return String(document.querySelector(CASE_PAGE+' .cases-picker summary')?.textContent||'').trim();
  }
  function activeBranchRootTitle(article){
    return String(article?.closest('.primary-branch')?.querySelector('.branch-title b')?.textContent||'').trim();
  }
  function activeQuestionTitle(article){
    const workspace=article?.closest('.case-workspace-inline,.case-workspace');
    let row=workspace?.previousElementSibling;
    if(!row?.classList?.contains('question-row-active')){
      row=article?.closest('.primary-branch')?.querySelector('.question-row-active');
    }
    return String(row?.querySelector('strong')?.textContent||'').trim();
  }
  function ownBlockIndex(article){
    const section=article?.closest('details');
    const blocks=section?[...section.querySelectorAll('.argument-block')]:[];
    return Math.max(0,blocks.indexOf(article));
  }
  function counterpartText(article,index){
    const workspace=article?.closest('.case-workspace-inline,.case-workspace')||document.querySelector(CASE_PAGE);
    const counterpart=[...(workspace?.querySelectorAll('details')||[])].find(section=>
      norm(section.querySelector('summary')?.textContent).includes('contraparte')
    );
    if(!counterpart)return '';
    const texts=[...counterpart.querySelectorAll('.argument-block textarea')]
      .map(node=>String(node.value||'').trim());
    return texts[index]||texts.filter(Boolean).join('\n\n');
  }
  function flattenNodes(nodes,out){
    out=out||[];
    (nodes||[]).forEach(node=>{out.push(node);flattenNodes(node.children||[],out);});
    return out;
  }

  async function resolveBlockContext(article){
    const caseName=currentCaseName();
    if(!caseName)throw new Error('No se pudo identificar el caso activo.');

    const list=await jsonFetch('/api/cases');
    const cases=Array.isArray(list.cases)?list.cases:[];
    const selected=cases.find(item=>norm(item.name)===norm(caseName))
      ||cases.find(item=>norm(item.name).includes(norm(caseName))||norm(caseName).includes(norm(item.name)));
    if(!selected)throw new Error('No se pudo resolver el caso activo.');

    const detail=await jsonFetch('/api/cases/'+encodeURIComponent(selected.id));
    const snapshot=detail.case&&detail.case.case?detail.case:detail;
    const roots=snapshot.nodes||detail.nodes||[];
    const rootTitle=activeBranchRootTitle(article);
    const questionTitle=activeQuestionTitle(article);
    const root=roots.find(node=>norm(node.title)===norm(rootTitle))||roots[0];
    const candidateNodes=flattenNodes(root?[root]:roots,[]);
    const index=ownBlockIndex(article);
    const visibleText=norm(article?.querySelector('textarea')?.value);

    let node=candidateNodes.find(item=>norm(item.title)===norm(questionTitle))||null;
    let block=node?(node.blocks?.propia||[])[index]:null;

    if(!block?.id||(visibleText&&norm(block.content)!==visibleText)){
      const exact=[];
      candidateNodes.forEach(candidate=>(candidate.blocks?.propia||[]).forEach((item,itemIndex)=>{
        if(visibleText&&norm(item.content)===visibleText)exact.push({node:candidate,block:item,index:itemIndex});
      }));
      if(exact.length===1){node=exact[0].node;block=exact[0].block;}
    }

    if(!node)node=candidateNodes.find(item=>(item.blocks?.propia||[]).length)||null;
    if(!block?.id&&node)block=(node.blocks?.propia||[])[index];
    if(!node||!block?.id)throw new Error('No se pudo identificar el bloque de nuestra postura.');

    const actualIndex=Math.max(0,(node.blocks?.propia||[])
      .findIndex(item=>String(item.id)===String(block.id)));

    return {
      caseId:Number(selected.id),
      caseName:selected.name||caseName,
      rootTitle:root?.title||rootTitle,
      nodeId:node.id,
      nodeTitle:node.title||questionTitle,
      blockId:block.id,
      blockIndex:actualIndex,
      block
    };
  }

  function navButton(term){
    const wanted=norm(term);
    return [...document.querySelectorAll('#globalSidebar .nav button,.global-sidebar .nav button')]
      .find(button=>norm(button.textContent).includes(wanted));
  }

  function closeCompactDrawer(){
    if(window.innerWidth>1199)return;
    document.documentElement.classList.remove('lexia-nav-open');
    document.body?.classList.remove('lexia-nav-open');
    document.querySelectorAll('.lexia-nav-open').forEach(node=>node.classList.remove('lexia-nav-open'));
  }

  function navigateToResearch(){
    const cases=document.querySelector(CASE_PAGE);
    if(cases)cases.style.display='none';
    const navigate=window.lexiaUI2NavigateGlobal||window.lexiaUI2NavigateSafe||window.lexiaUI2Navigate||window.lexiaUI2Show;
    if(typeof navigate==='function'){
      navigate('contextpage');
      closeCompactDrawer();
      return true;
    }
    const button=document.querySelector('#globalSidebar .nav button[data-route="contextpage"]')||navButton('investigacion');
    if(button){button.click();closeCompactDrawer();return true;}
    return false;
  }

  function researchPanelVisible(){
    const panel=document.getElementById('researchPanel');
    return Boolean(panel&&!panel.hidden&&getComputedStyle(panel).display!=='none');
  }

  function ensureResearchTabOnce(){
    if(researchPanelVisible())return;
    const tab=document.getElementById('researchTab');
    if(tab)tab.click();
  }

  function controlDescriptor(root,control){
    const id=control.id||'';
    const label=id?root.querySelector('label[for="'+CSS.escape(id)+'"]'):null;
    const parentText=control.closest('label,.field,.form-field,.context-field')?.textContent||'';
    return norm([
      label?.textContent||'',parentText,control.placeholder||'',control.getAttribute('aria-label')||'',
      control.id||'',control.getAttribute('name')||''
    ].join(' '));
  }

  function fieldByTerms(root,terms,excluded){
    if(!root)return null;
    const controls=[...root.querySelectorAll('textarea,input[type="text"],input[type="search"]')]
      .filter(node=>!excluded?.includes(node));
    let best=null,bestScore=0;
    controls.forEach(control=>{
      const text=controlDescriptor(root,control);
      let score=0;
      terms.forEach(term=>{if(text.includes(norm(term)))score+=norm(term).length;});
      if(score>bestScore){best=control;bestScore=score;}
    });
    return best;
  }

  function setNativeValue(node,value){
    if(!node)return;
    const proto=node instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
    if(setter)setter.call(node,value);else node.value=value;
    node.dispatchEvent(new Event('input',{bubbles:true}));
    node.dispatchEvent(new Event('change',{bubbles:true}));
  }

  function fillIfAvailable(node,value){
    if(!node||!value)return;
    if(document.activeElement===node)return;
    if(String(node.value||'').trim()&&node.dataset.lexiaCaseAutofill!=='1')return;
    setNativeValue(node,value);
    node.dataset.lexiaCaseAutofill='1';
  }

  function ensureOriginBanner(ctx,panel){
    let banner=document.getElementById('lexiaCaseResearchOrigin');
    if(!banner){
      banner=document.createElement('div');
      banner.id='lexiaCaseResearchOrigin';
      const target=panel.querySelector('.context-form')||panel;
      target.insertBefore(banner,target.firstChild);
    }
    banner.innerHTML='<b>Investigación vinculada al caso:</b> '
      +String(ctx.caseName||'Caso')
      +(ctx.nodeTitle?' · '+String(ctx.nodeTitle):'')
      +'. Los campos siguen siendo editables antes de investigar.';
  }

  function applyResearchContext(){
    const ctx=loadContext();
    if(!ctx||!researchPanelVisible())return false;
    const panel=document.getElementById('researchPanel');
    ensureOriginBanner(ctx,panel);

    const used=[];
    const query=fieldByTerms(panel,['consulta juridica','consulta','pregunta'],used);
    if(query)used.push(query);
    const objective=fieldByTerms(panel,['objetivo'],used);
    if(objective)used.push(objective);
    const instructions=fieldByTerms(panel,['indicaciones','instrucciones'],used);

    fillIfAvailable(query,String(ctx.ownText||'').trim());
    fillIfAvailable(objective,'Investigar y fundamentar jurídicamente la postura propia del caso.');

    const counter=String(ctx.counterText||'').trim();
    if(counter){
      fillIfAvailable(instructions,
        'El siguiente planteo corresponde a la contraparte y debe utilizarse únicamente como contexto adversarial. '
        +'Buscá refutaciones, distinciones, límites y respuestas; no orientes la investigación a sostener esta tesis:\n\n'
        +counter
      );
    }
    return true;
  }

  function applyResearchBurst(){
    [90,260,600,1100].forEach(delay=>window.setTimeout(()=>{
      ensureResearchTabOnce();
      applyResearchContext();
    },delay));
  }

  async function startCaseResearch(article){
    const textarea=article.querySelector('textarea');
    const own=String(textarea?.value||'').trim();
    article.querySelector('.lexia-case-block-warning')?.remove();
    if(!own){
      const warning=document.createElement('div');
      warning.className='lexia-case-block-warning';
      warning.textContent='Planteá primero el fundamento propio que querés investigar.';
      (textarea?.parentElement||article).appendChild(warning);
      textarea?.focus();
      return;
    }

    try{
      const base=await resolveBlockContext(article);
      const ctx={
        caseId:base.caseId,
        caseName:base.caseName,
        rootTitle:base.rootTitle,
        nodeId:base.nodeId,
        nodeTitle:base.nodeTitle,
        blockId:base.blockId,
        blockIndex:base.blockIndex,
        ownText:own,
        counterText:counterpartText(article,base.blockIndex),
        createdAt:new Date().toISOString()
      };
      saveContext(ctx);
      if(!navigateToResearch())throw new Error('No se pudo abrir Investigación.');
      applyResearchBurst();
    }catch(error){
      alert(error.message||String(error));
    }
  }

  function syncInvestigateButtons(){
    const page=document.querySelector(CASE_PAGE);
    if(!page)return;
    [...page.querySelectorAll('details')].forEach(section=>{
      if(!norm(section.querySelector('summary')?.textContent).includes('nuestra postura'))return;
      section.querySelectorAll('.argument-block').forEach(article=>{
        const actions=article.querySelector('.argument-block-actions');
        if(!actions||actions.querySelector('.lexia-case-investigate'))return;
        const button=document.createElement('button');
        button.type='button';
        button.className='cases-icon lexia-case-investigate';
        button.title='Investigar este fundamento';
        button.setAttribute('aria-label','Investigar este fundamento');
        button.innerHTML=svgSearch();
        button.addEventListener('click',event=>{
          event.preventDefault();event.stopPropagation();
          startCaseResearch(article);
        });
        const remove=actions.querySelector('.cases-danger,[title*="Eliminar" i]');
        if(remove)actions.insertBefore(button,remove);else actions.appendChild(button);
      });
    });
  }

  function evidenceIndex(article,evidence){
    return [...article.querySelectorAll('.argument-evidence')].indexOf(evidence);
  }

  function highlightForEvidence(context,article,evidence){
    const highlights=context.block?.highlights||[];
    if(!highlights.length)return null;

    const directId=evidence.dataset?.highlightId||evidence.getAttribute('data-highlight-id');
    if(directId){
      const direct=highlights.find(item=>String(item.id)===String(directId));
      if(direct)return direct;
    }

    const index=evidenceIndex(article,evidence);
    const evidenceCount=article.querySelectorAll('.argument-evidence').length;
    if(highlights.length===evidenceCount&&index>=0&&highlights[index])return highlights[index];

    const text=norm(evidence.textContent);
    const title=norm(evidence.getAttribute('title'));
    let matches=highlights.filter(item=>{
      const selected=norm(item.selected_text);
      return selected&&(text===selected||text.includes(selected)||selected.includes(text));
    });
    if(matches.length>1&&title){
      const byDocument=matches.filter(item=>item.document_name&&title.includes(norm(item.document_name)));
      if(byDocument.length)matches=byDocument;
    }
    if(matches[0])return matches[0];
    return index>=0?highlights[index]||null:null;
  }

  async function deleteEvidence(article,row,evidence){
    try{
      const context=await resolveBlockContext(article);
      const highlight=highlightForEvidence(context,article,evidence);
      if(!highlight?.id)throw new Error('No se pudo identificar esta fuente dentro del bloque.');
      if(!confirm('¿Eliminar esta fuente del bloque?\n\nEl archivo continuará disponible en “Archivos del caso”.'))return;
      await jsonFetch('/api/cases/block/highlight/delete',{
        method:'POST',
        body:JSON.stringify({case_id:context.caseId,highlight_id:highlight.id,confirmed:true})
      });
      row.remove();
    }catch(error){
      alert(error.message||String(error));
    }
  }

  function syncEvidenceDeleteButtons(){
    const page=document.querySelector(CASE_PAGE);
    if(!page)return;
    page.querySelectorAll('.argument-block').forEach(article=>{
      [...article.querySelectorAll('.argument-evidence')].forEach(evidence=>{
        if(evidence.closest('.lexia-case-evidence-row'))return;
        const row=document.createElement('div');
        row.className='lexia-case-evidence-row';
        evidence.parentNode.insertBefore(row,evidence);
        row.appendChild(evidence);

        const button=document.createElement('button');
        button.type='button';
        button.className='lexia-case-evidence-delete';
        button.title='Eliminar esta fuente del bloque';
        button.setAttribute('aria-label','Eliminar esta fuente del bloque');
        button.innerHTML=svgTrash();
        button.addEventListener('click',event=>{
          event.preventDefault();event.stopPropagation();
          deleteEvidence(article,row,evidence);
        });
        row.appendChild(button);
      });
    });
  }

  function syncCaseEnhancements(){
    installStyle();
    syncInvestigateButtons();
    syncEvidenceDeleteButtons();
  }

  function caseSyncBurst(){
    [0,80,240,600,1200].forEach(delay=>window.setTimeout(syncCaseEnhancements,delay));
  }

  function installEventRouting(){
    document.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(!target)return;
      const nav=target.closest('#globalSidebar .nav button,.global-sidebar .nav button');
      if(nav&&norm(nav.textContent)==='casos'){
        caseSyncBurst();
        return;
      }
      if(target.closest(CASE_PAGE))caseSyncBurst();
    },true);

    document.getElementById('researchTab')?.addEventListener('click',()=>{
      if(loadContext())window.setTimeout(applyResearchContext,60);
    },true);
  }

  function initialize(){
    installStyle();
    installEventRouting();
    caseSyncBurst();
    if(loadContext()&&researchPanelVisible())applyResearchContext();
  }

  window.lexiaCaseResearchBridge={
    sync:syncCaseEnhancements,
    context:loadContext,
    clear:clearContext,
    apply:applyResearchContext
  };

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();