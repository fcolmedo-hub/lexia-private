/* LexIA UI2 — bridge from Search results to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';
  const CONTENT_OPEN_ATTR='data-lexia-content-open';
  const STYLE_ID='lexiaSearchInvestigationButtonColors';
  const RECENT_TOUCH_STYLE_ID='lexiaSearchRecentTouchFix';
  const STUDY_LAYOUT_STYLE_ID='lexiaStudyLayoutFix';
  const STUDY_HISTORY_KEY='lexia.study.indications.history.v1';
  const STUDY_HISTORY_PANEL_ID='lexiaStudyIndicationsHistory';

  function decodePath(value){
    try{return decodeURIComponent(String(value||''));}
    catch(_){return String(value||'');}
  }

  function removeSearchInsight(){
    document.querySelector('#'+SEARCH_PAGE_ID+' .insight')?.remove();
    const grid=document.querySelector('#'+SEARCH_PAGE_ID+' .search-grid');
    if(grid)grid.style.setProperty('grid-template-columns','220px minmax(0,1fr)','important');
  }

  function ensureButtonColors(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${SEARCH_PAGE_ID} .result-actions .search-open-file[${CONTENT_OPEN_ATTR}="1"]{
        background:#149d55!important;
        border-color:#149d55!important;
        color:#fff!important;
      }
      #${SEARCH_PAGE_ID} .result-actions .search-open-file[${CONTENT_OPEN_ATTR}="1"]:hover{
        background:#0f8044!important;
        border-color:#0f8044!important;
      }
      #${SEARCH_PAGE_ID} .result-actions [${INVESTIGATE_ATTR}="1"]{
        background:#5146f6!important;
        border-color:#5146f6!important;
        color:#fff!important;
      }
      #${SEARCH_PAGE_ID} .result-actions [${INVESTIGATE_ATTR}="1"]:hover{
        background:#4338e8!important;
        border-color:#4338e8!important;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureStudyLayout(){
    let style=document.getElementById(STUDY_LAYOUT_STYLE_ID);
    if(!style){
      style=document.createElement('style');
      style.id=STUDY_LAYOUT_STYLE_ID;
      document.head.appendChild(style);
    }
    style.textContent=`
      #contextpage #studyPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0 0 22px 0!important;
        padding-bottom:20px!important;
        box-sizing:border-box!important;
        z-index:auto!important;
      }
      #contextpage #studyPanel[hidden]{display:none!important;}
      #contextpage #studyPanel .context-actions{
        display:flex!important;
        align-items:center!important;
        gap:12px!important;
        position:relative!important;
        left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;
        inset:auto!important;
        float:none!important;
        transform:none!important;
        margin:16px 0 0!important;
        padding:14px 0 0!important;
        min-height:42px!important;
        overflow:visible!important;
      }
      #contextpage #studyPanel .context-actions .primary,
      #contextpage #studyPanel #startStudy{
        position:static!important;
        left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;
        inset:auto!important;
        float:none!important;
        transform:none!important;
        margin:0 0 0 auto!important;
        flex:0 0 auto!important;
        z-index:auto!important;
      }
      #contextpage .output-card{
        display:block!important;
        position:relative!important;
        left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;
        inset:auto!important;
        transform:none!important;
        clear:both!important;
        margin:22px 0 0!important;
        z-index:auto!important;
      }
      #contextpage #studyStatus{position:relative!important;clear:both!important;}
      #contextpage .lexia-study-indications-wrap{position:relative!important;width:100%!important;}
      #contextpage #${STUDY_HISTORY_PANEL_ID}{
        display:none;position:absolute;left:0;right:0;top:calc(100% + 5px);z-index:10020;
        max-height:230px;overflow:auto;background:#fff;border:1px solid #dfe3ee;border-radius:9px;
        box-shadow:0 10px 28px rgba(41,49,83,.14);padding:5px;
      }
      #contextpage #${STUDY_HISTORY_PANEL_ID}.open{display:block;}
      #contextpage #${STUDY_HISTORY_PANEL_ID} .lexia-study-history-title{
        padding:7px 9px 5px;color:#687393;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
      }
      #contextpage #${STUDY_HISTORY_PANEL_ID} button{
        display:block;width:100%;border:0;background:#fff;text-align:left;border-radius:7px;
        padding:8px 9px;color:#263253;font-size:12px;line-height:1.3;cursor:pointer;white-space:normal;
      }
      #contextpage #${STUDY_HISTORY_PANEL_ID} button:hover{background:#f1f0ff;color:#352bc7;}
      #contextpage #${STUDY_HISTORY_PANEL_ID} .lexia-study-history-empty{padding:9px;color:#7a849f;font-size:11px;}
    `;
  }

  function setupRecentHistoryTouchFix(){
    if(!document.getElementById(RECENT_TOUCH_STYLE_ID)){
      const style=document.createElement('style');
      style.id=RECENT_TOUCH_STYLE_ID;
      style.textContent=`
        @media (max-width:700px){
          #${SEARCH_PAGE_ID} #searchRecentHistory,
          #${SEARCH_PAGE_ID} #searchRecentHistory *{
            -webkit-user-select:none!important;
            user-select:none!important;
            -webkit-touch-callout:none!important;
          }
          #${SEARCH_PAGE_ID} #searchRecentHistory{
            overflow-x:hidden!important;
            overflow-y:auto!important;
            -webkit-overflow-scrolling:auto!important;
            overscroll-behavior:contain!important;
            touch-action:none!important;
          }
          #${SEARCH_PAGE_ID} #searchRecentHistory button[data-query]{touch-action:none!important;}
        }
      `;
      document.head.appendChild(style);
    }

    let touchActive=false,moved=false,startX=0,startY=0,startScrollTop=0,activePanel=null,suppressClickUntil=0;
    const isMobileTouch=()=>{try{return window.matchMedia('(max-width:700px)').matches||Number(navigator.maxTouchPoints||0)>0;}catch(_){return Number(navigator.maxTouchPoints||0)>0;}};
    const recentPanel=target=>target?.closest?.('#searchRecentHistory');

    window.addEventListener('touchstart',event=>{
      if(!isMobileTouch()||event.touches.length!==1)return;
      const panel=recentPanel(event.target);if(!panel)return;
      const touch=event.touches[0];touchActive=true;moved=false;startX=touch.clientX;startY=touch.clientY;startScrollTop=panel.scrollTop;activePanel=panel;
    },{capture:true,passive:false});
    window.addEventListener('touchmove',event=>{
      if(!touchActive||!activePanel||event.touches.length!==1)return;
      const touch=event.touches[0],dx=touch.clientX-startX,dy=touch.clientY-startY;
      if(Math.abs(dx)>4||Math.abs(dy)>4)moved=true;if(!moved)return;
      event.preventDefault();event.stopPropagation();activePanel.scrollTop=startScrollTop-dy;try{window.getSelection()?.removeAllRanges();}catch(_){}
    },{capture:true,passive:false});
    window.addEventListener('touchend',event=>{
      if(!touchActive)return;if(moved){suppressClickUntil=performance.now()+700;event.preventDefault();event.stopPropagation();}
      touchActive=false;activePanel=null;
    },{capture:true,passive:false});
    window.addEventListener('touchcancel',()=>{if(moved)suppressClickUntil=performance.now()+700;touchActive=false;activePanel=null;},true);
    window.addEventListener('pointerout',event=>{if(!touchActive||!recentPanel(event.target))return;event.stopPropagation();},true);
    window.addEventListener('selectstart',event=>{if(!isMobileTouch()||!recentPanel(event.target))return;event.preventDefault();event.stopPropagation();},true);
    window.addEventListener('click',event=>{
      if(!isMobileTouch())return;
      const item=event.target.closest?.('#searchRecentHistory button[data-query]');if(!item)return;
      event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
      if(moved||performance.now()<suppressClickUntil){moved=false;return;}
      const input=document.getElementById('legalQuery');
      if(input){input.value=item.dataset.query||'';input.dispatchEvent(new Event('input',{bubbles:true}));try{input.focus({preventScroll:true});}catch(_){input.focus();}}
      document.getElementById('searchRecentHistory')?.classList.remove('open');
    },true);
  }

  function investigateButton(openButton){
    const button=openButton.cloneNode(true);
    button.removeAttribute(CONTENT_OPEN_ATTR);
    button.setAttribute(INVESTIGATE_ATTR,'1');
    button.classList.add('search-investigate-file');
    button.textContent='Investigar';
    button.title='Cargar este archivo en Investigación · Estudiar un archivo';
    return button;
  }

  function syncResultCard(card){
    const actions=card?.querySelector('.result-actions');
    if(!actions||actions.querySelector('['+INVESTIGATE_ATTR+']'))return;
    const openButton=[...actions.querySelectorAll('.search-open-file')].find(button=>!button.hasAttribute(INVESTIGATE_ATTR));
    if(!openButton)return;
    const contentResult=Boolean(actions.querySelector('.score'));
    if(contentResult){openButton.setAttribute(CONTENT_OPEN_ATTR,'1');openButton.insertAdjacentElement('afterend',investigateButton(openButton));return;}
    openButton.setAttribute(INVESTIGATE_ATTR,'1');openButton.classList.add('search-investigate-file');openButton.textContent='Investigar';openButton.title='Cargar este archivo en Investigación · Estudiar un archivo';
  }

  function syncSearchSurface(){
    removeSearchInsight();
    document.querySelectorAll('#'+SEARCH_PAGE_ID+' #realSearchResults .result-card').forEach(syncResultCard);
  }

  function navigateToInvestigation(){
    const navigate=window.lexiaUI2NavigateGlobal||window.lexiaUI2NavigateSafe||window.lexiaUI2Navigate||window.lexiaUI2Show;
    if(typeof navigate==='function'){navigate('contextpage');return;}
    ['home','library','searchpage','contextpage','activitypage','systempage','maintenance'].forEach(id=>{const page=document.getElementById(id);if(page)page.style.display='none';});
    const context=document.getElementById('contextpage');if(context)context.style.display='grid';
  }

  function selectOptionByText(select,text){
    if(!select)return false;
    const wanted=String(text||'').trim().toLocaleLowerCase('es');
    const option=[...select.options].find(item=>String(item.value||item.textContent||'').trim().toLocaleLowerCase('es')===wanted);
    if(!option)return false;
    select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));return true;
  }

  function applyStudyDefaultsFromPath(path){
    ensureStudyTypes();
    const normalized=('/'+String(path||'').replace(/\\/g,'/').replace(/^\/+|\/+$/g,'')+'/').toLocaleLowerCase('es');
    const type=document.getElementById('studyType');
    const objective=document.getElementById('studyObjective');
    if(normalized.includes('/doctrina/')){
      selectOptionByText(type,'Libro');
      selectOptionByText(objective,'Investigación jurídica');
    }else if(normalized.includes('/legislacion/')||normalized.includes('/legislación/')){
      selectOptionByText(type,'Legislación');
      selectOptionByText(objective,'Investigación jurídica');
    }
  }

  function loadStudyFile(path,name){
    const input=document.getElementById('studyPath');
    if(!input)throw new Error('No se encontró el campo “Archivo indexado” de Investigación.');
    input.value=path;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
    applyStudyDefaultsFromPath(path);
    navigateToInvestigation();
    const studyTab=document.getElementById('studyTab');if(studyTab)studyTab.click();
    const researchPanel=document.getElementById('researchPanel'),studyPanel=document.getElementById('studyPanel');
    if(researchPanel)researchPanel.hidden=true;if(studyPanel)studyPanel.hidden=false;
    ensureStudyLayout();
    const status=document.getElementById('studyStatus');
    if(status){status.hidden=false;status.textContent='Archivo cargado: '+(name||path)+'. Indicá qué querés investigar y presioná “Estudiar”.';}
    try{input.focus({preventScroll:true});}catch(_){input.focus();}
    studyPanel?.scrollIntoView({block:'start'});
  }

  function installHtmlViewerFix(){
    if(window.__lexiaHtmlViewerFixInstalled)return;
    const original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function'){window.setTimeout(installHtmlViewerFix,25);return;}
    window.__lexiaHtmlViewerFixInstalled=true;
    const extension=path=>{const clean=String(path||'').split('?')[0].split('#')[0],name=clean.split(/[\\/]/).pop()||'',dot=name.lastIndexOf('.');return dot>=0?name.slice(dot).toLowerCase():'';};
    const basename=path=>String(path||'').split(/[\\/]/).pop()||'Documento HTML';
    window.lexiaQuickViewerOpen=function(path,page,snippet){
      const ext=extension(path);if(ext!=='.htm'&&ext!=='.html')return original(path,page,snippet);
      const backdrop=document.getElementById('lexiaQuickViewer'),pane=document.getElementById('lexiaQvBody'),name=document.getElementById('lexiaQvName'),pathLabel=document.getElementById('lexiaQvPath'),open=document.getElementById('lexiaQvOpen');
      if(!backdrop||!pane)return original(path,page,snippet);
      if(name)name.textContent=basename(path);if(pathLabel)pathLabel.textContent=String(path||'');if(open)open.hidden=false;
      pane.classList.remove('lexia-qv-mobile-mode');pane.innerHTML='';
      const frame=document.createElement('iframe');frame.className='lexia-qv-html-frame';frame.title='Vista HTML · '+basename(path);frame.setAttribute('sandbox','');frame.setAttribute('referrerpolicy','no-referrer');frame.style.cssText='display:block;width:100%;height:100%;min-height:68vh;border:0;background:#fff;';frame.src='/api/file-preview?path='+encodeURIComponent(String(path||''));pane.appendChild(frame);
      backdrop.classList.add('open');backdrop.setAttribute('aria-hidden','false');return true;
    };
  }

  function readStudyHistory(){
    try{const raw=JSON.parse(localStorage.getItem(STUDY_HISTORY_KEY)||'[]');return Array.isArray(raw)?raw.map(v=>String(v||'').trim()).filter(Boolean).slice(0,20):[];}catch(_){return [];}
  }
  function saveStudyHistory(value){
    const text=String(value||'').trim();
    if(!text)return;

    const items=readStudyHistory()
      .filter(item=>item.toLocaleLowerCase('es')!==text.toLocaleLowerCase('es'));

    items.unshift(text);
    const saved=items.slice(0,20);

    try{
      localStorage.setItem(
        STUDY_HISTORY_KEY,
        JSON.stringify(saved)
      );
    }catch(_){}

    fetch('/api/study-history',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({items:saved}),
      cache:'no-store'
    }).catch(()=>{});
  }

  async function loadPersistentStudyHistory(){
    try{
      const response=await fetch(
        '/api/study-history',
        {cache:'no-store'}
      );
      if(!response.ok)return;

      const data=await response.json();
      const items=Array.isArray(data.items)
        ? data.items.map(v=>String(v||'').trim()).filter(Boolean).slice(0,20)
        : [];

      if(items.length){
        try{
          localStorage.setItem(
            STUDY_HISTORY_KEY,
            JSON.stringify(items)
          );
        }catch(_){}

        renderStudyHistory();
      }
    }catch(_){}
  }
  function renderStudyHistory(){
    const panel=document.getElementById(STUDY_HISTORY_PANEL_ID);if(!panel)return;
    const items=readStudyHistory();panel.innerHTML='<div class="lexia-study-history-title">Indicaciones recientes</div>';
    if(!items.length){panel.insertAdjacentHTML('beforeend','<div class="lexia-study-history-empty">Todavía no hay indicaciones anteriores.</div>');return;}
    items.forEach(value=>{
      const button=document.createElement('button');button.type='button';button.dataset.value=value;button.textContent=value;
      panel.appendChild(button);
    });
  }
  function closeStudyHistory(){document.getElementById(STUDY_HISTORY_PANEL_ID)?.classList.remove('open');}
  function openStudyHistory(){renderStudyHistory();document.getElementById(STUDY_HISTORY_PANEL_ID)?.classList.add('open');}
  function ensureStudyHistory(){
    const textarea=document.getElementById('studyInstruction');if(!textarea)return;
    if(textarea.dataset.lexiaStudyHistory==='1')return;
    textarea.dataset.lexiaStudyHistory='1';
    const parent=textarea.parentElement;if(!parent)return;
    const wrap=document.createElement('div');wrap.className='lexia-study-indications-wrap';
    parent.insertBefore(wrap,textarea);wrap.appendChild(textarea);
    const panel=document.createElement('div');panel.id=STUDY_HISTORY_PANEL_ID;panel.setAttribute('role','listbox');wrap.appendChild(panel);
    textarea.setAttribute('autocomplete','off');
    textarea.addEventListener('click',event=>{event.stopPropagation();openStudyHistory();});
    textarea.addEventListener('focus',()=>openStudyHistory());
    textarea.addEventListener('input',()=>closeStudyHistory());
    panel.addEventListener('mousedown',event=>event.preventDefault());
    panel.addEventListener('click',event=>{
      const button=event.target.closest('button[data-value]');if(!button)return;
      event.preventDefault();event.stopPropagation();textarea.value=button.dataset.value||'';textarea.dispatchEvent(new Event('input',{bubbles:true}));closeStudyHistory();try{textarea.focus({preventScroll:true});}catch(_){textarea.focus();}
    });
  }

  window.addEventListener('click',async event=>{
    const button=event.target.closest?.('['+INVESTIGATE_ATTR+']');
    if(button){
      event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
      const card=button.closest('.result-card'),name=(card?.querySelector('.result-title')?.textContent||'Documento').trim(),originalLabel=button.textContent;
      button.disabled=true;button.textContent='Cargando…';
      try{
        const requested=decodePath(button.dataset.path),resolver=window.lexiaSearch320bResolve;
        const resolved=typeof resolver==='function'&&!button.hasAttribute('data-lexia-navigator-investigate')?await resolver(card):requested;
        if(!resolved)throw new Error('El resultado no conserva una ruta utilizable.');loadStudyFile(resolved,name);
      }catch(error){alert('No se pudo cargar el archivo en Investigación:\n\n'+(error.message||error));}
      finally{button.disabled=false;button.textContent=originalLabel||'Investigar';}
      return;
    }
    if(event.target.closest?.('#startStudy')){
      saveStudyHistory(document.getElementById('studyInstruction')?.value||'');closeStudyHistory();return;
    }
    if(!event.target.closest?.('#studyInstruction')&&!event.target.closest?.('#'+STUDY_HISTORY_PANEL_ID))closeStudyHistory();
  },true);

  function ensureStudyTypes(){
    const select=document.getElementById('studyType');if(!select)return;
    const existing=new Set([...select.options].map(option=>option.value.trim().toLocaleLowerCase('es')));
    ['Libro','Doctrina','Legislación'].forEach(label=>{
      if(existing.has(label.toLocaleLowerCase('es')))return;
      const option=document.createElement('option');option.value=label;option.textContent=label;select.appendChild(option);
    });
  }

  function syncNavigatorSurface(){
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card').forEach(card=>{
      const actions=card.querySelector('.result-actions');if(!actions||actions.querySelector('[data-lexia-navigator-investigate]'))return;
      const encoded=card.dataset.navPath||actions.querySelector('[data-path]')?.dataset.path||'';if(!encoded)return;
      const button=document.createElement('button');button.type='button';button.setAttribute('role','menuitem');button.setAttribute(INVESTIGATE_ATTR,'1');button.setAttribute('data-lexia-navigator-investigate','1');button.className='search-investigate-file lexia-nav-investigate-file';button.dataset.path=encoded;button.textContent='Investigar';button.title='Cargar este archivo en Investigación · Estudiar un archivo';
      const remove=actions.querySelector('.search-delete-file');if(remove)actions.insertBefore(button,remove);else actions.appendChild(button);
    });
  }

  function syncAllSurfaces(){
    syncSearchSurface();syncNavigatorSurface();ensureStudyTypes();ensureStudyLayout();ensureStudyHistory();
  }

  function initialize(){
    ensureButtonColors();ensureStudyLayout();setupRecentHistoryTouchFix();installHtmlViewerFix();syncAllSurfaces();loadPersistentStudyHistory();
    const page=document.getElementById(SEARCH_PAGE_ID);
    if(page)new MutationObserver(syncAllSurfaces).observe(page,{childList:true,subtree:true});
    const context=document.getElementById('contextpage');
    if(context)new MutationObserver(()=>{ensureStudyTypes();ensureStudyLayout();ensureStudyHistory();}).observe(context,{childList:true,subtree:true});
    document.getElementById('studyPath')?.addEventListener('change',event=>applyStudyDefaultsFromPath(event.target.value));
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();

/* >>> LEXIA STUDY INSTRUCTION VALIDATION UI 1.0 */
(function(){
  'use strict';

  function el(id){
    return document.getElementById(id);
  }

  function runStudy(button){
    button.dataset.lexiaValidationBypass='1';
    button.click();
  }

  function showWarning(button, validation){
    const status=el('studyStatus');
    const field=el('studyInstruction');

    if(!status){
      runStudy(button);
      return;
    }

    status.hidden=false;
    status.innerHTML='';

    const box=document.createElement('div');
    box.style.cssText=[
      'border:1px solid #f0b429',
      'background:#fff8e6',
      'border-radius:10px',
      'padding:12px 14px',
      'color:#4a3500'
    ].join(';');

    const title=document.createElement('div');
    title.textContent=
      'La indicación no parece estar respaldada por el documento.';
    title.style.fontWeight='700';

    const detail=document.createElement('div');
    detail.style.marginTop='6px';

    const missing=Array.isArray(validation.missing_terms)
      ? validation.missing_terms
      : [];

    detail.textContent=missing.length
      ? 'No se localizaron con suficiente evidencia: '
        + missing.join(', ') + '.'
      : 'No se encontró evidencia textual suficiente.';

    const note=document.createElement('div');
    note.style.marginTop='6px';
    note.textContent=
      'Podés continuar igualmente si querés estudiar una relación '
      +'indirecta o comprobar expresamente si el documento trata ese tema.';

    const actions=document.createElement('div');
    actions.style.cssText=
      'display:flex;gap:8px;margin-top:10px;flex-wrap:wrap';

    const continueButton=document.createElement('button');
    continueButton.type='button';
    continueButton.textContent='Continuar igualmente';
    continueButton.style.cssText=[
      'background:#5146f6',
      'border:1px solid #5146f6',
      'color:#fff',
      'border-radius:8px',
      'padding:8px 13px',
      'font-weight:700'
    ].join(';');

    const modifyButton=document.createElement('button');
    modifyButton.type='button';
    modifyButton.textContent='Modificar indicación';
    modifyButton.className='secondary';
    modifyButton.style.cssText=
      'border-radius:8px;padding:8px 13px';

    continueButton.addEventListener('click',function(){
      status.innerHTML='';
      status.hidden=true;
      runStudy(button);
    });

    modifyButton.addEventListener('click',function(){
      field?.focus();
      field?.select();
    });

    actions.append(
      continueButton,
      modifyButton
    );

    box.append(
      title,
      detail,
      note,
      actions
    );

    status.appendChild(box);
  }

  document.addEventListener(
    'click',
    async function(event){
      const button=event.target?.closest?.('#startStudy');
      if(!button)return;

      if(button.dataset.lexiaValidationBypass==='1'){
        delete button.dataset.lexiaValidationBypass;
        return;
      }

      const path=String(el('studyPath')?.value||'').trim();
      const instruction=String(
        el('studyInstruction')?.value||''
      ).trim();

      // Sin indicación específica no hace falta validar.
      if(!path || !instruction)return;

      event.preventDefault();
      event.stopImmediatePropagation();

      const status=el('studyStatus');

      if(status){
        status.hidden=false;
        status.textContent='Validando la indicación contra el documento…';
      }

      try{
        const response=await fetch(
          '/api/study-instruction-validate',
          {
            method:'POST',
            headers:{
              'Content-Type':'application/json'
            },
            body:JSON.stringify({
              path:path,
              instruction:instruction
            }),
            cache:'no-store'
          }
        );

        const validation=await response.json();

        if(
          !response.ok
          || validation.ok===false
        ){
          // Un fallo del validador nunca debe impedir estudiar.
          if(status){
            status.hidden=true;
            status.textContent='';
          }
          runStudy(button);
          return;
        }

        if(validation.supported){
          if(status){
            status.hidden=true;
            status.textContent='';
          }
          runStudy(button);
          return;
        }

        showWarning(button,validation);

      }catch(_){
        // Fail-open: si falla exclusivamente la validación,
        // conservar el funcionamiento normal de Estudiar archivo.
        if(status){
          status.hidden=true;
          status.textContent='';
        }
        runStudy(button);
      }
    },
    true
  );
})();
/* <<< LEXIA STUDY INSTRUCTION VALIDATION UI 1.0 */

