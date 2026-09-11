/* LexIA Windows — ajustes visuales aislados para Investigación.
   Sin MutationObserver: el botón principal sólo se recoloca en cambios de tamaño
   o al navegar por Investigación. */
(function(){
  'use strict';

  if(document.getElementById('lexiaWindowsInvestigationLayoutFix'))return;
  const style=document.createElement('style');
  style.id='lexiaWindowsInvestigationLayoutFix';
  style.textContent=`
    html[data-lexia-app="1"] #contextpage .context-form,
    html[data-lexia-app="1"] #contextpage #researchPanel,
    html[data-lexia-app="1"] #contextpage .research-main-column{
      min-width:0!important;
      max-width:100%!important;
      box-sizing:border-box!important;
    }

    html[data-lexia-app="1"] #contextpage .context-form{
      height:auto!important;
      min-height:0!important;
      max-height:none!important;
      overflow:visible!important;
    }

    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock{
      box-sizing:border-box!important;
      width:100%!important;
      min-width:0!important;
      min-height:46px!important;
      display:flex!important;
      align-items:center!important;
      justify-content:flex-end!important;
      gap:8px!important;
      margin:10px 0 0!important;
      padding:6px 0 0!important;
      overflow:visible!important;
      clear:both!important;
    }
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock > button{
      position:static!important;
      inset:auto!important;
      float:none!important;
      transform:none!important;
      display:inline-flex!important;
      visibility:visible!important;
      opacity:1!important;
      width:auto!important;
      min-width:118px!important;
      max-width:100%!important;
      min-height:38px!important;
      margin:0!important;
      flex:0 0 auto!important;
      align-items:center!important;
      justify-content:center!important;
      z-index:auto!important;
    }

    @media (min-width:701px) and (max-width:1199px){
      html[data-lexia-app="1"] #contextpage #researchPanel .context-actions,
      html[data-lexia-app="1"] #contextpage .research-main-column .context-form .context-actions{
        box-sizing:border-box!important;
        position:relative!important;
        left:auto!important;
        right:auto!important;
        top:auto!important;
        bottom:auto!important;
        inset:auto!important;
        float:none!important;
        transform:none!important;
        display:flex!important;
        visibility:visible!important;
        width:100%!important;
        min-width:0!important;
        min-height:42px!important;
        height:auto!important;
        max-height:none!important;
        margin:12px 0 0!important;
        padding:8px 0 0!important;
        overflow:visible!important;
        flex-wrap:wrap!important;
        align-items:center!important;
        justify-content:flex-end!important;
        gap:8px!important;
      }
    }

    @media (min-width:1200px){
      html[data-lexia-app="1"] .lexia-sources-modal{
        box-sizing:border-box!important;
        width:min(880px,calc(100vw - var(--global-side,196px) - 28px))!important;
        max-width:calc(100vw - var(--global-side,196px) - 28px)!important;
        max-height:calc(100dvh - 28px)!important;
        translate:98px 0!important;
      }
    }

    @media (max-width:1199px){
      html[data-lexia-app="1"] .lexia-sources-modal{
        box-sizing:border-box!important;
        width:calc(100vw - 20px)!important;
        max-width:calc(100vw - 20px)!important;
        max-height:calc(100dvh - 20px)!important;
        translate:0 0!important;
      }
      html[data-lexia-app="1"] .lexia-sources-head,
      html[data-lexia-app="1"] .lexia-sources-foot{
        box-sizing:border-box!important;
        max-width:100%!important;
        flex-wrap:wrap!important;
      }
    }
  `;
  document.head.appendChild(style);

  const movedButtonState=new WeakMap();
  const normalize=value=>String(value||'')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ').trim().toLowerCase();

  function mainResearchButton(){
    const page=document.getElementById('contextpage');
    if(!page)return null;
    const buttons=[...page.querySelectorAll('button')];
    return buttons.find(button=>{
      if(normalize(button.textContent)!=='investigar')return false;
      if(button.closest('.source-actions,.lexia-sources-modal,.result-actions'))return false;
      return true;
    })||null;
  }

  function restoreButton(button){
    const state=movedButtonState.get(button);
    if(!state)return;
    const {parent,next}=state;
    if(parent&&parent.isConnected){
      if(next&&next.parentNode===parent)parent.insertBefore(button,next);
      else parent.appendChild(button);
    }
    movedButtonState.delete(button);
    document.getElementById('lexiaWindowsResearchActionDock')?.remove();
  }

  function syncResearchActionDock(){
    const button=mainResearchButton();
    if(!button)return;
    if(window.innerWidth>1199){
      restoreButton(button);
      return;
    }

    const panel=document.getElementById('researchPanel')
      ||button.closest('.research-main-column')
      ||document.querySelector('#contextpage .research-main-column')
      ||document.getElementById('contextpage');
    if(!panel)return;
    const host=button.closest('.context-form')
      ||panel.querySelector?.('.context-form')
      ||panel;
    if(!host)return;

    let dock=document.getElementById('lexiaWindowsResearchActionDock');
    if(!dock){
      dock=document.createElement('div');
      dock.id='lexiaWindowsResearchActionDock';
      dock.setAttribute('aria-label','Acción de investigación');
      host.appendChild(dock);
    }else if(dock.parentElement!==host){
      host.appendChild(dock);
    }

    if(button.parentElement!==dock){
      if(!movedButtonState.has(button)){
        movedButtonState.set(button,{parent:button.parentElement,next:button.nextSibling});
      }
      dock.appendChild(button);
    }
  }

  let resizeTimer=0;
  window.addEventListener('resize',()=>{
    window.clearTimeout(resizeTimer);
    resizeTimer=window.setTimeout(syncResearchActionDock,40);
  },{passive:true});

  document.addEventListener('click',event=>{
    const button=event.target instanceof Element?event.target.closest('button'):null;
    const label=normalize(button?.textContent);
    if(event.target instanceof Element&&(
      event.target.closest('#contextpage')
      ||label==='investigacion'
      ||label==='nueva investigacion'
    ))window.setTimeout(syncResearchActionDock,0);
  },true);

  syncResearchActionDock();
  window.setTimeout(syncResearchActionDock,80);
  window.setTimeout(syncResearchActionDock,350);
})();
