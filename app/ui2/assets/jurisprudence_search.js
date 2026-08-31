/* LexIA UI2 — filtros jurisprudenciales estructurados */
(function(){
  'use strict';
  const PANEL_ID='lexiaJurisprudenceFilters';
  const ids={
    court:'jurisCourt',chamber:'jurisChamber',scope:'jurisScope',province:'jurisProvince',
    date_from:'jurisDateFrom',date_to:'jurisDateTo',case_number:'jurisCaseNumber',
    party:'jurisParty',law:'jurisLaw'
  };
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const isJuris=value=>String(value||'').trim().toLocaleLowerCase('es-AR')==='jurisprudencia';
  let mobileViewerPath='';
  let mobileViewerObjectUrl='';

  function ensureResponsiveShellStyles(){
    const id='lexiaResponsiveShellStyles';
    if(document.getElementById(id))return;
    const link=document.createElement('link');
    link.id=id;
    link.rel='stylesheet';
    link.href='assets/responsive_shell.css?v=ui2-3.4.6-mobile-viewer';
    document.head.appendChild(link);
  }

  function ensureSearchInvestigationBridge(){
    const id='lexiaSearchInvestigationBridge';
    if(document.getElementById(id))return;
    const script=document.createElement('script');
    script.id=id;
    script.src='assets/search_investigation_bridge.js?v=ui2-3.4.3';
    script.defer=true;
    document.head.appendChild(script);
  }

  function isRemoteClient(){
    const host=String(window.location.hostname||'').toLowerCase();
    return host!=='' && host!=='localhost' && host!=='127.0.0.1' && host!=='::1';
  }

  function isMobileClient(){
    return window.matchMedia?.('(max-width: 900px)').matches || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent||'');
  }

  function enableMobileTextAssistance(){
    if(!isMobileClient())return;

    const viewport=document.querySelector('meta[name="viewport"]');
    if(viewport){
      viewport.id='lexiaViewport';
      const content=viewport.getAttribute('content')||'width=device-width,initial-scale=1';
      if(!/viewport-fit\s*=/.test(content))viewport.setAttribute('content',content+',viewport-fit=cover');
    }

    const resetViewportZoom=()=>{
      const viewport=document.querySelector('meta[name="viewport"]');
      if(!viewport)return;
      const stable=viewport.dataset.lexiaStableContent||viewport.getAttribute('content')||'width=device-width,initial-scale=1';
      viewport.dataset.lexiaStableContent=stable;
      const scale=Number(window.visualViewport?.scale||1);
      if(scale<=1.01)return;
      viewport.setAttribute('content',stable.replace(/\s*,?\s*(?:minimum|maximum)-scale\s*=\s*[^,]+/gi,'')+',minimum-scale=1,maximum-scale=1');
      window.setTimeout(()=>{
        viewport.setAttribute('content',stable);
        window.scrollTo(Math.max(0,window.scrollX),Math.max(0,window.scrollY));
      },120);
    };

    const shouldAssist=el=>{
      if(!el||!(el instanceof HTMLElement))return false;
      if(el.tagName==='TEXTAREA')return true;
      if(el.tagName!=='INPUT')return false;
      const type=String(el.getAttribute('type')||'text').toLowerCase();
      if(!['text','search','email','url','tel'].includes(type))return false;
      const id=String(el.id||'').toLowerCase();
      const name=String(el.getAttribute('name')||'').toLowerCase();
      if(id.includes('path')||name.includes('path'))return false;
      return true;
    };

    const assist=el=>{
      if(!shouldAssist(el))return;
      if(el.getAttribute('autocomplete')!=='on')el.setAttribute('autocomplete','on');
      if(el.getAttribute('autocorrect')!=='on')el.setAttribute('autocorrect','on');
      if(el.getAttribute('autocapitalize')!=='sentences')el.setAttribute('autocapitalize','sentences');
      if(el.getAttribute('spellcheck')!=='true')el.setAttribute('spellcheck','true');
      if((el.id==='legalQuery'||el.id==='homeQuickSearchInput') && el.getAttribute('enterkeyhint')!=='search'){
        el.setAttribute('enterkeyhint','search');
      }
      if(el.id==='legalQuery'){
        el.type='search';
        el.setAttribute('inputmode','search');
        el.style.setProperty('font-size','16px','important');
      }
    };

    const applyAll=()=>document.querySelectorAll('input,textarea').forEach(assist);
    applyAll();

    if(window.__lexiaMobileTextAssistObserver)return;
    window.__lexiaMobileTextAssistObserver=new MutationObserver(records=>{
      for(const record of records){
        if(record.type==='attributes')assist(record.target);
        for(const node of record.addedNodes||[]){
          if(!(node instanceof HTMLElement))continue;
          assist(node);
          node.querySelectorAll?.('input,textarea').forEach(assist);
        }
      }
    });
    window.__lexiaMobileTextAssistObserver.observe(document.documentElement,{
      subtree:true,
      childList:true,
      attributes:true,
      attributeFilter:['autocomplete','autocorrect','autocapitalize','spellcheck']
    });

    if(!window.__lexiaMobileViewportResetInstalled){
      window.__lexiaMobileViewportResetInstalled=true;
      document.addEventListener('focusout',event=>{
        if(event.target?.id==='legalQuery')window.setTimeout(resetViewportZoom,0);
      },true);
    }
  }

  function releaseMobileViewerObjectUrl(){
    if(!mobileViewerObjectUrl)return;
    URL.revokeObjectURL(mobileViewerObjectUrl);
    mobileViewerObjectUrl='';
  }

  function resetMobileViewerSurface(){
    releaseMobileViewerObjectUrl();
    mobileViewerPath='';
    document.getElementById('lexiaQvBody')?.classList.remove('lexia-qv-mobile-mode');
    const open=document.getElementById('lexiaQvOpen');
    if(open)open.hidden=false;
  }

  function installMobileViewerFix(){
    if(!isMobileClient()||window.__lexiaMobileViewerFixInstalled)return;
    const original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function'){
      window.setTimeout(installMobileViewerFix,0);
      return;
    }
    window.__lexiaMobileViewerFixInstalled=true;

    const ext=path=>{
      const name=String(path||'').split(/[\\/]/).pop()||'';
      const dot=name.lastIndexOf('.');
      return dot>=0?name.slice(dot).toLowerCase():'';
    };
    const basename=path=>String(path||'').split(/[\\/]/).pop()||'Documento';

    window.lexiaQuickViewerOpen=async function(path,page,snippet){
      const extension=ext(path);
      const office=['.doc','.docx','.rtf','.odt'].includes(extension);
      if(extension!=='.pdf'&&!office){
        resetMobileViewerSurface();
        return original(path,page,snippet);
      }

      const backdrop=document.getElementById('lexiaQuickViewer');
      const pane=document.getElementById('lexiaQvBody');
      const name=document.getElementById('lexiaQvName');
      const pathLabel=document.getElementById('lexiaQvPath');
      const open=document.getElementById('lexiaQvOpen');
      if(!backdrop||!pane)return original(path,page,snippet);

      releaseMobileViewerObjectUrl();
      mobileViewerPath=String(path||'');
      if(name)name.textContent=basename(path);
      if(pathLabel)pathLabel.textContent=String(path||'');
      if(open)open.hidden=true;
      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden','false');
      pane.classList.add('lexia-qv-mobile-mode');

      let current=Math.max(1,Number(page)||1),total=0,loading=false;
      let locateFirstPage=!office&&Boolean(String(snippet||'').trim());
      let touchStartX=0,touchStartY=0;
      pane.innerHTML=
        '<div class="lexia-qv-mobile-pager">'+
        '<button type="button" data-qv-page="previous" aria-label="Página anterior">Anterior</button>'+
        '<span class="lexia-qv-mobile-page-label">Página '+current+'</span>'+
        '<button type="button" data-qv-page="next" aria-label="Página siguiente">Siguiente</button>'+
        '</div><div class="lexia-qv-mobile-page-wrap">'+
        '<img class="lexia-qv-mobile-page" alt="Página '+current+'">'+
        '<div class="lexia-qv-mobile-error" hidden></div></div>';

      const previous=pane.querySelector('[data-qv-page="previous"]');
      const next=pane.querySelector('[data-qv-page="next"]');
      const label=pane.querySelector('.lexia-qv-mobile-page-label');
      const image=pane.querySelector('.lexia-qv-mobile-page');
      const pageWrap=pane.querySelector('.lexia-qv-mobile-page-wrap');
      const errorBox=pane.querySelector('.lexia-qv-mobile-error');

      const loadPage=async requested=>{
        if(loading||mobileViewerPath!==String(path||''))return;
        requested=Math.max(1,Number(requested)||1);
        loading=true;previous.disabled=true;next.disabled=true;
        label.textContent='Cargando página…';errorBox.hidden=true;
        try{
          const url='/api/preview-page-image?path='+encodeURIComponent(path)+
            '&page='+encodeURIComponent(requested)+(office?'&office=1':'')+
            (locateFirstPage?'&locate=1&snippet='+encodeURIComponent(String(snippet||'')):'')+
            '&t='+Date.now();
          const response=await fetch(url,{cache:'no-store'});
          if(!response.ok){
            let detail='';
            try{detail=String((await response.json()).error||'')}catch(_){}
            throw new Error(detail||('HTTP '+response.status));
          }
          const blob=await response.blob();
          if(mobileViewerPath!==String(path||''))return;
          current=Number(response.headers.get('X-LexIA-Page'))||requested;
          total=Number(response.headers.get('X-LexIA-Page-Count'))||current;
          locateFirstPage=false;
          releaseMobileViewerObjectUrl();
          mobileViewerObjectUrl=URL.createObjectURL(blob);
          image.src=mobileViewerObjectUrl;image.hidden=false;
          image.alt='Página '+current+' de '+total;
          label.textContent='Página '+current+' de '+total;
          pageWrap.scrollTop=0;pageWrap.scrollLeft=0;
        }catch(error){
          label.textContent='No se pudo cargar la página';
          image.hidden=true;errorBox.hidden=false;
          errorBox.innerHTML='<b>No se pudo mostrar el documento.</b><span>'+esc(error.message||error)+'</span>'+
            '<button type="button" data-qv-retry>Reintentar</button>';
        }finally{
          loading=false;
          previous.disabled=current<=1;
          next.disabled=total>0&&current>=total;
        }
      };

      previous.addEventListener('click',()=>loadPage(current-1));
      next.addEventListener('click',()=>loadPage(current+1));
      errorBox.addEventListener('click',event=>{
        if(event.target.closest('[data-qv-retry]'))loadPage(current);
      });
      pageWrap.addEventListener('touchstart',event=>{
        const touch=event.changedTouches?.[0];
        if(!touch)return;
        touchStartX=touch.clientX;touchStartY=touch.clientY;
      },{passive:true});
      pageWrap.addEventListener('touchend',event=>{
        const touch=event.changedTouches?.[0];
        if(!touch||loading)return;
        const dx=touch.clientX-touchStartX,dy=touch.clientY-touchStartY;
        if(Math.abs(dx)<60||Math.abs(dx)<Math.abs(dy)*1.35)return;
        if(dx<0&&(!total||current<total))loadPage(current+1);
        if(dx>0&&current>1)loadPage(current-1);
      },{passive:true});

      if(office&&String(snippet||'').trim()){
        try{
          const metaUrl='/api/office-preview-page?path='+encodeURIComponent(path)+
            '&fallback='+encodeURIComponent(current)+'&snippet='+encodeURIComponent(String(snippet||''));
          const response=await fetch(metaUrl,{cache:'no-store'});
          const data=await response.json();
          if(response.ok&&data.ok&&Number(data.page)>0)current=Number(data.page);
        }catch(_){}
      }
      await loadPage(current);
    };

    document.addEventListener('click',event=>{
      const backdrop=document.getElementById('lexiaQuickViewer');
      if(event.target?.id==='lexiaQvClose'||event.target===backdrop)resetMobileViewerSurface();
    },true);
  }

  function installMobileRecentHistoryFix(){
    if(!isMobileClient()||window.__lexiaMobileRecentHistoryInstalled)return;
    window.__lexiaMobileRecentHistoryInstalled=true;
    let activatedAt=0;

    const historyButton=target=>target?.closest?.('#searchRecentHistory button[data-query]');
    const activate=button=>{
      if(!button)return false;
      const input=document.getElementById('legalQuery');
      if(!input)return false;
      activatedAt=performance.now();
      input.value=String(button.dataset.query||'');
      input.dispatchEvent(new Event('input',{bubbles:true}));
      document.getElementById('searchRecentHistory')?.classList.remove('open');
      input.blur();
      window.setTimeout(()=>window.lexiaSearch320Run?.(),0);
      return true;
    };

    window.addEventListener('pointerdown',event=>{
      const button=historyButton(event.target);
      if(!button)return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      activate(button);
    },true);

    window.addEventListener('click',event=>{
      const button=historyButton(event.target);
      if(!button)return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      if(performance.now()-activatedAt>700)activate(button);
    },true);
  }

  function installHomeFilenameSearchFix(){
    if(window.__lexiaHomeFilenameSearchInstalled)return;
    window.__lexiaHomeFilenameSearchInstalled=true;
    let activatedAt=0;

    const navigateToSearch=()=>{
      const navigate=
        window.lexiaUI2NavigateGlobal||
        window.lexiaUI2NavigateSafe||
        window.lexiaUI2Navigate||
        window.lexiaUI2Show||
        window.go;
      if(typeof navigate==='function')navigate('searchpage');
    };

    const run=()=>{
      const home=document.getElementById('homeQuickSearchInput');
      const query=String(home?.value||'').trim();
      if(!query)return false;
      activatedAt=performance.now();
      navigateToSearch();
      window.setTimeout(()=>{
        window.lexiaSearch320SetMode?.('filename');
        const legal=document.getElementById('legalQuery');
        if(legal){
          legal.value=query;
          legal.dispatchEvent(new Event('input',{bubbles:true}));
        }
        window.lexiaSearch320Run?.();
      },0);
      return true;
    };

    if(isMobileClient()){
      window.addEventListener('pointerdown',event=>{
        if(!event.target?.closest?.('#homeQuickSearchButton'))return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        run();
      },true);
    }

    window.addEventListener('click',event=>{
      if(!event.target?.closest?.('#homeQuickSearchButton'))return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      if(performance.now()-activatedAt>700)run();
    },true);

    window.addEventListener('keydown',event=>{
      if(event.key!=='Enter'||event.target?.id!=='homeQuickSearchInput')return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      run();
    },true);
  }

  function mobileOpenResponse(path,page,snippet){
    const openInViewer=()=>{
      if(typeof window.lexiaQuickViewerOpen==='function'){
        window.lexiaQuickViewerOpen(path,Number(page)||0,String(snippet||''));
        return true;
      }
      return false;
    };
    if(!openInViewer())setTimeout(openInViewer,0);
    return new Response(JSON.stringify({ok:true,mobile:true,viewer:true}),{
      status:200,
      headers:{'Content-Type':'application/json; charset=utf-8'}
    });
  }

  function categoryElement(){return document.getElementById('filterCategory');}
  function host(){return document.getElementById('lexiaDynamicFilters');}
  function panel(){return document.getElementById(PANEL_ID);}

  function field(label,id,type='text',placeholder=''){
    return '<label class="lexia-juris-label" for="'+id+'">'+esc(label)+'</label>'+
      '<input class="field lexia-juris-field" id="'+id+'" type="'+type+'" placeholder="'+esc(placeholder)+'" autocomplete="off">';
  }

  function markup(){
    return '<section id="'+PANEL_ID+'" class="lexia-juris-panel" aria-label="Filtros de jurisprudencia">'+
      '<div class="lexia-juris-title">Datos del fallo</div>'+
      field('Tribunal',ids.court,'text','Ej. Corte Suprema')+
      field('Sala',ids.chamber,'text','Ej. Sala B')+
      '<label class="lexia-juris-label" for="'+ids.scope+'">Ámbito</label>'+
      '<select class="field lexia-juris-field" id="'+ids.scope+'"><option value="">Todos</option><option>Nacional</option><option>Federal</option><option>Provincial</option></select>'+
      field('Provincia',ids.province,'text','Ej. Santa Fe')+
      '<div class="lexia-juris-dates">'+
        '<div>'+field('Desde',ids.date_from,'date','')+'</div>'+
        '<div>'+field('Hasta',ids.date_to,'date','')+'</div>'+
      '</div>'+
      field('Expediente',ids.case_number,'text','Número o prefijo')+
      field('Parte',ids.party,'text','Actor o demandado')+
      field('Norma',ids.law,'text','Ej. Ley 11.683')+
      '<div class="lexia-juris-note">Los filtros se aplican sobre el índice jurídico y luego LexIA ordena por relevancia de contenido + metadatos.</div>'+
      '</section>';
  }

  function ensureStyles(){
    if(document.getElementById('lexiaJurisprudenceStyles'))return;
    const style=document.createElement('style');
    style.id='lexiaJurisprudenceStyles';
    style.textContent=`
      .search-grid>.filters{max-height:calc(100vh - 210px);overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:10px}
      .lexia-juris-panel{margin-top:16px;padding-top:14px;border-top:1px solid #e4e7f0;display:grid;gap:7px}
      .lexia-juris-title{font-size:12px;font-weight:800;color:#273052;margin-bottom:2px}
      .lexia-juris-label{font-size:10px;font-weight:700;color:#66708f;margin-top:3px}
      .lexia-juris-field{width:100%;min-width:0}
      .lexia-juris-dates{display:grid;grid-template-columns:1fr 1fr;gap:8px}
      .lexia-juris-dates>div{min-width:0;display:grid;gap:7px}
      .lexia-juris-note{font-size:9.5px;line-height:1.4;color:#7a829a;margin-top:3px}
    `;
    document.head.appendChild(style);
  }

  function render(){
    const h=host(),category=categoryElement();
    if(!h||!category)return;
    if(!isJuris(category.value)){panel()?.remove();return;}
    ensureStyles();
    if(!panel())h.insertAdjacentHTML('beforeend',markup());
    enableMobileTextAssistance();
  }

  function values(){
    const out={};
    Object.entries(ids).forEach(([key,id])=>{
      const value=String(document.getElementById(id)?.value||'').trim();
      if(value)out[key]=value;
    });
    return out;
  }

  function clear(){Object.values(ids).forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});}

  function encodeHex(payload){
    const bytes=new TextEncoder().encode(JSON.stringify(payload));
    return Array.from(bytes,byte=>byte.toString(16).padStart(2,'0')).join('');
  }

  function normalizeVisibleRanks(payload){
    if(!payload||!Array.isArray(payload.results))return payload;
    payload.results=payload.results.map((item,index)=>{
      if(!item||typeof item!=='object')return item;
      const displayRank=index+1;
      return {
        ...item,
        diagnostic_lexical_rank:item.lexical_rank ?? null,
        diagnostic_semantic_rank:item.semantic_rank ?? null,
        rank:displayRank,
        lexical_rank:displayRank,
        semantic_rank:displayRank
      };
    });
    return payload;
  }

  function responseFromJson(originalResponse,payload){
    const headers=new Headers(originalResponse.headers);
    headers.set('Content-Type','application/json; charset=utf-8');
    return new Response(JSON.stringify(payload),{
      status:originalResponse.status,
      statusText:originalResponse.statusText,
      headers
    });
  }

  function installFetchBridge(){
    if(window.__lexiaJurisFetchBridge)return;
    window.__lexiaJurisFetchBridge=true;
    const original=window.fetch.bind(window);
    window.fetch=async function(input,init){
      let jurisprudenceSearch=false;
      let searchUrl='';
      try{
        const url=typeof input==='string'?input:String(input?.url||'');
        searchUrl=url;
        const method=String(init?.method||input?.method||'GET').toUpperCase();

        if(isRemoteClient()&&method==='POST'&&url.includes('/api/open-file')&&init?.body){
          const body=JSON.parse(String(init.body));
          const path=String(body?.path||'').trim();
          if(path)return mobileOpenResponse(path,body?.page,body?.snippet);
        }

        if(method==='POST'&&url.includes('/api/search')&&init?.body){
          const body=JSON.parse(String(init.body));
          jurisprudenceSearch=isJuris(body.category);
          if(jurisprudenceSearch){
            const filters=values();
            if(Object.keys(filters).length){
              const payload={...filters,text_query:String(body.query||'').trim()};
              body.query='LEXIAJURISX'+encodeHex(payload);
              body.semantic_fallback=true;
              init={...init,body:JSON.stringify(body)};
            }
          }
        }
      }catch(_){/* La búsqueda normal nunca debe romperse por los filtros. */}

      const response=await original(input,init);

      if(jurisprudenceSearch&&searchUrl.includes('/api/search')){
        try{
          const payload=await response.clone().json();
          return responseFromJson(response,normalizeVisibleRanks(payload));
        }catch(_){/* Si no es JSON válido, devolver la respuesta original. */}
      }
      return response;
    };
  }

  function initialize(){
    ensureResponsiveShellStyles();
    ensureSearchInvestigationBridge();
    enableMobileTextAssistance();
    render();
    installFetchBridge();
    installMobileViewerFix();
    installMobileRecentHistoryFix();
    installHomeFilenameSearchFix();
    const category=categoryElement();
    category?.addEventListener('change',()=>setTimeout(render,0));
    document.getElementById('clearFilters')?.addEventListener('click',()=>setTimeout(clear,0),true);
    const h=host();
    if(h){
      const observer=new MutationObserver(()=>{
        if(isJuris(categoryElement()?.value)&&!panel())render();
      });
      observer.observe(h,{childList:true,subtree:false});
    }
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
