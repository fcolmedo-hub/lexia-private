/* LEXIA UI2 SEARCH PREVIEW = INVESTIGATION */
(function(){
  if(window.__lexiaSearchPreviewInvestigationInstalled)return;
  window.__lexiaSearchPreviewInvestigationInstalled=true;

  const OFFICE_EXTENSIONS=new Set(['.doc','.docx','.rtf','.odt']);

  function decode(value){
    try{return decodeURIComponent(String(value||''));}
    catch(_){return String(value||'');}
  }

  function extension(path){
    const clean=String(path||'').split(/[?#]/,1)[0].toLowerCase();
    const name=clean.split(/[\\/]/).pop()||'';
    const dot=name.lastIndexOf('.');
    return dot>=0?name.slice(dot):'';
  }

  function isOfficePreviewButton(button){
    if(!button?.matches?.('.search-preview-file'))return false;
    return OFFICE_EXTENSIONS.has(extension(decode(button.dataset.path||'')));
  }

  /*
    El Buscador tenía una segunda lógica para Office que precalculaba
    /api/office-preview-page y añadía data-page/data-preview-page. Esa ruta
    interceptaba el clic antes del visor común. Investigación no hace eso:
    entrega ruta + snippet al visor y éste localiza y resalta el pasaje.

    Quitamos esos atributos sólo en resultados Office del Buscador. La página
    original, si existe, sigue visible en la metadata del resultado; simplemente
    deja de gobernar la apertura de la vista previa.
  */
  function normalizeOfficeButtons(root){
    const buttons=[];
    if(root?.matches?.('.search-preview-file'))buttons.push(root);
    root?.querySelectorAll?.('.search-preview-file').forEach(button=>buttons.push(button));
    for(const button of buttons){
      if(!isOfficePreviewButton(button))continue;
      if(button.dataset.page&&!button.dataset.sourcePage){
        button.dataset.sourcePage=button.dataset.page;
      }
      button.removeAttribute('data-page');
      button.removeAttribute('data-preview-page');
    }
  }

  normalizeOfficeButtons(document);

  const observer=new MutationObserver(records=>{
    for(const record of records){
      if(record.type==='childList'){
        record.addedNodes.forEach(node=>{
          if(node.nodeType===1)normalizeOfficeButtons(node);
        });
      }else if(record.type==='attributes'){
        normalizeOfficeButtons(record.target);
      }
    }
  });
  observer.observe(document.documentElement,{
    childList:true,
    subtree:true,
    attributes:true,
    attributeFilter:['data-page','data-preview-page']
  });

  /*
    Para Office, abrir exactamente como Investigación: resolver la ruta real y
    pasar el snippet al visor compartido. No se calcula ni se espera una página
    previa. lexiaQuickViewerOpen ya se ocupa de encontrar el texto, envolverlo
    con .lexia-word-search-hit y centrarlo en pantalla.
  */
  document.addEventListener('click',async event=>{
    const button=event.target.closest?.('.search-preview-file');
    if(!isOfficePreviewButton(button))return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const card=button.closest('.result-card');
    const requestedPath=decode(button.dataset.path||'');
    const encodedSnippet=button.dataset.snippet||'';
    const snippet=(encodedSnippet?decode(encodedSnippet):
      (card?.querySelector('.result-body p')?.textContent||''))
      .replace(/\s+/g,' ')
      .trim();

    try{
      let path=requestedPath;
      if(typeof window.lexiaSearch320bResolve==='function'){
        path=(await window.lexiaSearch320bResolve(card))||requestedPath;
      }
      if(!path)throw new Error('No se pudo resolver la ubicación del documento.');
      if(typeof window.lexiaQuickViewerOpen!=='function'){
        throw new Error('La vista rápida de LexIA no está disponible.');
      }
      window.lexiaQuickViewerOpen(path,undefined,snippet);
    }catch(error){
      alert('No se pudo abrir la vista rápida:\n\n'+(error.message||error));
    }
  },true);
})();
