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

      /* El resaltado vive en la lista, no en la fila reemplazada por /api/live. */
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-scroll-list {
        position:relative!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-scroll-list::before {
        content:""!important;
        position:absolute!important;
        z-index:0!important;
        top:var(--lexia-home-hover-top, 0px)!important;
        left:2px!important;
        right:8px!important;
        height:var(--lexia-home-hover-height, 0px)!important;
        border-radius:8px!important;
        background:#f0efff!important;
        box-shadow:inset 3px 0 0 #6258ff!important;
        opacity:0!important;
        pointer-events:none!important;
        transition:none!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-scroll-list.lexia-home-hover-active::before {
        opacity:1!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-scroll-list .hr-row {
        position:relative!important;
        z-index:1!important;
      }
      #home .hr-lower>.hr-card:nth-child(-n+2) .hr-scroll-list .hr-row:hover {
        background:transparent!important;
        box-shadow:none!important;
        transform:none!important;
        transition:none!important;
      }
    `;
    document.head.appendChild(style);
  }

  // Investigación macOS: tres niveles tipográficos, sin cambiar la geometría de los controles.
  if (!document.getElementById('lexiaMacosResearchTypography')) {
    const style = document.createElement('style');
    style.id = 'lexiaMacosResearchTypography';
    style.textContent = `
      @media (min-width:900px) {
        .contextpage .head h1 {font-size:24px!important}
        #researchPanel .context-form h3,
        #researchProgress h3 {font-size:16px!important}
        .contextpage .head p,
        .contextpage .investigation-tab,
        #researchPanel .form-label,
        #researchPanel .research-scope-trigger,
        #researchPanel .optionbox,
        #researchPanel .optionbox small,
        #researchPanel select,
        #researchPanel .textarea,
        #researchPanel .hint,
        #researchPanel button,
        #researchProgress p,
        #researchProgress .job-state,
        #researchProgress .research-progress-foot {font-size:13px!important}

        #researchPanel .research-history-row,
        #researchPanel .form-row,
        #researchPanel .context-actions,
        #researchProgress,
        #researchProgress * {
          min-width:0!important;
          max-width:100%!important
        }
        #researchPanel .context-form,
        #researchPanel .context-form * {
          overflow-wrap:anywhere
        }
        #researchPanel .form-row>div {min-width:0!important}
      }

      #researchPanel .lexia-research-disclosure {
        min-width:0;
        max-width:100%;
        border:1px solid #e4e7f0;
        border-radius:8px;
        background:#fbfcff;
        overflow:hidden;
      }
      #researchPanel .lexia-research-disclosure>summary {
        display:flex;
        align-items:center;
        gap:10px;
        min-width:0;
        padding:9px 11px;
        list-style:none;
        cursor:pointer;
        color:#263252;
        font-weight:650;
        line-height:1.35;
      }
      #researchPanel .lexia-research-disclosure>summary::-webkit-details-marker {display:none}
      #researchPanel .lexia-research-disclosure>summary::after {
        content:"";
        flex:0 0 7px;
        width:7px;
        height:7px;
        margin-left:auto;
        border-right:1.5px solid #6258ff;
        border-bottom:1.5px solid #6258ff;
        transform:rotate(45deg) translateY(-2px);
        transition:transform .15s ease;
      }
      #researchPanel .lexia-research-disclosure[open]>summary::after {
        transform:rotate(225deg) translateY(-1px);
      }
      #researchPanel .lexia-research-disclosure>summary:hover {
        background:#f4f3ff;
      }
      #researchPanel .lexia-research-disclosure-state {
        flex:0 0 auto;
        padding:2px 7px;
        border-radius:999px;
        background:#eeecff;
        color:#5146f6;
        font-weight:600;
      }
      #researchPanel .lexia-research-disclosure textarea {
        display:block;
        width:calc(100% - 16px);
        max-width:calc(100% - 16px);
        margin:0 8px 8px;
      }
      #researchPanel .research-instruction-disclosure {margin-top:12px}
    `;
    document.head.appendChild(style);
  }

  // Los campos opcionales se pliegan sin reemplazar ni renombrar sus textareas.
  // Los IDs originales siguen siendo usados por el flujo de investigación.
  const installResearchDisclosures = () => {
    const panel = document.getElementById('researchPanel');
    if (!panel || panel.dataset.lexiaResearchDisclosures === '1') return;
    const makeDisclosure = (fieldId, className) => {
      const field = panel.querySelector('#' + fieldId);
      const label = field?.previousElementSibling;
      if (!field || !label) return;
      const disclosure = document.createElement('details');
      disclosure.className = 'lexia-research-disclosure ' + className;
      disclosure.dataset.fieldId = fieldId;
      disclosure.open = Boolean(String(field.value || '').trim());

      const summary = document.createElement('summary');
      const title = document.createElement('span');
      title.textContent = String(label.textContent || '').trim();
      const state = document.createElement('span');
      state.className = 'lexia-research-disclosure-state';
      state.textContent = 'Con contenido';
      state.hidden = !String(field.value || '').trim();
      summary.append(title, state);

      label.replaceWith(disclosure);
      disclosure.append(summary, field);
      field.addEventListener('input', event => {
        const populated = Boolean(String(field.value || '').trim());
        state.hidden = !populated;
        if (!event.isTrusted && populated) disclosure.open = true;
      });
    };

    makeDisclosure('researchFacts', 'research-facts-disclosure');
    makeDisclosure('researchObjective', 'research-objective-disclosure');
    makeDisclosure('researchInstruction', 'research-instruction-disclosure');
    panel.dataset.lexiaResearchDisclosures = '1';
  };
  installResearchDisclosures();


  // El refresco heredado reemplaza las filas cada pocos segundos. Mantener el
  // resaltado en la lista evita que el hover parpadee al cambiar esos nodos.
  const homeRecentHoverLists = new WeakSet();

  const clearHomeRecentHover = list => {
    list.classList.remove('lexia-home-hover-active');
    list.style.removeProperty('--lexia-home-hover-top');
    list.style.removeProperty('--lexia-home-hover-height');
  };

  const installStableHomeRecentHover = () => {
    document.addEventListener('pointerover', event => {
      const row = event.target?.closest?.('#home .hr-scroll-list .hr-row');
      if (!row) return;
      const list = row.closest('.hr-scroll-list');
      if (!list) return;

      if (!homeRecentHoverLists.has(list)) {
        homeRecentHoverLists.add(list);
        list.addEventListener('pointerleave', () => clearHomeRecentHover(list));
        list.addEventListener('scroll', () => clearHomeRecentHover(list), {passive: true});
      }

      list.style.setProperty('--lexia-home-hover-top', row.offsetTop + 'px');
      list.style.setProperty('--lexia-home-hover-height', row.offsetHeight + 'px');
      list.classList.add('lexia-home-hover-active');
    }, true);
  };

  paintActions(document);
  installStableHomeRecentHover();
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

  // Composición del render aprobado para Investigación en escritorio macOS.
  if (!document.getElementById('lexiaMacResearchRenderStyle')) {
    const style = document.createElement('style');
    style.id = 'lexiaMacResearchRenderStyle';
    style.textContent = `
      #contextpage .context-layout {height:auto!important;min-height:calc(100vh - var(--global-top,0px))!important;min-height:calc(100dvh - var(--global-top,0px))!important;max-height:none!important;display:flex!important;flex-direction:column!important;gap:14px!important;overflow-x:hidden!important;overflow-y:auto!important;padding-bottom:18px!important;box-sizing:border-box!important}
      #contextpage .context-layout>.head {flex:none!important;align-items:center!important;margin:0!important}
      #contextpage .context-layout>.head h1 {font-size:24px!important;line-height:1.15!important}
      #contextpage .context-layout>.head p {font-size:14px!important;line-height:1.4!important;margin-top:4px!important}
      #contextpage .context-layout>.head .head-actions .secondary {height:40px!important;padding:0 18px!important;font-size:14px!important;border-radius:9px!important}
      #contextpage .investigation-tabs {display:flex!important;flex:none!important;gap:0!important;min-height:42px!important;margin:0!important;padding:0!important;border-bottom:1px solid #dce1ef!important}
      #contextpage .investigation-tab {position:relative!important;min-height:42px!important;padding:0 20px!important;border:0!important;border-radius:8px 8px 0 0!important;background:transparent!important;color:#536184!important;font-size:14px!important;font-weight:600!important}
      #contextpage .investigation-tab.active {background:#f1f0ff!important;color:#3327d4!important}
      #contextpage .investigation-tab.active::after {content:"";position:absolute;right:0;bottom:-1px;left:0;height:3px;background:#5146f6;border-radius:3px 3px 0 0}
      #contextpage #researchPanel.context-grid {display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-auto-rows:auto!important;gap:12px!important;width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;margin:0!important;overflow:visible!important;align-items:stretch!important}
      #contextpage #researchPanel[hidden] {display:none!important}
      #contextpage #researchPanel .research-main-column {display:block!important;min-width:0!important;min-height:0!important;overflow:visible!important}
      #contextpage #researchPanel .context-form {display:block!important;width:100%!important;min-height:0!important;max-height:none!important;overflow:visible!important;padding:18px 20px!important;border-radius:11px!important;box-sizing:border-box!important}
      #contextpage #researchPanel .context-form>h3,#contextpage #researchProgress .job-top h3,#contextpage #researchPanel .context-side>h3,#contextpage #lexiaLatestResultsPanel .output-head h3 {font-size:18px!important;line-height:1.25!important;font-weight:700!important}
      #contextpage #researchPanel .context-form>h3 {margin:0 0 14px!important}
      #contextpage .research-settings {display:grid!important;grid-template-columns:minmax(190px,1fr) minmax(0,3fr)!important;gap:12px!important;align-items:center!important;margin:0 0 12px!important}
      #contextpage .research-scope-trigger {height:38px!important;border-radius:7px!important;padding:0 11px!important;background:#fff!important}
      #contextpage .research-scope-trigger span,#contextpage .research-scope-trigger small {font-size:13px!important}
      #contextpage .research-settings .context-options {display:flex!important;position:static!important;gap:10px!important;margin:0!important;min-width:0!important}
      #contextpage .research-settings .optionbox {display:flex!important;align-items:center!important;gap:10px!important;flex:1 1 0!important;min-width:0!important;height:38px!important;padding:0 10px!important;border-radius:7px!important;background:#fff!important;box-sizing:border-box!important}
      #contextpage .research-settings .optionbox small {flex:none!important;margin:0!important;font-size:11px!important;line-height:1.1!important;letter-spacing:.02em!important;color:#5d6b90!important}
      #contextpage .research-settings .optionbox select {min-width:0!important;width:100%!important;font-size:13px!important;font-weight:500!important}
      #contextpage #researchPanel .form-label {font-size:13px!important;line-height:1.3!important;margin:9px 0 5px!important}
      #contextpage #researchPanel .textarea {font-size:14px!important;line-height:1.45!important;padding:10px 12px!important;border-radius:7px!important}
      #contextpage #researchPanel .context-query {min-height:76px!important;height:76px!important}
      #contextpage .research-history-row {grid-template-columns:142px minmax(0,1fr)!important;gap:10px!important;margin-top:9px!important}
      #contextpage .research-history-row select {height:37px!important;padding:0 10px!important;font-size:13px!important;border-radius:7px!important}
      #contextpage #researchPanel .lexia-research-disclosure>summary {min-height:48px!important;box-sizing:border-box!important;padding:10px 14px!important;font-size:16px!important;line-height:1.25!important;font-weight:700!important}
      #contextpage #researchPanel .lexia-research-disclosure textarea {min-height:76px!important;font-size:14px!important}
      #contextpage #researchPanel .research-instruction-disclosure {margin-top:9px!important}
      #contextpage #researchPanel .context-actions {margin-top:12px!important;padding-top:11px!important;gap:14px!important}
      #contextpage #researchPanel .context-actions .hint {font-size:13px!important;line-height:1.35!important}
      #contextpage #startContext {min-height:42px!important;padding:0 22px!important;font-size:14px!important;border-radius:8px!important}
      #contextpage #researchProgress {display:block!important;width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;margin:0!important;padding:16px 20px!important;overflow:visible!important;border-radius:11px!important;box-sizing:border-box!important}
      #contextpage #researchProgress .job-top {align-items:center!important}
      #contextpage #researchProgress .job-top h3 {margin:0!important}
      #contextpage #researchProgress .job-top p,#contextpage #researchProgress .research-progress-foot {font-size:13px!important;line-height:1.35!important}
      #contextpage #researchProgress .job-state {font-size:13px!important;padding:6px 10px!important}
      #contextpage #researchProgress .research-progress-track {height:8px!important;margin-top:9px!important}
      #contextpage #researchPanel .context-side {display:flex!important;width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;margin:0!important;padding:16px 20px!important;overflow:visible!important;border-radius:11px!important;box-sizing:border-box!important}
      #contextpage #researchPanel .context-side .source-list {max-height:430px!important;overflow:auto!important}
      #contextpage #researchPanel .context-side .source-item strong,#contextpage #researchPanel .context-side .source-item .source-name-link {font-size:13px!important}
      #contextpage #researchPanel .context-side .source-item small,#contextpage #researchPanel .context-side .source-snippet {font-size:12px!important}
      #contextpage #researchPanel .context-side .source-actions button,#contextpage #researchPanel .context-side #viewSources {font-size:12px!important;min-height:30px!important;height:30px!important}
      #contextpage .context-layout #studyPanel,#contextpage .context-layout #lexiaLatestResultsPanel {flex:none!important;width:100%!important;margin:0!important;overflow:visible!important}
      #contextpage .context-layout #studyPanel {padding:18px 20px!important}
      #contextpage #lexiaLatestResultsPanel {padding:0!important;background:transparent!important;border:0!important;box-shadow:none!important}
      #contextpage #lexiaLatestResultsPanel .output-card {margin:0!important;padding:18px 20px!important}
      #contextpage #lexiaLatestResultsPanel .output-summary {max-height:none!important;overflow:visible!important;font-size:13px!important}
      #contextpage #lexiaLatestResultsPanel .outstat small {font-size:11px!important}
      #contextpage #lexiaLatestResultsPanel .outstat b {font-size:14px!important}
      #contextpage .context-layout>.footer {display:none!important}
      @media(max-width:1100px) {#contextpage .research-settings {grid-template-columns:minmax(170px,1fr) minmax(0,2.3fr)!important}#contextpage .research-settings .optionbox {gap:6px!important;padding:0 7px!important}#contextpage .research-settings .optionbox small {font-size:10px!important}}
      @media(max-width:820px) {#contextpage .research-settings {grid-template-columns:1fr!important}#contextpage .research-settings .context-options {display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important}#contextpage .research-settings .optionbox {display:block!important;height:auto!important;min-height:54px!important;padding:7px 9px!important}#contextpage .research-settings .optionbox small {display:block!important;margin-bottom:4px!important}#contextpage .research-history-row {grid-template-columns:1fr!important;gap:2px!important}#contextpage #researchPanel .lexia-research-disclosure>summary {font-size:15px!important}}
      @media(max-width:560px) {#contextpage .investigation-tab {padding:0 10px!important;font-size:12px!important}#contextpage .research-settings .context-options {grid-template-columns:1fr!important}#contextpage #researchPanel .context-actions {align-items:stretch!important;flex-direction:column!important}#contextpage #researchPanel .context-actions #startContext {align-self:flex-end}}
    `;
    document.head.appendChild(style);
  }

  const contextPage = document.getElementById('contextpage');
  const tabs = contextPage?.querySelector('.investigation-tabs');
  const researchTab = document.getElementById('researchTab');
  const studyTab = document.getElementById('studyTab');
  const researchPanel = document.getElementById('researchPanel');
  const studyPanel = document.getElementById('studyPanel');
  const researchMain = researchPanel?.querySelector('.research-main-column');
  const progress = document.getElementById('researchProgress');
  const outputCard = contextPage?.querySelector('.output-card');
  const page = contextPage?.querySelector('.context-layout');

  if (tabs && researchTab && studyTab && researchPanel && studyPanel && researchMain && progress && outputCard && page) {
    const sourcePanel = researchPanel.querySelector('.context-side');
    if (sourcePanel && progress.parentElement !== researchPanel) researchPanel.insertBefore(progress, sourcePanel);
    else if (!sourcePanel && progress.parentElement !== researchPanel) researchPanel.appendChild(progress);

    let latestPanel = document.getElementById('lexiaLatestResultsPanel');
    if (!latestPanel) {
      latestPanel = document.createElement('section');
      latestPanel.id = 'lexiaLatestResultsPanel';
      latestPanel.className = 'investigation-panel';
      latestPanel.setAttribute('role', 'tabpanel');
      latestPanel.hidden = true;
      latestPanel.appendChild(outputCard);
      const footer = page.querySelector('.footer');
      page.insertBefore(latestPanel, footer || null);
    }

    let latestTab = document.getElementById('lexiaLatestResultsTab');
    if (!latestTab) {
      latestTab = document.createElement('button');
      latestTab.type = 'button';
      latestTab.id = 'lexiaLatestResultsTab';
      latestTab.className = 'investigation-tab';
      latestTab.setAttribute('role', 'tab');
      latestTab.setAttribute('aria-selected', 'false');
      latestTab.textContent = 'Últimos resultados';
      tabs.appendChild(latestTab);
    }

    const selectPanel = name => {
      const panels = {research: researchPanel, study: studyPanel, latest: latestPanel};
      const buttons = {research: researchTab, study: studyTab, latest: latestTab};
      Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== name; });
      Object.entries(buttons).forEach(([key, button]) => {
        button.classList.toggle('active', key === name);
        button.setAttribute('aria-selected', String(key === name));
      });
    };

    researchTab.addEventListener('click', () => selectPanel('research'));
    studyTab.addEventListener('click', () => selectPanel('study'));
    latestTab.addEventListener('click', () => selectPanel('latest'));
    document.getElementById('newContext')?.addEventListener('click', () => selectPanel('research'));
  }

})();
