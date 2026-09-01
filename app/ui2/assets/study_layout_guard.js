/* LexIA UI2 — shared Study-file layout guard for desktop app. */
(function(){
  'use strict';

  const STYLE_ID='lexiaStudyModeLayoutGuardStyle';
  const MODE_CLASS='lexia-study-mode';

  function ensureStyle(){
    let style=document.getElementById(STYLE_ID);
    if(!style){
      style=document.createElement('style');
      style.id=STYLE_ID;
      document.head.appendChild(style);
    }

    style.textContent=`
      /*
       * El layout base de Investigación usa filas rígidas.
       * En Estudiar archivo, al aparecer el resultado, output-card puede
       * terminar comprimido/superpuesto. En este modo dejamos que cada
       * bloque mida su contenido real.
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

      #contextpage .context-layout.${MODE_CLASS}>#researchPanel[hidden]{
        display:none!important;
      }

      #contextpage .context-layout.${MODE_CLASS}>#studyPanel:not([hidden]){
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

      #contextpage .context-layout.${MODE_CLASS}>#studyPanel .context-actions{
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

      #contextpage .context-layout.${MODE_CLASS}>#studyPanel .context-actions .hint{
        flex:1 1 auto!important;
        min-width:0!important;
        margin:0!important;
      }

      #contextpage .context-layout.${MODE_CLASS}>#studyPanel #startStudy{
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

      #contextpage .context-layout.${MODE_CLASS}>#studyPanel #studyStatus{
        position:relative!important;
        clear:both!important;
        margin-top:12px!important;
      }

      #contextpage .context-layout.${MODE_CLASS}>.output-card{
        display:block!important;
        position:relative!important;
        inset:auto!important;
        top:auto!important;
        right:auto!important;
        bottom:auto!important;
        left:auto!important;
        transform:none!important;
        float:none!important;
        clear:both!important;
        margin:0!important;
        overflow:visible!important;
        min-height:0!important;
        height:auto!important;
      }
    `;
  }

  function sync(){
    ensureStyle();

    const context=document.getElementById('contextpage');
    const layout=context?.querySelector('.context-layout');
    const study=document.getElementById('studyPanel');

    if(!layout||!study)return;

    const studyMode=!study.hidden;
    layout.classList.toggle(MODE_CLASS,studyMode);

    if(studyMode){
      const output=layout.querySelector(':scope > .output-card');
      if(output){
        output.style.removeProperty('top');
        output.style.removeProperty('right');
        output.style.removeProperty('bottom');
        output.style.removeProperty('left');
        output.style.removeProperty('transform');
        output.style.removeProperty('position');
      }
    }
  }

  function init(){
    sync();

    const context=document.getElementById('contextpage');
    if(context){
      new MutationObserver(sync).observe(context,{
        childList:true,
        subtree:true,
        attributes:true,
        attributeFilter:['hidden','style','class']
      });
    }

    document.getElementById('researchTab')
      ?.addEventListener('click',()=>setTimeout(sync,0),true);

    document.getElementById('studyTab')
      ?.addEventListener('click',()=>setTimeout(sync,0),true);

    window.addEventListener('resize',sync,{passive:true});
  }

  if(document.readyState==='loading')
    document.addEventListener('DOMContentLoaded',init,{once:true});
  else
    init();
})();
