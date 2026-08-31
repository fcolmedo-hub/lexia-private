/* LexIA UI2 — runtime exclusivo de LexIA.app (PyWebView/Cocoa). */
(function(){
  'use strict';

  const params=new URLSearchParams(window.location.search||'');
  if(params.get('lexia_app')!=='1')return;

  document.documentElement.dataset.lexiaApp='1';

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

    const open=()=>{ refresh(); panel.classList.add('open'); };

    input.addEventListener('focus',open);
    input.addEventListener('click',event=>{ event.stopPropagation(); close(); });
    input.addEventListener('input',close);
    input.addEventListener('keydown',event=>{ if(event.key==='Escape')close(); });

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

    document.addEventListener('mousedown',event=>{
      if(event.target===input||panel.contains(event.target))return;
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
    installHomeHistory();
    installHtmlViewer();

    // Algunos módulos históricos vuelven a asignar lexiaQuickViewerOpen después
    // de cargar el runtime. Reinstalar el wrapper en fase de captura garantiza
    // que el clic que abre el archivo ya vea el visor HTML correcto.
    document.addEventListener('pointerdown',installHtmlViewer,true);
    document.addEventListener('mousedown',installHtmlViewer,true);
    document.addEventListener('click',installHtmlViewer,true);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
