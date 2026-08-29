/* LexIA UI2 — filtros jurisprudenciales estructurados */
(function(){
  'use strict';
  const PANEL_ID='lexiaJurisprudenceFilters';
  const ids={
    court:'jurisCourt',chamber:'jurisChamber',scope:'jurisScope',province:'jurisProvince',
    date_from:'jurisDateFrom',date_to:'jurisDateTo',case_number:'jurisCaseNumber',
    party:'jurisParty',law:'jurisLaw'
  };
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const isJuris=value=>String(value||'').trim().toLocaleLowerCase('es-AR')==='jurisprudencia';

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

      // La API conserva lexical_rank/semantic_rank como datos diagnósticos.
      // La interfaz histórica podía elegir uno de esos campos para la insignia
      // del resultado, mostrando números como 26, 29, 4 aunque la lista visible
      // estuviera correctamente ordenada. En Jurisprudencia normalizamos sólo
      // la respuesta del navegador: el backend mantiene intactos sus rankings.
      if(jurisprudenceSearch&&searchUrl.includes('/api/search')){
        try{
          const payload=await response.clone().json();
          return responseFromJson(response,normalizeVisibleRanks(payload));
        }catch(_){/* Si no es JSON válido, devolver la respuesta original. */}
      }
      return response;
    };
  }

  // Buscador de contenido: Office debe entrar al mismo visor compartido que
  // Investigación cuando sourcePage(source) devuelve 0. Esa rama presenta
  // texto extraído, localiza el snippet, lo resalta en amarillo y hace scroll.
  // PDF conserva data-page y su comportamiento paginado.
  const OFFICE_PREVIEW_RE=/\.(doc|docx|rtf|odt)$/i;

  function decodeData(value){
    try{return decodeURIComponent(String(value||''));}
    catch(_){return String(value||'');}
  }

  function isOfficeSearchPreview(button){
    if(!button||!button.matches?.('.search-preview-file'))return false;
    if(!button.closest?.('#realSearchResults'))return false;
    const path=decodeData(button.dataset.path||'').split(/[?#]/,1)[0];
    return OFFICE_PREVIEW_RE.test(path);
  }

  function stripOfficePageState(root=document){
    const buttons=[];
    if(root?.matches?.('.search-preview-file'))buttons.push(root);
    root?.querySelectorAll?.('.search-preview-file').forEach(button=>buttons.push(button));
    buttons.forEach(button=>{
      if(!isOfficeSearchPreview(button))return;
      button.removeAttribute('data-page');
      button.removeAttribute('data-preview-page');
    });
  }

  function installOfficeSearchInvestigationPreview(){
    if(window.__lexiaOfficeSearchInvestigationPreview)return;
    window.__lexiaOfficeSearchInvestigationPreview=true;

    stripOfficePageState(document.getElementById('realSearchResults')||document);

    const results=document.getElementById('realSearchResults');
    if(results){
      const observer=new MutationObserver(records=>{
        records.forEach(record=>{
          if(record.type==='attributes'){
            stripOfficePageState(record.target);
            return;
          }
          record.addedNodes.forEach(node=>{
            if(node?.nodeType===1)stripOfficePageState(node);
          });
        });
      });
      observer.observe(results,{
        childList:true,
        subtree:true,
        attributes:true,
        attributeFilter:['data-page','data-preview-page']
      });
    }

    // FINAL PAGE PREVIEW está registrado antes en window/capture y sólo toma
    // .search-preview-file[data-page]. Al quitar data-page a Office, ese bloque
    // lo deja pasar. Este listener llama luego al visor común con page=0.
    window.addEventListener('click',event=>{
      const button=event.target?.closest?.('#realSearchResults .search-preview-file');
      if(!isOfficeSearchPreview(button))return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();

      const path=decodeData(button.dataset.path||'');
      let snippet=decodeData(button.dataset.snippet||'');
      if(!snippet){
        snippet=String(button.closest('.result-card')?.querySelector('p')?.textContent||'')
          .replace(/\s+/g,' ')
          .trim();
      }

      if(typeof window.lexiaQuickViewerOpen==='function'){
        window.lexiaQuickViewerOpen(path,0,snippet);
      }
    },true);
  }

  function initialize(){
    render();
    installFetchBridge();
    installOfficeSearchInvestigationPreview();
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
