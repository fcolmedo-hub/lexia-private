/* LexIA UI2 — Windows-only guard for Study-file panel layout. */
(function(){
  'use strict';

  const SPACER_ID='lexiaWindowsStudyPackageSpacer';
  const STYLE_ID='lexiaWindowsStudyLayoutGuardStyle';

  function ensureStyle(){
    let style=document.getElementById(STYLE_ID);
    if(style)return;
    style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #contextpage #studyPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        height:auto!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0!important;
        padding-bottom:18px!important;
      }
      #contextpage #studyPanel .context-actions{
        display:flex!important;
        position:static!important;
        float:none!important;
        clear:both!important;
        width:100%!important;
        min-height:46px!important;
        margin:18px 0 0!important;
        padding:12px 0 0!important;
        transform:none!important;
        align-items:center!important;
      }
      #contextpage #studyPanel #startStudy{
        display:inline-flex!important;
        position:static!important;
        float:none!important;
        margin-left:auto!important;
        transform:none!important;
        visibility:visible!important;
      }
      #contextpage #${SPACER_ID}{
        display:block!important;
        width:100%!important;
        height:34px!important;
        min-height:34px!important;
        flex:0 0 34px!important;
        grid-column:1 / -1!important;
        clear:both!important;
        pointer-events:none!important;
      }
      #contextpage #${SPACER_ID} + .output-card,
      #contextpage #studyPanel ~ .output-card{
        position:relative!important;
        inset:auto!important;
        transform:none!important;
        clear:both!important;
        margin-top:0!important;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureSeparation(){
    ensureStyle();
    const panel=document.getElementById('studyPanel');
    if(!panel)return;

    const output=[...document.querySelectorAll('#contextpage .output-card')]
      .find(node=>node.compareDocumentPosition(panel)&Node.DOCUMENT_POSITION_PRECEDING);
    if(!output)return;

    let spacer=document.getElementById(SPACER_ID);
    if(!spacer){
      spacer=document.createElement('div');
      spacer.id=SPACER_ID;
      spacer.setAttribute('aria-hidden','true');
    }
    if(output.previousElementSibling!==spacer){
      output.parentNode.insertBefore(spacer,output);
    }
  }

  function init(){
    ensureSeparation();
    const context=document.getElementById('contextpage');
    if(context)new MutationObserver(ensureSeparation).observe(context,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','style','class']});
    window.addEventListener('resize',ensureSeparation,{passive:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
