/* LexIA Windows — integra fragmentos manuales en la misma lista nativa de fuentes. */
(function(){
  'use strict';
  if(window.__lexiaWindowsResearchManualSourcesMergeV2)return;
  window.__lexiaWindowsResearchManualSourcesMergeV2=true;

  const STYLE_ID='lexiaWindowsResearchManualSourcesMergeStyleV2';
  const LIST_ID='researchSourcesModalList';
  const SOURCE_SECTION_ID='lexiaManualResearchModalSources';
  const SIDEBAR_ID='lexiaManualResearchSources';
  const ADD_BUTTON_ID='lexiaAddManualResearchSource';

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #${SOURCE_SECTION_ID}{display:none!important}
      #${SIDEBAR_ID}{display:none!important}

      #contextpage #viewSources,
      #contextpage #${ADD_BUTTON_ID}{
        width:100%!important;
        min-height:30px!important;
        height:auto!important;
        margin-top:7px!important;
        padding:6px 10px!important;
        border-radius:8px!important;
        font-size:10.5px!important;
        line-height:1.2!important;
        font-weight:700!important;
        box-sizing:border-box!important;
      }
      #contextpage #viewSources{
        border:1px solid #ddd9f2!important;
        background:#fff!important;
        color:#3f3a62!important;
      }
      #contextpage #${ADD_BUTTON_ID}{
        border:1px solid #bcb6ff!important;
        background:#f7f6ff!important;
        color:#352bc7!important;
      }
      #contextpage #${ADD_BUTTON_ID}:hover{background:#efedff!important;border-color:#9f97ff!important}

      #${LIST_ID} .research-source-check{accent-color:#5146f6}
      #${LIST_ID} .lexia-manual-source-inline{
        border:1px solid #bfe5cf!important;
        background:#f4fbf7!important;
        box-shadow:none!important;
      }
      #${LIST_ID} .lexia-manual-source-inline .lexia-manual-source-check{
        accent-color:#169b62!important;
      }
      #${LIST_ID} .lexia-manual-source-inline .lexia-manual-inline-number{
        display:block;margin:0 0 3px;font-size:9px;line-height:1.1;font-weight:900;
        letter-spacing:.035em;color:#168054!important;
      }
      #${LIST_ID} .lexia-manual-source-inline b{color:#177245!important}
      #${LIST_ID} .lexia-manual-source-inline small{color:#3f7d60!important}
      #${LIST_ID} .lexia-manual-source-inline p{color:#475c50!important}
      #${LIST_ID} .lexia-manual-source-inline button[data-manual-remove]{
        border-color:#b8ddc7!important;background:#fff!important;color:#177245!important;
      }
    `;
    document.head.appendChild(style);
  }

  function merge(){
    installStyle();
    const list=document.getElementById(LIST_ID);
    const source=document.getElementById(SOURCE_SECTION_ID);
    if(!list||!source)return false;

    /* Sólo quitamos nuestras copias anteriores. Las fuentes halladas por LexIA
       nunca se eliminan ni se reemplazan. */
    list.querySelectorAll('.lexia-manual-source-inline').forEach(node=>node.remove());

    const nativeChecks=[...list.querySelectorAll('.research-source-check')]
      .filter(check=>!check.closest('.lexia-manual-source-inline'));
    const nativeCount=nativeChecks.length;
    const choices=[...source.querySelectorAll('.lexia-manual-source-choice')];

    choices.forEach((choice,index)=>{
      const clone=choice.cloneNode(true);
      clone.classList.add('lexia-manual-source-inline');
      clone.dataset.lexiaManualInline='1';
      const content=clone.querySelector('span');
      if(content){
        const number=document.createElement('span');
        number.className='lexia-manual-inline-number';
        number.textContent='FUENTE '+(nativeCount+index+1)+' · AGREGADA POR EL USUARIO';
        content.insertBefore(number,content.firstChild);
      }
      list.appendChild(clone);
    });
    return true;
  }

  function burst(){[0,80,220,520,1000,1800,3000].forEach(delay=>window.setTimeout(merge,delay));}

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(!target)return;
    if(target.closest('#reviewResearchSources,#viewSources,#lexiaAddManualResearchSource,[data-add-selection],[data-manual-remove]'))burst();
  },true);
  document.addEventListener('change',event=>{
    const target=event.target instanceof Element?event.target:null;
    if(target?.matches('.research-source-check,.lexia-manual-source-check'))window.setTimeout(merge,0);
  },true);

  [0,200,700,1500].forEach(delay=>window.setTimeout(merge,delay));
  window.lexiaMergeManualResearchSources=merge;
})();
