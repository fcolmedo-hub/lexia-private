/* LexIA UI2 — Windows-only guard for Study-file panel layout. */
(function(){
  'use strict';

  const STYLE_ID='lexiaWindowsStudyLayoutGuardStyle';
  const MODE_CLASS='lexia-windows-study-mode';
  const OLD_SPACER_ID='lexiaWindowsStudyPackageSpacer';

  function removeOldSpacer(){
    document.getElementById(OLD_SPACER_ID)?.remove();
  }

  function ensureStyle(){
    let style=document.getElementById(STYLE_ID);
    if(!style){
      style=document.createElement('style');
      style.id=STYLE_ID;
      document.head.appendChild(style);
    }
    style.textContent=`
      /*
       * index.html 3.3.3a usa cinco filas fijas para Investigación jurídica:
       * auto auto minmax(0,1fr) auto 0.
       * Al mostrar studyPanel cambia la lista de hijos visibles y output-card
       * termina en la fila de altura 0. En modo Estudiar anulamos solamente
       * ese esquema y dejamos que studyPanel + output-card midan su contenido.
       */
      #contextpage .context-layout.${MODE_CLASS}{
        height:auto!important;
        min-height:calc(100vh - var(--global-top))!important;
        display:grid!important;
        grid-template-rows:auto auto auto auto auto!important;
        align-content:start!important;
        overflow:visible!important;
        gap:10px!important;
        padding-bottom:18px!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #researchPanel[hidden]{
        display:none!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #studyPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0!important;
        padding-bottom:16px!important;
        box-sizing:border-box!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #studyPanel .context-actions{
        display:flex!important;
        position:static!important;
        float:none!important;
        clear:both!important;
        width:100%!important;
        min-height:44px!important;
        margin:16px 0 0!important;
        padding:12px 0 0!important;
        transform:none!important;
        align-items:center!important;
        justify-content:space-between!important;
        gap:12px!important;
        box-sizing:border-box!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #studyPanel .context-actions .hint{
        flex:1 1 auto!important;
        min-width:0!important;
        margin:0!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #studyPanel #startStudy{
        display:inline-flex!important;
        position:static!important;
        float:none!important;
        flex:0 0 auto!important;
        margin:0!important;
        transform:none!important;
        visibility:visible!important;
        align-items:center!important;
        justify-content:center!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > #studyPanel #studyStatus{
        position:relative!important;
        clear:both!important;
        margin-top:12px!important;
      }

      #contextpage .context-layout.${MODE_CLASS} > .output-card{
        position:relative!important;
        inset:auto!important;
        transform:none!important;
        clear:both!important;
        margin:0!important;
        overflow:visible!important;
        min-height:0!important;
      }
    `;
  }

  function syncStudyMode(){
    removeOldSpacer();
    ensureStyle();

    const context=document.getElementById('contextpage');
    const layout=context?.querySelector('.context-layout');
    const panel=document.getElementById('studyPanel');
    if(!layout||!panel)return;

    const studyMode=!panel.hidden;
    layout.classList.toggle(MODE_CLASS,studyMode);

    if(studyMode){
      const output=layout.querySelector(':scope > .output-card');
      if(output){
        output.style.removeProperty('top');
        output.style.removeProperty('bottom');
        output.style.removeProperty('transform');
      }
    }
  }

  function init(){
    syncStudyMode();
    const context=document.getElementById('contextpage');
    if(context){
      new MutationObserver(syncStudyMode).observe(context,{
        childList:true,
        subtree:true,
        attributes:true,
        attributeFilter:['hidden','style','class']
      });
    }
    document.getElementById('researchTab')?.addEventListener('click',()=>setTimeout(syncStudyMode,0),true);
    document.getElementById('studyTab')?.addEventListener('click',()=>setTimeout(syncStudyMode,0),true);
    window.addEventListener('resize',syncStudyMode,{passive:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
