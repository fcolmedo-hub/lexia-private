/* LexIA Windows — ajustes visuales aislados para Investigación.
   Sólo CSS: no observa el DOM ni modifica el flujo de investigación. */
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

    /* El formulario no debe recortar la fila que contiene Investigar. */
    html[data-lexia-app="1"] #contextpage .context-form{
      height:auto!important;
      min-height:0!important;
      max-height:none!important;
      overflow:visible!important;
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

      html[data-lexia-app="1"] #contextpage #researchPanel .context-actions button,
      html[data-lexia-app="1"] #contextpage .research-main-column .context-form .context-actions button{
        position:static!important;
        left:auto!important;
        right:auto!important;
        top:auto!important;
        bottom:auto!important;
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
