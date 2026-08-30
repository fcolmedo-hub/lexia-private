/* LexIA UI2 — bridge from Search results to Investigation / Study file. */
(function(){
  'use strict';

  const SEARCH_PAGE_ID='searchpage';
  const INVESTIGATE_ATTR='data-lexia-search-investigate';

  function decodePath(value){
    try{return decodeURIComponent(String(value||''));}
    catch(_){return String(value||'');}
  }

  function removeSearchInsight(){
    document.querySelector('#'+SEARCH_PAGE_ID+' .insight')?.remove();
    const grid=document.querySelector('#'+SEARCH_PAGE_ID+' .search-grid');
    if(grid)grid.style.setProperty('grid-template-columns','220px minmax(0,1fr)','important');
  }

  function investigateButton(openButton){
    const button=openButton.cloneNode(true);
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
    syncSearchSurface();
    const page=document.getElementById(SEARCH_PAGE_ID);
    if(!page)return;
    new MutationObserver(syncSearchSurface).observe(page,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
