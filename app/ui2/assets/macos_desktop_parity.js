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
    ocr: ['#ece9ff', '#ddd6ff', '#4b3fbd'],
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

  const forcedActionIcons = {
    case: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h7l2 2H20v11H4z"/><path d="M8 13h8M13 9l4 4-4 4"/></svg>',
    ocr: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 8V4l-2 2a7 7 0 1 0 1.7 7"/><path d="M19 4h-4"/></svg>'
  };

  const forceLavenderActionIcon = (button, kind) => {
    if (kind !== 'case' && kind !== 'ocr') return;
    const label = kind === 'case' ? 'Agregar al caso' : 'Reprocesar OCR';
    let icon = button.querySelector(':scope > .lexia-forced-action-icon');
    if (!icon) {
      icon = document.createElement('span');
      icon.className = 'lexia-forced-action-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = forcedActionIcons[kind];
      const text = document.createElement('span');
      text.className = 'lexia-forced-action-label';
      text.textContent = label;
      // Elimina el emoji original, cuyo amarillo forma parte del propio glifo
      // y no puede cambiarse con background/color.
      button.replaceChildren(icon, text);
    }
  };

  const paintActions = scope => {
    const root = scope?.querySelectorAll ? scope : document;
    root.querySelectorAll(
      '.result-actions button, .lexia-result-actions button, .lexia-result-menu button, [role="menu"] button, #lexiaNavigatorFiles .search-delete-file, .lexia-nav-preview-actions .search-delete-file'
    ).forEach(button => {
      const kind = actionKind(button);
      const colors = palette[kind];
      if (!colors) return;
      forceLavenderActionIcon(button, kind);
      button.style.setProperty('background', colors[0], 'important');
      button.style.setProperty('background-image', 'none', 'important');
      button.style.setProperty('border-color', colors[1], 'important');
      button.style.setProperty('color', colors[2], 'important');
      button.dataset.lexiaActionPalette = kind;
    });
  };

  const normalizedText = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('es-AR');

  const recentIcons = {
    research: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4.5 4.5M17.5 3.5v3M16 5h3"/></svg>',
    document: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h8l4 4V20H6z"/><path d="M14 3.5V8h4M9 12h6M9 15.5h6"/></svg>'
  };

  const recentPanel = title => {
    const wanted = normalizedText(title);
    const headings = document.querySelectorAll(
      '#home h1,#home h2,#home h3,#home h4,#home h5,#home h6,#home [class*="title"]'
    );
    const heading = [...headings].find(node => normalizedText(node.textContent) === wanted);
    if (!heading) return null;
    const exact = heading.closest(
      '.hr-card,.home-card,.dashboard-card,.recent-card,.card'
    );
    if (exact) return exact;
    let node = heading.parentElement;
    const home = document.getElementById('home');
    while (node && node !== home) {
      const rows = node.querySelectorAll(
        'li,a,[role="listitem"],[class*="recent-item"],[class*="recent-row"]'
      );
      if (rows.length >= 2) return node;
      node = node.parentElement;
    }
    return heading.parentElement;
  };

  const replaceRecentIcon = (host, kind) => {
    if (!host || host.dataset.lexiaRecentIcon === kind) return;
    host.dataset.lexiaRecentIcon = kind;
    host.classList.add('lexia-home-recent-icon');
    host.setAttribute('aria-hidden', 'true');
    host.replaceChildren();
    host.insertAdjacentHTML('afterbegin', recentIcons[kind]);
  };

  const polishRecentPanel = (panel, kind) => {
    if (!panel) return;
    [...panel.querySelectorAll('*')].forEach(node => {
      let overflow = '';
      try { overflow = window.getComputedStyle(node).overflowY; } catch (_) {}
      if (/auto|scroll/.test(overflow) || node.scrollHeight > node.clientHeight + 4) {
        node.classList.add('lexia-home-recent-scroll');
      }
    });

    const rows = panel.querySelectorAll(
      'li,a,button,[role="listitem"],[class*="recent-item"],[class*="recent-row"],[class*="document-item"],[class*="query-item"]'
    );
    rows.forEach(row => {
      const candidates = [...row.querySelectorAll('span,div,i')];
      let host = candidates.find(node => {
        const text = normalizedText(node.textContent);
        const classes = normalizedText(node.className);
        return (node.children.length === 0 && text === '?') ||
          (/icon|glyph|avatar/.test(classes) && text.length <= 2);
      });
      if (!host) {
        const first = row.firstElementChild;
        if (first) {
          const box = first.getBoundingClientRect();
          if (box.width >= 20 && box.width <= 48 && box.height >= 20 && box.height <= 48) {
            host = first;
          }
        }
      }
      replaceRecentIcon(host, kind);
    });

    // Fallback para filas del HTML local que no exponen una clase propia.
    [...panel.querySelectorAll('*')]
      .filter(node => node.children.length === 0 && normalizedText(node.textContent) === '?')
      .forEach(node => replaceRecentIcon(node, kind));
  };

  const polishHomeRecents = () => {
    polishRecentPanel(recentPanel('Consultas recientes de Investigación'), 'research');
    polishRecentPanel(recentPanel('Documentos recientes'), 'document');
  };

  const scheduleHomeRecents = () => {
    [0, 80, 220, 600, 1200].forEach(delay =>
      window.setTimeout(polishHomeRecents, delay)
    );
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
      button[data-lexia-action-palette="case"]::before,
      button[data-lexia-action-palette="case"]::after,
      button[data-lexia-action-palette="ocr"]::before,
      button[data-lexia-action-palette="ocr"]::after {
        content:none!important;
        display:none!important;
      }
      .lexia-forced-action-icon {
        display:inline-flex!important;
        align-items:center!important;
        justify-content:center!important;
        flex:0 0 20px!important;
        width:20px!important;
        height:20px!important;
        padding:0!important;
        border:0!important;
        border-radius:6px!important;
        background:#d8d2ff!important;
        color:#4639bd!important;
      }
      .lexia-forced-action-icon svg {
        width:14px!important;
        height:14px!important;
        fill:none!important;
        stroke:currentColor!important;
        stroke-width:2!important;
        stroke-linecap:round!important;
        stroke-linejoin:round!important;
      }
      .lexia-forced-action-label {
        background:transparent!important;
        color:inherit!important;
      }
      .lexia-home-recent-scroll {
        scrollbar-width:thin;
        scrollbar-color:#a89bff transparent;
      }
      .lexia-home-recent-scroll::-webkit-scrollbar {width:5px;height:5px}
      .lexia-home-recent-scroll::-webkit-scrollbar-track {background:transparent}
      .lexia-home-recent-scroll::-webkit-scrollbar-thumb {
        min-height:34px;
        border-radius:999px;
        background:#a89bff;
      }
      .lexia-home-recent-scroll::-webkit-scrollbar-thumb:hover {background:#7668ef}
      .lexia-home-recent-icon {
        display:inline-flex!important;
        align-items:center!important;
        justify-content:center!important;
        flex:0 0 30px!important;
        width:30px!important;
        height:30px!important;
        min-width:30px!important;
        border-radius:8px!important;
        background:#f0edff!important;
        color:#5a4cff!important;
      }
      .lexia-home-recent-icon svg {
        width:17px!important;
        height:17px!important;
        fill:none!important;
        stroke:currentColor!important;
        stroke-width:1.8!important;
        stroke-linecap:round!important;
        stroke-linejoin:round!important;
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
  scheduleHomeRecents();
  document.addEventListener('pointerover', event => {
    const card = event.target?.closest?.('#searchpage .result-card');
    if (card) paintActions(card);
  }, true);
  document.addEventListener('click', event => {
    const trigger = event.target?.closest?.(
      '.lexia-result-menu-trigger, .result-actions button, .lexia-result-menu button, [role="menu"] button'
    );
    if (trigger) {
      [0, 30, 100, 250, 500].forEach(delay => window.setTimeout(() => paintActions(document), delay));
    }
    if (event.target?.closest?.('a,button,[data-page],[data-route]')) scheduleHomeRecents();
  }, true);
  window.addEventListener('lexia:home-updated', polishHomeRecents);
})();
