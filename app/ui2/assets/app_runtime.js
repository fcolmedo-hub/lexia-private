/* LexIA UI2 — runtime exclusivo de LexIA.app (PyWebView/Cocoa). */
(function(){
  'use strict';

  const params=new URLSearchParams(window.location.search||'');
  if(params.get('lexia_app')!=='1')return;

  document.documentElement.dataset.lexiaApp='1';

  function installInvestigationResponsiveStyles(){
    if(document.getElementById('lexiaAppInvestigationResponsiveStyle'))return;
    const style=document.createElement('style');
    style.id='lexiaAppInvestigationResponsiveStyle';
    style.textContent=`
      html[data-lexia-app="1"] #contextpage,
      html[data-lexia-app="1"] #contextpage>.main,
      html[data-lexia-app="1"] #contextpage .page.context-layout,
      html[data-lexia-app="1"] #contextpage .context-grid,
      html[data-lexia-app="1"] #contextpage .research-main-column,
      html[data-lexia-app="1"] #contextpage .context-side,
      html[data-lexia-app="1"] #contextpage .context-form,
      html[data-lexia-app="1"] #contextpage #studyPanel,
      html[data-lexia-app="1"] #contextpage .output-card{
        min-width:0!important;
        max-width:100%!important;
        box-sizing:border-box!important;
      }
      html[data-lexia-app="1"] #contextpage .head,
      html[data-lexia-app="1"] #contextpage .head>div,
      html[data-lexia-app="1"] #contextpage .context-actions,
      html[data-lexia-app="1"] #contextpage .output-head,
      html[data-lexia-app="1"] #contextpage .output-actions{
        min-width:0!important;
      }
      html[data-lexia-app="1"] #contextpage .head p,
      html[data-lexia-app="1"] #contextpage .study-help,
      html[data-lexia-app="1"] #contextpage .context-actions .hint,
      html[data-lexia-app="1"] #contextpage .output-summary,
      html[data-lexia-app="1"] #contextpage .study-output,
      html[data-lexia-app="1"] #contextpage label,
      html[data-lexia-app="1"] #contextpage small,
      html[data-lexia-app="1"] #contextpage b{
        max-width:100%!important;
        overflow-wrap:anywhere!important;
        word-break:normal!important;
      }
      html[data-lexia-app="1"] #contextpage input,
      html[data-lexia-app="1"] #contextpage textarea,
      html[data-lexia-app="1"] #contextpage select{
        min-width:0!important;
        max-width:100%!important;
        box-sizing:border-box!important;
      }
      @media (min-width:701px) and (max-width:1199px){
        html[data-lexia-app="1"] #contextpage>.main,
        html[data-lexia-app="1"] #contextpage .page.context-layout{
          width:100%!important;
          max-width:100%!important;
          min-width:0!important;
          overflow-x:hidden!important;
        }
        html[data-lexia-app="1"] #contextpage .context-grid{
          grid-template-columns:minmax(0,1fr)!important;
          width:100%!important;
          gap:12px!important;
        }
        html[data-lexia-app="1"] #contextpage .research-main-column,
        html[data-lexia-app="1"] #contextpage .context-side{
          width:100%!important;
          max-width:100%!important;
        }
        html[data-lexia-app="1"] #contextpage .context-options,
        html[data-lexia-app="1"] #contextpage .research-settings,
        html[data-lexia-app="1"] #contextpage .form-row{
          grid-template-columns:minmax(0,1fr)!important;
        }
        html[data-lexia-app="1"] #contextpage .head,
        html[data-lexia-app="1"] #contextpage .output-head,
        html[data-lexia-app="1"] #contextpage .context-actions{
          display:flex!important;
          flex-wrap:wrap!important;
          gap:10px!important;
          align-items:flex-start!important;
        }
        html[data-lexia-app="1"] #contextpage .head>div:first-child{
          flex:1 1 420px!important;
          min-width:0!important;
        }
        html[data-lexia-app="1"] #contextpage .head-actions,
        html[data-lexia-app="1"] #contextpage .output-actions{
          max-width:100%!important;
          display:flex!important;
          flex-wrap:wrap!important;
          gap:7px!important;
        }
        html[data-lexia-app="1"] #contextpage .steps,
        html[data-lexia-app="1"] #contextpage .output-stats{
          grid-template-columns:repeat(2,minmax(0,1fr))!important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function installStudyFileInterface(){
    if(window.__lexiaAppStudyFileInterfaceInstalled)return;
    const type=document.getElementById('studyType');
    const instruction=document.getElementById('studyInstruction');
    if(!type||!instruction){
      window.setTimeout(installStudyFileInterface,50);
      return;
    }
    window.__lexiaAppStudyFileInterfaceInstalled=true;

    [...type.options].forEach(option=>{
      if(String(option.textContent||'').trim().toLowerCase()==='dictamen')option.remove();
    });

    const existing=new Set(
      [...type.options].map(option=>String(option.textContent||'').trim().toLowerCase())
    );
    const insertBefore=[...type.options].find(option=>
      String(option.textContent||'').trim().toLowerCase()==='otro documento jurídico'
    );
    ['Libro','Doctrina','Legislación'].forEach(label=>{
      if(existing.has(label.toLowerCase()))return;
      const option=document.createElement('option');
      option.value=label;
      option.textContent=label;
      if(insertBefore)type.insertBefore(option,insertBefore);
      else type.appendChild(option);
      existing.add(label.toLowerCase());
    });

    const label=document.querySelector('label[for="studyInstruction"]');
    if(label)label.textContent='Indicaciones';
    instruction.placeholder='Ej.: divorcio, responsabilidad parental, alimentos…';
  }

  function removeLiveSearchBadge(){
    const normalize=value=>String(value||'').replace(/\s+/g,' ').trim().toLowerCase();
    const nodes=[...document.querySelectorAll('div,aside,section')];
    for(const node of nodes){
      const text=normalize(node.textContent);
      if(!text.includes('live')||!text.includes('búsqueda real'))continue;
      if(text.length>240)continue;

      let candidate=node;
      for(let depth=0;depth<5&&candidate&&candidate!==document.body;depth+=1){
        const style=window.getComputedStyle(candidate);
        if(style.position==='fixed'||style.position==='sticky'){
          candidate.remove();
          return true;
        }
        candidate=candidate.parentElement;
      }

      node.remove();
      return true;
    }
    return false;
  }

  function installLiveSearchBadgeRemoval(){
    removeLiveSearchBadge();
    if(window.__lexiaAppLiveBadgeObserverInstalled)return;
    window.__lexiaAppLiveBadgeObserverInstalled=true;
    const observer=new MutationObserver(()=>removeLiveSearchBadge());
    observer.observe(document.body,{childList:true,subtree:true});
  }

  function installNavigatorExactFolderFilter(){
    if(window.__lexiaAppNavigatorExactFolderInstalled)return;
    window.__lexiaAppNavigatorExactFolderInstalled=true;

    const nativeFetch=window.fetch.bind(window);
    const normalizePath=value=>String(value||'')
      .replace(/\\/g,'/')
      .replace(/\/+$/,'')
      .toLowerCase();
    const parentPath=value=>{
      const normalized=normalizePath(value);
      const slash=normalized.lastIndexOf('/');
      return slash>0?normalized.slice(0,slash):'';
    };

    window.fetch=async function(input,init){
      const requestUrl=typeof input==='string'?input:String(input?.url||'');
      const method=String(init?.method||input?.method||'GET').toUpperCase();
      if(method!=='POST'||!requestUrl.includes('/api/navigator-documents')){
        return nativeFetch(input,init);
      }

      let body;
      try{
        body=JSON.parse(String(init?.body||''));
      }catch(_){
        return nativeFetch(input,init);
      }

      const rawSelections=Array.isArray(body?.selections)
        ? body.selections
        : ((body?.folder||body?.category)
          ? [{category:body?.category||'',folder:body?.folder||''}]
          : []);
      const folders=rawSelections
        .map(selection=>normalizePath(selection?.folder))
        .filter(Boolean);
      if(!folders.length)return nativeFetch(input,init);

      const requestedOffset=Math.max(0,Number(body?.offset||0));
      const requestedLimit=Math.max(1,Math.min(Number(body?.limit||200),200));
      const wanted=requestedOffset+requestedLimit+1;
      const exact=[];
      let recursiveOffset=0;
      let recursiveTotal=Infinity;
      let template=null;
      let templateResponse=null;

      while(recursiveOffset<recursiveTotal&&exact.length<wanted){
        const scanBody={...body,offset:recursiveOffset,limit:200};
        const scanInit={...(init||{}),body:JSON.stringify(scanBody)};
        const response=await nativeFetch(input,scanInit);
        if(!response.ok)return response;

        const data=await response.json();
        if(!template){
          template=data;
          templateResponse=response;
        }
        const items=Array.isArray(data?.items)?data.items:[];
        recursiveTotal=Math.max(0,Number(data?.total||0));
        for(const item of items){
          if(folders.includes(parentPath(item?.document_path)))exact.push(item);
        }
        if(!items.length)break;
        recursiveOffset+=items.length;
      }

      if(!template)return nativeFetch(input,init);

      const exhausted=recursiveOffset>=recursiveTotal;
      const pageItems=exact.slice(requestedOffset,requestedOffset+requestedLimit);
      const hasMore=exact.length>requestedOffset+requestedLimit||!exhausted;
      const exactTotal=exhausted
        ? exact.length
        : requestedOffset+pageItems.length+(hasMore?1:0);
      const output={
        ...template,
        items:pageItems,
        total:exactTotal,
        offset:requestedOffset,
        limit:requestedLimit,
        has_more:hasMore,
        include_subfolders:false,
      };
      const headers=new Headers(templateResponse?.headers||{});
      headers.set('content-type','application/json; charset=utf-8');
      return new Response(JSON.stringify(output),{
        status:templateResponse?.status||200,
        statusText:templateResponse?.statusText||'OK',
        headers,
      });
    };
  }

  function installHomeHistory(){
    if(window.__lexiaAppHomeHistoryInstalled)return;
    const input=document.getElementById('homeQuickSearchInput');
    const form=input?.closest?.('.hr-search');
    if(!input||!form){
      window.setTimeout(installHomeHistory,50);
      return;
    }
    window.__lexiaAppHomeHistoryInstalled=true;
    input.setAttribute('autocomplete','off');

    const style=document.createElement('style');
    style.id='lexiaAppHomeHistoryStyle';
    style.textContent=`
      html[data-lexia-app="1"] .hr-search{position:relative!important;overflow:visible!important}
      html[data-lexia-app="1"] #lexiaAppHomeHistory{
        position:absolute;left:42px;right:142px;top:calc(100% + 7px);z-index:1000;
        display:none;max-height:280px;overflow-x:hidden;overflow-y:auto;
        background:#fff;border:1px solid #e4e7f0;border-radius:12px;
        box-shadow:0 16px 38px rgba(17,24,57,.16);padding:6px;
      }
      html[data-lexia-app="1"] #lexiaAppHomeHistory.open{display:block}
      html[data-lexia-app="1"] #lexiaAppHomeHistory .head{
        padding:8px 10px 6px;color:#66708f;font-size:12px;font-weight:700;
        text-transform:uppercase;letter-spacing:.03em
      }
      html[data-lexia-app="1"] #lexiaAppHomeHistory button{
        width:100%;display:block;border:0;border-radius:8px;background:transparent;
        padding:10px 11px;text-align:left;color:#0f1734;font-size:14px;line-height:1.25;
        white-space:normal;overflow-wrap:anywhere;cursor:pointer
      }
      html[data-lexia-app="1"] #lexiaAppHomeHistory button:hover{background:#f4f3ff}
      html[data-lexia-app="1"] #lexiaAppHomeHistory .empty{padding:10px 11px 12px;color:#66708f;font-size:13px}
    `;
    document.head.appendChild(style);

    const panel=document.createElement('div');
    panel.id='lexiaAppHomeHistory';
    panel.setAttribute('role','listbox');
    panel.setAttribute('aria-label','Búsquedas recientes por nombre');
    form.appendChild(panel);

    let serial=0;
    const close=()=>panel.classList.remove('open');
    const refresh=async()=>{
      const current=++serial;
      panel.innerHTML='<div class="head">Búsquedas recientes por nombre</div>';
      try{
        const response=await fetch('/api/search-history?mode=filename',{cache:'no-store'});
        const data=await response.json();
        if(current!==serial)return;
        const items=Array.isArray(data?.items)?data.items:[];
        if(!items.length){
          panel.insertAdjacentHTML('beforeend','<div class="empty">Todavía no hay búsquedas recientes por nombre.</div>');
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
        if(current===serial)panel.insertAdjacentHTML('beforeend','<div class="empty">No se pudo cargar el historial.</div>');
      }
    };

    const open=()=>{
      refresh();
      panel.classList.add('open');
    };

    document.addEventListener('click',event=>{
      if(event.target.closest?.('#homeQuickSearchInput'))open();
    },true);

    document.addEventListener('input',event=>{
      if(event.target?.id==='homeQuickSearchInput')close();
    },true);

    input.addEventListener('keydown',event=>{
      if(event.key==='Escape')close();
    });

    panel.addEventListener('mousedown',event=>event.preventDefault());
    panel.addEventListener('click',event=>{
      const button=event.target.closest?.('button[data-query]');
      if(!button)return;
      event.preventDefault();
      event.stopPropagation();
      input.value=button.dataset.query||'';
      input.dispatchEvent(new Event('input',{bubbles:true}));
      close();
      try{input.focus({preventScroll:true});}catch(_){input.focus();}
    });

    document.addEventListener('pointerdown',event=>{
      if(panel.contains(event.target)||input.contains(event.target))return;
      close();
    },true);
  }

  function extension(path){
    const clean=String(path||'').split('?')[0].split('#')[0];
    const name=clean.split(/[\\/]/).pop()||'';
    const dot=name.lastIndexOf('.');
    return dot>=0?name.slice(dot).toLowerCase():'';
  }

  function basename(path){
    return String(path||'').split(/[\\/]/).pop()||'Documento HTML';
  }

  async function decodeHtml(response){
    const buffer=await response.arrayBuffer();
    const bytes=new Uint8Array(buffer);
    let probe='';
    try{probe=new TextDecoder('windows-1252').decode(bytes.slice(0,Math.min(bytes.length,8192)));}
    catch(_){probe=new TextDecoder('utf-8').decode(bytes.slice(0,Math.min(bytes.length,8192)));}
    const match=probe.match(/charset\s*=\s*["']?\s*([a-zA-Z0-9._-]+)/i);
    let charset=String(match?.[1]||'utf-8').toLowerCase();
    if(['iso8859-1','iso-8859-1','latin1','latin-1'].includes(charset))charset='windows-1252';
    try{return new TextDecoder(charset).decode(bytes);}
    catch(_){return new TextDecoder('utf-8').decode(bytes);}
  }

  function sanitizeLegacyHtml(source){
    let html=String(source||'');
    html=html.replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi,'');
    html=html.replace(/<frame\b[^>]*>/gi,'');
    html=html.replace(/<frameset\b[^>]*>/gi,'').replace(/<\/frameset\s*>/gi,'');
    html=html.replace(/\son[a-z]+\s*=\s*(["']).*?\1/gi,'');
    const base='<base href="about:blank">';
    if(/<head\b[^>]*>/i.test(html))html=html.replace(/<head\b([^>]*)>/i,'<head$1>'+base);
    else html=base+html;
    return html;
  }

  function installHtmlViewer(){
    const current=window.lexiaQuickViewerOpen;
    if(typeof current!=='function'){
      window.setTimeout(installHtmlViewer,50);
      return;
    }
    if(current.__lexiaHtmlViewerWrapper===true)return;

    const original=current;
    const wrapped=async function(path,page,snippet){
      const ext=extension(path);
      if(ext!=='.htm'&&ext!=='.html')return original(path,page,snippet);

      const backdrop=document.getElementById('lexiaQuickViewer');
      const pane=document.getElementById('lexiaQvBody');
      const name=document.getElementById('lexiaQvName');
      const pathLabel=document.getElementById('lexiaQvPath');
      const openButton=document.getElementById('lexiaQvOpen');
      if(!backdrop||!pane)return original(path,page,snippet);

      if(name)name.textContent=basename(path);
      if(pathLabel)pathLabel.textContent=String(path||'');
      if(openButton)openButton.hidden=false;
      pane.classList.remove('lexia-qv-mobile-mode');
      pane.innerHTML='<div style="padding:18px;color:#66708f">Renderizando HTML…</div>';
      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden','false');

      try{
        const response=await fetch('/api/file-preview?path='+encodeURIComponent(String(path||''))+'&t='+Date.now(),{cache:'no-store'});
        if(!response.ok)throw new Error('HTTP '+response.status);
        const source=await decodeHtml(response);
        const frame=document.createElement('iframe');
        frame.title='Vista HTML · '+basename(path);
        frame.setAttribute('sandbox','');
        frame.setAttribute('referrerpolicy','no-referrer');
        frame.style.cssText='display:block;width:100%;height:100%;min-height:72vh;border:0;background:#fff;';
        frame.srcdoc=sanitizeLegacyHtml(source);
        pane.innerHTML='';
        pane.appendChild(frame);
      }catch(error){
        pane.innerHTML='<div style="padding:18px;color:#991b1b">No se pudo renderizar el HTML: '+String(error?.message||error)+'</div>';
      }
      return true;
    };

    wrapped.__lexiaHtmlViewerWrapper=true;
    wrapped.__lexiaHtmlViewerOriginal=original;
    window.lexiaQuickViewerOpen=wrapped;
  }

  function initialize(){
    installInvestigationResponsiveStyles();
    installStudyFileInterface();
    installLiveSearchBadgeRemoval();
    installNavigatorExactFolderFilter();
    installHomeHistory();
    installHtmlViewer();
    document.addEventListener('pointerdown',installHtmlViewer,true);
    document.addEventListener('mousedown',installHtmlViewer,true);
    document.addEventListener('click',installHtmlViewer,true);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
  // El espacio Casos se mantiene separado de la página principal para que
  // las actualizaciones del visor y de Windows no alteren su bitácora.
  if(!document.querySelector('script[data-lexia-case-workspace]')){
    const caseWorkspace=document.createElement('script');
    caseWorkspace.src='assets/case_workspace.js?v=case-4';
    caseWorkspace.async=false;
    caseWorkspace.dataset.lexiaCaseWorkspace='1';
    (document.body||document.documentElement).appendChild(caseWorkspace);
  }

})();