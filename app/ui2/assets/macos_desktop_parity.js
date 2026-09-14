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
      '#searchpage .result-actions button, #lexiaNavigatorFiles .search-delete-file, .lexia-nav-preview-actions .search-delete-file'
    ).forEach(button => {
      const colors = palette[actionKind(button)];
      if (!colors) return;
      button.style.setProperty('background', colors[0], 'important');
      button.style.setProperty('border-color', colors[1], 'important');
      button.style.setProperty('color', colors[2], 'important');
      const kind = actionKind(button);
      button.dataset.lexiaActionPalette = kind;
      const icon = button.firstElementChild;
      if ((kind === 'case' || kind === 'ocr') && icon) {
        icon.style.setProperty('background', kind === 'case' ? '#d5ceff' : '#dfd9ff', 'important');
        icon.style.setProperty('color', kind === 'case' ? '#3428c7' : '#5146a8', 'important');
        icon.style.setProperty('border-color', kind === 'case' ? '#c9c2ff' : '#d2ccf4', 'important');
      }
    });
  };

  if (!document.getElementById('lexiaMacosVisualParityStyle')) {
    const style = document.createElement('style');
    style.id = 'lexiaMacosVisualParityStyle';
    style.textContent = `
      #searchpage button[data-lexia-action-palette="case"]::before,
      #searchpage button[data-lexia-action-palette="case"] > :first-child,
      #searchpage button[data-lexia-action-palette="case"] > :first-child::before {
        background:#d5ceff!important;
        background-image:none!important;
        border-color:#c9c2ff!important;
        color:#3428c7!important;
      }
      #searchpage button[data-lexia-action-palette="ocr"]::before,
      #searchpage button[data-lexia-action-palette="ocr"] > :first-child,
      #searchpage button[data-lexia-action-palette="ocr"] > :first-child::before {
        background:#dfd9ff!important;
        background-image:none!important;
        border-color:#d2ccf4!important;
        color:#5146a8!important;
      }
      [data-lexia-standards-home]:hover,
      [data-lexia-standards-home]:focus-visible,
      [data-lexia-standards-home].active,
      [data-lexia-standards-home][aria-current="page"] {
        background:#f4f3ff!important;
        border-color:#d8d3ff!important;
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
      '#searchpage .lexia-result-menu-trigger, #searchpage .result-actions button'
    );
    if (!trigger) return;
    [0, 20, 80].forEach(delay => window.setTimeout(() => paintActions(document), delay));
  }, true);
})();
