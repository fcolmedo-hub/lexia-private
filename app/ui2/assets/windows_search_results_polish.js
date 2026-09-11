/* LexIA Windows — ajuste tipográfico de resultados de búsqueda. */
(() => {
  'use strict';

  document.documentElement.classList.add('lexia-windows-search-polish');

  // Cargar una única corrección de Investigación exclusiva de Windows.
  // Es CSS puro: corrige el flujo compacto sin vigilancia continua del DOM.
  if (!document.querySelector('script[data-lexia-windows-investigation-layout]')) {
    const investigationLayout = document.createElement('script');
    investigationLayout.src = 'assets/windows_investigation_layout_fix.js?v=investigation-layout-4';
    investigationLayout.async = false;
    investigationLayout.dataset.lexiaWindowsInvestigationLayout = '1';
    (document.body || document.documentElement).appendChild(investigationLayout);
  }

  // Vinculación Casos -> Investigación. Está separada del motor de Investigación
  // y funciona sólo por acciones explícitas del usuario; no observa el DOM.
  if (!document.querySelector('script[data-lexia-windows-case-research-bridge]')) {
    const caseResearchBridge = document.createElement('script');
    caseResearchBridge.src = 'assets/windows_case_research_bridge.js?v=case-research-2';
    caseResearchBridge.async = false;
    caseResearchBridge.dataset.lexiaWindowsCaseResearchBridge = '1';
    (document.body || document.documentElement).appendChild(caseResearchBridge);
  }

  // El menú Casos es inyectado por un módulo distinto al navegador global.
  // Al saltar a Investigación se normaliza explícitamente el único estado activo.
  if (!document.querySelector('script[data-lexia-windows-case-nav-state]')) {
    const caseNavState = document.createElement('script');
    caseNavState.src = 'assets/windows_case_nav_state_fix.js?v=case-nav-1';
    caseNavState.async = false;
    caseNavState.dataset.lexiaWindowsCaseNavState = '1';
    (document.body || document.documentElement).appendChild(caseNavState);
  }

  // Devuelve las fuentes ya seleccionadas por el motor al bloque que originó
  // la investigación. Reutiliza la selección nativa del modal y no observa el DOM.
  if (!document.querySelector('script[data-lexia-windows-case-research-return]')) {
    const caseResearchReturn = document.createElement('script');
    caseResearchReturn.src = 'assets/windows_case_research_return.js?v=case-return-2';
    caseResearchReturn.async = false;
    caseResearchReturn.dataset.lexiaWindowsCaseResearchReturn = '1';
    (document.body || document.documentElement).appendChild(caseResearchReturn);
  }

  if (document.getElementById('lexiaWindowsSearchResultsPolish')) return;

  const style = document.createElement('style');
  style.id = 'lexiaWindowsSearchResultsPolish';
  style.textContent = `
    /* El nombre del archivo conserva la misma tipografía 800 de Contenido. */
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:not(:has(.result-actions > .score)) .result-meta {
      margin-top:1px!important;
      font-size:10.5px!important;
      font-weight:500!important;
      line-height:1.25!important;
      color:#596482!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:not(:has(.result-actions > .score)) .result-path {
      margin-top:2px!important;
      font-size:9px!important;
      line-height:1.2!important;
      color:#77819d!important;
    }

    /* En WebView2 la métrica vertical del botón deja el bloque de contenido
       seis píxeles más abajo que en macOS. Subimos el bloque completo para
       alinear el título con el número y recuperar aire debajo de la ruta. */
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-body {
      position:relative!important;
      top:-6px!important;
    }

    /* La tarjeta Estándares del menú principal debe responder igual que las
       demás tarjetas: fondo lavanda al pasar/seleccionar y navegación lateral
       marcada cuando Estándares está activo. */
    .lexia-windows-search-polish [data-lexia-standards-home]:hover,
    .lexia-windows-search-polish [data-lexia-standards-home]:focus-visible,
    .lexia-windows-search-polish [data-lexia-standards-home].active,
    .lexia-windows-search-polish [data-lexia-standards-home][aria-current="page"] {
      background:#f4f3ff!important;
      border-color:#d8d3ff!important;
    }
    .lexia-windows-search-polish .global-sidebar .nav [data-lexia-standards-nav].active {
      background:#efeeff!important;
      color:#2f25b8!important;
      box-shadow:inset 3px 0 0 #5146f6!important;
    }

    /* Acciones de las fuentes recuperadas por una investigación. */
    .lexia-windows-search-polish #contextpage .source-actions .study-source {
      background:#5146f6!important;
      border-color:#5146f6!important;
      color:#fff!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .study-source:hover {
      background:#4338e8!important;
      border-color:#4338e8!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-case-link {
      background:#8a5a2b!important;
      border-color:#8a5a2b!important;
      color:#fff!important;
      border-radius:6px!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-case-link:hover {
      background:#70451f!important;
      border-color:#70451f!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-ocr-reprocess {
      background:#e87514!important;
      border-color:#e87514!important;
      color:#fff!important;
      border-radius:6px!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-ocr-reprocess:hover {
      background:#c95e08!important;
      border-color:#c95e08!important;
    }
  `;
  document.head.appendChild(style);
})();