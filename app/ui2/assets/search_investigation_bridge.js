/* LexIA UI2 — bridge from Search results to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';
  const CONTENT_OPEN_ATTR='data-lexia-content-open';
  const STYLE_ID='lexiaSearchInvestigationButtonColors';
  const RECENT_TOUCH_STYLE_ID='lexiaSearchRecentTouchFix';

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
          #${SEARCH_PAGE_ID} #searchRecentHistory button[data-query]{
            touch-action:none!important;
          }
        }
      `;
      document.head.appendChild(style);
    }

    let touchActive=false;
    let moved=false;
    let startX=0;
    let startY=0;
    let startScrollTop=0;
    let activePanel=null;
    let suppressClickUntil=0;

    const isMobileTouch=()=>{
      try{return window.matchMedia('(max-width:700px)').matches || Number(navigator.maxTouchPoints||0)>0;}
      catch(_){return Number(navigator.maxTouchPoints||0)>0;}
    };
    const recentPanel=target=>target?.closest?.('#searchRecentHistory');

    window.addEventListener('touchstart',event=>{
      if(!isMobileTouch()||event.touches.length!==1)return;
      const panel=recentPanel(event.target);
      if(!panel)return;
      const touch=event.touches[0];
      touchActive=true;
      moved=false;
      startX=touch.clientX;
      startY=touch.clientY;
      startScrollTop=panel.scrollTop;
      activePanel=panel;
    },{capture:true,passive:false});

    window.addEventListener('touchmove',event=>{
      if(!touchActive||!activePanel||event.touches.length!==1)return;
      const touch=event.touches[0];
      const dx=touch.clientX-startX;
      const dy=touch.clientY-startY;
      if(Math.abs(dx)>4 || Math.abs(dy)>4)moved=true;
      if(!moved)return;

      event.preventDefault();
      event.stopPropagation();
      activePanel.scrollTop=startScrollTop-dy;
      try{window.getSelection()?.removeAllRanges();}catch(_){}
    },{capture:true,passive:false});

    window.addEventListener('touchend',event=>{
      if(!touchActive)return;
      if(moved){
        suppressClickUntil=performance.now()+700;
        event.preventDefault();
        event.stopPropagation();
      }
      touchActive=false;
      activePanel=null;
    },{capture:true,passive:false});

    window.addEventListener('touchcancel',()=>{
      if(moved)suppressClickUntil=performance.now()+700;
      touchActive=false;
      activePanel=null;
    },true);

    window.addEventListener('pointerout',event=>{
      if(!touchActive||!recentPanel(event.target))return;
      event.stopPropagation();
    },true);

    window.addEventListener('selectstart',event=>{
      if(!isMobileTouch()||!recentPanel(event.target))return;
      event.preventDefault();
      event.stopPropagation();
    },true);

    window.addEventListener('click',event=>{
      if(!isMobileTouch())return;
      const item=event.target.closest?.('#searchRecentHistory button[data-query]');
      if(!item)return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      if(moved || performance.now()<suppressClickUntil){
        moved=false;
        return;
      }

      const input=document.getElementById('legalQuery');
      if(input){
        input.value=item.dataset.query||'';
        input.dispatchEvent(new Event('input',{bubbles:true}));
        try{input.focus({preventScroll:true});}catch(_){input.focus();}
      }
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

    const openButton=[...actions.querySelectorAll('.search-open-file')]
      .find(button=>!button.hasAttribute(INVESTIGATE_ATTR));
    if(!openButton)return;

    const contentResult=Boolean(actions.querySelector('.score'));
    if(contentResult){
      openButton.setAttribute(CONTENT_OPEN_ATTR,'1');
      openButton.insertAdjacentElement('afterend',investigateButton(openButton));
      return;
    }

    openButton.setAttribute(INVESTIGATE_ATTR,'1');
    openButton.classList.add('search-investigate-file');
    openButton.textContent='Investigar';
    openButton.title='Cargar este archivo en Investigación · Estudiar un archivo';
  }

  function syncSearchSurface(){
    removeSearchInsight();
    document.querySelectorAll('#'+SEARCH_PAGE_ID+' #realSearchResults .result-card')
      .forEach(syncResultCard);
  }

  function navigateToInvestigation(){
    const navigate=
      window.lexiaUI2NavigateGlobal||
      window.lexiaUI2NavigateSafe||
      window.lexiaUI2Navigate||
      window.lexiaUI2Show;
    if(typeof navigate==='function'){
      navigate('contextpage');
      return;
    }

    ['home','library','searchpage','contextpage','activitypage','systempage','maintenance']
      .forEach(id=>{const page=document.getElementById(id);if(page)page.style.display='none';});
    const context=document.getElementById('contextpage');
    if(context)context.style.display='grid';
  }

  function loadStudyFile(path,name){
    const input=document.getElementById('studyPath');
    if(!input)throw new Error('No se encontró el campo “Archivo indexado” de Investigación.');

    input.value=path;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    navigateToInvestigation();

    const studyTab=document.getElementById('studyTab');
    if(studyTab)studyTab.click();
    const researchPanel=document.getElementById('researchPanel');
    const studyPanel=document.getElementById('studyPanel');
    if(researchPanel)researchPanel.hidden=true;
    if(studyPanel)studyPanel.hidden=false;

    const status=document.getElementById('studyStatus');
    if(status){
      status.hidden=false;
      status.textContent='Archivo cargado desde Buscar: '+(name||path)+'. Configurá el objetivo y presioná “Estudiar”.';
    }
    input.focus({preventScroll:true});
    studyPanel?.scrollIntoView({block:'start'});
  }

  window.addEventListener('click',async event=>{
    const button=event.target.closest?.('['+INVESTIGATE_ATTR+']');
    if(!button)return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const card=button.closest('.result-card');
    const name=(card?.querySelector('.result-title')?.textContent||'Documento').trim();
    const originalLabel=button.textContent;
    button.disabled=true;
    button.textContent='Cargando…';

    try{
      const requested=decodePath(button.dataset.path);
      const resolver=window.lexiaSearch320bResolve;
      const resolved=typeof resolver==='function' ? await resolver(card) : requested;
      if(!resolved)throw new Error('El resultado no conserva una ruta utilizable.');
      loadStudyFile(resolved,name);
    }catch(error){
      alert('No se pudo cargar el archivo en Investigación:\n\n'+(error.message||error));
    }finally{
      button.disabled=false;
      button.textContent=originalLabel||'Investigar';
    }
  },true);

  function initialize(){
    ensureButtonColors();
    setupRecentHistoryTouchFix();
    syncSearchSurface();
    const page=document.getElementById(SEARCH_PAGE_ID);
    if(!page)return;
    new MutationObserver(syncSearchSurface).observe(page,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
