/* LexIA Windows — tolerancia a fallos transitorios en Investigación.
   Sólo reintenta consultas GET de estado/resultado. Nunca reintenta los POST
   que inician, pausan, reanudan o cancelan trabajos. */
(function(){
  'use strict';

  if(window.__lexiaWindowsResearchTransportResilience)return;
  window.__lexiaWindowsResearchTransportResilience=true;

  const originalFetch=window.fetch.bind(window);
  const retryableStatus=new Set([408,429,502,503,504]);
  const retryDelays=[0,250,700,1500];
  const stats={retries:0,lastPath:'',lastStatus:0,lastError:''};
  window.__lexiaResearchTransportStats=stats;

  function sleep(ms){return new Promise(resolve=>window.setTimeout(resolve,ms));}

  function requestMethod(input,init){
    return String(init?.method||input?.method||'GET').toUpperCase();
  }

  function requestPath(input){
    try{
      const raw=typeof input==='string'?input:String(input?.url||'');
      return new URL(raw,window.location.href).pathname;
    }catch(_){return '';}
  }

  function isResilientGet(input,init){
    if(requestMethod(input,init)!=='GET')return false;
    return /^\/api\/(?:research|research-candidates|research-package)-(?:status|result)$/.test(requestPath(input));
  }

  async function emptyCompletedResult(response,path){
    if(!path.endsWith('-result')||!response?.ok)return false;
    try{
      const data=await response.clone().json();
      const sources=data?.result?.sources;
      return Array.isArray(sources)&&sources.length===0;
    }catch(_){return false;}
  }

  window.fetch=async function lexiaWindowsResilientFetch(input,init){
    if(!isResilientGet(input,init))return originalFetch(input,init);

    const path=requestPath(input);
    let lastError=null;
    let lastResponse=null;

    for(let attempt=0;attempt<retryDelays.length;attempt+=1){
      if(retryDelays[attempt])await sleep(retryDelays[attempt]);
      try{
        const response=await originalFetch(input,init);
        lastResponse=response;
        stats.lastPath=path;
        stats.lastStatus=Number(response.status||0);
        stats.lastError='';

        const transient=retryableStatus.has(response.status);
        const emptyRace=attempt<2&&await emptyCompletedResult(response,path);
        if(!transient&&!emptyRace)return response;

        if(attempt<retryDelays.length-1){
          stats.retries+=1;
          continue;
        }
        return response;
      }catch(error){
        lastError=error;
        stats.lastPath=path;
        stats.lastStatus=0;
        stats.lastError=String(error?.message||error||'');
        if(attempt<retryDelays.length-1){
          stats.retries+=1;
          continue;
        }
      }
    }

    if(lastResponse)return lastResponse;
    throw lastError||new Error('No se pudo consultar el estado de Investigación.');
  };
})();
