/* LexIA UI2 — bridge from Search results to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';
  const CONTENT_OPEN_ATTR='data-lexia-content-open';
  const STYLE_ID='lexiaSearchInvestigationButtonColors';
  const RECENT_TOUCH_STYLE_ID='lexiaSearchRecentTouchFix';
  const HOME_HISTORY_STYLE_ID='lexiaHomeRecentHistoryStyles';

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

  function setupHomeRecentHistory(){
    const input=document.getElementById('homeQuickSearchInput');
    const form=input?.closest?.('.hr-search');
    if(!input||!form||window.__lexiaHomeRecentHistoryInstalled)return;
    window.__lexiaHomeRecentHistoryInstalled=true;

    if(!document.getElementById(HOME_HISTORY_STYLE_ID)){
      const style=document.createElement('style');
      style.id=HOME_HISTORY_STYLE_ID;
      style.textContent=`
        .hr-search{position:relative!important;overflow:visible!important}
        #homeRecentHistory{
          position:absolute;
          left:42px;
          right:142px;
          top:calc(100% + 7px);
          z-index:500;
          display:none;
          max-height:280px;
          overflow-x:hidden;
          overflow-y:auto;
          -webkit-overflow-scrolling:touch;
          overscroll-behavior:contain;
          touch-action:pan-y;
          background:#fff;
          border:1px solid #e4e7f0;
          border-radius:12px;
          box-shadow:0 16px 38px rgba(17,24,57,.16);
          padding:6px;
        }
        #homeRecentHistory.open{display:block}
        #homeRecentHistory .home-history-head{
          padding:8px 10px 6px;
          color:#66708f;
          font-size:12px;
          font-weight:700;
          text-transform:uppercase;
          letter-spacing:.03em;
        }
        #homeRecentHistory button[data-query]{
          width:100%;
          display:block;
          border:0;
          border-radius:8px;
          background:transparent;
          padding:10px 11px;
          text-align:left;
          color:#0f1734;
          font-size:14px;
          line-height:1.25;
          white-space:normal;
          overflow-wrap:anywhere;
          cursor:pointer;
          -webkit-user-select:none;
          user-select:none;
          touch-action:pan-y;
        }
        #homeRecentHistory button[data-query]:hover{background:#f4f3ff}
        #homeRecentHistory .home-history-empty{
          padding:10px 11px 12px;
          color:#66708f;
          font-size:13px;
        }
        @media(max-width:700px){
          #homeRecentHistory{
            left:8px;
            right:8px;
            max-height:min(45vh,320px);
          }
        }
      `;
      document.head.appendChild(style);
    }

    const panel=document.createElement('div');
    panel.id='homeRecentHistory';
    panel.setAttribute('role','listbox');
    panel.setAttribute('aria-label','Búsquedas recientes');
    form.appendChild(panel);

    let requestSerial=0;
    const close=()=>panel.classList.remove('open');
    const refresh=async()=>{
      const serial=++requestSerial;
      panel.innerHTML='<div class="home-history-head">Búsquedas recientes</div>';
      try{
        const response=await fetch('/api/search-history?mode=professional',{cache:'no-store'});
        const data=await response.json();
        if(serial!==requestSerial)return;
        const items=Array.isArray(data?.items)?data.items:[];
        if(!items.length){
          panel.insertAdjacentHTML('beforeend','<div class="home-history-empty">Todavía no hay búsquedas recientes.</div>');
          return;
        }
        items.slice(0,30).forEach(item=>{
          const query=String(item?.query||'').trim();
          if(!query)return;
          const button=document.createElement('button');
          button.type='button';
          button.dataset.query=query;
          button.textContent=query;
          panel.appendChild(button);
        });
      }catch(_){
        if(serial===requestSerial){
          panel.insertAdjacentHTML('beforeend','<div class="home-history-empty">No se pudo cargar el historial.</div>');
        }
      }
    };

    const open=()=>{
      refresh();
      panel.classList.add('open');
    };

    input.addEventListener('click',event=>{
      event.stopPropagation();
      open();
    });

    panel.addEventListener('click',event=>{
      const button=event.target.closest?.('button[data-query]');
      if(!button)return;
      event.preventDefault();
      event.stopPropagation();
      input.value=String(button.dataset.query||'');
      input.dispatchEvent(new Event('input',{bubbles:true}));
      close();
      try{input.focus({preventScroll:true});}catch(_){input.focus();}
    });

    document.addEventListener('pointerdown',event=>{
      if(panel.contains(event.target)||event.target===input)return;
      close();
    },true);

    input.addEventListener('input',()=>close());
    input.addEventListener('keydown',event=>{
      if(event.key==='Escape')close();
    });
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

    const decodeHtml=async response=>{
      const buffer=await response.arrayBuffer();
      const bytes=new Uint8Array(buffer);
      let probe='';
      try{probe=new TextDecoder('windows-1252').decode(bytes.slice(0,Math.min(bytes.length,8192)));}
      catch(_){probe=new TextDecoder().decode(bytes.slice(0,Math.min(bytes.length,8192)));}
      const match=probe.match(/charset\s*=\s*["']?\s*([a-zA-Z0-9._-]+)/i);
      let charset=String(match?.[1]||'utf-8').toLowerCase();
      if(charset==='iso8859-1'||charset==='iso-8859-1'||charset==='latin1')charset='windows-1252';
      try{return new TextDecoder(charset).decode(bytes);}
      catch(_){return new TextDecoder('utf-8').decode(bytes);}
    };

    window.lexiaQuickViewerOpen=async function(path,page,snippet){
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
      pane.innerHTML='<div style="padding:24px;color:#66708f;font:14px system-ui,sans-serif">Preparando vista HTML…</div>';
      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden','false');

      try{
        const response=await fetch('/api/file-preview?path='+encodeURIComponent(String(path||''))+'&t='+Date.now(),{cache:'no-store'});
        if(!response.ok)throw new Error('HTTP '+response.status);
        let html=await decodeHtml(response);
        const safeStyle='<style id="lexia-html-preview-style">html,body{background:#fff;color:#111}body{margin:18px;font-family:Arial,Helvetica,sans-serif;line-height:1.42}img{max-width:100%;height:auto}table{max-width:100%;border-collapse:collapse}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>';
        if(/<head[\s>]/i.test(html))html=html.replace(/<head([^>]*)>/i,'<head$1>'+safeStyle);
        else html='<!doctype html><html><head><meta charset="utf-8">'+safeStyle+'</head><body>'+html+'</body></html>';

        const frame=document.createElement('iframe');
        frame.className='lexia-qv-html-frame';
        frame.title='Vista HTML · '+basename(path);
        frame.setAttribute('sandbox','');
        frame.setAttribute('referrerpolicy','no-referrer');
        frame.style.cssText='display:block;width:100%;height:100%;min-height:68vh;border:0;background:#fff;';
        frame.srcdoc=html;
        pane.innerHTML='';
        pane.appendChild(frame);
      }catch(error){
        pane.innerHTML='<div style="padding:24px;color:#9b1c1c;font:14px system-ui,sans-serif"><b>No se pudo renderizar el HTML.</b><br>'+String(error?.message||error).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+'</div>';
      }
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
    setupHomeRecentHistory();
    installHtmlViewerFix();
    syncSearchSurface();
    const page=document.getElementById(SEARCH_PAGE_ID);
    if(!page)return;
    new MutationObserver(syncSearchSurface).observe(page,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
