/* LexIA Windows — ajustes visuales aislados para Investigación.
   Sólo corrige geometría responsive y el selector de fuentes. No observa ni
   reescribe continuamente el DOM de Investigación. */
(function(){
  'use strict';

  if(document.getElementById('lexiaWindowsInvestigationLayoutFix'))return;
  const style=document.createElement('style');
  style.id='lexiaWindowsInvestigationLayoutFix';
  style.textContent=`
    html[data-lexia-app="1"] #contextpage .context-form,
    html[data-lexia-app="1"] #contextpage #researchPanel,
    html[data-lexia-app="1"] #contextpage .research-main-column,
    html[data-lexia-app="1"] #contextpage .context-side,
    html[data-lexia-app="1"] #contextpage .context-grid{
      min-width:0!important;
      max-width:100%!important;
      box-sizing:border-box!important;
    }

    /* Entre 701 y 1199 px la UI base ya pasa a una sola columna, pero conserva
       alturas de escritorio. Eso hace que Objetivo/Indicaciones y la acción
       Investigar queden por debajo del track visible, mientras Fuentes
       encontradas empieza antes y los tapa. En este rango toda la investigación
       vuelve a flujo natural: primero el formulario completo y después fuentes. */
    @media (min-width:701px) and (max-width:1199px){
      html[data-lexia-app="1"] #contextpage .page.context-layout{
        display:block!important;
        width:100%!important;
        max-width:100%!important;
        height:auto!important;
        min-height:calc(100dvh - var(--global-top,0px))!important;
        max-height:none!important;
        overflow:visible!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel:not([hidden]){
        display:block!important;
        position:relative!important;
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        margin:0 0 12px!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-grid{
        display:flex!important;
        flex-direction:column!important;
        align-items:stretch!important;
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
        gap:12px!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .research-main-column{
        order:1!important;
        display:block!important;
        position:relative!important;
        inset:auto!important;
        float:none!important;
        transform:none!important;
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-form{
        display:flex!important;
        flex-direction:column!important;
        position:relative!important;
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:visible!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-form > *{
        flex:0 0 auto!important;
        min-width:0!important;
        max-width:100%!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-actions{
        display:flex!important;
        position:static!important;
        inset:auto!important;
        float:none!important;
        clear:both!important;
        transform:none!important;
        visibility:visible!important;
        opacity:1!important;
        width:100%!important;
        min-width:0!important;
        min-height:44px!important;
        height:auto!important;
        max-height:none!important;
        margin:14px 0 0!important;
        padding:10px 0 0!important;
        overflow:visible!important;
        flex-wrap:wrap!important;
        align-items:center!important;
        justify-content:space-between!important;
        gap:8px!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-actions .hint{
        flex:1 1 260px!important;
        min-width:0!important;
        margin:0!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-actions button,
      html[data-lexia-app="1"] #contextpage #researchPanel #startResearch,
      html[data-lexia-app="1"] #contextpage #researchPanel #runResearch,
      html[data-lexia-app="1"] #contextpage #researchPanel #buildContext{
        display:inline-flex!important;
        position:static!important;
        inset:auto!important;
        float:none!important;
        transform:none!important;
        visibility:visible!important;
        opacity:1!important;
        width:auto!important;
        min-width:118px!important;
        max-width:100%!important;
        min-height:38px!important;
        margin:0 0 0 auto!important;
        align-items:center!important;
        justify-content:center!important;
        flex:0 0 auto!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-side{
        order:2!important;
        display:block!important;
        position:relative!important;
        inset:auto!important;
        float:none!important;
        clear:both!important;
        transform:none!important;
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        margin:0!important;
        overflow:visible!important;
      }

      html[data-lexia-app="1"] #contextpage #researchPanel .context-side .source-list{
        max-height:380px!important;
        overflow-y:auto!important;
      }
    }

    /* En escritorio el selector de fuentes debe centrarse en el área útil,
       no en el viewport completo que también contiene la barra lateral. */
    @media (min-width:1200px){
      html[data-lexia-app="1"] .lexia-sources-modal{
        box-sizing:border-box!important;
        width:min(880px,calc(100vw - var(--global-side,196px) - 28px))!important;
        max-width:calc(100vw - var(--global-side,196px) - 28px)!important;
        max-height:calc(100dvh - 28px)!important;
        translate:98px 0!important;
      }
    }

    /* Con drawer/hamburguesa no se reserva espacio lateral. */
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
})();
