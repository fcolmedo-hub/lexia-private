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
      '<div class="lexia-juris-note">Estos filtros usan el índice jurídico del fallo y se combinan con la búsqueda de contenido.</div>'+
      '</section>';
  }

  function ensureStyles(){
    if(document.getElementById('lexiaJurisprudenceStyles'))return;
    const style=document.createElement('style');
    style.id='lexiaJurisprudenceStyles';
    style.textContent=`
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
    const active=isJuris(category.value);
    if(!active){panel()?.remove();return;}
    ensureStyles();
    if(!panel())h.insertAdjacentHTML('beforeend',markup());
  }

  function values(){
    const out={};
    Object.entries(ids).forEach(([key,id])=>{
      const el=document.getElementById(id);
      const value=String(el?.value||'').trim();
      if(value)out[key]=value;
    });
    return out;
  }

  function hasValues(obj){return Object.keys(obj||{}).length>0;}
  function clear(){Object.values(ids).forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});}

  function encode(payload){
    const bytes=new TextEncoder().encode(JSON.stringify(payload));
    let binary='';
    bytes.forEach(byte=>{binary+=String.fromCharCode(byte);});
    return btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }

  function installFetchBridge(){
    if(window.__lexiaJurisFetchBridge)return;
    window.__lexiaJurisFetchBridge=true;
    const original=window.fetch.bind(window);
    window.fetch=async function(input,init){
      try{
        const url=typeof input==='string'?input:String(input?.url||'');
        const method=String(init?.method||input?.method||'GET').toUpperCase();
        if(method==='POST'&&url.includes('/api/search')&&init?.body){
          const body=JSON.parse(String(init.body));
          if(isJuris(body.category)){
            const filters=values();
            if(hasValues(filters)){
              const payload={...filters,text_query:String(body.query||'').trim()};
              body.query='[[LEXIA_JURIS:'+encode(payload)+']]';
              body.semantic_fallback=true;
              init={...init,body:JSON.stringify(body)};
            }
          }
        }
      }catch(_){/* La búsqueda normal nunca debe romperse por los filtros. */}
      return original(input,init);
    };
  }

  function initialize(){
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
