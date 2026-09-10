/* LexIA Windows — ajuste tipográfico de resultados de búsqueda. */
(() => {
  'use strict';

  document.documentElement.classList.add('lexia-windows-search-polish');
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
  `;
  document.head.appendChild(style);
})();
