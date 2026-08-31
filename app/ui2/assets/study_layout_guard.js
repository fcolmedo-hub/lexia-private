/* LexIA UI2 — shared Study-file layout guard for desktop app. */
(function(){
  'use strict';

  const STYLE_ID='lexiaStudyModeLayoutGuardStyle';
  const MODE_CLASS='lexia-study-mode';

  function ensureStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #contextpage .context-layout.${MODE_CLASS}{
        height:auto!important;
        min-height:calc(100vh - var(--global-top))!important;
        grid-template-rows:auto auto auto auto auto!important;
        overflow:visible!important;
      }
      #contextpage .context-layout.${MODE_CLASS}>#studyPanel{
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0!important;
      }
      #contextpage .context-layout.${MODE_CLASS}>#studyPanel .context-actions{
        display:flex!important;
        position:static!important;
        width:100%!important;
        margin:14px 0 0!important;
        padding:12px 0 0!important;
        align-items:center!important;
        justify-content:space-between!important;
        gap:12px!important;
      }
      #contextpage .context-layout.${MODE_CLASS}>#studyPanel #startStudy{
        position:static!important;
        float:none!important;
        flex:0 0 auto!important;
        margin:0!important;
        transform:none!important;
        align-self:center!important;
      }
      #contextpage .context-layout.${MODE_CLASS}>#studyPanel #studyStatus{
        position:relative!important;
        clear:both!important;
        margin-top:12px!important;
      }
      html body #contextpage>.main>.page.context-layout.${MODE_CLASS}>.output-card{
        position:relative!important;
        inset:auto!important;
        transform:none!important;
        overflow:visible!important;
        min-height:0!important;
        margin:18px 0 0!important;
      }
    `;
    document.head.appendChild(style);
  }

  function sync(){
    ensureStyle();
    const layout=document.querySelector('#contextpage .context-layout');
    const study=document.getElementById('studyPanel');
    if(!layout||!study)return;
    layout.classList.toggle(MODE_CLASS,!study.hidden);
  }

  function init(){
    sync();
    const context=document.getElementById('contextpage');
    if(context){
      new MutationObserver(sync).observe(context,{
        childList:true,
        subtree:true,
        attributes:true,
        attributeFilter:['hidden','class']
      });
    }
    window.addEventListener('resize',sync,{passive:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
