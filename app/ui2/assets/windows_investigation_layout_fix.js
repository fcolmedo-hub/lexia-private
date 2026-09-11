/* LexIA Windows — ajustes visuales aislados para Investigación.
   Sin observación continua del DOM: en ventana compacta se recoloca el bloque
   de acciones de Investigación y se conserva su funcionamiento original. */
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
      min-height:48px!important;
      display:block!important;
      margin:10px 0 0!important;
      padding:6px 0 0!important;
      overflow:visible!important;
      clear:both!important;
    }
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock .context-actions{
      box-sizing:border-box!important;
      position:static!important;
      inset:auto!important;
      float:none!important;
      transform:none!important;
      display:flex!important;
      visibility:visible!important;
      opacity:1!important;
      width:100%!important;
      min-width:0!important;
      min-height:42px!important;
      height:auto!important;
      max-height:none!important;
      margin:0!important;
      padding:8px 0 0!important;
      overflow:visible!important;
      flex-wrap:wrap!important;
      align-items:center!important;
      justify-content:flex-end!important;
      gap:8px!important;
    }
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock .context-actions .hint{
      flex:1 1 280px!important;
      min-width:0!important;
      margin:0!important;
    }
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock button,
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock input[type="button"],
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock input[type="submit"],
    html[data-lexia-app="1"] #lexiaWindowsResearchActionDock [role="button"]{
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

  const movedState=new WeakMap();
  const normalize=value=>String(value||'')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ').trim().toLowerCase();

  function researchPanel(){
    const panel=document.getElementById('researchPanel');
    return panel&&!panel.hidden?panel:null;
  }

  function mainResearchActionNode(){
    const panel=researchPanel();
    if(!panel)return null;

    const explicit=panel.querySelector('.context-actions')
      ||document.querySelector('#contextpage .research-main-column .context-actions');
    if(explicit&&!explicit.closest('#studyPanel,.source-actions,.lexia-sources-modal'))return explicit;

    const form=panel.querySelector('.context-form')||panel;
    const candidates=[...form.querySelectorAll(
      '#startResearch,#runResearch,#buildContext,button.primary,input.primary,[role="button"].primary,button,input[type="button"],input[type="submit"],[role="button"]'
    )];
    return candidates.find(control=>{
      if(control.closest('#studyPanel,.source-actions,.lexia-sources-modal,.head-actions,.investigation-tabs'))return false;
      const label=normalize(
        control.textContent||control.value||control.getAttribute('aria-label')||control.getAttribute('title')
      );
      const identity=normalize((control.id||'')+' '+(control.className||''));
      return label==='investigar'||label.startsWith('investigar ')||/(start|run|build).*(research|context)|(research|context).*(start|run|build)/.test(identity);
    })||null;
  }

  function restoreNode(node){
    const state=movedState.get(node);
    if(!state)return;
    const {parent,next}=state;
    if(parent&&parent.isConnected){
      if(next&&next.parentNode===parent)parent.insertBefore(node,next);
      else parent.appendChild(node);
    }
    movedState.delete(node);
    document.getElementById('lexiaWindowsResearchActionDock')?.remove();
  }

  function syncResearchActionDock(){
    const existingDock=document.getElementById('lexiaWindowsResearchActionDock');
    const panel=researchPanel();
    if(!panel){
      const moved=existingDock?.firstElementChild;
      if(moved)restoreNode(moved);
      else existingDock?.remove();
      return false;
    }

    const node=mainResearchActionNode();
    if(!node)return false;

    if(window.innerWidth>1199){
      restoreNode(node);
      return true;
    }

    const host=panel.querySelector('.context-form')
      ||panel.querySelector('.research-main-column')
      ||panel;
    if(!host)return false;

    let dock=existingDock;
    if(!dock){
      dock=document.createElement('div');
      dock.id='lexiaWindowsResearchActionDock';
      dock.setAttribute('aria-label','Acción de investigación');
      host.appendChild(dock);
    }else if(dock.parentElement!==host){
      host.appendChild(dock);
    }

    if(node.parentElement!==dock){
      if(!movedState.has(node))movedState.set(node,{parent:node.parentElement,next:node.nextSibling});
      dock.appendChild(node);
    }
    return true;
  }

  function syncBurst(){
    [0,80,220,500,900,1500,2400].forEach(delay=>window.setTimeout(syncResearchActionDock,delay));
  }

  let resizeTimer=0;
  window.addEventListener('resize',()=>{
    window.clearTimeout(resizeTimer);
    resizeTimer=window.setTimeout(syncResearchActionDock,50);
  },{passive:true});

  document.getElementById('researchTab')?.addEventListener('click',syncBurst,true);
  document.getElementById('studyTab')?.addEventListener('click',syncBurst,true);

  document.addEventListener('click',event=>{
    const button=event.target instanceof Element?event.target.closest('button'):null;
    const label=normalize(button?.textContent);
    if(label==='investigacion'||label==='nueva investigacion'||label==='investigacion juridica')syncBurst();
  },true);

  syncBurst();
})();
