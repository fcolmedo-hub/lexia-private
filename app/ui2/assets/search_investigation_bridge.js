/* LexIA UI2 — bridge from Search/Navigator to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';
  const CONTENT_OPEN_ATTR='data-lexia-content-open';
  const STYLE_ID='lexiaSearchInvestigationButtonColors';
  const RECENT_TOUCH_STYLE_ID='lexiaSearchRecentTouchFix';
  const INVESTIGATION_STYLE_ID='lexiaInvestigationResponsiveFix';

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
        background:#149d55!important;border-color:#149d55!important;color:#fff!important;
      }
      #${SEARCH_PAGE_ID} .result-actions .search-open-file[${CONTENT_OPEN_ATTR}="1"]:hover{
        background:#0f8044!important;border-color:#0f8044!important;
      }
      #${SEARCH_PAGE_ID} .result-actions [${INVESTIGATE_ATTR}="1"]{
        background:#5146f6!important;border-color:#5146f6!important;color:#fff!important;
      }
      #${SEARCH_PAGE_ID} .result-actions [${INVESTIGATE_ATTR}="1"]:hover{
        background:#4338e8!important;border-color:#4338e8!important;
      }
      #lexiaNavigatorFiles .result-actions [${INVESTIGATE_ATTR}="1"]{
        color:#245eea!important;background:transparent!important;border-color:transparent!important;font-weight:700!important;
      }
      #lexiaNavigatorFiles .result-actions [${INVESTIGATE_ATTR}="1"]:hover{
        color:#1747bd!important;background:#eef4ff!important;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureInvestigationResponsiveStyles(){
    if(document.getElementById(INVESTIGATION_STYLE_ID))return;
    const style=document.createElement('style');
    style.id=INVESTIGATION_STYLE_ID;
    style.textContent=`
      #contextpage,#contextpage .main,#contextpage .context-layout,#contextpage .context-grid,
      #contextpage .investigation-panel,#contextpage .context-form,#contextpage .context-side,
      #contextpage .output-card,#contextpage .context-layout>.head,#contextpage .context-layout>.head>div{
        min-width:0!important;max-width:100%;
      }
      #contextpage .context-layout>.head{gap:10px;align-items:flex-start;}
      #contextpage .context-layout>.head p,#contextpage .study-help,#contextpage .context-actions .hint{
        overflow-wrap:anywhere;word-break:normal;min-width:0;
      }
      #studyPanel .context-options>div{min-width:0;}
      #studyPanel .study-path,#studyPanel textarea,#studyPanel select{width:100%;min-width:0;max-width:100%;}
      #contextpage .context-actions{min-width:0;gap:8px;flex-wrap:wrap;}
      #contextpage .output-actions{min-width:0;flex-wrap:wrap;justify-content:flex-end;}
      #contextpage .output-summary,#contextpage .study-output{max-width:100%;overflow-wrap:anywhere;white-space:pre-wrap;}
      @media(max-width:980px){
        #contextpage .context-layout>.head{display:flex!important;flex-wrap:wrap!important;}
        #contextpage .context-layout>.head>div:first-child{flex:1 1 420px;}
        #contextpage .context-layout>.head .head-actions{flex:0 0 auto;}
        #contextpage .output-head{gap:8px;flex-wrap:wrap;}
      }
      @media(max-width:760px){
        #studyPanel .context-options{grid-template-columns:1fr!important;}
        #contextpage .context-layout>.head .head-actions{width:100%;}
        #contextpage .context-layout>.head .head-actions button{max-width:100%;}
        #contextpage .context-actions .hint{flex:1 1 100%;}
      }
    `;
    document.head.appendChild(style);
  }

  function setupInvestigationFields(){
    const type=document.getElementById('studyType');
    if(type){
      [...type.options].forEach(option=>{
        if(String(option.textContent||'').trim().toLowerCase()==='dictamen')option.remove();
      });
      const labels=[...type.options].map(option=>String(option.textContent||'').trim().toLowerCase());
      const other=[...type.options].find(option=>String(option.textContent||'').trim()==='Otro documento jurídico');
      ['Libro','Doctrina'].forEach(label=>{
        if(labels.includes(label.toLowerCase()))return;
        const option=document.createElement('option');
        option.textContent=label;
        option.value=label;
        if(other)type.insertBefore(option,other); else type.appendChild(option);
      });
    }

    const instruction=document.getElementById('studyInstruction');
    if(instruction){
      const label=document.querySelector('label[for="studyInstruction"]');
      if(label)label.textContent='Indicaciones';
      instruction.placeholder='Ej.: divorcio, responsabilidad parental, alimentos…';
    }

    const help=document.querySelector('#studyPanel .study-help');
    if(help)help.textContent='Seleccioná un archivo indexado. En Libro o Doctrina, LexIA buscará dentro de todo el documento los pasajes relacionados con las Indicaciones y los incorporará como fuentes al paquete de investigación.';
  }

  function setupRecentHistoryTouchFix(){
    if(!document.getElementById(RECENT_TOUCH_STYLE_ID)){
      const style=document.createElement('style');
      style.id=RECENT_TOUCH_STYLE_ID;
      style.textContent=`
        @media (max-width:700px){
          #${SEARCH_PAGE_ID} #searchRecentHistory,#${SEARCH_PAGE_ID} #searchRecentHistory *{
            -webkit-user-select:none!important;user-select:none!important;-webkit-touch-callout:none!important;
          }
          #${SEARCH_PAGE_ID} #searchRecentHistory{
            overflow-x:hidden!important;overflow-y:auto!important;-webkit-overflow-scrolling:auto!important;
            overscroll-behavior:contain!important;touch-action:none!important;
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
    window.addEventListener('pointerout',event=>{if(touchActive&&recentPanel(event.target))event.stopPropagation();},true);
    window.addEventListener('selectstart',event=>{if(isMobileTouch()&&recentPanel(event.target)){event.preventDefault();event.stopPropagation();}},true);
    window.addEventListener('click',event=>{
      if(!isMobileTouch())return;const item=event.target.closest?.('#searchRecentHistory button[data-query]');if(!item)return;
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

  function syncNavigatorCard(card){
    const trigger=card?.querySelector('.lexia-nav-file-menu-trigger');
    if(!trigger)return;
    const menuId=trigger.getAttribute('aria-controls')||trigger.dataset.navMenu||'';
    const menu=(menuId&&document.getElementById(menuId))||trigger.nextElementSibling;
    if(!menu||menu.querySelector('['+INVESTIGATE_ATTR+']'))return;
    const detail=menu.querySelector('.search-file-info');
    const del=menu.querySelector('.search-delete-file');
    const path=decodePath(detail?.dataset.path||del?.dataset.path||card.dataset.navPath||'');
    if(!path)return;
    const button=document.createElement('button');
    button.type='button';button.setAttribute('role','menuitem');button.setAttribute(INVESTIGATE_ATTR,'1');
    button.className='lexia-nav-investigate-file';button.dataset.path=encodeURIComponent(path);button.textContent='Investigar';
    button.title='Cargar este archivo en Investigación';
    if(del)menu.insertBefore(button,del);else menu.appendChild(button);
  }

  function syncSearchSurface(){
    removeSearchInsight();
    document.querySelectorAll('#'+SEARCH_PAGE_ID+' #realSearchResults .result-card').forEach(syncResultCard);
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card').forEach(syncNavigatorCard);
    setupInvestigationFields();
  }

  function navigateToInvestigation(){
    const navigate=window.lexiaUI2NavigateGlobal||window.lexiaUI2NavigateSafe||window.lexiaUI2Navigate||window.lexiaUI2Show;
    if(typeof navigate==='function'){navigate('contextpage');return;}
    ['home','library','searchpage','contextpage','activitypage','systempage','maintenance'].forEach(id=>{const page=document.getElementById(id);if(page)page.style.display='none';});
    const context=document.getElementById('contextpage');if(context)context.style.display='grid';
  }

  function loadStudyFile(path,name,origin='Buscar'){
    const input=document.getElementById('studyPath');
    if(!input)throw new Error('No se encontró el campo “Archivo indexado” de Investigación.');
    input.value=path;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
    navigateToInvestigation();setupInvestigationFields();
    const studyTab=document.getElementById('studyTab');if(studyTab)studyTab.click();
    const researchPanel=document.getElementById('researchPanel'),studyPanel=document.getElementById('studyPanel');
    if(researchPanel)researchPanel.hidden=true;if(studyPanel)studyPanel.hidden=false;
    const status=document.getElementById('studyStatus');
    if(status){status.hidden=false;status.textContent='Archivo cargado desde '+origin+': '+(name||path)+'. Elegí el tipo, completá Indicaciones y presioná “Estudiar”.';}
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
      if(name)name.textContent=basename(path);if(pathLabel)pathLabel.textContent=String(path||'');if(open)open.hidden=false;pane.classList.remove('lexia-qv-mobile-mode');pane.innerHTML='';
      const frame=document.createElement('iframe');frame.className='lexia-qv-html-frame';frame.title='Vista HTML · '+basename(path);frame.setAttribute('sandbox','');frame.setAttribute('referrerpolicy','no-referrer');frame.style.cssText='display:block;width:100%;height:100%;min-height:68vh;border:0;background:#fff;';frame.src='/api/file-preview?path='+encodeURIComponent(String(path||''));pane.appendChild(frame);
      backdrop.classList.add('open');backdrop.setAttribute('aria-hidden','false');return true;
    };
  }

  window.addEventListener('click',async event=>{
    const button=event.target.closest?.('['+INVESTIGATE_ATTR+']');if(!button)return;
    event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
    const card=button.closest('.result-card'),navCard=button.closest('.lexia-nav-file-card');
    const name=(card?.querySelector('.result-title')?.textContent||navCard?.querySelector('.lexia-nav-file-name,.lexia-nav-file-title')?.textContent||'Documento').trim();
    const originalLabel=button.textContent;button.disabled=true;button.textContent='Cargando…';
    try{
      const requested=decodePath(button.dataset.path);
      const resolver=window.lexiaSearch320bResolve;
      const resolved=(card&&typeof resolver==='function')?await resolver(card):requested;
      if(!resolved)throw new Error('El archivo no conserva una ruta utilizable.');
      loadStudyFile(resolved,name,navCard?'Biblioteca':'Buscar');
    }catch(error){alert('No se pudo cargar el archivo en Investigación:\n\n'+(error.message||error));}
    finally{button.disabled=false;button.textContent=originalLabel||'Investigar';}
  },true);

  function initialize(){
    ensureButtonColors();ensureInvestigationResponsiveStyles();setupRecentHistoryTouchFix();installHtmlViewerFix();syncSearchSurface();
    const roots=[document.getElementById(SEARCH_PAGE_ID),document.getElementById('library'),document.getElementById('contextpage')].filter(Boolean);
    roots.forEach(root=>new MutationObserver(syncSearchSurface).observe(root,{childList:true,subtree:true}));
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
