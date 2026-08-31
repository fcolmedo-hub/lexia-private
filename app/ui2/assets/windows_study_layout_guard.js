/* LexIA UI2 — Windows-only guard for Study-file panel layout. */
(function(){
  'use strict';

  const STYLE_ID='lexiaWindowsStudyLayoutGuardStyle';
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
      #contextpage #studyPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0 0 18px 0!important;
        padding-bottom:16px!important;
        box-sizing:border-box!important;
      }
      #contextpage #studyPanel .context-actions{
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
      #contextpage #studyPanel .context-actions .hint{
        flex:1 1 auto!important;
        min-width:0!important;
        margin:0!important;
      }
      #contextpage #studyPanel #startStudy{
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
      #contextpage #studyStatus{
        position:relative!important;
        clear:both!important;
        margin-top:12px!important;
      }
      #contextpage #studyPanel + .output-card,
      #contextpage #studyPanel ~ .output-card{
        position:relative!important;
        inset:auto!important;
        transform:none!important;
        clear:both!important;
        margin-top:18px!important;
      }
    `;
  }

  function keepOutputVisible(){
    removeOldSpacer();
    ensureStyle();
    const panel=document.getElementById('studyPanel');
    if(!panel)return;

    const outputs=[...document.querySelectorAll('#contextpage .output-card')];
    for(const output of outputs){
      const relation=panel.compareDocumentPosition(output);
      if(relation&Node.DOCUMENT_POSITION_FOLLOWING){
        output.style.removeProperty('top');
        output.style.removeProperty('bottom');
        output.style.removeProperty('transform');
      }
    }
  }

  function init(){
    keepOutputVisible();
    const context=document.getElementById('contextpage');
    if(context){
      new MutationObserver(keepOutputVisible).observe(context,{
        childList:true,
        subtree:true,
        attributes:true,
        attributeFilter:['hidden','style','class']
      });
    }
    window.addEventListener('resize',keepOutputVisible,{passive:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
