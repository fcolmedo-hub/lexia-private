/* Keep the shared quick viewer, resolving statutory headings before opening it. */
(function(){
  'use strict';

  function install(){
    if(window.__lexiaLegalArticlePreview)return;
    const original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function')return;
    window.__lexiaLegalArticlePreview=true;
    let sequence=0,controller=null;

    window.lexiaQuickViewerOpen=async function(path,page,snippet){
      const token=++sequence;
      controller?.abort();
      controller=null;
      const source=String(path||'');
      const excerpt=String(snippet||'').trim();
      const isStatute=/(?:^|[\\/])(?:legislaci[oó]n|ley\b|c[oó]digo\b)/i.test(source);
      const hasArticle=/^(?:art(?:[íi]culo)?s?|art[yý]culo|art═culo)\.?\s*(?:n(?:ro|[úu]mero|o)?\.?\s*[°ºo]?\s*)?\d/i.test(excerpt);
      if(!/\.pdf$/i.test(source)||!isStatute||!hasArticle){
        return original.call(this,path,page,snippet);
      }

      // Open immediately using the existing viewer; do not freeze the UI while
      // the server checks the PDF. Ignore replies after another file is opened.
      const abort=new AbortController();
      controller=abort;
      await original.call(this,path,page,'');
      const pane=document.getElementById('lexiaQvBody');
      const backdrop=document.getElementById('lexiaQuickViewer');
      if(token!==sequence||!backdrop?.classList.contains('open'))return;
      const status=document.createElement('div');
      status.className='lexia-qv-extracted-note';
      status.setAttribute('role','status');
      status.textContent='Localizando el artículo en el PDF…';
      pane?.prepend(status);
      try{
        const response=await fetch('/api/legal-article-location',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({path:source,page:Number(page)||1,snippet:excerpt}),
          signal:abort.signal,
        });
        const location=await response.json();
        if(token!==sequence||!backdrop?.classList.contains('open'))return;
        const shownPath=document.getElementById('lexiaQvPath');
        if(shownPath&&shownPath.textContent!==source)return;
        if(!response.ok||!location.ok||!location.found){
          status.textContent='No se pudo localizar el encabezado del artículo; se muestra la página indexada.';
          return;
        }
        // Suppress the mobile approximate snippet locator after an exact match.
        const mobile=Boolean(pane?.querySelector('.lexia-qv-mobile-page'));
        await original.call(this,path,location.page,mobile?'':snippet);
        if(token!==sequence)return;
        const frame=pane?.querySelector('iframe.lexia-qv-frame');
        if(frame){
          const url=new URL(frame.src,window.location.href);
          const position=new URLSearchParams();
          position.set('page',String(location.page));
          // Native viewers that support PDF Open Parameters position the
          // heading at the top; others still receive the verified page.
          position.set('view','FitH,'+Math.max(0,Number(location.top)));
          url.hash=position.toString();
          frame.src=url.href;
        }
        const image=pane?.querySelector('.lexia-qv-mobile-page');
        const pageWrap=pane?.querySelector('.lexia-qv-mobile-page-wrap');
        if(image&&pageWrap){
          const focus=()=>{
            if(token!==sequence)return;
            pageWrap.scrollTop=Math.max(0,image.clientHeight*Number(location.top)/Number(location.page_height));
          };
          if(image.complete)focus();
          else image.addEventListener('load',focus,{once:true});
        }
      }catch(error){
        if(error?.name!=='AbortError'&&token===sequence){
          status.textContent='No se pudo verificar la ubicación del artículo; se muestra la página indexada.';
        }
      }
    };
  }

  // Install after the desktop/mobile wrappers without timers or DOM observers.
  if(document.readyState==='complete')install();
  else window.addEventListener('load',install,{once:true});
})();
