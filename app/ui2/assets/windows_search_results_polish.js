/* LexIA Windows — ajuste tipográfico de resultados de búsqueda. */
(() => {
  'use strict';

  document.documentElement.classList.add('lexia-windows-search-polish');
  if (document.getElementById('lexiaWindowsSearchResultsPolish')) return;

  const style = document.createElement('style');
  style.id = 'lexiaWindowsSearchResultsPolish';
  style.textContent = `
    /* Búsqueda por nombre: jerarquía más liviana y legible. */
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:not(:has(.result-actions > .score)) .result-title {
      font-size:13px!important;
      font-weight:600!important;
      line-height:1.28!important;
      letter-spacing:-.005em!important;
      color:#202944!important;
    }
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

    /* Búsqueda por contenido: alinear el nombre con número y acciones. */
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) {
      padding-top:10px!important;
      padding-bottom:14px!important;
      align-items:start!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-body {
      padding-top:0!important;
      padding-bottom:4px!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-title {
      margin:0!important;
      line-height:1.28!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-meta {
      margin-top:3px!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-body > p {
      margin:7px 0 4px!important;
    }
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-path {
      margin:6px 0 2px!important;
      line-height:1.25!important;
    }
  `;
  document.head.appendChild(style);
})();
