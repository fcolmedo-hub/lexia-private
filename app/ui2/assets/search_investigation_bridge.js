/* LexIA UI2 — bridge from Search results to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';
  const CONTENT_OPEN_ATTR='data-lexia-content-open';
  const STYLE_ID='lexiaSearchInvestigationButtonColors';
  const RECENT_TOUCH_STYLE_ID='lexiaSearchRecentTouchFix';
  const STUDY_LAYOUT_STYLE_ID='lexiaStudyLayoutFix';

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
    if(document.getElementById(STUDY_LAYOUT_STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STUDY_LAYOUT_STYLE_ID;
    style.textContent=`
      #contextpage #studyPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin-bottom:20px!important;
        box-sizing:border-box!important;
      }
      #contextpage #studyPanel[hidden]{
        display:none!important;
      }
      #contextpage #studyPanel .context-actions{
        position:static!important;
        inset:auto!important;
        transform:none!important;
        margin-top:14px!important;
        padding-top:12px!important;
      }
      #contextpage .output-card{
        position:relative!important;
        inset:auto!important;
        transform:none!important;
        clear:both!important;
        margin-top:0!important;
        z-index:0!important;
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
      status.textContent='Archivo cargado: '+(name||path)+'. Indicá qué querés investigar, elegí el tipo de documento y presioná “Estudiar”.';
    }
    try{input.focus({preventScroll:true});}catch(_){input.focus();}
    studyPanel?.scrollIntoView({block:'start'});
  }

  function installHtmlViewerFix(){
    if(window.__lexiaHtmlViewerFixInstalled)return;
    const original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function'){
      window.setTimeout(installHtmlViewerFix,25);
      return;
    }
    window.__lexiaHtmlViewerFixInstalled=true;

    const extension=path=>{
      const clean=String(path||'').split('?')[0].split('#')[0];
      const name=clean.split(/[\\/]/).pop()||'';
      const dot=name.lastIndexOf('.');
      return dot>=0?name.slice(dot).toLowerCase():'';
    };
    const basename=path=>String(path||'').split(/[\\/]/).pop()||'Documento HTML';

    window.lexiaQuickViewerOpen=function(path,page,snippet){
      const ext=extension(path);
      if(ext!=='.htm'&&ext!=='.html')return original(path,page,snippet);

      const backdrop=document.getElementById('lexiaQuickViewer');
      const pane=document.getElementById('lexiaQvBody');
      const name=document.getElementById('lexiaQvName');
      const pathLabel=document.getElementById('lexiaQvPath');
      const open=document.getElementById('lexiaQvOpen');
      if(!backdrop||!pane)return original(path,page,snippet);

      if(name)name.textContent=basename(path);
      if(pathLabel)pathLabel.textContent=String(path||'');
      if(open)open.hidden=false;
      pane.classList.remove('lexia-qv-mobile-mode');
      pane.innerHTML='';

      const frame=document.createElement('iframe');
      frame.className='lexia-qv-html-frame';
      frame.title='Vista HTML · '+basename(path);
      frame.setAttribute('sandbox','');
      frame.setAttribute('referrerpolicy','no-referrer');
      frame.style.cssText='display:block;width:100%;height:100%;min-height:68vh;border:0;background:#fff;';
      frame.src='/api/file-preview?path='+encodeURIComponent(String(path||''));
      pane.appendChild(frame);

      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden','false');
      return true;
    };
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
      const resolved=typeof resolver==='function' && !button.hasAttribute('data-lexia-navigator-investigate') ? await resolver(card) : requested;
      if(!resolved)throw new Error('El resultado no conserva una ruta utilizable.');
      loadStudyFile(resolved,name);
    }catch(error){
      alert('No se pudo cargar el archivo en Investigación:\n\n'+(error.message||error));
    }finally{
      button.disabled=false;
      button.textContent=originalLabel||'Investigar';
    }
  },true);

  function ensureStudyTypes(){
    const select=document.getElementById('studyType');
    if(!select)return;
    const existing=new Set([...select.options].map(option=>option.value.trim().toLocaleLowerCase('es')));
    ['Libro','Doctrina','Legislación'].forEach(label=>{
      if(existing.has(label.toLocaleLowerCase('es')))return;
      const option=document.createElement('option');
      option.value=label;
      option.textContent=label;
      select.appendChild(option);
    });
  }

  function syncNavigatorSurface(){
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card').forEach(card=>{
      const actions=card.querySelector('.result-actions');
      if(!actions||actions.querySelector('[data-lexia-navigator-investigate]'))return;
      const encoded=card.dataset.navPath||actions.querySelector('[data-path]')?.dataset.path||'';
      if(!encoded)return;
      const button=document.createElement('button');
      button.type='button';
      button.setAttribute('role','menuitem');
      button.setAttribute(INVESTIGATE_ATTR,'1');
      button.setAttribute('data-lexia-navigator-investigate','1');
      button.className='search-investigate-file lexia-nav-investigate-file';
      button.dataset.path=encoded;
      button.textContent='Investigar';
      button.title='Cargar este archivo en Investigación · Estudiar un archivo';
      const remove=actions.querySelector('.search-delete-file');
      if(remove)actions.insertBefore(button,remove);
      else actions.appendChild(button);
    });
  }

  function syncAllSurfaces(){
    syncSearchSurface();
    syncNavigatorSurface();
    ensureStudyTypes();
    ensureStudyLayout();
  }

  function initialize(){
    ensureButtonColors();
    ensureStudyLayout();
    setupRecentHistoryTouchFix();
    installHtmlViewerFix();
    syncAllSurfaces();
    const page=document.getElementById(SEARCH_PAGE_ID);
    if(!page)return;
    new MutationObserver(syncAllSurfaces).observe(page,{childList:true,subtree:true});
    const context=document.getElementById('contextpage');
    if(context)new MutationObserver(()=>{ensureStudyTypes();ensureStudyLayout();}).observe(context,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
