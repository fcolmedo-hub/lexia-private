/* LexIA Windows — normaliza el estado visual del menú al pasar de Casos a Investigación. */
(function(){
  'use strict';

  if(window.__lexiaWindowsCaseNavStateFix)return;
  window.__lexiaWindowsCaseNavStateFix=true;

  const norm=value=>String(value||'')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ').trim().toLowerCase();

  function navButtons(){
    return [...document.querySelectorAll('#globalSidebar .nav button,.global-sidebar .nav button')];
  }

  function clearSelected(button){
    if(!button)return;
    button.classList.remove('active','is-active','selected','current');
    button.removeAttribute('aria-current');
    button.setAttribute('aria-selected','false');
  }

  function selectButton(button){
    if(!button)return;
    button.classList.add('active');
    button.setAttribute('aria-current','page');
    button.setAttribute('aria-selected','true');
  }

  function syncResearchNavState(){
    let research=null;
    navButtons().forEach(button=>{
      const label=norm(button.textContent);
      if(label==='casos')clearSelected(button);
      if(label==='investigacion'||label==='investigación')research=button;
    });
    selectButton(research);
  }

  function syncBurst(){
    [0,50,180,500].forEach(delay=>window.setTimeout(syncResearchNavState,delay));
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;

    if(target.closest('.lexia-case-investigate')){
      syncBurst();
      return;
    }

    const nav=target.closest('#globalSidebar .nav button,.global-sidebar .nav button');
    if(!nav)return;
    const label=norm(nav.textContent);
    if(label!=='casos'){
      const cases=navButtons().find(button=>norm(button.textContent)==='casos');
      if(cases)window.requestAnimationFrame(()=>clearSelected(cases));
    }
  },true);
})();
