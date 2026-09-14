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
    ['lexiaWindowsResearchManualSelectionFix', 'assets/windows_research_manual_selection_fix.js?v=manual-selection-3'],
    ['lexiaWindowsResearchManualSourcesMerge', 'assets/windows_research_manual_sources_merge.js?v=manual-sources-merge-6'],
    ['lexiaWindowsMaintenanceStatusDetail', 'assets/windows_maintenance_status_detail.js?v=maintenance-status-1'],
    ['lexiaWindowsMaintenanceDuplicates', 'assets/windows_maintenance_duplicates.js?v=maintenance-duplicates-2'],
    ['lexiaWindowsInvestigationLayout', 'assets/windows_investigation_layout_fix.js?v=investigation-layout-4'],
    ['lexiaWindowsResponsiveLayoutGuard', 'assets/windows_responsive_layout_guard.js?v=responsive-routes-1'],
    ['lexiaWindowsCaseResearchBridge', 'assets/windows_case_research_bridge.js?v=case-research-7'],
    ['lexiaWindowsCaseNavState', 'assets/windows_case_nav_state_fix.js?v=case-nav-2'],
    ['lexiaWindowsCaseResearchReturn', 'assets/windows_case_research_return.js?v=case-return-3'],
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
})();
