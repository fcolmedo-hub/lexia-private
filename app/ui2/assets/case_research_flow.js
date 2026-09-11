/* LexIA UI2 — flujo Casos -> Investigación y sub-bloques por fuente. */
(function(){
  'use strict';

  const STORAGE_KEY='lexia.case.research.context.v1';
  const CASE_PAGE='#casespage';
  const RESEARCH_PAGE='#contextpage';
  const norm=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();

  function jsonFetch(url,options){
    return fetch(url,Object.assign({headers:{'Content-Type':'application/json'}},options||{})).then(async response=>{
      let data={};
      try{data=await response.json();}catch(_){/* noop */}
      if(!response.ok)throw new Error(data.detail||data.error||data.message||('HTTP '+response.status));
      return data;
    });
  }

  function injectStyles(){
    if(document.getElementById('lexiaCaseResearchFlowStyle'))return;
    const style=document.createElement('style');
    style.id='lexiaCaseResearchFlowStyle';
    style.textContent=`
      ${CASE_PAGE} .argument-block{position:relative!important;padding-right:0!important}
      ${CASE_PAGE} .argument-block .argument-block-actions{
        position:static!important;inset:auto!important;transform:none!important;
        display:flex!important;flex-direction:row!important;align-items:flex-start!important;
        justify-content:flex-end!important;gap:2px!important;width:auto!important;margin:1px 0 0!important;
        align-self:start!important
      }
      ${CASE_PAGE} .argument-block .argument-block-actions .cases-icon{
        width:24px!important;min-width:24px!important;height:24px!important;min-height:24px!important;
        display:grid!important;place-items:center!important;padding:0!important
      }
      ${CASE_PAGE} .lexia-case-investigate{color:#5146f6!important}
      ${CASE_PAGE} .lexia-case-investigate:hover{background:#eceaff!important;color:#352ac7!important}
      ${CASE_PAGE} .lexia-case-evidence-row{position:relative;display:block;min-width:0}
      ${CASE_PAGE} .lexia-case-evidence-row>.argument-evidence{box-sizing:border-box;min-width:0;margin-right:0!important;padding-right:30px!important}
      ${CASE_PAGE} .lexia-case-evidence-delete{
        position:absolute;z-index:2;top:5px;right:4px;box-sizing:border-box;width:20px;height:20px;padding:0;border:0;border-radius:5px;
        display:grid;place-items:center;background:transparent;color:#b23848;cursor:pointer;opacity:.76
      }
      ${CASE_PAGE} .lexia-case-evidence-delete:hover{background:#fff0f2;color:#982b3a;opacity:1}
      ${CASE_PAGE} .lexia-case-block-warning{margin:5px 0 0;color:#a43b45;font-size:10px;font-weight:750}

      ${RESEARCH_PAGE} #lexiaCaseResearchContext{
        box-sizing:border-box;width:100%;margin:0 0 12px;padding:12px;border:1px solid #d8d4ff;
        border-radius:10px;background:#faf9ff;color:#293357
      }
      ${RESEARCH_PAGE} #lexiaCaseResearchContext .lexia-case-research-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:9px}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext h3{margin:0;font-size:12px;color:#3d35a9}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext p{margin:3px 0 0;font-size:10px;line-height:1.4;color:#697391}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext .lexia-case-research-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext label{display:grid;gap:4px;font-size:9px;font-weight:850;text-transform:uppercase;letter-spacing:.025em;color:#626d8c}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext textarea{box-sizing:border-box;width:100%;min-height:78px;padding:8px 9px;border:1px solid #dce1ed;border-radius:8px;background:#fff;color:#293357;font:11px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;resize:vertical}
      ${RESEARCH_PAGE} #lexiaCaseResearchContext .lexia-case-adversarial-note{grid-column:1/-1;margin:0;padding:7px 8px;border-left:3px solid #8a80f6;background:#f4f2ff;color:#5d6785;font-size:10px;line-height:1.4}
      ${RESEARCH_PAGE} .lexia-case-source-select-wrap{display:flex;align-items:center;gap:5px;margin:0 0 6px;font-size:10px;font-weight:800;color:#5146f6}
      ${RESEARCH_PAGE} .lexia-case-source-select{width:15px!important;height:15px!important;min-width:15px!important;margin:0!important;accent-color:#5146f6}
      ${RESEARCH_PAGE} #lexiaCaseResearchSelectionBar{
        position:sticky;z-index:8;top:4px;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;
        gap:8px;width:100%;margin:10px 0;padding:8px 10px;border:1px solid #d9d5ff;border-radius:9px;background:#fff;
        box-shadow:0 4px 12px rgba(49,43,128,.08)
      }
      ${RESEARCH_PAGE} #lexiaCaseResearchSelectionBar small{color:#66708f;font-size:10px}
      ${RESEARCH_PAGE} #lexiaCaseResearchSelectionBar button{min-height:30px;padding:6px 10px;border:1px solid #5146f6;border-radius:7px;background:#5146f6;color:#fff;font:800 10px/1.1 system-ui,sans-serif;cursor:pointer}
      ${RESEARCH_PAGE} #lexiaCaseResearchSelectionBar button:disabled{opacity:.45;cursor:default}
      ${RESEARCH_PAGE} [data-lexia-case-link],${RESEARCH_PAGE} .lexia-case-link{display:none!important}

      @media(max-width:1199px){
        ${RESEARCH_PAGE},${RESEARCH_PAGE}>.main,${RESEARCH_PAGE} .page,${RESEARCH_PAGE} .context-grid,
        ${RESEARCH_PAGE} #researchPanel,${RESEARCH_PAGE} .research-main-column,${RESEARCH_PAGE} .context-side,
        ${RESEARCH_PAGE} .output-card,${RESEARCH_PAGE} .sources-found,${RESEARCH_PAGE} .research-sources{
          box-sizing:border-box!important;min-width:0!important;max-width:100%!important
        }
        ${RESEARCH_PAGE} .context-grid{grid-template-columns:minmax(0,1fr)!important;height:auto!important;min-height:0!important;overflow:visible!important}
        ${RESEARCH_PAGE} #researchPanel{position:relative!important;inset:auto!important;transform:none!important;float:none!important;clear:both!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important}
        ${RESEARCH_PAGE} .research-main-column,${RESEARCH_PAGE} .context-side{position:relative!important;inset:auto!important;transform:none!important;float:none!important;width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important}
        ${RESEARCH_PAGE} .output-card,${RESEARCH_PAGE} .sources-found,${RESEARCH_PAGE} .research-sources,
        ${RESEARCH_PAGE} [class*="source-list"],${RESEARCH_PAGE} [class*="sources-list"]{
          position:relative!important;inset:auto!important;transform:none!important;float:none!important;clear:both!important;
          width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;margin-top:12px!important;overflow:visible!important
        }
      }
      @media(max-width:700px){
        ${RESEARCH_PAGE} #lexiaCaseResearchContext .lexia-case-research-grid{grid-template-columns:minmax(0,1fr)}
      }
    `;
    document.head.appendChild(style);
  }

  function compactMenuToggles(){
    const selectors=[
      '.global-menu-toggle','.global-nav-toggle','.nav-toggle','.menu-toggle',
      '[data-lexia-nav-toggle]','#globalMenuToggle','#globalNavToggle',
      '[aria-controls*="globalSidebar" i]','[aria-controls*="sidebar" i]'
    ];
    return [...new Set(document.querySelectorAll(selectors.join(',')))];
  }

  function resetCompactMenuToggle(){
    compactMenuToggles().forEach(node=>{
      node.setAttribute('aria-expanded','false');
      node.classList.remove('open','active','show','expanded','is-open','is-active');
      const text=String(node.textContent||'').trim();
      if(!node.querySelector('svg')&&/^[×✕✖]$/.test(text))node.textContent='☰';
    });
  }

  function closeCompactDrawer(){
    if(window.innerWidth>1199)return;
    document.documentElement.classList.remove('lexia-nav-open');
    document.body?.classList.remove('lexia-nav-open');
    document.querySelectorAll('.lexia-nav-open').forEach(node=>node.classList.remove('lexia-nav-open'));
    resetCompactMenuToggle();
    const backdrop=document.querySelector('.lexia-nav-backdrop');
    if(backdrop){backdrop.classList.remove('open','active','show');backdrop.setAttribute('aria-hidden','true');}
  }

  function installCompactNavFix(){
    document.addEventListener('click',event=>{
      const button=event.target instanceof Element?event.target.closest('.global-sidebar .nav button'):null;
      if(!button)return;
      const label=norm(button.textContent);
      if(label.includes('estandares')||label==='casos'||label.includes(' casos'))requestAnimationFrame(closeCompactDrawer);
    },true);
  }

  function svgSearch(){return '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="6"></circle><path d="m16 16 4 4"></path></svg>';}
  function svgTrash(){return '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5M14 11v5"></path></svg>';}

  function pageVisible(selector){
    const node=document.querySelector(selector);if(!node)return false;
    const style=getComputedStyle(node);return style.display!=='none'&&style.visibility!=='hidden';
  }
  function currentCaseName(){return String(document.querySelector(CASE_PAGE+' .cases-picker summary')?.textContent||'').trim();}
  function activeBranchRootTitle(blockArticle){return String(blockArticle?.closest('.primary-branch')?.querySelector('.branch-title b')?.textContent||'').trim();}
  function activeQuestionTitle(blockArticle){
    const inline=blockArticle?.closest('.case-workspace-inline,.case-workspace');
    let row=inline?.previousElementSibling;
    if(!row?.classList?.contains('question-row-active'))row=blockArticle?.closest('.primary-branch')?.querySelector('.question-row-active');
    return String(row?.querySelector('strong')?.textContent||'').trim();
  }
  function ownBlockIndex(article){
    const section=article?.closest('details');const blocks=section?[...section.querySelectorAll('.argument-block')]:[];
    return Math.max(0,blocks.indexOf(article));
  }
  function counterpartText(article,index){
    const workspace=article?.closest('.case-workspace-inline,.case-workspace')||document.querySelector(CASE_PAGE);
    const counterpart=[...(workspace?.querySelectorAll('details')||[])].find(node=>norm(node.querySelector('summary')?.textContent).includes('contraparte'));
    if(!counterpart)return '';
    const texts=[...counterpart.querySelectorAll('.argument-block textarea')].map(node=>node.value.trim()).filter(Boolean);
    return texts[index]||texts.join('\n\n');
  }
  function flattenNodes(nodes,out){out=out||[];(nodes||[]).forEach(node=>{out.push(node);flattenNodes(node.children||[],out);});return out;}

  async function resolveBlockContext(article){
    const caseName=currentCaseName();if(!caseName)throw new Error('No se pudo identificar el caso activo.');
    const cases=await jsonFetch('/api/cases',{cache:'no-store'});
    const candidates=(cases.cases||[]).filter(item=>norm(item.name)===norm(caseName));
    const selected=candidates[0]||(cases.cases||[]).find(item=>norm(item.name).includes(norm(caseName))||norm(caseName).includes(norm(item.name)));
    if(!selected)throw new Error('No se pudo resolver el caso activo.');
    const detail=await jsonFetch('/api/cases/'+encodeURIComponent(selected.id),{cache:'no-store'});
    const snapshot=detail.case&&detail.case.case?detail.case:detail;
    const roots=snapshot.nodes||detail.nodes||[];
    const rootTitle=activeBranchRootTitle(article),questionTitle=activeQuestionTitle(article);
    const root=roots.find(node=>norm(node.title)===norm(rootTitle))||roots[0];
    const candidateNodes=flattenNodes(root?[root]:roots,[]);
    const index=ownBlockIndex(article),visibleText=norm(article?.querySelector('textarea')?.value);
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
    const actualIndex=Math.max(0,(node.blocks?.propia||[]).findIndex(item=>String(item.id)===String(block.id)));
    return {caseId:Number(selected.id),caseName:selected.name||caseName,rootTitle:root?.title||rootTitle,nodeId:node.id,nodeTitle:node.title||questionTitle,blockId:block.id,blockIndex:actualIndex,snapshot,block};
  }

  function saveResearchContext(ctx){localStorage.setItem(STORAGE_KEY,JSON.stringify(ctx));}
  function loadResearchContext(){try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');}catch(_){return null;}}
  function clearResearchContext(){localStorage.removeItem(STORAGE_KEY);}
  function navButton(term){
    const wanted=norm(term);
    return [...document.querySelectorAll('.global-sidebar .nav button,button[data-target],button[data-page]')].find(button=>norm(button.textContent).includes(wanted));
  }
  function navigateToResearch(){
    const casePage=document.querySelector(CASE_PAGE);if(casePage)casePage.style.display='none';
    const navigate=window.lexiaUI2NavigateGlobal||window.lexiaUI2NavigateSafe||window.lexiaUI2Navigate||window.lexiaUI2Show;
    if(typeof navigate==='function'){
      navigate('contextpage');closeCompactDrawer();return true;
    }
    const button=document.querySelector('#globalSidebar .nav button[data-route="contextpage"]')||navButton('investigacion');
    if(button){button.click();closeCompactDrawer();return true;}
    ['home','library','searchpage','contextpage','activitypage','systempage','maintenance'].forEach(id=>{const page=document.getElementById(id);if(page)page.style.display='none';});
    const research=document.querySelector(RESEARCH_PAGE);if(!research)return false;research.style.display='grid';closeCompactDrawer();return true;
  }
  function navigateToCases(){
    const button=navButton('casos');if(button){button.click();closeCompactDrawer();return;}
    const research=document.querySelector(RESEARCH_PAGE),cases=document.querySelector(CASE_PAGE);if(research)research.style.display='none';if(cases)cases.style.display='block';
  }

  async function startCaseResearch(article){
    const textarea=article.querySelector('textarea'),own=String(textarea?.value||'').trim();article.querySelector('.lexia-case-block-warning')?.remove();
    if(!own){
      const warning=document.createElement('div');warning.className='lexia-case-block-warning';warning.textContent='Planteá primero el fundamento propio que querés investigar.';
      (textarea?.parentElement||article).appendChild(warning);textarea?.focus();return;
    }
    try{
      const base=await resolveBlockContext(article),counter=counterpartText(article,base.blockIndex);
      const ctx=Object.assign(base,{ownText:own,counterText:counter,createdAt:new Date().toISOString()});delete ctx.snapshot;delete ctx.block;
      saveResearchContext(ctx);
      if(!navigateToResearch())throw new Error('No se pudo abrir Investigación.');
      [80,250,600,1000].forEach(delay=>setTimeout(()=>{try{applyResearchContext();}catch(error){console.error('LexIA Casos→Investigación:',error);}},delay));
    }catch(error){alert(error.message||String(error));}
  }

  function syncInvestigateButtons(){
    const page=document.querySelector(CASE_PAGE);if(!page)return;
    [...page.querySelectorAll('details')].forEach(section=>{
      if(!norm(section.querySelector('summary')?.textContent).includes('nuestra postura'))return;
      section.querySelectorAll('.argument-block').forEach(article=>{
        const actions=article.querySelector('.argument-block-actions');if(!actions||actions.querySelector('.lexia-case-investigate'))return;
        const button=document.createElement('button');button.type='button';button.className='cases-icon lexia-case-investigate';button.title='Investigar este fundamento';button.setAttribute('aria-label','Investigar este fundamento');button.innerHTML=svgSearch();
        button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();startCaseResearch(article);});
        const remove=actions.querySelector('.cases-danger,[title*="Eliminar" i]');if(remove)actions.insertBefore(button,remove);else actions.appendChild(button);
      });
    });
  }

  function highlightForEvidence(context,row){
    const evidence=row.querySelector('.argument-evidence'),highlights=context.block?.highlights||[];
    if(!evidence||!highlights.length)return null;
    const savedId=row.dataset.highlightId;
    if(savedId){const saved=highlights.find(item=>String(item.id)===String(savedId));if(saved)return saved;}
    const text=norm(evidence.textContent),title=norm(evidence.getAttribute('title'));
    let matches=highlights.filter(item=>norm(item.selected_text)===text);
    if(matches.length>1&&title){
      const byDocument=matches.filter(item=>item.document_name&&title.includes(norm(item.document_name)));
      if(byDocument.length)matches=byDocument;
    }
    if(matches.length>1){
      const pageMatch=String(evidence.getAttribute('title')||'').match(/p[aá]g\.?\s*(\d+)/i);
      if(pageMatch){const byPage=matches.filter(item=>Number(item.page_start||0)===Number(pageMatch[1]));if(byPage.length)matches=byPage;}
    }
    if(matches[0])return matches[0];
    const index=[...row.closest('.argument-block').querySelectorAll('.lexia-case-evidence-row')].indexOf(row);
    return highlights[index]||null;
  }

  async function deleteEvidence(article,row){
    try{
      const context=await resolveBlockContext(article),highlight=highlightForEvidence(context,row);
      if(!highlight?.id)throw new Error('No se pudo identificar esta fuente dentro del bloque.');
      row.dataset.highlightId=String(highlight.id);
      if(!confirm('¿Eliminar esta fuente del bloque?\n\nEl archivo continuará disponible en “Archivos del caso”.'))return;
      await jsonFetch('/api/cases/block/highlight/delete',{method:'POST',body:JSON.stringify({case_id:context.caseId,highlight_id:highlight.id,confirmed:true})});row.remove();
    }catch(error){alert(error.message||String(error));}
  }

  function syncEvidenceDeleteButtons(){
    const page=document.querySelector(CASE_PAGE);if(!page)return;
    page.querySelectorAll('.argument-block').forEach(article=>{
      [...article.querySelectorAll('.argument-evidence')].forEach(evidence=>{
        if(evidence.closest('.lexia-case-evidence-row'))return;
        const row=document.createElement('div');row.className='lexia-case-evidence-row';evidence.parentNode.insertBefore(row,evidence);row.appendChild(evidence);
        const button=document.createElement('button');button.type='button';button.className='lexia-case-evidence-delete';button.title='Eliminar esta fuente del bloque';button.setAttribute('aria-label','Eliminar esta fuente del bloque');button.innerHTML=svgTrash();
        button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();deleteEvidence(article,row);});row.appendChild(button);
      });
    });
  }

  function removeResearchCaseButtons(){
    document.querySelectorAll(RESEARCH_PAGE+' [data-lexia-case-link],'+RESEARCH_PAGE+' .lexia-case-link').forEach(node=>{node.hidden=true;node.setAttribute('aria-hidden','true');node.tabIndex=-1;});
  }

  function fieldByLabel(root,terms,exclude){
    if(!root)return null;
    const controls=[...root.querySelectorAll('textarea,input[type="text"],input[type="search"]')].filter(node=>!exclude?.includes(node)&&!node.closest('#lexiaCaseResearchContext'));
    let best=null,bestScore=0;
    controls.forEach(control=>{
      const id=control.id,label=id?root.querySelector('label[for="'+CSS.escape(id)+'"]'):null;
      const text=norm((label?.textContent||'')+' '+(control.placeholder||'')+' '+(control.getAttribute('aria-label')||''));let score=0;
      terms.forEach(term=>{if(text.includes(norm(term)))score+=term.length;});if(score>bestScore){best=control;bestScore=score;}
    });
    return best;
  }
  function setNativeValue(node,value){
    if(!node)return;const proto=node instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
    if(setter)setter.call(node,value);else node.value=value;node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));
  }

  function createResearchContextCard(ctx){
    let card=document.getElementById('lexiaCaseResearchContext');
    if(!card){
      card=document.createElement('section');card.id='lexiaCaseResearchContext';
      card.innerHTML='<div class="lexia-case-research-head"><div><h3>Investigación vinculada al caso</h3><p></p></div></div><div class="lexia-case-research-grid"><label>Nuestra postura a investigar<textarea id="lexiaCaseResearchOwn"></textarea></label><label>Planteo de la contraparte<textarea id="lexiaCaseResearchCounter"></textarea></label><p class="lexia-case-adversarial-note">El planteo de la contraparte se incorpora sólo como referencia adversarial: sirve para buscar refutaciones, distinciones, límites y respuestas. No debe orientar la búsqueda hacia fundamentos que sostengan esa tesis.</p></div>';
      const panel=document.getElementById('researchPanel')||document.querySelector(RESEARCH_PAGE+' .research-main-column')||document.querySelector(RESEARCH_PAGE+' .context-grid')||document.querySelector(RESEARCH_PAGE);
      if(!panel)return null;
      panel.insertBefore(card,panel.firstChild);
      card.querySelectorAll('textarea').forEach(node=>node.addEventListener('input',()=>syncVisibleResearchFields(ctx)));
    }
    const subtitle=card.querySelector('.lexia-case-research-head p'),subtitleText=(ctx.caseName||'Caso')+' · '+(ctx.nodeTitle||'Cuestión jurídica');if(subtitle&&subtitle.textContent!==subtitleText)subtitle.textContent=subtitleText;
    const own=card.querySelector('#lexiaCaseResearchOwn'),counter=card.querySelector('#lexiaCaseResearchCounter');if(own&&document.activeElement!==own&&own.value!==String(ctx.ownText||''))own.value=String(ctx.ownText||'');if(counter&&document.activeElement!==counter&&counter.value!==String(ctx.counterText||''))counter.value=String(ctx.counterText||'');
    return card;
  }

  function syncVisibleResearchFields(ctx){
    const panel=document.getElementById('researchPanel')||document.querySelector(RESEARCH_PAGE);if(!panel)return;
    const own=document.getElementById('lexiaCaseResearchOwn')?.value.trim()||String(ctx.ownText||'').trim(),counter=document.getElementById('lexiaCaseResearchCounter')?.value.trim()||String(ctx.counterText||'').trim();
    const query=fieldByLabel(panel,['consulta','pregunta','tema','investigacion','buscar','cuestion'],[]),facts=fieldByLabel(panel,['hechos relevantes','hechos','contexto','antecedentes'],query?[query]:[]);
    if(query&&document.activeElement!==query&&(!query.value.trim()||query.dataset.lexiaCaseAutofill==='1')){setNativeValue(query,own);query.dataset.lexiaCaseAutofill='1';}
    if(facts&&document.activeElement!==facts&&(!facts.value.trim()||facts.dataset.lexiaCaseAutofill==='1')){
      const adversarial=counter?'Planteo de la contraparte (solo referencia adversarial; no buscar fundamentos que lo respalden):\n'+counter:'';setNativeValue(facts,adversarial);facts.dataset.lexiaCaseAutofill='1';
    }
  }

  function applyResearchContext(){
    const ctx=loadResearchContext();if(!ctx||!document.querySelector(RESEARCH_PAGE))return;
    document.getElementById('researchTab')?.click();
    const card=createResearchContextCard(ctx);if(!card)return;
    syncVisibleResearchFields(ctx);removeResearchCaseButtons();syncResearchSources(ctx);
  }

  function decodeMaybe(value){try{return decodeURIComponent(value);}catch(_){return value;}}
  function sourceCardData(card){
    const pathNode=card.matches('[data-path]')?card:card.querySelector('[data-path]'),path=decodeMaybe(String(pathNode?.dataset?.path||card.dataset?.path||''));
    const titleNode=card.querySelector('.source-name-link,.result-title-btn,.result-title,[data-document-name],strong,b');
    const name=String(titleNode?.dataset?.documentName||titleNode?.textContent||path.split(/[\\/]/).pop()||'Fuente de investigación').trim();
    const snippetNode=card.querySelector('.source-snippet,.result-body p,.snippet,.excerpt,blockquote,p');let snippet=String(snippetNode?.textContent||'').trim();if(!snippet)snippet=name;
    const pageAttr=card.dataset?.page||pathNode?.dataset?.page||'',meta=String(card.querySelector('.source-meta,.result-meta,.meta')?.textContent||''),match=(String(pageAttr)+' '+meta).match(/(?:p[aá]g(?:ina)?\.?\s*)?(\d{1,5})/i),page=match?Math.max(1,Number(match[1])):1;
    return {name,path,snippet,page};
  }
  function sourceCards(){
    const root=document.getElementById('researchPanel')||document.querySelector(RESEARCH_PAGE);if(!root)return [];
    const candidates=[...root.querySelectorAll('.source-item,.result-card,[class*="source-card"],.source-list>*')];
    return [...new Set(candidates)].filter(card=>card instanceof Element&&!card.closest('#lexiaCaseResearchContext')&&!card.closest('#lexiaCaseResearchSelectionBar')&&(card.querySelector('[data-path],.source-name-link,.result-title,.result-title-btn')||card.dataset?.path));
  }
  function updateSelectionBar(){
    const bar=document.getElementById('lexiaCaseResearchSelectionBar');if(!bar)return;const count=document.querySelectorAll(RESEARCH_PAGE+' .lexia-case-source-select:checked').length;
    bar.querySelector('small').textContent=count?count+' fuente(s) seleccionada(s)':'Seleccioná las fuentes que quieras incorporar al bloque';bar.querySelector('button').disabled=!count;
  }

  async function incorporateSelectedSources(ctx,button){
    const selected=[...document.querySelectorAll(RESEARCH_PAGE+' .lexia-case-source-select:checked')].map(check=>check.closest('.source-item,.result-card,[class*="source-card"],.source-list>*')).filter(Boolean);if(!selected.length)return;
    button.disabled=true;const original=button.textContent;button.textContent='Incorporando…';let done=0;
    try{
      for(const card of selected){
        const source=sourceCardData(card);
        const linked=await jsonFetch('/api/cases/link-document',{method:'POST',body:JSON.stringify({case_id:ctx.caseId,document_name:source.name,document_path:source.path,category:'',relation_kind:'fuente de investigación',note:''})});
        const caseDocumentId=Number(linked.link_id||linked.case_document?.id||linked.document?.id||0);
        if(!caseDocumentId)throw new Error('No se pudo registrar “'+source.name+'” en Archivos del caso.');
        await jsonFetch('/api/cases/block/highlight',{method:'POST',body:JSON.stringify({case_id:ctx.caseId,block_id:ctx.blockId,case_document_id:caseDocumentId,page_start:source.page,page_end:source.page,selected_text:source.snippet,anchor_data:''})});done+=1;
      }
      clearResearchContext();alert('Se incorporaron '+done+' fuente(s) al mismo bloque del caso.');navigateToCases();
    }catch(error){alert('Se incorporaron '+done+' fuente(s). Luego ocurrió un error: '+(error.message||String(error)));}
    finally{button.textContent=original;button.disabled=false;}
  }

  function ensureSelectionBar(ctx,cards){
    if(!cards.length)return;let bar=document.getElementById('lexiaCaseResearchSelectionBar');
    if(!bar){
      bar=document.createElement('div');bar.id='lexiaCaseResearchSelectionBar';const small=document.createElement('small'),button=document.createElement('button');button.type='button';button.textContent='Incorporar fuentes seleccionadas';button.disabled=true;
      button.addEventListener('click',()=>incorporateSelectedSources(loadResearchContext()||ctx,button));bar.append(small,button);cards[0].parentNode.insertBefore(bar,cards[0]);
    }
    updateSelectionBar();
  }
  function syncResearchSources(ctx){
    if(!ctx)return;const cards=sourceCards();
    cards.forEach(card=>{
      if(card.querySelector('.lexia-case-source-select'))return;const wrap=document.createElement('label');wrap.className='lexia-case-source-select-wrap';wrap.innerHTML='<input type="checkbox" class="lexia-case-source-select"> Incorporar al bloque del caso';
      wrap.querySelector('input').addEventListener('change',updateSelectionBar);card.insertBefore(wrap,card.firstChild);
    });
    ensureSelectionBar(ctx,cards);
  }

  function guardResearchStart(){
    document.addEventListener('click',event=>{
      const ctx=loadResearchContext();if(!ctx)return;const button=event.target instanceof Element?event.target.closest(RESEARCH_PAGE+' button'):null;if(!button)return;
      const label=norm(button.textContent);if(!/(investigar|iniciar|buscar fuentes|comenzar)/.test(label))return;
      const own=document.getElementById('lexiaCaseResearchOwn')?.value.trim()||'';
      if(!own){event.preventDefault();event.stopImmediatePropagation();alert('La investigación necesita una postura propia concreta. Completá “Nuestra postura a investigar”.');document.getElementById('lexiaCaseResearchOwn')?.focus();return;}
      ctx.ownText=own;ctx.counterText=document.getElementById('lexiaCaseResearchCounter')?.value.trim()||'';saveResearchContext(ctx);syncVisibleResearchFields(ctx);
    },true);
  }

  function syncAll(){injectStyles();syncInvestigateButtons();syncEvidenceDeleteButtons();removeResearchCaseButtons();if(pageVisible(RESEARCH_PAGE))applyResearchContext();}
  function initialize(){
    injectStyles();installCompactNavFix();guardResearchStart();syncAll();
    const observer=new MutationObserver(()=>syncAll());observer.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});else initialize();
})();