/* LexIA Casos 2.0 — estructura procesal local, sin llamadas a IA. */
(function () {
  'use strict';
  const PAGE_ID = 'casespage';
  let currentCase = null, caseList = [], expandedNodeId = null;
  const openPrimaryIds = new Set();
  let activeEvidenceBlockId = null;
  const selectedQuestionIdsByRoot = new Map();
  let showNewCase = false, showNewBranch = false, questionParentId = null, editingCase = false;
  let activeWorkspaceSide = 'contraparte';
  const autosaveTimers = new Map();

  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(([key, value]) => {
      if (key === 'className') node.className = value;
      else if (key === 'textContent') node.textContent = value;
      else if (key === 'value') node.value = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    });
    children.flat().filter(Boolean).forEach(child => node.append(child));
    return node;
  }
  function actionIcon(kind, label, extraClass) {
    const paths = {
      show: '<path d="m9 5 7 7-7 7"></path>',
      hide: '<path d="m5 9 7 7 7-7"></path>',
      files: '<path d="M4 5h6l2 2h8v12H4z"></path><path d="M4 10h16"></path>',
      add: '<path d="M12 5v14M5 12h14"></path>',
      edit: '<path d="m5 19 3.5-.8L18 8.7 15.3 6 5.8 15.5z"></path><path d="m14.8 6.5 2.7 2.7"></path>',
      remove: '<path d="M5 7h14M10 7V5h4v2M8 7l.7 12h6.6L16 7M10 11v5M14 11v5"></path>',
    };
    const button = el('button', {
      type: 'button',
      className: 'cases-icon' + (extraClass ? ' ' + extraClass : ''),
      title: label,
      'aria-label': label,
    });
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24'); icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = paths[kind] || paths.add;
    button.append(icon);
    return button;
  }
  async function api(url, options) {
    const response = await fetch(url, Object.assign({cache: 'no-store', headers: {'Content-Type': 'application/json'}}, options || {}));
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || ('HTTP ' + response.status));
    return data;
  }
  function style() {
    if (document.getElementById('lexiaCasesStyle')) return;
    const css = [
      '#' + PAGE_ID + '{display:none;position:fixed;z-index:20;inset:0 0 0 var(--global-side,0px);background:#f6f7fb;color:#202a48;overflow:auto;box-sizing:border-box}',
      '#' + PAGE_ID + ' .cases-main{box-sizing:border-box;width:100%;max-width:1560px;margin:0 auto;padding:18px 24px 34px}',
      '#' + PAGE_ID + ' .cases-toolbar{display:flex;gap:8px;margin-bottom:12px}#' + PAGE_ID + ' .cases-picker{flex:1;min-width:180px}#' + PAGE_ID + ' .cases-picker input{box-sizing:border-box;width:100%;padding:8px 10px;border:1px solid #dce1ed;border-radius:8px;background:#fff;font:inherit;font-size:11px;color:#263154}',
      '#' + PAGE_ID + ' .cases-button,#' + PAGE_ID + ' .cases-button-secondary,#' + PAGE_ID + ' .cases-icon{box-sizing:border-box;min-height:0;font:inherit!important;font-size:9px!important;line-height:1.1!important;font-weight:800;cursor:pointer;border-radius:6px;padding:5px 7px!important}#' + PAGE_ID + ' .cases-button{background:#5146f6;color:#fff;border:1px solid #5146f6}#' + PAGE_ID + ' .cases-button:hover{background:#4136df}#' + PAGE_ID + ' .cases-button-secondary{background:#fff;color:#465176;border:1px solid #d8deed}#' + PAGE_ID + ' .cases-button-secondary:hover{border-color:#6459f4;color:#493de2}#' + PAGE_ID + ' .cases-icon{background:transparent;color:#5f6989;border:0;padding:4px 5px!important}#' + PAGE_ID + ' .cases-icon:hover{background:#f0efff;color:#493de2}#' + PAGE_ID + ' .cases-danger{border-color:#f0c7ce;color:#b23848}#' + PAGE_ID + ' .cases-danger:hover{background:#fff4f5;border-color:#df7786;color:#9d2939}',
      '.cases-card{background:#fff;border:1px solid #e0e5ef;border-radius:14px;box-shadow:0 3px 14px rgba(31,39,76,.045)}.cases-empty{padding:22px;color:#74809d;font-size:13px;text-align:center}.cases-create{margin-bottom:16px;padding:16px}.cases-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cases-field{display:grid;gap:5px}.cases-field.wide{grid-column:1/-1}.cases-field label{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.035em;color:#6b7593}.cases-field input,.cases-field textarea,.cases-field select{box-sizing:border-box;width:100%;border:1px solid #dce1ed;border-radius:8px;padding:9px 10px;font:inherit;font-size:12px;color:#273153;background:#fff}.cases-field textarea{min-height:74px;resize:vertical}.cases-form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}',
      '.case-identification{padding:14px 16px;margin-bottom:12px}.case-identification-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.case-identification h1{margin:0;font-size:18px}.case-summary{margin:6px 0 0;max-width:930px;white-space:pre-wrap;color:#5f6b8c;font-size:11px;line-height:1.4}.case-actions{display:flex;gap:5px;flex-wrap:wrap}.case-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid #edf0f5}.case-fact small{display:block;font-size:9px;font-weight:800;color:#7a84a0;text-transform:uppercase;letter-spacing:.035em;margin-bottom:2px}.case-fact span{display:block;font-size:11px;color:#313b5e;overflow-wrap:anywhere}',
      '.case-tree{padding:13px 16px}.case-tree-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.case-tree-head h2{font-size:13px;margin:0}.case-tree-head p{font-size:10px;color:#74809d;margin:2px 0 0}.branch-form{margin:0 0 9px;padding:10px;background:#f8f8fd;border:1px dashed #cbd2e6;border-radius:8px}.branch-form h3{font-size:11px;margin:0 0 8px}.branch-list{display:grid;gap:7px}.primary-branch{border:1px solid #dce2f0;border-radius:9px;overflow:hidden}.primary-branch.drop-target{border-color:#6558f5;box-shadow:0 0 0 3px rgba(101,88,245,.14)}.primary-head{display:flex;align-items:center;gap:7px;padding:7px 9px;background:#fbfbff}.branch-mark{display:grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#eeeaff;color:#5548ef;font-size:11px;font-weight:900}.branch-title{flex:1;min-width:0}.branch-title b{display:block;font-size:11px;color:#283257}.branch-title small{display:block;margin-top:1px;color:#75809b;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.branch-actions{display:flex;gap:1px;align-items:center}.branch-questions{padding:6px 8px 8px;border-top:1px solid #edf0f6}.question-row{display:flex;align-items:center;gap:7px;border:1px solid #e4e8f2;border-radius:7px;padding:6px 7px;margin-top:5px;background:#fff}.question-row:first-child{margin-top:0}.question-row:hover{border-color:#bcb5ff;background:#fcfbff}.question-row strong{display:block;font-size:10px;color:#303a60;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row small{display:block;margin-top:1px;max-width:580px;font-size:9px;color:#78839e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row .cases-icon{border:1px solid #dbe0ee;padding:4px 6px!important;font-size:9px!important}.question-add{margin-top:6px;background:transparent;border:0;color:#5146f6;font-size:9px;font-weight:800;cursor:pointer;padding:3px 1px}.question-add:hover{text-decoration:underline}',
      '.case-workspace{margin-top:16px;min-height:520px;overflow:hidden}.workspace-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:15px 18px;border-bottom:1px solid #e6eaf2}.workspace-head small{display:block;color:#78829c;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}.workspace-head h2{margin:0;font-size:16px;color:#263156}.workspace-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(285px,.42fr);min-height:460px}.workspace-editor{padding:18px;border-right:1px solid #e8ebf3}.workspace-sources{padding:16px;background:#fbfbfe}.workspace-section{margin-bottom:16px}.workspace-section h3{font-size:11px;text-transform:uppercase;letter-spacing:.035em;color:#687492;margin:0 0 7px}.workspace-section textarea,.workspace-section input{box-sizing:border-box;width:100%;font:inherit;font-size:13px;line-height:1.5;color:#293357;border:1px solid #dce2ee;border-radius:9px;padding:10px;background:#fff}.workspace-section textarea{min-height:112px;resize:vertical}.workspace-section textarea.own-position{min-height:180px}.workspace-save{display:flex;justify-content:flex-end}.source-title{font-size:13px;margin:0 0 8px;color:#2b3559}.source-help{font-size:11px;line-height:1.4;color:#74809d;margin:0 0 10px}.source-accordion{border:1px solid #e0e5ef;border-radius:9px;background:#fff;margin:8px 0}.source-accordion summary{cursor:pointer;list-style:none;padding:9px 10px;font-size:11px;font-weight:800;color:#354064}.source-accordion summary::-webkit-details-marker{display:none}.source-accordion summary:before{content:"▸";display:inline-block;color:#5b4ff1;margin-right:7px}.source-accordion[open] summary:before{transform:rotate(90deg)}.source-body{border-top:1px solid #edf0f5;padding:9px 10px}.source-body p{white-space:pre-wrap;font-size:11px;line-height:1.45;color:#56617e;margin:0 0 9px}.source-actions{display:flex;gap:7px;justify-content:flex-end}.source-link-form{margin-top:13px;padding-top:13px;border-top:1px solid #e4e8f1}.source-link-form select{margin-bottom:7px}.source-link-form .cases-button{width:100%;margin-top:7px}.sources-empty{padding:13px 4px;color:#7b85a1;font-size:11px;line-height:1.4}',
      '#' + PAGE_ID + ' .case-workspace{margin:5px 0 7px;min-height:0;overflow:hidden;border-color:#d6dcef}#' + PAGE_ID + ' .workspace-head{padding:9px 11px}#' + PAGE_ID + ' .workspace-head h2{font-size:13px}#' + PAGE_ID + ' .workspace-layout{grid-template-columns:minmax(0,1fr) 300px;min-height:0}#' + PAGE_ID + ' .workspace-editor{padding:8px 10px;border-right:1px solid #e8ebf3}#' + PAGE_ID + ' .workspace-sources{padding:10px;background:#fbfbfe}#' + PAGE_ID + ' .argument-section{border-bottom:1px solid #e7eaf2}#' + PAGE_ID + ' .argument-section:last-child{border-bottom:0}#' + PAGE_ID + ' .argument-section summary{cursor:pointer;list-style:none;padding:8px 2px;font-size:10px;font-weight:800;color:#344064}#' + PAGE_ID + ' .argument-section summary::-webkit-details-marker{display:none}#' + PAGE_ID + ' .argument-section summary:before{content:"▸";display:inline-block;color:#5b4ff1;margin-right:6px}#' + PAGE_ID + ' .argument-section[open] summary:before{transform:rotate(90deg)}#' + PAGE_ID + ' .argument-section-body{padding:0 2px 9px}#' + PAGE_ID + ' .argument-block{margin:5px 0;padding:7px;border:1px solid #e2e6f0;border-radius:7px;background:#fff}#' + PAGE_ID + ' .argument-block-head{display:flex;justify-content:space-between;gap:6px;align-items:center;margin-bottom:5px;color:#697594;font-size:9px;font-weight:800}#' + PAGE_ID + ' .argument-block textarea{box-sizing:border-box;width:100%;min-height:64px;resize:vertical;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;line-height:1.35;color:#293357}#' + PAGE_ID + ' .argument-block-actions{display:flex;justify-content:flex-end;gap:4px;margin-top:5px}#' + PAGE_ID + ' .workspace-enunciado{box-sizing:border-box;width:100%;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;color:#293357}#' + PAGE_ID + ' .workspace-ai{margin-top:4px;padding-top:4px}#' + PAGE_ID + ' .source-title{font-size:11px;margin:0 0 5px}#' + PAGE_ID + ' .source-help{font-size:9px;line-height:1.35;margin:0 0 7px}#' + PAGE_ID + ' .source-accordion{margin:5px 0;border-radius:7px}#' + PAGE_ID + ' .source-accordion summary{padding:7px 8px;font-size:9px}#' + PAGE_ID + ' .source-body{padding:7px 8px}#' + PAGE_ID + ' .source-body p{font-size:9px;line-height:1.35;margin:0 0 6px}#' + PAGE_ID + ' .evidence-candidate{display:flex;align-items:center;gap:5px;padding:6px 0;border-bottom:1px solid #edf0f5;font-size:9px;color:#465176}#' + PAGE_ID + ' .evidence-candidate:last-child{border-bottom:0}#' + PAGE_ID + ' .evidence-candidate b{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#' + PAGE_ID + ' .lexia-evidence-dialog{width:min(940px,92vw);max-width:940px;border:1px solid #d8deeb;border-radius:12px;padding:0;box-shadow:0 20px 70px rgba(20,30,65,.28)}#' + PAGE_ID + ' .lexia-evidence-dialog::backdrop{background:rgba(24,31,56,.34)}#' + PAGE_ID + ' .evidence-dialog-head{padding:11px 13px;border-bottom:1px solid #e6eaf2;display:flex;justify-content:space-between;gap:8px;align-items:center}#' + PAGE_ID + ' .evidence-dialog-head b{font-size:12px}#' + PAGE_ID + ' .evidence-dialog-body{padding:11px 13px}#' + PAGE_ID + ' .evidence-reader{height:min(52vh,520px);overflow:auto;white-space:pre-wrap;user-select:text;padding:10px;border:1px solid #dce2ee;border-radius:7px;background:#fcfcff;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#283254}#' + PAGE_ID + ' .evidence-selection-status{margin:7px 0;color:#687492;font-size:10px}#' + PAGE_ID + ' .evidence-dialog-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:8px}',
      '#' + PAGE_ID + ' .argument-block{display:grid;grid-template-columns:17px minmax(0,1fr) auto;column-gap:5px;align-items:start;margin:2px 0;padding:4px 0;border:0;border-radius:0;background:transparent}#' + PAGE_ID + ' .argument-block + .argument-block{border-top:1px solid #edf0f5;padding-top:6px}#' + PAGE_ID + ' .argument-paragraph-number{display:grid;place-items:center;width:16px;height:16px;margin-top:5px;border-radius:50%;background:#eeeaff;color:#5648ed;font-size:8px;font-weight:800}#' + PAGE_ID + ' .argument-block-body{min-width:0}#' + PAGE_ID + ' .argument-block textarea{min-height:44px;border-color:transparent;background:#fcfcff;padding:5px 6px}#' + PAGE_ID + ' .argument-block textarea:focus{border-color:#b9b3ff;background:#fff}#' + PAGE_ID + ' .argument-block-actions{margin:3px 0 0;display:flex;gap:2px;align-items:flex-start}#' + PAGE_ID + ' .argument-evidence{margin:4px 0 0;padding:5px 7px;border-left:2px solid #8075fa;background:#f8f7ff;white-space:pre-wrap;font-size:10px;line-height:1.35;color:#4e5878}#' + PAGE_ID + ' .argument-evidence:first-of-type{margin-top:3px}#' + PAGE_ID + ' .workspace-sources.drop-target{outline:2px dashed #6558f5;outline-offset:-5px;background:#f3f1ff}#' + PAGE_ID + ' .sources-drop-help{margin:7px 0 0;padding:8px;border:1px dashed #c9c3ff;border-radius:7px;color:#6257db;font-size:9px;text-align:center}#' + PAGE_ID + ' .branch-actions .cases-icon,#' + PAGE_ID + ' .question-row .cases-icon{display:grid;place-items:center;min-width:22px;padding:4px!important}#' + PAGE_ID + ' .cases-icon svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}#' + PAGE_ID + ' .branch-ai{margin:8px 8px 2px;padding:8px 9px;border-top:1px solid #e5e8f1;background:#fbfbfe}#' + PAGE_ID + ' .branch-ai summary{cursor:pointer;color:#38436a;font-size:10px;font-weight:800}#' + PAGE_ID + ' .branch-ai-options{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}#' + PAGE_ID + ' .branch-ai-option{display:flex;align-items:center;gap:4px;max-width:100%;padding:4px 6px;border:1px solid #e0e4ee;border-radius:6px;background:#fff;color:#56617f;font-size:9px}#' + PAGE_ID + ' .branch-ai-option span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}#' + PAGE_ID + ' .branch-ai textarea{box-sizing:border-box;width:100%;min-height:96px;margin-top:7px;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;line-height:1.4;color:#293357}',
      '@media(max-width:1199px){#' + PAGE_ID + '{left:0;padding-top:58px}#' + PAGE_ID + ' .cases-main{padding:16px 18px 32px}}@media(max-width:800px){#' + PAGE_ID + ' .cases-main{padding:14px 12px 28px}.cases-form-grid,.case-facts,.workspace-layout{grid-template-columns:1fr}.workspace-editor{border-right:0;border-bottom:1px solid #e8ebf3}.case-identification-head,.workspace-head{align-items:flex-start;flex-direction:column}.case-identification-head .case-actions{align-self:stretch}.case-actions button{flex:1}.primary-head{align-items:flex-start}.branch-actions{flex-wrap:wrap;justify-content:flex-end}}'
    ].join('');
    document.head.appendChild(el('style', {id: 'lexiaCasesStyle', textContent: css}));
  }
  function page() { return document.getElementById(PAGE_ID); }
  function hide() {
    if (page()) page().style.display = 'none';
    const cases = document.querySelector('#globalSidebar .nav [data-lexia-cases]');
    if (cases) cases.classList.remove('active');
    if ((location.hash || '').slice(1) === PAGE_ID) history.replaceState(null, '', location.pathname + location.search);
  }
  function show() {
    if (!page()) return;
    page().style.display = 'block';
    const nav = document.querySelector('#globalSidebar .nav');
    nav && nav.querySelectorAll('button').forEach(item => item.classList.remove('active'));
    const cases = nav && nav.querySelector('[data-lexia-cases]');
    if (cases) cases.classList.add('active');
    history.replaceState(null, '', '#' + PAGE_ID);
    page().scrollTo({top: 0}); loadCases();
  }
  function navigation() {
    const nav = document.querySelector('#globalSidebar .nav');
    if (!nav) return setTimeout(navigation, 80);
    if (nav.querySelector('[data-lexia-cases]')) return;
    const button = el('button', {type: 'button', 'data-lexia-cases': '1'});
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24'); icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = '<rect x="3" y="7" width="18" height="13" rx="2"></rect><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M3 12h18"></path><path d="M10 12v2h4v-2"></path>';
    button.append(icon, document.createTextNode('Casos'));
    button.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); show(); }, true);
    const before = nav.querySelector('button[data-route="contextpage"]') || [...nav.querySelectorAll('button')].find(item => item.textContent.trim() === 'Investigación');
    if (before) before.insertAdjacentElement('beforebegin', button); else nav.append(button);
  }
  function navigationExit() {
    if (window.__lexiaCasesExit) return;
    window.__lexiaCasesExit = true;
    window.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target : null;
      const destination = target && target.closest('#globalSidebar .nav button');
      if (destination && !destination.matches('[data-lexia-cases]')) hide();
    }, true);
  }
  function createPage() {
    if (page()) return;
    const section = el('section', {id: PAGE_ID});
    section.append(el('main', {className: 'cases-main'})); document.body.append(section);
  }
  function field(label, control, wide) {
    return el('div', {className: 'cases-field' + (wide ? ' wide' : '')}, el('label', {textContent: label}), control);
  }
  function docSelect(documents, value) {
    const select = el('select');
    select.append(el('option', {value: '', textContent: 'Sin documento inicial'}));
    documents.forEach(doc => select.append(el('option', {value: String(doc.id), textContent: doc.document_name + ' · ' + (doc.category || 'Documento')})));
    select.value = value ? String(value) : ''; return select;
  }
  function evidenceSelect(snapshot) {
    const select = el('select'); select.append(el('option', {value: '', textContent: 'Elegir documento o fragmento…'}));
    if ((snapshot.documents || []).length) {
      const group = el('optgroup', {label: 'Documentos vinculados'});
      snapshot.documents.forEach(doc => group.append(el('option', {value: 'document:' + doc.id, textContent: doc.document_name}))); select.append(group);
    }
    const excerpts = (snapshot.entries || []).filter(entry => entry.document_name || entry.source_excerpt);
    if (excerpts.length) {
      const group = el('optgroup', {label: 'Fragmentos y extractos'});
      excerpts.forEach(entry => group.append(el('option', {value: 'entry:' + entry.id, textContent: (entry.document_name || entry.title || 'Extracto') + (entry.page_start ? ' · pág. ' + entry.page_start : '')}))); select.append(group);
    }
    return select;
  }
  function nextQuestionLabel(parent) {
    const total = (parent && parent.children ? parent.children : []).filter(child => child.node_kind === 'cuestion').length;
    return '+ Cuestión ' + (total + 1);
  }
  function render(data) {
    caseList = data.cases || [];
    const root = page().querySelector('.cases-main'); root.replaceChildren(toolbar());
    if (showNewCase) root.append(newCaseForm());
    if (currentCase && currentCase.case) root.append(identification(currentCase), tree(currentCase));
    else root.append(el('section', {className: 'cases-card cases-empty', textContent: 'Elegí un caso desde el buscador o creá uno nuevo para comenzar.'}));
  }
  function toolbar() {
    const input = el('input', {type: 'search', list: 'lexiaCaseOptions', placeholder: 'Buscar o seleccionar un caso…', value: currentCase && currentCase.case ? currentCase.case.name : ''});
    const list = el('datalist', {id: 'lexiaCaseOptions'}); caseList.forEach(item => list.append(el('option', {value: item.name})));
    input.addEventListener('change', () => { const found = caseList.find(item => item.name === input.value.trim()); if (found) loadCase(found.id); });
    const add = el('button', {type: 'button', className: 'cases-button', textContent: '+ Caso'});
    add.addEventListener('click', () => { showNewCase = !showNewCase; render({cases: caseList}); });
    return el('header', {className: 'cases-toolbar'}, el('div', {className: 'cases-picker'}, input, list), add);
  }
  function newCaseForm() {
    const form = el('form', {className: 'cases-card cases-create'});
    const name = el('input', {placeholder: 'Carátula o nombre del caso', required: 'required'}), authority = el('input', {placeholder: 'Juzgado, tribunal o autoridad'}), fileNumber = el('input', {placeholder: 'Número de expediente'}), description = el('textarea', {placeholder: 'Resumen del caso: hechos, pretensión y estado actual.'});
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Crear caso'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', () => { showNewCase = false; render({cases: caseList}); });
    form.append(el('div', {className: 'cases-form-grid'}, field('Carátula', name, true), field('Tribunal o autoridad', authority), field('Expediente', fileNumber), field('Resumen del caso', description, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try { const response = await api('/api/cases', {method: 'POST', body: JSON.stringify({name: name.value, authority: authority.value, file_number: fileNumber.value, description: description.value})}); currentCase = response.case; showNewCase = false; await loadCases(false); }
      catch (error) { alert(error.message); } finally { submit.disabled = false; }
    }); return form;
  }
  function fact(label, value) { return el('div', {className: 'case-fact'}, el('small', {textContent: label}), el('span', {textContent: value})); }
  function identification(snapshot) {
    if (editingCase) return editCase(snapshot);
    const details = snapshot.case, card = el('section', {className: 'cases-card case-identification'});
    const edit = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Editar'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Eliminar'});
    edit.addEventListener('click', () => { editingCase = true; render({cases: caseList}); });
    remove.addEventListener('click', async () => {
      if (!confirm('¿Eliminar el caso “' + details.name + '”?\\n\\nSe eliminarán ramas, notas y vínculos locales. Los documentos originales de LexIA no se borrarán.')) return;
      try { await api('/api/cases/delete', {method: 'POST', body: JSON.stringify({case_id: details.id, confirmed: true})}); currentCase = null; expandedNodeId = null; await loadCases(false); } catch (error) { alert(error.message); }
    });
    card.append(el('div', {className: 'case-identification-head'}, el('div', {}, el('h1', {textContent: details.name}), el('p', {className: 'case-summary', textContent: details.description || 'Sin resumen aún.'})), el('div', {className: 'case-actions'}, edit, remove)), el('div', {className: 'case-facts'}, fact('Tribunal o autoridad', details.authority || 'Sin consignar'), fact('Expediente', details.file_number || 'Sin consignar')));
    return card;
  }
  function editCase(snapshot) {
    const details = snapshot.case, form = el('form', {className: 'cases-card case-identification'});
    const name = el('input', {value: details.name, required: 'required'}), authority = el('input', {value: details.authority || ''}), fileNumber = el('input', {value: details.file_number || ''}), description = el('textarea', {value: details.description || ''});
    const save = el('button', {type: 'submit', className: 'cases-button', textContent: 'Guardar datos'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', () => { editingCase = false; render({cases: caseList}); });
    form.append(el('div', {className: 'cases-form-grid'}, field('Carátula', name, true), field('Tribunal o autoridad', authority), field('Expediente', fileNumber), field('Resumen del caso', description, true)), el('div', {className: 'cases-form-actions'}, cancel, save));
    form.addEventListener('submit', async event => {
      event.preventDefault(); save.disabled = true;
      try { const response = await api('/api/cases/update', {method: 'POST', body: JSON.stringify({case_id: details.id, name: name.value, authority: authority.value, file_number: fileNumber.value, description: description.value})}); currentCase = response.case; editingCase = false; await loadCases(false); }
      catch (error) { alert(error.message); } finally { save.disabled = false; }
    }); return form;
  }

  function tree(snapshot) {
    const card = el('section', {className: 'cases-card case-tree'}), add = el('button', {type: 'button', className: 'cases-button', textContent: '+ Rama'});
    add.addEventListener('click', () => { showNewBranch = !showNewBranch; questionParentId = null; render({cases: caseList}); });
    card.append(el('header', {className: 'case-tree-head'}, el('div', {}, el('h2', {textContent: 'Estructura del caso'}), el('p', {textContent: 'Ramas principales y cuestiones jurídicas. Abrí una cuestión para trabajar sus argumentos y fuentes.'})), add));
    if (showNewBranch) card.append(branchForm(snapshot));
    const roots = snapshot.nodes || [];
    if (!roots.length) card.append(el('p', {className: 'cases-empty', textContent: 'Agregá la primera rama principal: por ejemplo, Demanda, Actuación administrativa o Sentencia.'}));
    const list = el('div', {className: 'branch-list'}); roots.forEach(node => list.append(primary(snapshot, node))); card.append(list);
    return card;
  }
  function branchForm(snapshot) {
    const form = el('form', {className: 'branch-form'}), title = el('input', {placeholder: 'Ej.: Demanda, Actuación administrativa, Sentencia', required: 'required'}), document = docSelect(snapshot.documents || []);
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Agregar rama'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', () => { showNewBranch = false; render({cases: caseList}); });
    form.append(el('h3', {textContent: 'Nueva rama principal'}), el('div', {className: 'cases-form-grid'}, field('Nombre del hito', title, true), field('Documento que lo origina', document, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { await createNode({case_id: snapshot.case.id, node_kind: 'hito', title: title.value, primary_document_id: document.value ? Number(document.value) : null}); showNewBranch = false; } finally { submit.disabled = false; } });
    return form;
  }
  function primary(snapshot, node) {
    const sourceLabel = node.primary_document_name || ((node.sources || []).length ? ((node.sources || []).length + ' archivo(s) vinculado(s)') : 'Hito sin documento inicial');
    const article = el('article', {className: 'primary-branch'}), title = el('div', {className: 'branch-title'}, el('b', {textContent: node.title}), el('small', {textContent: sourceLabel}));
    const input = el('input', {type: 'file', multiple: 'multiple', accept: '.pdf,.doc,.docx,.odt,.txt,.html,.htm,.rtf,.xls,.ods', hidden: 'hidden'});
    const isOpen = openPrimaryIds.has(node.id);
    const toggle = actionIcon(isOpen ? 'hide' : 'show', isOpen ? 'Ocultar rama' : 'Mostrar rama');
    const upload = actionIcon('files', 'Cargar archivos en esta rama');
    const canAddQuestion = !!node.primary_document_id || (node.sources || []).some(source => source.document_id);
    const addQuestion = actionIcon('add', canAddQuestion ? 'Agregar cuestión' : 'Cargá primero un archivo en esta rama'), edit = actionIcon('edit', 'Editar rama'), remove = actionIcon('remove', 'Eliminar rama', 'cases-danger');
    addQuestion.disabled = !canAddQuestion;
    toggle.addEventListener('click', () => { if (isOpen) { openPrimaryIds.delete(node.id); expandedNodeId = null; } else openPrimaryIds.add(node.id); render({cases: caseList}); });
    upload.addEventListener('click', () => input.click());
    input.addEventListener('change', () => { if (input.files?.length) importBranchFiles(snapshot, node, input.files, upload); input.value = ''; });
    addQuestion.addEventListener('click', () => { openPrimaryIds.add(node.id); questionParentId = node.id; showNewBranch = false; render({cases: caseList}); });
    edit.addEventListener('click', async () => { const titleValue = prompt('Nombre de la rama principal:', node.title); if (titleValue === null) return; try { await updateNode(Object.assign({}, node, {title: titleValue, primary_document_id: node.primary_document_id || null})); } catch (error) { alert(error.message); } });
    remove.addEventListener('click', () => removeNode(node, node.children && node.children.length ? 'También se eliminarán sus cuestiones y vínculos locales.' : ''));
    article.append(input, el('header', {className: 'primary-head'}, el('span', {className: 'branch-mark', textContent: '↳'}), title, el('div', {className: 'branch-actions'}, toggle, upload, addQuestion, edit, remove)));
    if (!isOpen) return article;
    const questions = el('div', {className: 'branch-questions'}); (node.children || []).forEach(question => questions.append(questionRow(snapshot, question)));
    if (questionParentId === node.id) questions.append(questionForm(snapshot, node.id));
    article.append(questions, branchAiSection(snapshot, node));
    return article;
  }
  function findNode(nodes, id) {
    for (const node of nodes || []) {
      if (node.id === id) return node;
      const found = findNode(node.children || [], id);
      if (found) return found;
    }
    return null;
  }
  function questionRow(snapshot, node) {
    const blockCount = ((node.blocks?.contraparte || []).length + (node.blocks?.propia || []).length);
    const preview = blockCount ? (blockCount + ' bloque(s) de trabajo') : (node.adversary_text || node.own_position || 'Sin desarrollo todavía'), open = actionIcon(expandedNodeId === node.id ? 'hide' : 'show', expandedNodeId === node.id ? 'Ocultar cuestión' : 'Mostrar cuestión');
    open.addEventListener('click', () => { expandedNodeId = expandedNodeId === node.id ? null : node.id; render({cases: caseList}); if (expandedNodeId) setTimeout(() => { const box = document.querySelector('.case-workspace'); if (box) box.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 0); });
    const canAddChild = Object.values(node.blocks || {}).some(blocks => (blocks || []).some(block => (block.highlights || []).length));
    const addChild = actionIcon('add', canAddChild ? 'Agregar subcuestión' : 'Agregá primero un resaltado a esta cuestión');
    addChild.disabled = !canAddChild;
    addChild.addEventListener('click', () => { questionParentId = node.id; render({cases: caseList}); });
    const row = el('div', {className: 'question-row'}, el('div', {className: 'branch-mark', textContent: '§'}), el('div', {style: 'flex:1;min-width:0'}, el('strong', {textContent: node.title}), el('small', {textContent: preview})), open, addChild);
    const article = el('article', {});
    article.append(row);
    if (expandedNodeId === node.id) article.append(workspace(snapshot, node));
    const children = el('div', {style: 'margin-left:22px'});
    (node.children || []).forEach(child => children.append(questionRow(snapshot, child)));
    if (questionParentId === node.id) children.append(questionForm(snapshot, node.id));
    article.append(children);
    return article;
  }
  function questionForm(snapshot, parentId) {
    const form = el('form', {className: 'branch-form'}), title = el('input', {placeholder: 'Título de la cuestión', required: 'required'}), adversary = el('textarea', {placeholder: 'Planteo o afirmación de la contraparte.'}), position = el('textarea', {placeholder: 'Nuestra postura inicial.'});
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Agregar cuestión'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', () => { questionParentId = null; render({cases: caseList}); });
    form.append(el('h3', {textContent: 'Nueva cuestión dentro de esta rama'}), el('div', {className: 'cases-form-grid'}, field('Enunciado', title, true), field('Planteo de la contraparte', adversary, true), field('Nuestra postura', position, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { await createNode({case_id: snapshot.case.id, node_kind: 'cuestion', parent_id: parentId, title: title.value, adversary_text: adversary.value, own_position: position.value}); questionParentId = null; } finally { submit.disabled = false; } });
    return form;
  }
  function scheduleAutosave(key, action) {
    clearTimeout(autosaveTimers.get(key));
    autosaveTimers.set(key, setTimeout(async () => {
      try { await action(); } catch (error) { alert('No se pudo guardar automáticamente.\n\n' + error.message); }
    }, 650));
  }
  function nodeTrail(nodes, targetId, trail) {
    const prior = trail || [];
    for (const item of nodes || []) {
      const next = prior.concat(item);
      if (item.id === targetId) return next;
      const found = nodeTrail(item.children || [], targetId, next); if (found.length) return found;
    }
    return [];
  }
  function availableDocuments(snapshot, node) {
    const all = snapshot.documents || [], byId = new Map(all.map(item => [item.id, item])), result = [], seen = new Set();
    const include = documentId => { const item = byId.get(Number(documentId)); if (item && !seen.has(item.id)) { seen.add(item.id); result.push(item); } };
    nodeTrail(snapshot.nodes || [], node.id).forEach(item => {
      include(item.primary_document_id);
      (item.sources || []).forEach(source => include(source.document_id));
    });
    all.forEach(item => include(item.id)); return result;
  }
  function compactSection(label, open, content) {
    const details = el('details', {className: 'argument-section'}); details.open = !!open;
    details.append(el('summary', {textContent: label}), el('div', {className: 'argument-section-body'}, content));
    return details;
  }
  function workspace(snapshot, node) {
    const box = el('section', {className: 'cases-card case-workspace'}), edit = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Editar'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Eliminar'}), hide = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Ocultar'});
    edit.addEventListener('click', async () => { const title = prompt('Nombre de la cuestión jurídica:', node.title); if (title === null) return; try { await updateNode(Object.assign({}, node, {title, adversary_text: node.adversary_text || '', own_position: node.own_position || ''})); } catch (error) { alert(error.message); } });
    remove.addEventListener('click', () => removeNode(node, 'Se eliminarán también sus bloques, resaltados y resultado de IA.')); hide.addEventListener('click', () => { expandedNodeId = null; render({cases: caseList}); });
    box.append(el('header', {className: 'workspace-head'}, el('div', {}, el('small', {textContent: 'Cuestión jurídica'}), el('h2', {textContent: node.title})), el('div', {className: 'case-actions'}, edit, remove, hide)));
    const editor = el('section', {className: 'workspace-editor'});
    editor.append(argumentSection(snapshot, node, 'contraparte', 'Planteo de la contraparte'));
    editor.append(argumentSection(snapshot, node, 'propia', 'Nuestra postura y fundamentos'));
    box.append(el('div', {className: 'workspace-layout'}, editor, sources(snapshot, node, activeWorkspaceSide))); return box;
  }
  function argumentSection(snapshot, node, side, label) {
    const blocks = (node.blocks && node.blocks[side]) || [], body = el('div', {});
    blocks.forEach((block, index) => body.append(argumentBlock(snapshot, node, side, block, index + 1)));
    const add = el('button', {type: 'button', className: 'cases-button-secondary', textContent: '+ Bloque'});
    add.addEventListener('click', async () => {
      try { const response = await api('/api/cases/block', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, side})}); currentCase = response.case; activeWorkspaceSide = side; await loadCases(false); } catch (error) { alert(error.message); }
    }); body.append(add);
    const details = compactSection(label + ' · ' + blocks.length + ' bloque(s)', activeWorkspaceSide === side, body);
    details.addEventListener('toggle', () => { if (details.open && activeWorkspaceSide !== side) { activeWorkspaceSide = side; render({cases: caseList}); } }); return details;
  }
  function argumentBlock(snapshot, node, side, block, number) {
    const text = el('textarea', {value: block.content || '', placeholder: side === 'contraparte' ? 'Desarrollá este planteo de la contraparte.' : 'Desarrollá este fundamento propio.'});
    const selectBlock = () => { activeEvidenceBlockId = block.id; };
    text.addEventListener('focus', selectBlock); text.addEventListener('pointerdown', selectBlock);
    text.addEventListener('input', () => scheduleAutosave('block:' + block.id, async () => {
      const response = await api('/api/cases/block/update', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, block_id: block.id, content: text.value, title: block.title || ''})}); currentCase = response.case;
    }));
    const evidence = actionIcon('add', 'Agregar fuente al párrafo'), remove = actionIcon('remove', 'Eliminar párrafo', 'cases-danger');
    evidence.addEventListener('click', () => { selectBlock(); openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node)); });
    remove.addEventListener('click', async () => { if (!confirm('¿Eliminar este bloque y sus resaltados?')) return; try { const response = await api('/api/cases/block/delete', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, block_id: block.id, confirmed: true})}); currentCase = response.case; await loadCases(false); } catch (error) { alert(error.message); } });
    const body = el('div', {className: 'argument-block-body'}, text);
    (block.highlights || []).forEach(highlight => {
      const excerpt = el('blockquote', {
        className: 'argument-evidence',
        textContent: highlight.selected_text,
        title: highlight.document_name + (highlight.page_start ? ' · pág. ' + highlight.page_start : ''),
      });
      // El texto insertado en el párrafo representa un resaltado guardado: el
      // clic principal debe abrir su editor, no el visor de sólo lectura.
      excerpt.addEventListener('click', () => openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node), highlight));
      body.append(excerpt);
    });
    const article = el('article', {className: 'argument-block'}); article.addEventListener('pointerdown', selectBlock); article.append(el('span', {className: 'argument-paragraph-number', textContent: String(number)}), body, el('div', {className: 'argument-block-actions'}, evidence, remove)); return article;
  }
  function sources(snapshot, node, side) {
    const sideLabel = side === 'propia' ? 'nuestra postura' : side === 'contraparte' ? 'el planteo de la contraparte' : 'la cuestión';
    const panel = el('aside', {className: 'workspace-sources'}, el('h3', {className: 'source-title', textContent: 'Resaltados incorporados'}), el('p', {className: 'source-help', textContent: 'Pasajes que ya integran ' + sideLabel + '. Podés editarlos o quitarlos; se guardan literalmente como los elegiste.'}));
    const blocks = side === 'enunciado' ? [] : ((node.blocks && node.blocks[side]) || []), highlights = [];
    blocks.forEach(block => (block.highlights || []).forEach(highlight => highlights.push({block, highlight})));
    if (side === 'enunciado') panel.append(el('p', {className: 'sources-empty', textContent: 'El enunciado no lleva fuentes. Abrí el planteo de la contraparte o nuestra postura.'}));
    else if (!highlights.length) panel.append(el('p', {className: 'sources-empty', textContent: 'Todavía no hay resaltados en estos bloques.'}));
    highlights.forEach(item => panel.append(highlightItem(snapshot, node, item.block, item.highlight)));
    if (side !== 'enunciado') {
      const candidates = availableDocuments(snapshot, node), candidateBox = el('div', {className: 'source-link-form'}, el('h3', {className: 'source-title', textContent: 'Archivos del caso'}), el('p', {className: 'source-help', textContent: 'Todavía no son fundamento: elegí uno para seleccionar el pasaje que querés incorporar al párrafo activo.'}));
      if (!candidates.length) candidateBox.append(el('p', {className: 'sources-empty', textContent: 'Cargá un archivo en la rama para poder crear una cuestión respaldada.'}));
      candidates.slice(0, 8).forEach(doc => {
        const choose = actionIcon('add', 'Seleccionar un pasaje de este archivo');
        choose.addEventListener('click', () => {
          const block = blocks.find(item => item.id === activeEvidenceBlockId);
          if (!block) return alert('Primero hacé clic dentro del párrafo al que querés vincular este pasaje.');
          openEvidenceDialog(snapshot, node, block, [doc]);
        });
        candidateBox.append(el('div', {className: 'evidence-candidate'}, el('b', {textContent: doc.document_name}), choose));
      }); panel.append(candidateBox);
      panel.append(el('p', {className: 'sources-drop-help', textContent: 'Para incorporar un archivo nuevo, seleccioná primero el bloque y arrastrá aquí el archivo.'}));
      panel.addEventListener('dragover', event => { event.preventDefault(); panel.classList.add('drop-target'); });
      panel.addEventListener('dragleave', event => { if (!panel.contains(event.relatedTarget)) panel.classList.remove('drop-target'); });
      panel.addEventListener('drop', event => {
        event.preventDefault(); panel.classList.remove('drop-target');
        const block = blocks.find(item => item.id === activeEvidenceBlockId);
        if (!block) return alert('Primero hacé clic dentro del bloque al que querés vincular el archivo.');
        if (event.dataTransfer?.files?.length) importBlockFiles(snapshot, node, block, event.dataTransfer.files, panel);
      });
    }
    return panel;
  }
  function highlightItem(snapshot, node, block, highlight) {
    const details = el('details', {className: 'source-accordion'}), open = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Ver documento'}), edit = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Editar resaltado'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Quitar'});
    open.addEventListener('click', () => openSource(highlight)); edit.addEventListener('click', () => openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node), highlight));
    remove.addEventListener('click', async () => { if (!confirm('¿Quitar este resaltado del bloque?')) return; try { const response = await api('/api/cases/block/highlight/delete', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, highlight_id: highlight.id, confirmed: true})}); currentCase = response.case; await loadCases(false); } catch (error) { alert(error.message); } });
    details.append(el('summary', {textContent: highlight.document_name + (highlight.page_start ? ' · pág. ' + highlight.page_start : '')}), el('div', {className: 'source-body'}, el('p', {textContent: highlight.selected_text}), el('div', {className: 'source-actions'}, open, edit, remove))); return details;
  }
  function openSource(source) {
    const path = String(source.document_path || '').trim(); if (!path) return alert('Esta fuente no conserva una ruta local.');
    const pageNumber = Number(source.page_start || 0) || 1, snippet = String(source.selected_text || '').trim();
    if (typeof window.lexiaQuickViewerOpen === 'function') return window.lexiaQuickViewerOpen(path, pageNumber, snippet);
    window.open('/api/file-preview?path=' + encodeURIComponent(path), '_blank', 'noopener');
  }
  function selectionOffsets(reader) {
    const selection = window.getSelection(); if (!selection || !selection.rangeCount || !selection.toString().trim()) return null;
    const range = selection.getRangeAt(0); if (!reader.contains(range.commonAncestorContainer)) return null;
    const prefix = range.cloneRange(); prefix.selectNodeContents(reader); prefix.setEnd(range.startContainer, range.startOffset);
    const selected = selection.toString().trim(), start = prefix.toString().length;
    return {text: selected, start, end: start + selected.length};
  }
  function openEvidenceDialog(snapshot, node, block, documents, existing) {
    if (!documents.length) return alert('Primero cargá o vinculá un archivo a la rama del caso.');
    const dialog = el('dialog', {className: 'lexia-evidence-dialog'}), select = el('select', {className: 'workspace-enunciado'}), reader = el('pre', {className: 'evidence-reader', textContent: 'Elegí un documento para cargar su texto indexado.'}), status = el('p', {className: 'evidence-selection-status', textContent: 'Seleccioná con el mouse el pasaje exacto que querés conservar.'});
    documents.forEach(doc => select.append(el('option', {value: String(doc.id), textContent: doc.document_name})));
    if (existing) select.value = String(existing.case_document_id);
    const cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'}), save = el('button', {type: 'button', className: 'cases-button', textContent: existing ? 'Reemplazar resaltado' : 'Incorporar resaltado'});
    let selected = null, preview = null;
    const selectedDocument = () => documents.find(item => String(item.id) === select.value);
    const load = async () => {
      selected = null; status.textContent = 'Cargando el texto indexado de LexIA…'; reader.textContent = '';
      try {
        const doc = selectedDocument(), data = await api('/api/catalog-text-preview?path=' + encodeURIComponent(doc.document_path));
        preview = data; reader.textContent = data.text || '';
        status.textContent = 'Seleccioná con el mouse el pasaje exacto que querés conservar.';
      } catch (error) { preview = null; reader.textContent = ''; status.textContent = 'No se pudo cargar texto seleccionable: ' + error.message; }
    };
    const capture = () => { selected = selectionOffsets(reader); if (selected) status.textContent = selected.text.length + ' caracteres seleccionados. Se guardará exactamente ese texto.'; };
    reader.addEventListener('mouseup', capture); reader.addEventListener('keyup', capture); select.addEventListener('change', load);
    cancel.addEventListener('click', () => { dialog.close(); dialog.remove(); });
    save.addEventListener('click', async () => {
      selected = selectionOffsets(reader) || selected;
      if (!selected || !selected.text) return alert('Seleccioná un pasaje del documento antes de incorporarlo.');
      const doc = selectedDocument(), segment = (preview?.segments || []).find(item => selected.start < Number(item.end_char || 0) && selected.end > Number(item.start_char || 0)), payload = {case_id: snapshot.case.id, selected_text: selected.text, page_start: segment?.page_start || null, page_end: segment?.page_end || null, anchor_data: JSON.stringify({start_char: selected.start, end_char: selected.end})};
      save.disabled = true;
      try {
        let response;
        if (existing) response = await api('/api/cases/block/highlight/update', {method: 'POST', body: JSON.stringify(Object.assign(payload, {highlight_id: existing.id}))});
        else response = await api('/api/cases/block/highlight', {method: 'POST', body: JSON.stringify(Object.assign(payload, {block_id: block.id, case_document_id: doc.id}))});
        currentCase = response.case; dialog.close(); dialog.remove(); await loadCases(false);
      } catch (error) { alert(error.message); } finally { save.disabled = false; }
    });
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Seleccionar evidencia para el bloque'}), cancel), el('div', {className: 'evidence-dialog-body'}, field('Documento del caso', select), reader, status, el('div', {className: 'evidence-dialog-actions'}, save)));
    document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open'); load();
  }
  function questionAiMaterial(node) {
    const side = name => ((node.blocks && node.blocks[name]) || []).map((block, index) => {
      const evidence = (block.highlights || []).map((item, itemIndex) => '[Fuente ' + (index + 1) + '.' + (itemIndex + 1) + ' · ' + item.document_name + (item.page_start ? ' · pág. ' + item.page_start : '') + ']\n' + item.selected_text).join('\n\n');
      return 'BLOQUE ' + (index + 1) + '\n' + (block.content || '(sin desarrollo)') + (evidence ? '\n\n' + evidence : '');
    }).join('\n\n') || '(sin bloques)';
    return 'CUESTIÓN\n' + node.title + '\n\nPLANTEO DE LA CONTRAPARTE\n' + side('contraparte') + '\n\nNUESTRA POSTURA Y FUNDAMENTOS\n' + side('propia');
  }
  function descendantQuestions(node, output) {
    const values = output || [];
    (node.children || []).forEach(child => {
      if (child.node_kind === 'cuestion') values.push(child);
      descendantQuestions(child, values);
    });
    return values;
  }
  function branchSelection(root, questions) {
    const valid = new Set(questions.map(question => question.id));
    let selected = selectedQuestionIdsByRoot.get(root.id);
    if (!selected) {
      selected = new Set(valid);
      selectedQuestionIdsByRoot.set(root.id, selected);
    } else {
      [...selected].forEach(id => { if (!valid.has(id)) selected.delete(id); });
    }
    return selected;
  }
  function buildBranchAiPackage(root, questions) {
    return 'INSTRUCCIÓN ESTRICTA\nRedactá exclusivamente sobre el material incluido abajo. No uses conocimiento externo, no completes datos ausentes, no inventes hechos, normas, antecedentes ni citas. Si una conclusión no surge de las fuentes, indicá expresamente: "No surge de las fuentes aportadas". Diferenciá con claridad el planteo contrario y nuestra postura.\n\nRAMA PRINCIPAL\n' + root.title + '\n\n' + questions.map((question, index) => '=== CUESTIÓN ' + (index + 1) + ' ===\n' + questionAiMaterial(question)).join('\n\n');
  }
  function branchAiSection(snapshot, root) {
    const questions = descendantQuestions(root), selected = branchSelection(root, questions), output = root.ai_output;
    const details = el('details', {className: 'branch-ai'}); details.open = !!output;
    const body = el('div', {}), options = el('div', {className: 'branch-ai-options'});
    questions.forEach(question => {
      const check = el('input', {type: 'checkbox'}); check.checked = selected.has(question.id);
      check.addEventListener('change', () => { if (check.checked) selected.add(question.id); else selected.delete(question.id); });
      options.append(el('label', {className: 'branch-ai-option', title: question.title}, check, el('span', {textContent: question.title})));
    });
    if (questions.length) body.append(options);
    else body.append(el('p', {className: 'sources-empty', textContent: 'Agregá al menos una cuestión antes de preparar una consulta.'}));
    let outputId = output ? output.id : null;
    const text = el('textarea', {value: output ? output.content : '', placeholder: 'Pegá aquí la respuesta de la IA para conservarla en la rama principal.'});
    text.addEventListener('input', () => scheduleAutosave('branch-ai:' + root.id, async () => {
      if (!text.value.trim() && !outputId) return;
      const chosen = questions.filter(question => selected.has(question.id)), packageText = buildBranchAiPackage(root, chosen);
      const payload = {case_id: snapshot.case.id, content: text.value, status: 'borrador'};
      const response = outputId
        ? await api('/api/cases/node/ai-output/update', {method: 'POST', body: JSON.stringify(Object.assign(payload, {output_id: outputId}))})
        : await api('/api/cases/node/ai-output', {method: 'POST', body: JSON.stringify(Object.assign(payload, {node_id: root.id, prompt: packageText, source_package: packageText}))});
      currentCase = response.case;
      outputId = findNode(response.case.nodes || [], root.id)?.ai_output?.id || outputId;
    }));
    const prepare = el('button', {type: 'button', className: 'cases-button', textContent: 'Preparar consulta IA'});
    prepare.addEventListener('click', () => {
      const chosen = questions.filter(question => selected.has(question.id));
      if (!chosen.length) return alert('Seleccioná al menos una cuestión.');
      const unsupported = chosen.some(question => ((question.blocks && question.blocks.contraparte) || []).some(block => !(block.highlights || []).length));
      if (unsupported) return alert('Cada bloque del planteo de la contraparte debe contener al menos un pasaje resaltado antes de consultar a la IA.');
      showAiPackage(buildBranchAiPackage(root, chosen));
    });
    body.append(el('div', {className: 'argument-block-actions'}, prepare), text);
    details.append(el('summary', {textContent: output ? 'Consulta a IA · resultado guardado' : 'Consulta a IA'}), body);
    return details;
  }
  function showAiPackage(packageText) {
    const dialog = el('dialog', {className: 'lexia-evidence-dialog'}), area = el('textarea', {className: 'evidence-reader', value: packageText}); area.style.height = '52vh';
    const close = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cerrar'}), copy = el('button', {type: 'button', className: 'cases-button', textContent: 'Copiar'});
    close.addEventListener('click', () => { dialog.close(); dialog.remove(); }); copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(packageText); copy.textContent = 'Copiado'; } catch (_) { area.select(); document.execCommand('copy'); copy.textContent = 'Copiado'; } });
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Paquete cerrado para IA'}), close), el('div', {className: 'evidence-dialog-body'}, area, el('div', {className: 'evidence-dialog-actions'}, copy))); document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open');
  }
  async function importBlockFiles(snapshot, node, block, fileList, target) {
    const files = Array.from(fileList || []); if (!files.length) return;
    const help = target.querySelector('.sources-drop-help'), previous = help ? help.textContent : '';
    if (help) help.textContent = 'Incorporando e indexando archivo…';
    try {
      const form = new FormData(); form.append('case_id', String(snapshot.case.id)); form.append('node_id', String(node.id)); files.forEach(file => form.append('files', file, file.name));
      const response = await fetch('/api/cases/import', {method: 'POST', body: form}), data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) throw new Error(data.error || ('HTTP ' + response.status));
      currentCase = data.case;
      const refreshedNode = findNode(data.case.nodes || [], node.id), allBlocks = Object.values(refreshedNode?.blocks || {}).flat(), refreshedBlock = allBlocks.find(item => item.id === block.id), importedPath = (data.linked || [])[0], document = (data.case.documents || []).find(item => item.document_path === importedPath);
      await loadCases(false);
      if (refreshedNode && refreshedBlock && document) openEvidenceDialog(data.case, refreshedNode, refreshedBlock, availableDocuments(data.case, refreshedNode));
      else alert('El archivo fue incorporado. Seleccionalo con “+ Fuente” para elegir el pasaje que respaldará este bloque.');
    } catch (error) { alert('No se pudo incorporar el archivo a este bloque.\n\n' + error.message); }
    finally { if (help) help.textContent = previous; }
  }
  async function importBranchFiles(snapshot, node, fileList, button) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const original = button.textContent;
    button.disabled = true; button.textContent = 'Cargando…';
    try {
      const form = new FormData();
      form.append('case_id', String(snapshot.case.id));
      form.append('node_id', String(node.id));
      files.forEach(file => form.append('files', file, file.name));
      const response = await fetch('/api/cases/import', {method: 'POST', body: form});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) throw new Error(data.error || ('HTTP ' + response.status));
      currentCase = data.case;
      await loadCases(false);
      const imported = (data.imported || []).length, skipped = (data.skipped || []).length;
      const suffix = skipped ? (' · ' + skipped + ' ya existía(n)') : '';
      alert(imported + ' archivo(s) incorporado(s) en Escritos\\Casos\\' + snapshot.case.name + suffix + '.');
    } catch (error) {
      alert('No se pudieron cargar los archivos en esta rama.\n\n' + error.message);
    } finally {
      button.disabled = false; button.textContent = original;
    }
  }
  async function createNode(payload) { try { const response = await api('/api/cases/node', {method: 'POST', body: JSON.stringify(payload)}); currentCase = response.case; await loadCases(false); } catch (error) { alert(error.message); throw error; } }
  async function updateNode(node) { const response = await api('/api/cases/node/update', {method: 'POST', body: JSON.stringify({case_id: currentCase.case.id, node_id: node.id, title: node.title, adversary_text: node.adversary_text || '', own_position: node.own_position || '', primary_document_id: node.primary_document_id || null})}); currentCase = response.case; await loadCases(false); }
  async function removeNode(node, detail) {
    if (!confirm('¿Eliminar “' + node.title + '”?\\n\\n' + detail + '\\nLos documentos originales de LexIA no se borrarán.')) return;
    try { const response = await api('/api/cases/node/delete', {method: 'POST', body: JSON.stringify({case_id: currentCase.case.id, node_id: node.id, confirmed: true})}); currentCase = response.case; if (expandedNodeId === node.id) expandedNodeId = null; await loadCases(false); } catch (error) { alert(error.message); }
  }
  async function loadCases(refresh) {
    if (refresh === undefined) refresh = true;
    try { const response = await api('/api/cases'); caseList = response.cases || []; if (refresh && currentCase && currentCase.case) { const selected = caseList.find(item => item.id === currentCase.case.id); if (selected) return loadCase(selected.id, response); currentCase = null; expandedNodeId = null; } render(response); } catch (error) { page().querySelector('.cases-main').textContent = 'No se pudieron cargar los casos: ' + error.message; }
  }
  async function loadCase(caseId, alreadyLoaded) {
    try { const response = await api('/api/cases/' + caseId); currentCase = response.case; expandedNodeId = null; editingCase = false; showNewCase = false; render(alreadyLoaded || await api('/api/cases')); } catch (error) { alert(error.message); }
  }
  async function cardDocument(card) {
    const name = card.querySelector('.result-title,.result-title-btn,.source-name-link,strong')?.textContent?.trim() || 'Documento';
    const snippet = card.querySelector('p,.source-snippet')?.textContent?.trim() || '';
    let path = card.querySelector('[data-path]')?.dataset.path || '';
    try { path = decodeURIComponent(path); } catch (_) {}
    if (!path) {
      const resolved = await api('/api/resolve-document', {method: 'POST', body: JSON.stringify({name: name, snippet: snippet})});
      path = resolved.path;
    }
    const pageNumber = Number(card.querySelector('[data-page]')?.dataset.page || 0) || null;
    const category = (card.querySelector('.result-meta,.source-meta small')?.textContent || '').split('·')[0].trim() || 'Documento';
    return {name: name, snippet: snippet, path: path, page: pageNumber, category: category};
  }
  async function caseToLink() {
    const response = await api('/api/cases'), items = response.cases || [];
    if (!items.length) throw new Error('Primero creá un caso en la sección Casos.');
    if (currentCase?.case?.id && items.some(item => item.id === currentCase.case.id)) return currentCase.case.id;
    const options = items.map((item, index) => (index + 1) + '. ' + item.name).join('\n');
    const selected = Number(prompt('¿A qué caso querés incorporarlo?\n\n' + options, '1'));
    if (!Number.isInteger(selected) || selected < 1 || selected > items.length) throw new Error('No se seleccionó un caso válido.');
    return items[selected - 1].id;
  }
  async function addCardToCase(card, button) {
    const previous = button.textContent; button.disabled = true; button.textContent = 'Incorporando…';
    try {
      const document = await cardDocument(card), caseId = await caseToLink();
      await api('/api/cases/link-document', {method: 'POST', body: JSON.stringify({case_id: caseId, document_name: document.name, document_path: document.path, category: document.category, relation_kind: 'fuente vinculada'})});
      if (document.snippet) await api('/api/cases/entry', {method: 'POST', body: JSON.stringify({case_id: caseId, entry_type: 'extracto documental', title: document.name, content: document.snippet, document_name: document.name, document_path: document.path, page_start: document.page, source_excerpt: document.snippet})});
      button.textContent = 'Incorporado'; setTimeout(() => { button.textContent = previous; button.disabled = false; }, 1000);
    } catch (error) { alert('No se pudo incorporar la fuente al caso.\n\n' + error.message); button.textContent = previous; button.disabled = false; }
  }
  function installDocumentActions(root) {
    const cards = [];
    if (root?.nodeType === 1 && root.matches('.result-card,.source-item')) cards.push(root);
    if (root?.querySelectorAll) cards.push(...root.querySelectorAll('.result-card,.source-item'));
    cards.forEach(card => {
      const actions = card.querySelector('.result-actions,.source-actions');
      if (!actions || actions.querySelector('[data-lexia-case-link]')) return;
      const button = el('button', {type: 'button', 'data-lexia-case-link': '1', className: 'lexia-case-link', textContent: 'Al caso', title: 'Vincular esta fuente y su extracto a un caso'});
      button.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); addCardToCase(card, button); });
      actions.append(button);
    });
  }
  function initialize() {
    style(); createPage(); navigation(); navigationExit();
    installDocumentActions(document);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === 1) installDocumentActions(node);
    }))).observe(document.body, {childList: true, subtree: true});
    if ((location.hash || '').slice(1) === PAGE_ID) show();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true}); else initialize();
})();
