/* LexIA Windows — normaliza el estado visual del menú al pasar de Casos a Investigación. */
(function(){
  'use strict';

  if(window.__lexiaWindowsCaseNavStateFixV2)return;
  window.__lexiaWindowsCaseNavStateFixV2=true;

  const SCROLL_LOCK='lexia-windows-cases-open';

  function installScrollStyle(){
    if(document.getElementById('lexiaWindowsCasesScrollStyle'))return;
    const style=document.createElement('style');
    style.id='lexiaWindowsCasesScrollStyle';
    style.textContent=`
      html.${SCROLL_LOCK},html.${SCROLL_LOCK} body{
        height:100%!important;overflow:hidden!important
      }
      html.${SCROLL_LOCK} #casespage{overscroll-behavior:contain}
    `;
    document.head.appendChild(style);
  }

  function setCasesScrollLock(active){
    document.documentElement.classList.toggle(SCROLL_LOCK,Boolean(active));
  }

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
      setCasesScrollLock(false);
      syncBurst();
      return;
    }

    if(target.closest('#home [data-home-target="casespage"],#home [data-lexia-cases-home]')){
      setCasesScrollLock(true);
      return;
    }

    const nav=target.closest('#globalSidebar .nav button,.global-sidebar .nav button');
    if(!nav)return;
    const label=norm(nav.textContent);
    setCasesScrollLock(label==='casos');
    if(label!=='casos'){
      const cases=navButtons().find(button=>norm(button.textContent)==='casos');
      if(cases)window.requestAnimationFrame(()=>clearSelected(cases));
    }
  },true);

  installScrollStyle();
  setCasesScrollLock((location.hash||'').slice(1)==='casespage');
})();
