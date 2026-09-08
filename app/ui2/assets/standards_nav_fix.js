/* LexIA UI2 — inserción nativa del menú Estándares. */
(function(){
  'use strict';

  function standardsShell(){
    return document.getElementById('lexiaStandardsShell');
  }

  function installVisualFixes(){
    if(document.getElementById('lexiaStandardsNativeVisualFix'))return;
    const style=document.createElement('style');
    style.id='lexiaStandardsNativeVisualFix';
    style.textContent=`
      #lexiaStandardsShell .std-kicker{display:none!important}
      #lexiaStandardsShell .std-wrap{max-width:none!important;margin:0!important;padding:22px 18px 38px!important}
      #lexiaStandardsShell .std-head{margin-bottom:14px!important}
      #lexiaStandardsShell .std-title{margin-top:0!important}
      @media(max-width:1100px){#lexiaStandardsShell .std-wrap{padding:18px 14px!important}}
      @media(max-width:680px){#lexiaStandardsShell .std-wrap{padding:12px!important}}
    `;
    document.head.appendChild(style);
  }

  function syncStandardsInset(){
    const sidebar=document.getElementById('globalSidebar');
    const shell=standardsShell();
    if(!sidebar||!shell)return;
    const rect=sidebar.getBoundingClientRect();
    const left=Math.max(0,Math.round(rect.right));
    shell.style.setProperty('left',left+'px','important');
    shell.style.setProperty('right','0','important');
    shell.style.setProperty('top','0','important');
    shell.style.setProperty('bottom','0','important');
    shell.style.setProperty('width','auto','important');
  }

  function openStandards(){
    const shell=standardsShell();
    if(!shell)return;
    installVisualFixes();
    syncStandardsInset();
    const nav=document.querySelector('#globalSidebar .nav');
    if(nav)nav.querySelectorAll('button').forEach(item=>item.classList.remove('active'));
    const button=nav&&nav.querySelector('[data-lexia-standards-nav]');
    if(button){button.classList.add('active');button.setAttribute('aria-current','page');}
    shell.classList.add('open');
    const searchButton=document.getElementById('stdSearch');
    if(searchButton)searchButton.click();
  }

  function closeStandards(){
    const shell=standardsShell();
    if(shell)shell.classList.remove('open');
    const button=document.querySelector('#globalSidebar .nav [data-lexia-standards-nav]');
    if(button){button.classList.remove('active');button.removeAttribute('aria-current');}
  }

  function buildButton(){
    const button=document.createElement('button');
    button.type='button';
    button.dataset.lexiaStandardsNav='1';
    button.setAttribute('aria-label','Estándares');

    const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');
    icon.setAttribute('viewBox','0 0 24 24');
    icon.setAttribute('aria-hidden','true');
    icon.innerHTML='<path d="M12 3v18"></path><path d="M5 6h14"></path><path d="M7 6 3.5 12h7L7 6Z"></path><path d="M17 6 13.5 12h7L17 6Z"></path><path d="M8 21h8"></path>';
    button.append(icon,document.createTextNode('Estándares'));
    button.addEventListener('click',event=>{
      event.preventDefault();
      event.stopPropagation();
      openStandards();
    },true);
    return button;
  }

  function install(){
    installVisualFixes();
    const nav=document.querySelector('#globalSidebar .nav');
    if(!nav)return false;
    if(nav.querySelector('[data-lexia-standards-nav]')){
      syncStandardsInset();
      return true;
    }

    const button=buildButton();
    const buttons=[...nav.querySelectorAll(':scope > button')];
    const maintenance=buttons.find(item=>String(item.textContent||'').trim().toLowerCase()==='mantenimiento');
    const investigation=nav.querySelector('button[data-route="contextpage"]') ||
      buttons.find(item=>['investigación','investigacion'].includes(String(item.textContent||'').trim().toLowerCase()));

    if(maintenance){
      maintenance.insertAdjacentElement('beforebegin',button);
    }else if(investigation){
      investigation.insertAdjacentElement('afterend',button);
    }else{
      nav.append(button);
    }
    syncStandardsInset();
    return true;
  }

  function allSearchFieldsBlank(){
    const ids=['stdQ','stdCourt','stdSpeaker','stdTreatment','stdFrom','stdTo','stdTag'];
    return ids.every(id=>{
      const node=document.getElementById(id);
      return !node || !String(node.value||'').trim();
    });
  }

  let blankSearchTimer=null;
  function scheduleShowAllIfBlank(){
    clearTimeout(blankSearchTimer);
    blankSearchTimer=window.setTimeout(()=>{
      const shell=standardsShell();
      if(!shell||!shell.classList.contains('open')||!allSearchFieldsBlank())return;
      document.getElementById('stdSearch')?.click();
    },120);
  }

  function installStandardsInteractionFixes(){
    if(window.__lexiaStandardsInteractionFixes)return;
    window.__lexiaStandardsInteractionFixes=true;

    document.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target.closest('#stdGraphBtn'):null;
      if(!target)return;
      const graph=document.getElementById('stdGraph');
      if(!graph)return;
      const isOpen=graph.dataset.lexiaGraphOpen==='1' || graph.classList.contains('std-graph') || graph.childElementCount>0;
      if(isOpen){
        event.preventDefault();
        event.stopImmediatePropagation();
        graph.innerHTML='';
        graph.className='';
        graph.dataset.lexiaGraphOpen='0';
        target.textContent='Ver grafo';
        target.setAttribute('aria-expanded','false');
        return;
      }
      graph.dataset.lexiaGraphOpen='1';
      target.textContent='Cerrar grafo';
      target.setAttribute('aria-expanded','true');
    },true);

    document.addEventListener('input',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(target?.matches('#stdQ,#stdFrom,#stdTo,#stdTag'))scheduleShowAllIfBlank();
    },true);
    document.addEventListener('change',event=>{
      const target=event.target instanceof Element?event.target:null;
      if(target?.matches('#stdCourt,#stdSpeaker,#stdTreatment,#stdFrom,#stdTo,#stdTag'))scheduleShowAllIfBlank();
    },true);
  }

  function installExitHandler(){
    if(window.__lexiaStandardsNativeExit)return;
    window.__lexiaStandardsNativeExit=true;
    window.addEventListener('click',event=>{
      const target=event.target instanceof Element?event.target:null;
      const destination=target&&target.closest('#globalSidebar .nav button');
      if(destination&&!destination.matches('[data-lexia-standards-nav]'))closeStandards();
    },true);
  }

  function boot(){
    install();
    installExitHandler();
    installStandardsInteractionFixes();
    window.addEventListener('resize',syncStandardsInset,{passive:true});
    const observer=new MutationObserver(()=>install());
    observer.observe(document.body,{childList:true,subtree:true});
    window.setTimeout(install,100);
    window.setTimeout(install,500);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
