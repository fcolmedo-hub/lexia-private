/* LexIA Windows — ajuste tipográfico de resultados de búsqueda. */
(() => {
  'use strict';

  document.documentElement.classList.add('lexia-windows-search-polish');

  if (!document.querySelector('script[data-lexia-windows-research-resilience]')) {
    const researchResilience = document.createElement('script');
    researchResilience.src = 'assets/windows_research_transport_resilience.js?v=research-resilience-1';
    researchResilience.async = false;
    researchResilience.dataset.lexiaWindowsResearchResilience = '1';
    (document.body || document.documentElement).appendChild(researchResilience);
  }

  if (!document.querySelector('script[data-lexia-windows-research-manual-sources]')) {
    const manualSources = document.createElement('script');
    manualSources.src = 'assets/windows_research_manual_sources.js?v=research-manual-sources-1';
    manualSources.async = false;
    manualSources.dataset.lexiaWindowsResearchManualSources = '1';
    (document.body || document.documentElement).appendChild(manualSources);
  }

  if (!document.querySelector('script[data-lexia-windows-investigation-layout]')) {
    const investigationLayout = document.createElement('script');
    investigationLayout.src = 'assets/windows_investigation_layout_fix.js?v=investigation-layout-4';
    investigationLayout.async = false;
    investigationLayout.dataset.lexiaWindowsInvestigationLayout = '1';
    (document.body || document.documentElement).appendChild(investigationLayout);
  }

  if (!document.querySelector('script[data-lexia-windows-case-research-bridge]')) {
    const caseResearchBridge = document.createElement('script');
    caseResearchBridge.src = 'assets/windows_case_research_bridge.js?v=case-research-2';
    caseResearchBridge.async = false;
    caseResearchBridge.dataset.lexiaWindowsCaseResearchBridge = '1';
    (document.body || document.documentElement).appendChild(caseResearchBridge);
  }

  if (!document.querySelector('script[data-lexia-windows-case-nav-state]')) {
    const caseNavState = document.createElement('script');
    caseNavState.src = 'assets/windows_case_nav_state_fix.js?v=case-nav-1';
    caseNavState.async = false;
    caseNavState.dataset.lexiaWindowsCaseNavState = '1';
    (document.body || document.documentElement).appendChild(caseNavState);
  }

  if (!document.querySelector('script[data-lexia-windows-case-research-return]')) {
    const caseResearchReturn = document.createElement('script');
    caseResearchReturn.src = 'assets/windows_case_research_return.js?v=case-return-2';
    caseResearchReturn.async = false;
    caseResearchReturn.dataset.lexiaWindowsCaseResearchReturn = '1';
    (document.body || document.documentElement).appendChild(caseResearchReturn);
  }

  if (!window.__lexiaWindowsStudyActionLabelInstalled) {
    window.__lexiaWindowsStudyActionLabelInstalled = true;
    const syncStudyLabels = scope => {
      const root = scope?.querySelectorAll ? scope : document;
      root.querySelectorAll(
        '[data-lexia-search-investigate="1"], .search-investigate-file, [data-lexia-file-action-kind="investigate"]'
      ).forEach(study => {
        const label = String(study.textContent || '').trim().toLocaleLowerCase('es-AR');
        if (label === 'investigar' || label === 'estudiar') study.textContent = 'Estudiar';
        study.title = 'Cargar este archivo en Estudiar';
      });
    };
    const burst = scope => {
      [0, 80, 220, 500, 1000, 1800, 3200].forEach(delay => {
        window.setTimeout(() => syncStudyLabels(scope || document), delay);
      });
    };
    burst(document);
    document.addEventListener('pointerover', event => {
      const card = event.target?.closest?.('#searchpage .result-card');
      if (card) syncStudyLabels(card);
    }, true);
    document.addEventListener('click', event => {
      const card = event.target?.closest?.('#searchpage .result-card');
      if (card) syncStudyLabels(card);
      if (event.target?.closest?.('#searchpage button, #searchpage [role="tab"], #searchpage .tab')) burst(document);
    }, true);
  }

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

  const paintButton = button => {
    const kind = actionKind(button);
    const colors = palette[kind];
    if (!colors) return;
    button.style.setProperty('background', colors[0], 'important');
    button.style.setProperty('border-color', colors[1], 'important');
    button.style.setProperty('color', colors[2], 'important');
  };

  const paintActions = scope => {
    const root = scope?.querySelectorAll ? scope : document;
    root.querySelectorAll('#searchpage .result-actions button, #lexiaNavigatorFiles .search-delete-file, .lexia-nav-preview-actions .search-delete-file').forEach(paintButton);
  };

  paintActions(document);
  document.addEventListener('pointerover', event => {
    const card = event.target?.closest?.('#searchpage .result-card');
    if (card) paintActions(card);
  }, true);
  document.addEventListener('click', event => {
    const menuTrigger = event.target?.closest?.('#searchpage .lexia-result-menu-trigger, #searchpage .result-actions button');
    if (!menuTrigger) return;
    const card = menuTrigger.closest?.('.result-card') || document;
    [0, 20, 80].forEach(delay => window.setTimeout(() => paintActions(card), delay));
  }, true);

  if (document.getElementById('lexiaWindowsSearchResultsPolish')) return;

  const style = document.createElement('style');
  style.id = 'lexiaWindowsSearchResultsPolish';
  style.textContent = `
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
    .lexia-windows-search-polish #searchpage #realSearchResults
      .result-card:has(.result-actions > .score) .result-body {
      position:relative!important;
      top:-6px!important;
    }
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
      background:#e5e0ff!important;
      border-color:#d5ceff!important;
      color:#3428c7!important;
      border-radius:6px!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-case-link:hover {
      background:#d8d1ff!important;
      border-color:#c4bcff!important;
      color:#2f25b8!important;
    }
    .lexia-windows-search-polish #contextpage .source-actions .lexia-ocr-reprocess {
      display:none!important;
    }
  `;
  document.head.appendChild(style);
})();
