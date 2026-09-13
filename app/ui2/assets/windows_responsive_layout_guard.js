/* LexIA Windows — contención responsive común para todas las rutas.
   Sólo instala estilos; no observa el DOM ni ejecuta tareas periódicas. */
(function(){
  'use strict';

  if(document.getElementById('lexiaWindowsResponsiveLayoutGuard'))return;
  const style=document.createElement('style');
  style.id='lexiaWindowsResponsiveLayoutGuard';
  style.textContent=`
    html[data-lexia-app="1"] :is(
      #home,#library,#searchpage,#contextpage,#activitypage,#systempage,
      #casespage,#maintenance,#lexiaStandardsShell
    ),
    html[data-lexia-app="1"] :is(
      #home,#library,#searchpage,#contextpage,#activitypage,#systempage,
      #casespage,#maintenance,#lexiaStandardsShell
    ) :is(.main,.page,.card,.panel,.context-grid,.search-grid,.contentgrid,
      .activity-grid,.system-grid,.workspace-layout,.maint-grid,.std-grid,.std-layout){
      min-width:0!important;max-width:100%;box-sizing:border-box!important
    }

    html[data-lexia-app="1"] :is(
      #home,#library,#searchpage,#contextpage,#activitypage,#systempage,
      #casespage,#maintenance,#lexiaStandardsShell
    ) :is(input,textarea,select,button,pre){
      min-width:0;max-width:100%;box-sizing:border-box
    }

    @media (min-width:1200px){
      html[data-lexia-app="1"] #lexiaStandardsShell{
        left:var(--global-side,224px)!important
      }
    }

    /* En monitores bajos el tablero fijo de Investigación deja sin altura al
       proceso y al paquete final. Se conserva la doble columna, pero el alto
       pasa a depender del contenido y la página usa un único scroll natural. */
    @media (min-width:1200px) and (max-height:950px){
      html[data-lexia-app="1"] #contextpage{
        height:auto!important;min-height:100dvh!important;overflow-y:auto!important
      }
      html[data-lexia-app="1"] #contextpage>.main{
        height:auto!important;min-height:100dvh!important;overflow:visible!important
      }
      html[data-lexia-app="1"] #contextpage .page.context-layout{
        display:block!important;height:auto!important;min-height:100dvh!important;
        max-height:none!important;overflow:visible!important;padding-bottom:18px!important
      }
      html[data-lexia-app="1"] #contextpage .investigation-tabs{
        margin:8px 0!important
      }
      html[data-lexia-app="1"] #contextpage #researchPanel:not([hidden]){
        display:grid!important;height:auto!important;min-height:0!important;
        max-height:none!important;overflow:visible!important;margin-top:8px!important
      }
      html[data-lexia-app="1"] #contextpage .research-main-column,
      html[data-lexia-app="1"] #contextpage .research-main-column>.context-form{
        height:auto!important;min-height:0!important;max-height:none!important;
        overflow:visible!important
      }
      html[data-lexia-app="1"] #contextpage .context-side{
        position:sticky!important;top:12px!important;height:auto!important;
        min-height:420px!important;max-height:calc(100dvh - 28px)!important;
        align-self:start!important;overflow:hidden!important
      }
      html[data-lexia-app="1"] #contextpage .context-side .source-list{
        min-height:0!important;max-height:calc(100dvh - 190px)!important;
        overflow-y:auto!important
      }
      html[data-lexia-app="1"] #contextpage>.main>.page.context-layout>.output-card{
        margin-top:12px!important;overflow:visible!important
      }
    }

    /* Anchos intermedios: ninguna columna puede imponer un ancho mayor que
       el lienzo disponible. Los breakpoints existentes deciden el apilado. */
    @media (max-width:1199px){
      html[data-lexia-app="1"] :is(#casespage,#maintenance,#lexiaStandardsShell){
        left:0!important;right:0!important;width:100vw!important;max-width:100vw!important
      }
      html[data-lexia-app="1"] :is(
        #library,#searchpage,#contextpage,#activitypage,#systempage
      )>.main{
        width:100%!important;max-width:100%!important;overflow-x:hidden!important
      }
    }

    /* En teléfono, los diálogos y sus acciones permanecen dentro del viewport. */
    @media (max-width:700px){
      html[data-lexia-app="1"] :is(dialog,.lexia-qv-modal,.lexia-sources-modal){
        max-width:calc(100vw - 16px)!important
      }
      html[data-lexia-app="1"] :is(
        .evidence-dialog-actions,.lexia-sources-foot,.maint-actions,.std-badges
      ){
        flex-wrap:wrap!important
      }
    }
  `;
  document.head.appendChild(style);
})();
