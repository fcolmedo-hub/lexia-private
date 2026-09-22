/* LexIA macOS — habilita las funciones de escritorio estabilizadas en Windows.
   Reutiliza capas event-driven; no observa el DOM ni ejecuta polling. */
(() => {
  'use strict';

  if (window.__lexiaMacosDesktopParityV1) return;
  window.__lexiaMacosDesktopParityV1 = true;

  // Compatibilidad con el renderer compartido de Casos. La bandera activa
  // multiselección, persistencia, agrupación y borrado individual en escritorio.
  window.__lexiaWindowsCaseEvidenceSelectionV2 = true;

  const scripts = [
    ['lexiaWindowsResearchResilience', 'assets/windows_research_transport_resilience.js?v=research-resilience-1'],
    ['lexiaWindowsResearchManualSources', 'assets/windows_research_manual_sources.js?v=research-manual-sources-1'],
    ['lexiaWindowsResearchManualSelectionFix', 'assets/windows_research_manual_selection_fix.js?v=manual-selection-5'],
    ['lexiaWindowsResearchManualSourcesMerge', 'assets/windows_research_manual_sources_merge.js?v=manual-sources-merge-6'],
    ['lexiaWindowsMaintenanceStatusDetail', 'assets/windows_maintenance_status_detail.js?v=maintenance-status-1'],
    ['lexiaWindowsMaintenanceDuplicates', 'assets/windows_maintenance_duplicates.js?v=maintenance-duplicates-2'],
    ['lexiaWindowsInvestigationLayout', 'assets/windows_investigation_layout_fix.js?v=investigation-layout-4'],
    ['lexiaWindowsResponsiveLayoutGuard', 'assets/windows_responsive_layout_guard.js?v=responsive-routes-1'],
    ['lexiaWindowsCaseResearchBridge', 'assets/windows_case_research_bridge.js?v=case-research-11'],
    ['lexiaWindowsCaseNavState', 'assets/windows_case_nav_state_fix.js?v=case-nav-2'],
    ['lexiaWindowsCaseResearchReturn', 'assets/windows_case_research_return.js?v=case-return-4'],
  ];

  scripts.forEach(([datasetKey, src]) => {
    const selector = 'script[data-' + datasetKey.replace(/[A-Z]/g, letter => '-' + letter.toLowerCase()) + ']';
    if (document.querySelector(selector)) return;
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset[datasetKey] = '1';
    (document.body || document.documentElement).appendChild(script);
  });

  // Paridad visual con los menús de acciones de Windows.
  const palette = {
    open: ['#dff3e7', '#c7e8d4', '#177245'],
    investigate: ['#5146f6', '#5146f6', '#ffffff'],
    case: ['#e5e0ff', '#d5ceff', '#3428c7'],
    details: ['#f0edff', '#dfd9ff', '#4036b4'],
    ocr: ['#ececf6', '#ddddea', '#59627a'],
    delete: ['#9a3b8f', '#9a3b8f', '#ffffff']
  };

  const actionKind = button => {
    const label = String(button?.textContent || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('es-AR');
    const classes = String(button?.className || '').toLocaleLowerCase('es-AR');
    const explicit = String(button?.getAttribute?.('data-lexia-file-action-kind') || '').trim();
    if (explicit && palette[explicit]) return explicit;
    if (button?.hasAttribute?.('data-lexia-search-investigate') || classes.includes('investigate') || label === 'estudiar' || label === 'investigar') return 'investigate';
    if (button?.matches?.('.search-open-file,.lexia-nav-open-file') || label.startsWith('abrir')) return 'open';
    if (button?.matches?.('.search-file-info') || label.includes('detalle')) return 'details';
    if (button?.matches?.('.search-delete-file') || label.startsWith('eliminar')) return 'delete';
    if (button?.matches?.('[data-lexia-case-link],.lexia-case-link') || label.includes('caso')) return 'case';
    if (classes.includes('ocr') || label.includes('ocr')) return 'ocr';
    return '';
  };

  const paintActions = scope => {
    const root = scope?.querySelectorAll ? scope : document;
    root.querySelectorAll(
      '.result-actions button, .lexia-result-actions button, .lexia-result-menu button, [role="menu"] button, #lexiaNavigatorFiles .search-delete-file, .lexia-nav-preview-actions .search-delete-file'
    ).forEach(button => {
      const colors = palette[actionKind(button)];
      if (!colors) return;
      button.style.setProperty('background', colors[0], 'important');
      button.style.setProperty('border-color', colors[1], 'important');
      button.style.setProperty('color', colors[2], 'important');
      const kind = actionKind(button);
      button.dataset.lexiaActionPalette = kind;
      if (kind === 'case' || kind === 'ocr') {
        const shade = kind === 'case' ? '#d5ceff' : '#dfd9ff';
        const ink = kind === 'case' ? '#3428c7' : '#5146a8';
        const border = kind === 'case' ? '#c9c2ff' : '#d2ccf4';
        [button, ...button.querySelectorAll('*')].forEach(part => {
          part.style.setProperty('background', shade, 'important');
          part.style.setProperty('background-image', 'none', 'important');
          part.style.setProperty('border-color', border, 'important');
          part.style.setProperty('color', ink, 'important');
        });
      }
    });
  };

  if (!document.getElementById('lexiaMacosVisualParityStyle')) {
    const style = document.createElement('style');
    style.id = 'lexiaMacosVisualParityStyle';
    style.textContent = `
      button[data-lexia-action-palette="case"]::before,
      button[data-lexia-action-palette="case"] > :first-child,
      button[data-lexia-action-palette="case"]::after,
      button[data-lexia-action-palette="case"] > *,
      button[data-lexia-action-palette="case"] > *::before,
      button[data-lexia-action-palette="case"] > *::after {
        background:#d5ceff!important;
        background-image:none!important;
        border-color:#c9c2ff!important;
        color:#3428c7!important;
      }
      button[data-lexia-action-palette="ocr"]::before,
      button[data-lexia-action-palette="ocr"] > :first-child,
      button[data-lexia-action-palette="ocr"]::after,
      button[data-lexia-action-palette="ocr"] > *,
      button[data-lexia-action-palette="ocr"] > *::before,
      button[data-lexia-action-palette="ocr"] > *::after {
        background:#dfd9ff!important;
        background-image:none!important;
        border-color:#d2ccf4!important;
        color:#5146a8!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2),
      #home .hr-lower>.hr-card:nth-child(-n+2) * {
        scrollbar-width:thin;
        scrollbar-color:transparent transparent;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2)::-webkit-scrollbar,
      #home .hr-lower>.hr-card:nth-child(-n+2) *::-webkit-scrollbar {
        width:4px;
        height:4px;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2)::-webkit-scrollbar-track,
      #home .hr-lower>.hr-card:nth-child(-n+2) *::-webkit-scrollbar-track {
        background:transparent;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2)::-webkit-scrollbar-thumb,
      #home .hr-lower>.hr-card:nth-child(-n+2) *::-webkit-scrollbar-thumb {
        border-radius:999px;
        background:transparent;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2):hover,
      #home .hr-lower>.hr-card:nth-child(-n+2):hover * {
        scrollbar-color:#b5adff transparent;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2):hover::-webkit-scrollbar-thumb,
      #home .hr-lower>.hr-card:nth-child(-n+2):hover *::-webkit-scrollbar-thumb {
        background:#b5adff;
      }
      #home .hr-lower>.hr-card:nth-child(1) .hr-row>i,
      #home .hr-lower>.hr-card:nth-child(2) .hr-row>i {
        font-size:0!important;
        background:#f0efff!important;
        color:#5146f6!important;
      }
      #home .hr-lower>.hr-card:nth-child(1) .hr-row>i::before {
        content:"⌕";
        font:800 17px/1 system-ui,-apple-system,"Segoe UI",sans-serif!important;
      }
      #home .hr-lower>.hr-card:nth-child(2) .hr-row>i::before {
        content:"▣";
        font:800 15px/1 system-ui,-apple-system,"Segoe UI",sans-serif!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-row>i.lexia-home-recent-icon::before {
        content:none!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .lexia-home-recent-icon svg {
        width:17px;
        height:17px;
        display:block;
        fill:none;
        stroke:currentColor;
        stroke-width:1.8;
        stroke-linecap:round;
        stroke-linejoin:round;
      }
      [data-lexia-standards-home]:hover,
      [data-lexia-standards-home]:focus-visible,
      [data-lexia-standards-home].active,
      [data-lexia-standards-home][aria-current="page"] {
        background:#f4f3ff!important;
        border-color:#d8d3ff!important;
      }

      /* Inicio macOS: el lienzo no debe desplazarse; sólo las listas recientes. */
      #home {
        height:100vh!important;
        min-height:0!important;
        overflow-x:hidden!important;
        overflow-y:hidden!important;
      }
      #home .home-real,
      #home .hr-main {
        height:100%!important;
        min-height:0!important;
        overflow:hidden!important;
      }
      #home .hr-content {
        box-sizing:border-box!important;
        height:100%!important;
        min-height:0!important;
        overflow:hidden!important;
        display:flex!important;
        flex-direction:column!important;
      }
      #home .hr-content>h1,
      #home .hr-content>.hr-sub,
      #home .hr-content>.hr-search,
      #home .hr-content>.hr-metrics,
      #home .hr-content>.footer {
        flex:0 0 auto!important;
      }
      #home .hr-lower {
        flex:1 1 0!important;
        min-height:0!important;
        overflow:hidden!important;
      }
      #home .hr-lower>.hr-card {
        height:auto!important;
        min-height:0!important;
        max-height:none!important;
        overflow:hidden!important;
        display:flex!important;
        flex-direction:column!important;
      }
      #home .hr-lower>.hr-card .hr-card-title {
        flex:0 0 38px!important;
      }
      #home .hr-lower>.hr-card .hr-scroll-list {
        flex:1 1 0!important;
        min-height:0!important;
        overflow-x:hidden!important;
        overflow-y:auto!important;
      }

      /* Iconos deterministas: no dependen de glifos ni del texto "?" heredado. */
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-row>i {
        font-size:0!important;
        color:transparent!important;
        background-color:#f0efff!important;
        background-repeat:no-repeat!important;
        background-position:center!important;
        background-size:18px 18px!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-row>i::before,
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-row>i::after {
        content:none!important;
        display:none!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-row>i svg {
        display:none!important;
      }
      #home .hr-lower>.hr-card:nth-child(1) .hr-row>i {
        background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235146f6' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 5.5A2.5 2.5 0 0 1 6.5 3H10a3 3 0 0 1 3 3v15a3 3 0 0 0-3-3H6.5A2.5 2.5 0 0 0 4 20.5z'/%3E%3Cpath d='M20 5.5A2.5 2.5 0 0 0 17.5 3H16a3 3 0 0 0-3 3v15a3 3 0 0 1 3-3h1.5a2.5 2.5 0 0 1 2.5 2.5z'/%3E%3C/svg%3E")!important;
      }
      #home .hr-lower>.hr-card:nth-child(2) .hr-row>i {
        background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235146f6' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 3h7l4 4v14H7z'/%3E%3Cpath d='M14 3v5h4'/%3E%3Cpath d='M10 12h5M10 16h5'/%3E%3C/svg%3E")!important;
      }
    `;
    document.head.appendChild(style);
  }

  paintActions(document);
  document.addEventListener('pointerover', event => {
    const card = event.target?.closest?.('#searchpage .result-card');
    if (card) paintActions(card);
  }, true);
  document.addEventListener('click', event => {
    const trigger = event.target?.closest?.(
      '.lexia-result-menu-trigger, .result-actions button, .lexia-result-menu button, [role="menu"] button'
    );
    if (!trigger) return;
    [0, 30, 100, 250, 500].forEach(delay => window.setTimeout(() => paintActions(document), delay));
  }, true);
})();
