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

  function ensureResponsiveShellStyles(){
    const id='lexiaResponsiveShellStyles';
    if(document.getElementById(id))return;
    const link=document.createElement('link');
    link.id=id;
    link.rel='stylesheet';
    link.href='assets/responsive_shell.css?v=ui2-3.4.1-full-width';
    document.head.appendChild(link);
  }

  function ensureSearchInvestigationBridge(){
    const id='lexiaSearchInvestigationBridge';
    if(document.getElementById(id))return;
    const script=document.createElement('script');
    script.id=id;
    script.src='assets/search_investigation_bridge.js?v=ui2-3.4.2';
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
  }

  function mobileOpenResponse(path){
    const openInViewer=()=>{
      if(typeof window.lexiaQuickViewerOpen==='function'){
        window.lexiaQuickViewerOpen(path,0,'');
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
          if(path)return mobileOpenResponse(path);
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
