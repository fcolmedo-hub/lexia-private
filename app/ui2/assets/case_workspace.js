/* LexIA Casos 2.0 — estructura procesal local, sin llamadas a IA. */
(function () {
  'use strict';
  const PAGE_ID = 'casespage';
  let currentCase = null, caseList = [], expandedNodeId = null;
  const openPrimaryIds = new Set();
  let activeEvidenceBlockId = null;
  const selectedQuestionIdsByRoot = new Map();
  let editingCase = false;
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
      ai: '<path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"></path><path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"></path>',
      replace: '<path d="M7 7h10l-3-3"></path><path d="M17 7l-3 3"></path><path d="M17 17H7l3 3"></path><path d="M7 17l3-3"></path>',
      refresh: '<path d="M20 11a8 8 0 1 0 2 5"></path><path d="M20 4v7h-7"></path>',
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
  function safeDownloadName(value) {
    return String(value || 'documento').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 100);
  }
  function downloadTextFile(filename, content) {
    const blob = new Blob([String(content || '')], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob), link = el('a', {href: url, download: filename, hidden: 'hidden'});
    document.body.append(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function isWorkspaceControl(target) {
    return !!target.closest?.('button,input,textarea,select,a,label');
  }
  function enableDoubleClickToggle(element, toggle) {
    element.addEventListener('dblclick', event => {
      if (isWorkspaceControl(event.target)) return;
      event.preventDefault(); toggle();
    });
  }
  function style() {
    if (document.getElementById('lexiaCasesStyle')) return;
    const css = [
      '#searchpage #realSearchResults .result-card:not(:has(.result-actions>.score)){box-sizing:border-box!important;min-height:62px!important;height:auto!important;max-height:none!important;padding:10px 14px!important;align-items:center!important;overflow:visible!important}#searchpage #realSearchResults .result-card:not(:has(.result-actions>.score)) .result-body{box-sizing:border-box!important;display:flex!important;flex-direction:column!important;align-items:flex-start!important;justify-content:center!important;gap:3px!important;min-width:0!important;min-height:40px!important;height:auto!important;overflow:hidden!important}#searchpage #realSearchResults .result-card:not(:has(.result-actions>.score)) .result-title{display:block!important;width:100%!important;min-width:0!important;line-height:1.3!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}#searchpage #realSearchResults .result-card:not(:has(.result-actions>.score)) .result-meta{display:block!important;box-sizing:border-box!important;width:100%!important;min-width:0!important;margin:0!important;line-height:1.25!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}',
      '#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-open{background:#149d55!important;border-color:#149d55!important;color:#fff!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-open:hover{background:#0f8044!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-investigate{background:#5146f6!important;border-color:#5146f6!important;color:#fff!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-investigate:hover{background:#4338e8!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-info{background:#f4c542!important;border-color:#d7a817!important;color:#453300!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-info:hover{background:#e7b82f!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-case{background:#8a5a2b!important;border-color:#8a5a2b!important;color:#fff!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-case:hover{background:#70451f!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-ocr{background:#e87514!important;border-color:#e87514!important;color:#fff!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-ocr:hover{background:#c95e08!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-delete{background:#c93645!important;border-color:#c93645!important;color:#fff!important}#searchpage #realSearchResults .result-menu-popover button.result-menu-item.result-menu-delete:hover{background:#aa2937!important}',
      '#' + PAGE_ID + '{display:none;position:fixed;z-index:20;inset:0 0 0 var(--global-side,0px);background:#f6f7fb;color:#202a48;overflow:auto;box-sizing:border-box}',
      '#' + PAGE_ID + ' .cases-main{box-sizing:border-box;width:100%;max-width:none;margin:0;padding:18px 24px 34px}',
      '#' + PAGE_ID + ' .cases-toolbar{display:flex;gap:8px;margin-bottom:12px;align-items:flex-start}#' + PAGE_ID + ' .cases-picker{position:relative;flex:1;min-width:180px}#' + PAGE_ID + ' .cases-picker summary{box-sizing:border-box;display:flex;align-items:center;gap:8px;width:100%;min-height:34px;padding:8px 11px;border:1px solid #dce1ed;border-radius:8px;background:#fff;color:#263154;cursor:pointer;font-size:12px;font-weight:800;list-style:none}#' + PAGE_ID + ' .cases-picker summary::-webkit-details-marker{display:none}#' + PAGE_ID + ' .cases-picker summary:after{content:"▾";margin-left:auto;color:#6257dc;font-size:12px}#' + PAGE_ID + ' .cases-picker[open] summary{border-color:#8176fa;border-radius:8px 8px 0 0;box-shadow:0 0 0 2px rgba(93,81,244,.1)}#' + PAGE_ID + ' .cases-picker[open] summary:after{transform:rotate(180deg)}#' + PAGE_ID + ' .cases-picker-menu{position:absolute;z-index:60;top:100%;left:0;right:0;padding:7px;border:1px solid #8176fa;border-top:0;border-radius:0 0 8px 8px;background:#fff;box-shadow:0 10px 22px rgba(34,42,79,.16)}#' + PAGE_ID + ' .cases-picker-menu input{box-sizing:border-box;width:100%;padding:7px 8px;border:1px solid #dce1ed;border-radius:6px;background:#fafaff;font:inherit;font-size:11px;color:#263154}#' + PAGE_ID + ' .cases-picker-list{display:grid;gap:2px;max-height:245px;margin-top:6px;overflow:auto}#' + PAGE_ID + ' .cases-picker-option{display:flex;align-items:center;gap:7px;width:100%;padding:7px 8px;border:0;border-radius:6px;background:transparent;color:#303a60;text-align:left;cursor:pointer;font:inherit;font-size:11px}#' + PAGE_ID + ' .cases-picker-option:hover{background:#f1efff}#' + PAGE_ID + ' .cases-picker-option.is-current{background:#f0efff;color:#493de2;font-weight:800}#' + PAGE_ID + ' .cases-picker-check{width:13px;color:#5146f6;font-weight:900;text-align:center}',
      '#' + PAGE_ID + ' .cases-button,#' + PAGE_ID + ' .cases-button-secondary,#' + PAGE_ID + ' .cases-icon{box-sizing:border-box;min-height:0;font:inherit!important;font-size:9px!important;line-height:1.1!important;font-weight:800;cursor:pointer;border-radius:6px;padding:5px 7px!important}#' + PAGE_ID + ' .cases-button{background:#5146f6;color:#fff;border:1px solid #5146f6}#' + PAGE_ID + ' .cases-button:hover{background:#4136df}#' + PAGE_ID + ' .cases-button-secondary{background:#fff;color:#465176;border:1px solid #d8deed}#' + PAGE_ID + ' .cases-button-secondary:hover{border-color:#6459f4;color:#493de2}#' + PAGE_ID + ' .cases-icon{background:transparent;color:#5f6989;border:0;padding:4px 5px!important}#' + PAGE_ID + ' .cases-icon:hover{background:#f0efff;color:#493de2}#' + PAGE_ID + ' .cases-danger{border-color:#f0c7ce;color:#b23848}#' + PAGE_ID + ' .cases-danger:hover{background:#fff4f5;border-color:#df7786;color:#9d2939}',
      '.cases-card{background:#fff;border:1px solid #e0e5ef;border-radius:14px;box-shadow:0 3px 14px rgba(31,39,76,.045)}.cases-empty{padding:22px;color:#74809d;font-size:13px;text-align:center}.cases-create{margin-bottom:16px;padding:16px}.cases-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cases-field{display:grid;gap:5px}.cases-field.wide{grid-column:1/-1}.cases-field label{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.035em;color:#6b7593}.cases-field input,.cases-field textarea,.cases-field select{box-sizing:border-box;width:100%;border:1px solid #dce1ed;border-radius:8px;padding:9px 10px;font:inherit;font-size:12px;color:#273153;background:#fff}.cases-field textarea{min-height:74px;resize:vertical}.cases-form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}',
      '.case-identification{padding:14px 16px;margin-bottom:12px}.case-identification-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.case-identification h1{margin:0;font-size:18px}.case-summary{margin:6px 0 0;max-width:930px;white-space:pre-wrap;color:#5f6b8c;font-size:11px;line-height:1.4}.case-actions{display:flex;gap:5px;flex-wrap:wrap}.case-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid #edf0f5}.case-fact small{display:block;font-size:9px;font-weight:800;color:#7a84a0;text-transform:uppercase;letter-spacing:.035em;margin-bottom:2px}.case-fact span{display:block;font-size:11px;color:#313b5e;overflow-wrap:anywhere}',
      '.case-tree{padding:13px 16px}.case-tree-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.case-tree-head h2{font-size:13px;margin:0}.case-tree-head p{font-size:10px;color:#74809d;margin:2px 0 0}.branch-form{margin:0 0 9px;padding:10px;background:#f8f8fd;border:1px dashed #cbd2e6;border-radius:8px}.branch-form h3{font-size:11px;margin:0 0 8px}.branch-list{display:grid;gap:7px}.primary-branch{border:1px solid #dce2f0;border-radius:9px;overflow:hidden}.primary-branch.drop-target{border-color:#6558f5;box-shadow:0 0 0 3px rgba(101,88,245,.14)}.primary-head{display:flex;align-items:center;gap:7px;padding:7px 9px;background:#fbfbff}.branch-mark{display:grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#eeeaff;color:#5548ef;font-size:11px;font-weight:900}.branch-title{flex:1;min-width:0}.branch-title b{display:block;font-size:11px;color:#283257}.branch-title small{display:block;margin-top:1px;color:#75809b;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.branch-actions{display:flex;gap:1px;align-items:center}.branch-questions{padding:6px 8px 8px;border-top:1px solid #edf0f6}.question-row{display:flex;align-items:center;gap:7px;border:1px solid #e4e8f2;border-radius:7px;padding:6px 7px;margin-top:5px;background:#fff}.question-row:first-child{margin-top:0}.question-row:hover{border-color:#bcb5ff;background:#fcfbff}.question-row strong{display:block;font-size:10px;color:#303a60;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row small{display:block;margin-top:1px;max-width:580px;font-size:9px;color:#78839e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row .cases-icon{border:1px solid #dbe0ee;padding:4px 6px!important;font-size:9px!important}.question-add{margin-top:6px;background:transparent;border:0;color:#5146f6;font-size:9px;font-weight:800;cursor:pointer;padding:3px 1px}.question-add:hover{text-decoration:underline}',
      '.case-workspace{margin-top:16px;min-height:520px;overflow:hidden}.workspace-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:15px 18px;border-bottom:1px solid #e6eaf2}.workspace-head small{display:block;color:#78829c;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}.workspace-head h2{margin:0;font-size:16px;color:#263156}.workspace-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(285px,.42fr);min-height:460px}.workspace-editor{padding:18px;border-right:1px solid #e8ebf3}.workspace-sources{padding:16px;background:#fbfbfe}.workspace-section{margin-bottom:16px}.workspace-section h3{font-size:11px;text-transform:uppercase;letter-spacing:.035em;color:#687492;margin:0 0 7px}.workspace-section textarea,.workspace-section input{box-sizing:border-box;width:100%;font:inherit;font-size:13px;line-height:1.5;color:#293357;border:1px solid #dce2ee;border-radius:9px;padding:10px;background:#fff}.workspace-section textarea{min-height:112px;resize:vertical}.workspace-section textarea.own-position{min-height:180px}.workspace-save{display:flex;justify-content:flex-end}.source-title{font-size:13px;margin:0 0 8px;color:#2b3559}.source-help{font-size:11px;line-height:1.4;color:#74809d;margin:0 0 10px}.source-accordion{border:1px solid #e0e5ef;border-radius:9px;background:#fff;margin:8px 0}.source-accordion summary{cursor:pointer;list-style:none;padding:9px 10px;font-size:11px;font-weight:800;color:#354064}.source-accordion summary::-webkit-details-marker{display:none}.source-accordion summary:before{content:"▸";display:inline-block;color:#5b4ff1;margin-right:7px}.source-accordion[open] summary:before{transform:rotate(90deg)}.source-body{border-top:1px solid #edf0f5;padding:9px 10px}.source-body p{white-space:pre-wrap;font-size:11px;line-height:1.45;color:#56617e;margin:0 0 9px}.source-actions{display:flex;gap:7px;justify-content:flex-end}.source-link-form{margin-top:13px;padding-top:13px;border-top:1px solid #e4e8f1}.source-link-form select{margin-bottom:7px}.source-link-form .cases-button{width:100%;margin-top:7px}.sources-empty{padding:13px 4px;color:#7b85a1;font-size:11px;line-height:1.4}',
      '#' + PAGE_ID + ' .case-workspace{margin:5px 0 7px;min-height:0;overflow:hidden;border-color:#d6dcef}#' + PAGE_ID + ' .workspace-head{padding:9px 11px}#' + PAGE_ID + ' .workspace-head h2{font-size:13px}#' + PAGE_ID + ' .workspace-layout{grid-template-columns:minmax(0,1fr) 300px;min-height:0}#' + PAGE_ID + ' .workspace-editor{padding:8px 10px;border-right:1px solid #e8ebf3}#' + PAGE_ID + ' .workspace-sources{padding:10px;background:#fbfbfe}#' + PAGE_ID + ' .argument-section{border-bottom:1px solid #e7eaf2}#' + PAGE_ID + ' .argument-section:last-child{border-bottom:0}#' + PAGE_ID + ' .argument-section summary{cursor:pointer;list-style:none;padding:8px 2px;font-size:10px;font-weight:800;color:#344064}#' + PAGE_ID + ' .argument-section summary::-webkit-details-marker{display:none}#' + PAGE_ID + ' .argument-section summary:before{content:"▸";display:inline-block;color:#5b4ff1;margin-right:6px}#' + PAGE_ID + ' .argument-section[open] summary:before{transform:rotate(90deg)}#' + PAGE_ID + ' .argument-section-body{padding:0 2px 9px}#' + PAGE_ID + ' .argument-block{margin:5px 0;padding:7px;border:1px solid #e2e6f0;border-radius:7px;background:#fff}#' + PAGE_ID + ' .argument-block-head{display:flex;justify-content:space-between;gap:6px;align-items:center;margin-bottom:5px;color:#697594;font-size:9px;font-weight:800}#' + PAGE_ID + ' .argument-block textarea{box-sizing:border-box;width:100%;min-height:64px;resize:vertical;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;line-height:1.35;color:#293357}#' + PAGE_ID + ' .argument-block-actions{display:flex;justify-content:flex-end;gap:4px;margin-top:5px}#' + PAGE_ID + ' .workspace-enunciado{box-sizing:border-box;width:100%;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;color:#293357}#' + PAGE_ID + ' .workspace-ai{margin-top:4px;padding-top:4px}#' + PAGE_ID + ' .source-title{font-size:11px;margin:0 0 5px}#' + PAGE_ID + ' .source-help{font-size:9px;line-height:1.35;margin:0 0 7px}#' + PAGE_ID + ' .source-accordion{margin:5px 0;border-radius:7px}#' + PAGE_ID + ' .source-accordion summary{padding:7px 8px;font-size:9px}#' + PAGE_ID + ' .source-body{padding:7px 8px}#' + PAGE_ID + ' .source-body p{font-size:9px;line-height:1.35;margin:0 0 6px}#' + PAGE_ID + ' .evidence-candidate{display:flex;align-items:center;gap:5px;padding:6px 0;border-bottom:1px solid #edf0f5;font-size:9px;color:#465176}#' + PAGE_ID + ' .evidence-candidate:last-child{border-bottom:0}#' + PAGE_ID + ' .evidence-candidate b{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#' + PAGE_ID + ' .lexia-evidence-dialog{width:min(940px,92vw);max-width:940px;border:1px solid #d8deeb;border-radius:12px;padding:0;box-shadow:0 20px 70px rgba(20,30,65,.28)}#' + PAGE_ID + ' .lexia-evidence-dialog::backdrop{background:rgba(24,31,56,.34)}#' + PAGE_ID + ' .evidence-dialog-head{padding:11px 13px;border-bottom:1px solid #e6eaf2;display:flex;justify-content:space-between;gap:8px;align-items:center}#' + PAGE_ID + ' .evidence-dialog-head b{font-size:12px}#' + PAGE_ID + ' .evidence-dialog-body{padding:11px 13px}#' + PAGE_ID + ' .evidence-reader{height:min(52vh,520px);overflow:auto;white-space:pre-wrap;user-select:text;padding:10px;border:1px solid #dce2ee;border-radius:7px;background:#fcfcff;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#283254}#' + PAGE_ID + ' .evidence-selection-status{margin:7px 0;color:#687492;font-size:10px}#' + PAGE_ID + ' .evidence-dialog-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:8px}',
      '#' + PAGE_ID + ' .argument-block{display:grid;grid-template-columns:17px minmax(0,1fr) auto;column-gap:5px;align-items:start;margin:1px 0;padding:2px 0;border:0;border-radius:0;background:transparent}#' + PAGE_ID + ' .argument-block + .argument-block{border-top:1px solid #edf0f5;padding-top:4px}#' + PAGE_ID + ' .argument-paragraph-number{display:grid;place-items:center;width:16px;height:16px;margin-top:3px;border-radius:50%;background:#eeeaff;color:#5648ed;font-size:8px;font-weight:800}#' + PAGE_ID + ' .argument-block-body{min-width:0}#' + PAGE_ID + ' .argument-block textarea{min-height:24px!important;height:24px;border-color:transparent;background:#fcfcff;padding:3px 5px!important;font-size:10px!important;line-height:1.25!important;overflow:hidden!important}#' + PAGE_ID + ' .argument-block textarea:focus{border-color:#b9b3ff;background:#fff}#' + PAGE_ID + ' .argument-block-actions{margin:1px 0 0;display:flex;gap:2px;align-items:flex-start}#' + PAGE_ID + ' .argument-evidence{margin:2px 0 0;padding:4px 6px;border-left:2px solid #8075fa;background:#f8f7ff;white-space:pre-wrap;font-size:9px;line-height:1.3;color:#4e5878}#' + PAGE_ID + ' .argument-evidence:first-of-type{margin-top:2px}#' + PAGE_ID + ' .workspace-sources.drop-target{outline:2px dashed #6558f5;outline-offset:-5px;background:#f3f1ff}#' + PAGE_ID + ' .sources-drop-help{margin:7px 0 0;padding:8px;border:1px dashed #c9c3ff;border-radius:7px;color:#6257db;font-size:9px;text-align:center}#' + PAGE_ID + ' .branch-actions .cases-icon,#' + PAGE_ID + ' .question-row .cases-icon{display:grid;place-items:center;min-width:22px;padding:4px!important}#' + PAGE_ID + ' .cases-icon svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}#' + PAGE_ID + ' .evidence-dialog-head{justify-content:space-between}#' + PAGE_ID + ' .evidence-reader{box-sizing:border-box!important;display:block!important;width:100%!important;max-width:100%!important;min-width:0!important;white-space:pre-wrap!important;overflow-x:hidden!important;overflow-y:auto!important;overflow-wrap:anywhere!important;word-break:break-word!important;tab-size:4}#' + PAGE_ID + ' .branch-ai{margin:8px 8px 2px;padding:8px 9px;border-top:1px solid #e5e8f1;background:#fbfbfe}#' + PAGE_ID + ' .branch-ai summary{cursor:pointer;color:#38436a;font-size:10px;font-weight:800}#' + PAGE_ID + ' .branch-ai-options{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}#' + PAGE_ID + ' .branch-ai-option{display:flex;align-items:center;gap:4px;max-width:100%;padding:4px 6px;border:1px solid #e0e4ee;border-radius:6px;background:#fff;color:#56617f;font-size:9px}#' + PAGE_ID + ' .branch-ai-option span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}#' + PAGE_ID + ' .branch-ai textarea{box-sizing:border-box;width:100%;min-height:96px;margin-top:7px;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;line-height:1.4;color:#293357}',
      '#' + PAGE_ID + ' .argument-block{display:grid;grid-template-columns:17px minmax(0,1fr) auto;column-gap:5px;align-items:start;margin:1px 0;padding:2px 0;border:0;border-radius:0;background:transparent}#' + PAGE_ID + ' .argument-block + .argument-block{border-top:1px solid #edf0f5;padding-top:4px}#' + PAGE_ID + ' .argument-paragraph-number{display:grid;place-items:center;width:16px;height:16px;margin-top:3px;border-radius:50%;background:#eeeaff;color:#5648ed;font-size:9px;font-weight:800}#' + PAGE_ID + ' .argument-block-body{min-width:0}#' + PAGE_ID + ' .argument-block textarea{min-height:27px!important;height:27px;border-color:transparent;background:#fcfcff;padding:4px 5px!important;font-size:11px!important;line-height:1.3!important;overflow:hidden!important}#' + PAGE_ID + ' .argument-block textarea:focus{border-color:#b9b3ff;background:#fff}#' + PAGE_ID + ' .argument-block-actions{margin:1px 0 0;display:flex;gap:2px;align-items:flex-start}#' + PAGE_ID + ' .argument-evidence{margin:3px 0 0;padding:6px 7px;border-left:2px solid #8075fa;background:#f8f7ff;white-space:pre-wrap;font-size:11px;line-height:1.4;color:#4e5878;cursor:pointer}#' + PAGE_ID + ' .argument-evidence:hover{background:#efedff;box-shadow:inset 0 0 0 1px #c5bfff}#' + PAGE_ID + ' .argument-evidence:focus{outline:2px solid #8176fa;outline-offset:1px}#' + PAGE_ID + ' .argument-evidence:first-of-type{margin-top:3px}#' + PAGE_ID + ' .case-identification{padding:10px 12px;margin-bottom:9px}#' + PAGE_ID + ' .case-identification h1{font-size:15px}#' + PAGE_ID + ' .case-identification .case-summary{margin-top:4px;font-size:10px;line-height:1.3}#' + PAGE_ID + ' .case-identification .case-facts{gap:6px;margin-top:8px;padding-top:8px}#' + PAGE_ID + ' .case-identification .case-fact small{font-size:8px;margin-bottom:1px}#' + PAGE_ID + ' .case-identification .case-fact span{font-size:10px}#' + PAGE_ID + ' .case-identification .cases-form-grid{gap:7px}#' + PAGE_ID + ' .case-identification .cases-field{gap:3px}#' + PAGE_ID + ' .case-identification .cases-field label{font-size:8px}#' + PAGE_ID + ' .case-identification .cases-field input,#' + PAGE_ID + ' .case-identification .cases-field textarea{padding:6px 8px;font-size:11px;line-height:1.25}#' + PAGE_ID + ' .case-identification .cases-field textarea{min-height:52px}#' + PAGE_ID + ' .case-identification .cases-form-actions{margin-top:7px}#' + PAGE_ID + ' .workspace-sources.drop-target{outline:2px dashed #6558f5;outline-offset:-5px;background:#f3f1ff}#' + PAGE_ID + ' .sources-drop-help{margin:7px 0 0;padding:8px;border:1px dashed #c9c3ff;border-radius:7px;color:#6257db;font-size:9px;text-align:center}#' + PAGE_ID + ' .argument-section summary{font-size:11px}#' + PAGE_ID + ' .branch-actions .cases-icon,#' + PAGE_ID + ' .question-row .cases-icon{display:grid;place-items:center;min-width:22px;padding:4px!important}#' + PAGE_ID + ' .cases-icon svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}#' + PAGE_ID + ' .evidence-dialog-head{justify-content:space-between}#' + PAGE_ID + ' .evidence-reader{box-sizing:border-box!important;display:block!important;width:100%!important;max-width:100%!important;min-width:0!important;white-space:pre-wrap!important;overflow-x:hidden!important;overflow-y:auto!important;overflow-wrap:anywhere!important;word-break:break-word!important;tab-size:4}#' + PAGE_ID + ' .branch-ai{margin:8px 8px 2px;padding:8px 9px;border-top:1px solid #e5e8f1;background:#fbfbfe}#' + PAGE_ID + ' .branch-ai summary{cursor:pointer;color:#38436a;font-size:10px;font-weight:800}#' + PAGE_ID + ' .branch-ai-options{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}#' + PAGE_ID + ' .branch-ai-option{display:flex;align-items:center;gap:4px;max-width:100%;padding:4px 6px;border:1px solid #e0e4ee;border-radius:6px;background:#fff;color:#56617f;font-size:9px}#' + PAGE_ID + ' .branch-ai-option span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}#' + PAGE_ID + ' .branch-ai textarea{box-sizing:border-box;width:100%;min-height:96px;margin-top:7px;padding:7px 8px;border:1px solid #dce2ee;border-radius:6px;font:inherit;font-size:11px;line-height:1.4;color:#293357}',
      '.cases-create-dialog{width:min(680px,92vw);max-width:680px}.cases-create-dialog .branch-form{margin:0;padding:2px;border:0;background:transparent}.cases-create-dialog .cases-form-actions{margin-bottom:0}.cases-new-case-dialog[open]{width:min(720px,92vw);max-width:720px;background:#fff}.cases-new-case-dialog::backdrop{background:#f6f7fb}.cases-new-case-dialog .cases-create{margin:0;padding:2px;border:0;box-shadow:none}',
      '.evidence-selection-dialog[open]{width:min(940px,92vw);height:min(84vh,720px);max-height:84vh;border:1px solid #d8deeb;border-radius:12px;padding:0;box-shadow:0 20px 70px rgba(20,30,65,.28);display:flex;flex-direction:column;overflow:hidden}.evidence-selection-dialog[open]::backdrop{background:rgba(24,31,56,.34)}.evidence-selection-dialog .evidence-dialog-head{flex:0 0 auto;padding:11px 13px;border-bottom:1px solid #e6eaf2;display:flex;justify-content:space-between;gap:8px;align-items:center}.evidence-selection-dialog .evidence-dialog-body{box-sizing:border-box;display:flex;flex:1 1 auto;flex-direction:column;min-height:0;overflow:hidden;padding:11px 13px}.evidence-selection-dialog .evidence-reader{box-sizing:border-box;display:block;flex:1 1 auto;width:100%;min-height:130px;height:auto!important;margin-top:8px;overflow:auto!important;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}.evidence-selection-dialog .evidence-selection-status{flex:0 0 auto;margin:7px 0}.evidence-selection-dialog .evidence-dialog-actions{flex:0 0 auto;display:flex;justify-content:flex-end;gap:6px;margin-top:0;padding-top:8px;background:#fff;border-top:1px solid #edf0f5}',
      '.case-ai-dialog[open]{box-sizing:border-box;width:min(900px,94vw);max-height:88vh;border:1px solid #d8deeb;border-radius:12px;padding:0;box-shadow:0 20px 70px rgba(20,30,65,.28);overflow:hidden}.case-ai-dialog::backdrop{background:rgba(24,31,56,.38)}.case-ai-dialog .evidence-dialog-head{padding:11px 13px;border-bottom:1px solid #e6eaf2;display:flex;justify-content:space-between;gap:8px;align-items:center}.case-ai-dialog .evidence-dialog-body{box-sizing:border-box;max-height:calc(88vh - 48px);padding:13px;overflow:auto}.case-ai-dialog .cases-button,.case-ai-dialog .cases-button-secondary{box-sizing:border-box;font:inherit;font-size:10px;line-height:1.1;font-weight:800;cursor:pointer;border-radius:6px;padding:7px 9px}.case-ai-dialog .cases-button{background:#5146f6;color:#fff;border:1px solid #5146f6}.case-ai-dialog .cases-button-secondary{background:#fff;color:#465176;border:1px solid #d8deed}.case-ai-intro{color:#596583;font-size:11px;line-height:1.45;margin:0 0 12px}.case-ai-option{display:flex;align-items:flex-start;gap:7px;padding:10px;border:1px solid #e1e5ef;border-radius:8px;background:#fafaff;color:#374162;font-size:11px}.case-ai-option input{margin-top:2px}.case-ai-status{min-height:18px;margin:9px 0;color:#6659e8;font-size:10px}.case-ai-preview-meta{margin:0 0 10px;color:#697493;font-size:10px}.case-ai-issue{margin:7px 0;padding:9px;border:1px solid #dfe4ef;border-radius:9px;background:#fff}.case-ai-issue-head{display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px;align-items:center}.case-ai-issue-head input[type=text]{box-sizing:border-box;width:100%;padding:6px 8px;border:1px solid #dce1ed;border-radius:6px;font:inherit;font-size:11px;font-weight:800;color:#293357}.case-ai-side{margin:7px 0 0;padding-top:6px;border-top:1px solid #edf0f5}.case-ai-side h4{margin:0 0 4px;color:#687492;font-size:9px;text-transform:uppercase}.case-ai-block{display:grid;grid-template-columns:auto minmax(0,1fr);gap:6px;margin:3px 0;padding:5px;background:#fafaff;border-radius:6px}.case-ai-block textarea{box-sizing:border-box;width:100%;min-height:45px;resize:vertical;padding:5px 6px;border:1px solid #e0e4ee;border-radius:5px;font:10px/1.35 inherit;color:#303a5e}.case-ai-quote{margin:4px 0 0;padding:5px 7px;border-left:2px solid #7c70f7;background:#f5f3ff;color:#56607d;font-size:9px;line-height:1.35;white-space:pre-wrap}.case-ai-dialog .cases-form-actions{position:sticky;bottom:-13px;margin:10px -13px -13px;padding:10px 13px;background:#fff;border-top:1px solid #e7eaf2}',
      '.case-ai-review{margin:7px 0 1px;padding:7px;border:1px solid #efc988;border-radius:6px;background:#fffaf0}.case-ai-review strong{display:block;color:#8a5b05;font-size:9px}.case-ai-review label{display:block;margin-top:5px;color:#6a7490;font-size:8px;font-weight:800;text-transform:uppercase}.case-ai-review pre{max-height:92px;margin:2px 0;padding:5px 6px;overflow:auto;white-space:pre-wrap;background:#fff;border-left:2px solid #e1ad45;color:#48526e;font:9px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace}.case-ai-review select{box-sizing:border-box;width:100%;margin-top:6px;padding:5px 6px;border:1px solid #d9c08c;border-radius:5px;background:#fff;color:#36405f;font:9px inherit}',
      '.case-ai-manual-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.case-ai-manual-response{box-sizing:border-box;width:100%;min-height:145px;margin-top:8px;padding:8px 9px;border:1px solid #dce2ee;border-radius:7px;resize:vertical;font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#293357}.case-ai-api-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:13px;padding-top:10px;border-top:1px solid #e8ebf3;color:#7a84a0;font-size:9px}',
      '#' + PAGE_ID + ' .evidence-reader{cursor:text!important;-webkit-user-select:text!important;user-select:text!important;caret-color:#5146f6;outline:none}#' + PAGE_ID + ' .evidence-reader.evidence-reader-editing{border-color:#d0ad16!important;box-shadow:inset 0 0 0 1px #f1d64f}#' + PAGE_ID + ' .evidence-reader::selection,#' + PAGE_ID + ' .evidence-reader *::selection{background:#f1d64f!important;color:#202944!important}#' + PAGE_ID + ' .evidence-existing-mark{background:#fff19c!important;color:#202944!important;padding:1px 0;border-radius:2px;box-shadow:0 0 0 1px #e1c542;-webkit-user-select:text!important;user-select:text!important}#' + PAGE_ID + ' .evidence-new-mark{background:#f1d64f!important;color:#202944!important;padding:1px 0;border-radius:2px;box-shadow:0 0 0 1px #d0ad16;-webkit-user-select:text!important;user-select:text!important}',
      '#' + PAGE_ID + ' .evidence-selection-list{display:flex;flex:0 0 auto;flex-wrap:wrap;gap:5px;margin:0 0 7px}#' + PAGE_ID + ' .evidence-selection-list[hidden]{display:none}#' + PAGE_ID + ' .evidence-selection-chip{box-sizing:border-box;padding:4px 7px;border:1px solid #e1c542;border-radius:999px;background:#fff9c7;color:#514300;font:800 9px/1.1 system-ui,sans-serif;cursor:pointer}#' + PAGE_ID + ' .evidence-selection-chip:hover{border-color:#c84955;background:#fff1f2;color:#a12635}',
      '#' + PAGE_ID + ' .question-number{box-sizing:border-box;width:auto!important;min-width:24px;padding:0 5px;white-space:nowrap}',
      '#' + PAGE_ID + ' .primary-head{gap:9px;padding:9px 11px}#' + PAGE_ID + ' .branch-mark{width:24px;height:24px;font-size:12px}#' + PAGE_ID + ' .branch-title b{font-size:13px;line-height:1.25}#' + PAGE_ID + ' .branch-title small{margin-top:2px;font-size:10px}#' + PAGE_ID + ' .branch-questions{padding:8px 10px 10px}#' + PAGE_ID + ' .question-row{gap:9px;padding:8px 9px;margin-top:6px}#' + PAGE_ID + ' .question-row strong{font-size:12px;line-height:1.28}#' + PAGE_ID + ' .question-row small{margin-top:2px;max-width:none;font-size:10px;line-height:1.3}#' + PAGE_ID + ' .question-row-active strong{font-size:13px}',
      '#' + PAGE_ID + ' .question-row-active{position:relative;z-index:1;margin-top:7px;padding:8px 9px;border-color:#8e85ff;background:#fbfaff;box-shadow:0 0 0 2px rgba(93,81,244,.10)}#' + PAGE_ID + ' .question-row-active strong{font-size:13px;color:#25305a;white-space:normal;overflow:visible}#' + PAGE_ID + ' .question-row-active small{display:none}#' + PAGE_ID + ' .case-workspace-inline{margin:0!important;border:1px solid #8e85ff!important;border-top:0!important;border-radius:0 0 8px 8px!important;box-shadow:0 2px 7px rgba(72,62,184,.08)!important}#' + PAGE_ID + ' .question-row-active + .case-workspace-inline{margin-top:-1px!important}#' + PAGE_ID + ' .case-workspace-inline .workspace-layout{min-height:0!important}#' + PAGE_ID + ' .case-workspace-inline .workspace-editor{padding-top:9px!important}',
      '#searchpage #realSearchResults .result-card{grid-template-columns:34px minmax(0,1fr) 72px!important;column-gap:12px!important;height:auto!important;max-height:none!important;min-height:0!important;padding:14px!important;overflow:visible!important;align-items:start!important}#searchpage #realSearchResults .result-body{display:block!important;min-width:0!important;height:auto!important;max-height:none!important;overflow:visible!important}#searchpage #realSearchResults .result-body p{display:block!important;visibility:visible!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}#searchpage #realSearchResults .result-actions{position:relative!important;display:flex!important;flex-direction:column!important;align-items:flex-end!important;justify-content:flex-start!important;width:72px!important;min-width:72px!important;max-width:72px!important;gap:7px!important;overflow:visible!important}#searchpage #realSearchResults .result-actions>.score{order:2!important;box-sizing:border-box!important;width:auto!important;min-width:0!important;max-width:72px!important;height:auto!important;min-height:0!important;padding:4px 6px!important;font-size:9px!important;line-height:1!important;white-space:nowrap!important}#searchpage #realSearchResults .result-action-menu{position:relative!important;order:1!important;display:block!important;width:30px!important;height:28px!important}#searchpage #realSearchResults .result-menu-toggle{box-sizing:border-box!important;width:30px!important;min-width:30px!important;height:28px!important;min-height:28px!important;padding:0!important;display:grid!important;place-items:center!important;border:1px solid #cfd5e5!important;border-radius:7px!important;background:#fff!important;color:#3d4563!important;font:900 18px/1 system-ui,sans-serif!important;letter-spacing:1px!important;cursor:pointer!important}#searchpage #realSearchResults .result-menu-toggle:hover,#searchpage #realSearchResults .result-menu-toggle[aria-expanded="true"]{border-color:#7168f5!important;background:#f3f1ff!important;color:#5146f6!important}#searchpage #realSearchResults .result-menu-popover{position:fixed!important;z-index:10120!important;box-sizing:border-box!important;width:220px!important;min-width:220px!important;padding:6px!important;display:flex!important;flex-direction:column!important;gap:2px!important;border:1px solid #dce1ed!important;border-radius:10px!important;background:#fff!important;box-shadow:0 14px 38px rgba(28,37,73,.22)!important}#searchpage #realSearchResults .result-menu-popover[hidden]{display:none!important}#searchpage #realSearchResults button.result-menu-item{box-sizing:border-box!important;width:100%!important;min-width:0!important;height:auto!important;min-height:34px!important;margin:0!important;padding:7px 9px!important;display:grid!important;grid-template-columns:20px minmax(0,1fr)!important;gap:8px!important;align-items:center!important;justify-items:start!important;border:0!important;border-radius:7px!important;background:#fff!important;color:#303a5b!important;font:700 11px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif!important;text-align:left!important;white-space:normal!important;cursor:pointer!important}#searchpage #realSearchResults button.result-menu-item:hover{background:#f4f3ff!important;color:#272e50!important}#searchpage #realSearchResults button.result-menu-item::before{display:grid!important;place-items:center!important;width:20px!important;height:20px!important;border-radius:5px!important;font:900 14px/1 system-ui,sans-serif!important}#searchpage #realSearchResults button.result-menu-open::before{content:"↗"!important;background:#e7f7ee!important;color:#128447!important}#searchpage #realSearchResults button.result-menu-investigate::before{content:"⌕"!important;background:#eceaff!important;color:#5146f6!important}#searchpage #realSearchResults button.result-menu-case::before{content:"⇥"!important;background:#fff2c7!important;color:#785800!important}#searchpage #realSearchResults button.result-menu-info::before{content:"i"!important;background:#f1f3f8!important;color:#45506f!important;font-family:Georgia,serif!important}#searchpage #realSearchResults button.result-menu-ocr::before{content:"↻"!important;background:#fff5d9!important;color:#805e00!important}#searchpage #realSearchResults button.result-menu-delete{margin-top:4px!important;border-top:1px solid #edf0f5!important;border-radius:0 0 7px 7px!important;color:#b32638!important}#searchpage #realSearchResults button.result-menu-delete::before{content:"×"!important;background:#fff0f1!important;color:#c72b3d!important;font-size:16px!important}',
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
  function updateHomeCaseCount(value) {
    const counter = document.getElementById('homeCaseCount');
    if (counter) counter.textContent = Number(value || 0).toLocaleString('es-AR');
  }
  function installHomeCasesCard() {
    const card = document.querySelector('#home .hr-metrics article[data-home-target="search-professional"]');
    if (!card) return window.setTimeout(installHomeCasesCard, 80);
    if (!card.dataset.lexiaCasesHome) {
      card.dataset.lexiaCasesHome = '1';
      card.dataset.homeTarget = 'casespage';
      card.setAttribute('role', 'button');
      card.tabIndex = 0;
      card.replaceChildren(
        el('div', {className: 'hr-mhead'}, el('i', {textContent: '▣'}), el('b', {textContent: 'Casos'})),
        el('strong', {id: 'homeCaseCount', textContent: '—'}),
        el('div', {className: 'hr-line'}, el('span', {textContent: 'Casos activos'}), el('em', {textContent: 'Abrir'})),
        el('div', {className: 'hr-progress'}, el('i', {style: 'width:100%'})),
        el('small', {textContent: 'Espacio de trabajo'}),
        el('p', {textContent: 'Bitácoras y cuestiones'})
      );
    }
    if (!window.__lexiaCasesHomeListener) {
      window.__lexiaCasesHomeListener = true;
      window.addEventListener('click', event => {
        const target = event.target instanceof Element ? event.target : null;
        if (!target || !target.closest('#home .hr-metrics article[data-lexia-cases-home]')) return;
        event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); show();
      }, true);
      window.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const target = event.target instanceof Element ? event.target : null;
        if (!target || !target.closest('#home .hr-metrics article[data-lexia-cases-home]')) return;
        event.preventDefault(); show();
      }, true);
    }
    api('/api/cases').then(data => updateHomeCaseCount((data.cases || []).length)).catch(() => updateHomeCaseCount(0));
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
    if (currentCase && currentCase.case) root.append(identification(currentCase), tree(currentCase));
    else root.append(el('section', {className: 'cases-card cases-empty', textContent: 'Elegí un caso desde el buscador o creá uno nuevo para comenzar.'}));
  }
  function toolbar() {
    const currentId = Number(currentCase?.case?.id || 0), currentName = String(currentCase?.case?.name || 'Elegir un caso');
    const picker = el('details', {className: 'cases-picker'}), summary = el('summary', {textContent: currentName});
    const input = el('input', {type: 'search', placeholder: 'Buscar casos…', autocomplete: 'off'}), list = el('div', {className: 'cases-picker-list'});
    const draw = filter => {
      const term = String(filter || '').trim().toLocaleLowerCase('es');
      list.replaceChildren();
      const visible = caseList.filter(item => !term || String(item.name || '').toLocaleLowerCase('es').includes(term));
      if (!visible.length) list.append(el('p', {className: 'sources-empty', textContent: 'No hay casos que coincidan.'}));
      visible.forEach(item => {
        const selected = Number(item.id) === currentId;
        const option = el('button', {type: 'button', className: 'cases-picker-option' + (selected ? ' is-current' : '')}, el('span', {className: 'cases-picker-check', textContent: selected ? '✓' : ''}), el('span', {textContent: item.name}));
        option.addEventListener('click', () => { picker.open = false; if (!selected) loadCase(item.id); });
        list.append(option);
      });
    };
    draw(''); input.addEventListener('input', () => draw(input.value));
    picker.addEventListener('toggle', () => { if (picker.open) setTimeout(() => input.focus(), 0); else { input.value = ''; draw(''); } });
    picker.append(summary, el('div', {className: 'cases-picker-menu'}, input, list));
    const add = el('button', {type: 'button', className: 'cases-button', textContent: '+ Caso'});
    add.addEventListener('click', openNewCaseDialog);
    return el('header', {className: 'cases-toolbar'}, picker, add);
  }
  function newCaseForm(close) {
    const form = el('form', {className: 'cases-card cases-create'});
    const name = el('input', {placeholder: 'Carátula o nombre del caso', required: 'required'}), authority = el('input', {placeholder: 'Juzgado, tribunal o autoridad'}), fileNumber = el('input', {placeholder: 'Número de expediente'}), description = el('textarea', {placeholder: 'Resumen del caso: hechos, pretensión y estado actual.'});
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Crear caso'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', close);
    form.append(el('div', {className: 'cases-form-grid'}, field('Carátula', name, true), field('Tribunal o autoridad', authority), field('Expediente', fileNumber), field('Resumen del caso', description, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try { const response = await api('/api/cases', {method: 'POST', body: JSON.stringify({name: name.value, authority: authority.value, file_number: fileNumber.value, description: description.value})}); currentCase = response.case; close(); await loadCases(false); }
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
    add.addEventListener('click', () => openBranchDialog(snapshot));
    card.append(el('header', {className: 'case-tree-head'}, el('div', {}, el('h2', {textContent: 'Estructura del caso'}), el('p', {textContent: 'Ramas principales y cuestiones jurídicas. Abrí una cuestión para trabajar sus argumentos y fuentes.'})), add));
    const roots = snapshot.nodes || [];
    if (!roots.length) card.append(el('p', {className: 'cases-empty', textContent: 'Agregá la primera rama principal: por ejemplo, Demanda, Actuación administrativa o Sentencia.'}));
    const list = el('div', {className: 'branch-list'}); roots.forEach(node => list.append(primary(snapshot, node))); card.append(list);
    return card;
  }
  function openCreationDialog(title, buildForm, extraClass) {
    const dialog = el('dialog', {className: 'lexia-evidence-dialog cases-create-dialog' + (extraClass ? ' ' + extraClass : '')});
    const close = () => { if (dialog.open && dialog.close) dialog.close(); dialog.remove(); };
    const closeButton = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cerrar'});
    closeButton.addEventListener('click', close);
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: title}), closeButton), el('div', {className: 'evidence-dialog-body'}, buildForm(close)));
    document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open');
  }
  function openNewCaseDialog() { openCreationDialog('Nuevo caso', close => newCaseForm(close), 'cases-new-case-dialog'); }
  function openBranchDialog(snapshot) { openCreationDialog('Nueva rama principal', close => branchForm(snapshot, close)); }
  function openQuestionDialog(snapshot, parentId) { openCreationDialog('Nueva cuestión jurídica', close => questionForm(snapshot, parentId, close)); }
  function openAiStructureDialog(snapshot, node) {
    if (!node.primary_document_id) return alert('Cargá primero el documento inicial de la rama.');
    const dialog = el('dialog', {className: 'case-ai-dialog'}), body = el('div', {className: 'evidence-dialog-body'});
    const close = () => { if (dialog.open && dialog.close) dialog.close(); dialog.remove(); };
    const closeButton = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cerrar'});
    closeButton.addEventListener('click', close);
    const includeOwn = el('input', {type: 'checkbox'}); includeOwn.checked = false;
    const download = el('button', {type: 'button', className: 'cases-button', textContent: 'Descargar TXT para ChatGPT'});
    const openChatGpt = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Abrir ChatGPT'});
    const responseText = el('textarea', {className: 'case-ai-manual-response', placeholder: 'Después de adjuntar el TXT en ChatGPT, pegá aquí únicamente la respuesta JSON que devuelve.'});
    const review = el('button', {type: 'button', className: 'cases-button', textContent: 'Revisar respuesta de ChatGPT'});
    const analyze = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Analizar con API'}), status = el('p', {className: 'case-ai-status'});
    const setBusy = busy => {
      [download, openChatGpt, responseText, review, analyze, includeOwn].forEach(control => { control.disabled = busy; });
    };
    body.append(
      el('p', {className: 'case-ai-intro', textContent: 'Podés probar el árbol sin API: descargá el TXT, adjuntalo a ChatGPT y pegá aquí su respuesta. LexIA sólo aceptará citas textuales que existan en el documento antes de mostrar el borrador.'}),
      el('label', {className: 'case-ai-option'}, includeOwn, el('span', {}, el('b', {textContent: 'Proponer también nuestra postura'}), document.createTextNode(' · Desactivado por defecto. Sólo podrá usar elementos que surjan del mismo documento.'))),
      el('div', {className: 'case-ai-manual-actions'}, download, openChatGpt),
      responseText,
      el('div', {className: 'case-ai-manual-actions'}, review),
      status,
      el('div', {className: 'case-ai-api-actions'}, el('span', {textContent: 'Cuando tengas una API configurada:'}), analyze)
    );
    download.addEventListener('click', async () => {
      setBusy(true); status.textContent = 'Preparando el TXT con el documento y la consigna…';
      try {
        const result = await api('/api/cases/ai/structure-prompt', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, include_own: includeOwn.checked})});
        if (result.export_path) {
          status.textContent = (result.export_opened ? 'TXT guardado y abierto: ' : 'TXT guardado: ') + result.export_path + '. Adjuntalo a ChatGPT, pedile que responda sólo el JSON y pegá su respuesta aquí.';
        } else {
          downloadTextFile('LexIA_arbol_' + safeDownloadName(result.document_name) + '.txt', result.prompt);
          status.textContent = 'TXT descargado. Adjuntalo a ChatGPT, pedile que responda sólo el JSON y pegá su respuesta aquí.';
        }
      } catch (error) { status.textContent = error.message; }
      finally { setBusy(false); }
    });
    openChatGpt.addEventListener('click', () => window.open('https://chatgpt.com/', '_blank', 'noopener'));
    review.addEventListener('click', async () => {
      if (!responseText.value.trim()) { status.textContent = 'Pegá primero la respuesta JSON de ChatGPT.'; return; }
      setBusy(true); status.textContent = 'Verificando las citas contra el documento…';
      try {
        const result = await api('/api/cases/ai/manual-preview', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, include_own: includeOwn.checked, response_text: responseText.value})});
        renderAiStructurePreview(dialog, body, snapshot, node, result, close);
      } catch (error) { status.textContent = error.message; setBusy(false); }
    });
    analyze.addEventListener('click', async () => {
      setBusy(true); status.textContent = 'Analizando el documento y verificando las citas…';
      try {
        const result = await api('/api/cases/ai/structure-preview', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, include_own: includeOwn.checked})});
        renderAiStructurePreview(dialog, body, snapshot, node, result, close);
      } catch (error) {
        status.textContent = error.message; setBusy(false);
      }
    });
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Armar árbol con IA · ' + node.title}), closeButton), body);
    document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open');
  }
  function renderAiStructurePreview(dialog, body, snapshot, node, result, close) {
    const proposal = result.proposal || {issues: []}, issueViews = [];
    body.replaceChildren(el('p', {className: 'case-ai-preview-meta', textContent: proposal.issues.length + ' cuestión(es) detectada(s) · Modelo ' + result.model + ' · ' + Number(result.usage?.total_tokens || 0).toLocaleString('es-AR') + ' tokens' + (result.document_truncated ? ' · El documento fue recortado por su extensión' : '')}));
    proposal.issues.forEach((issue, issueIndex) => {
      const enabled = el('input', {type: 'checkbox'}); enabled.checked = true;
      const title = el('input', {type: 'text', value: issue.title, 'aria-label': 'Título de la cuestión ' + (issueIndex + 1)}), blockViews = [];
      const article = el('article', {className: 'case-ai-issue'}, el('div', {className: 'case-ai-issue-head'}, enabled, title));
      [['contraparte', 'Planteo de la contraparte'], ['propia', 'Nuestra postura y fundamentos']].forEach(([side, label]) => {
        const values = (issue.blocks && issue.blocks[side]) || [];
        if (!values.length) return;
        const section = el('section', {className: 'case-ai-side'}, el('h4', {textContent: label}));
        values.forEach(block => {
          const keep = el('input', {type: 'checkbox'}); keep.checked = true;
          const content = el('textarea', {value: block.content || ''}), blockBody = el('div', {}, content), reviewViews = [];
          (block.highlights || []).forEach(highlight => blockBody.append(el('blockquote', {className: 'case-ai-quote', textContent: highlight.selected_text})));
          (block.review_quotes || []).forEach((reviewItem, reviewIndex) => {
            const candidate = reviewItem.lexia_candidate || null;
            const choice = el('select', {'aria-label': 'Resolver diferencia de cita ' + (reviewIndex + 1)});
            const lexiaOption = el('option', {value: 'lexia', textContent: candidate ? 'Usar el pasaje que encontró LexIA' : 'LexIA no encontró un pasaje utilizable'});
            lexiaOption.disabled = !candidate;
            choice.append(
              el('option', {value: '', textContent: 'Elegí qué cita conservar…'}),
              lexiaOption,
              el('option', {value: 'ai', textContent: 'Conservar la cita propuesta por la IA'}),
              el('option', {value: 'discard', textContent: 'Descartar este bloque'})
            );
            choice.addEventListener('change', () => { if (choice.value === 'discard') keep.checked = false; });
            const reviewBox = el('div', {className: 'case-ai-review'}, el('strong', {textContent: 'Diferencia para revisar · decisión requerida'}), el('label', {textContent: 'Cita propuesta por la IA'}), el('pre', {textContent: reviewItem.ai_quote || ''}));
            if (candidate) reviewBox.append(el('label', {textContent: 'Pasaje literal localizado por LexIA · similitud ' + Math.round(Number(candidate.similarity || 0) * 100) + '%'}), el('pre', {textContent: candidate.selected_text || ''}));
            else reviewBox.append(el('label', {textContent: 'LexIA'}), el('pre', {textContent: 'No encontró un pasaje cercano en el texto indexado.'}));
            reviewBox.append(choice); blockBody.append(reviewBox);
            reviewViews.push({choice, candidate, aiQuote: String(reviewItem.ai_quote || '')});
          });
          section.append(el('div', {className: 'case-ai-block'}, keep, blockBody));
          blockViews.push({side, keep, content, highlights: block.highlights || [], reviewViews});
        });
        article.append(section);
      });
      issueViews.push({enabled, title, blockViews}); body.append(article);
    });
    const cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'}), apply = el('button', {type: 'button', className: 'cases-button', textContent: 'Crear estructura'}), status = el('p', {className: 'case-ai-status'});
    cancel.addEventListener('click', close);
    apply.addEventListener('click', async () => {
      const issues = issueViews.filter(view => view.enabled.checked).map(view => {
        const blocks = {contraparte: [], propia: []};
        view.blockViews.filter(item => item.keep.checked).forEach(item => {
          const highlights = item.highlights.slice();
          item.reviewViews.forEach(reviewItem => {
            if (reviewItem.choice.value === 'lexia' && reviewItem.candidate) highlights.push(reviewItem.candidate);
            if (reviewItem.choice.value === 'ai') highlights.push({
              selected_text: reviewItem.aiQuote,
              user_approved_ai: true,
              lexia_candidate: reviewItem.candidate || null
            });
          });
          blocks[item.side].push({content: item.content.value, highlights});
        });
        return {title: view.title.value, blocks};
      });
      if (!issues.length) return alert('Seleccioná al menos una cuestión.');
      const unresolved = issueViews.some(view => view.enabled.checked && view.blockViews.some(item => item.keep.checked && item.reviewViews.some(reviewItem => !reviewItem.choice.value)));
      if (unresolved) return alert('En cada diferencia, elegí si conservar el pasaje de LexIA, la cita de la IA o descartar el bloque.');
      if (issues.some(issue => !issue.blocks.contraparte.length)) return alert('Cada cuestión necesita al menos un bloque respaldado del planteo de la contraparte.');
      if ((node.children || []).length && !confirm('Esta rama ya contiene cuestiones. La propuesta se agregará sin reemplazarlas. ¿Continuar?')) return;
      apply.disabled = true; cancel.disabled = true; status.textContent = 'Creando cuestiones, bloques y resaltados…';
      try {
        const response = await api('/api/cases/ai/apply-structure', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, proposal: {issues}, model: result.model, response_id: result.response_id})});
        currentCase = response.case; openPrimaryIds.add(node.id); expandedNodeId = (response.created_node_ids || [])[0] || null; close(); await loadCases(false);
      } catch (error) { status.textContent = error.message; apply.disabled = false; cancel.disabled = false; }
    });
    body.append(status, el('div', {className: 'cases-form-actions'}, cancel, apply));
  }
  function branchForm(snapshot, close) {
    const form = el('form', {className: 'branch-form'}), title = el('input', {placeholder: 'Ej.: Demanda, Actuación administrativa, Sentencia', required: 'required'}), document = docSelect(snapshot.documents || []);
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Agregar rama'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', close);
    form.append(el('div', {className: 'cases-form-grid'}, field('Nombre del hito', title, true), field('Documento que lo origina', document, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { await createNode({case_id: snapshot.case.id, node_kind: 'hito', title: title.value, primary_document_id: document.value ? Number(document.value) : null}); close(); } finally { submit.disabled = false; } });
    return form;
  }
  function primary(snapshot, node) {
    const sourceLabel = node.primary_document_name || ((node.sources || []).length ? ((node.sources || []).length + ' archivo(s) vinculado(s)') : 'Hito sin documento inicial');
    const article = el('article', {className: 'primary-branch'}), title = el('div', {className: 'branch-title'}, el('b', {textContent: node.title}), el('small', {textContent: sourceLabel}));
    const input = el('input', {type: 'file', multiple: 'multiple', accept: '.pdf,.doc,.docx,.odt,.txt,.html,.htm,.rtf,.xls,.ods', hidden: 'hidden'});
    const isOpen = openPrimaryIds.has(node.id);
    const toggle = actionIcon(isOpen ? 'hide' : 'show', isOpen ? 'Ocultar rama' : 'Mostrar rama');
    const upload = actionIcon('files', 'Cargar archivos en esta rama');
    const replace = node.primary_document_id ? actionIcon('replace', 'Reemplazar documento inicial') : null;
    const analyze = node.primary_document_id ? actionIcon('ai', 'Armar árbol con IA') : null;
    const canAddQuestion = !!node.primary_document_id || (node.sources || []).some(source => source.document_id);
    const addQuestion = actionIcon('add', canAddQuestion ? 'Agregar cuestión' : 'Cargá primero un archivo en esta rama'), edit = actionIcon('edit', 'Editar rama'), remove = actionIcon('remove', 'Eliminar rama', 'cases-danger');
    addQuestion.disabled = !canAddQuestion;
    const togglePrimary = () => { if (openPrimaryIds.has(node.id)) { openPrimaryIds.delete(node.id); expandedNodeId = null; } else openPrimaryIds.add(node.id); render({cases: caseList}); };
    toggle.addEventListener('click', togglePrimary);
    upload.addEventListener('click', () => input.click());
    if (replace) replace.addEventListener('click', () => replacePrimaryDocument(snapshot, node));
    if (analyze) analyze.addEventListener('click', () => openAiStructureDialog(snapshot, node));
    input.addEventListener('change', () => { if (input.files?.length) importBranchFiles(snapshot, node, input.files, upload); input.value = ''; });
    addQuestion.addEventListener('click', () => { openPrimaryIds.add(node.id); openQuestionDialog(snapshot, node.id); });
    edit.addEventListener('click', async () => { const titleValue = prompt('Nombre de la rama principal:', node.title); if (titleValue === null) return; try { await updateNode(Object.assign({}, node, {title: titleValue, primary_document_id: node.primary_document_id || null})); } catch (error) { alert(error.message); } });
    remove.addEventListener('click', () => removeNode(node, node.children && node.children.length ? 'También se eliminarán sus cuestiones y vínculos locales.' : ''));
    const head = el('header', {className: 'primary-head'}, el('span', {className: 'branch-mark', textContent: '↳'}), title, el('div', {className: 'branch-actions'}, toggle, upload, replace, analyze, addQuestion, edit, remove));
    enableDoubleClickToggle(head, togglePrimary); article.append(input, head);
    if (!isOpen) return article;
    const questions = el('div', {className: 'branch-questions'}); (node.children || []).forEach((question, index) => questions.append(questionRow(snapshot, question, String(index + 1))));
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
  function questionRow(snapshot, node, numberLabel) {
    const blockCount = ((node.blocks?.contraparte || []).length + (node.blocks?.propia || []).length);
    const active = expandedNodeId === node.id;
    const preview = blockCount ? (blockCount + ' bloque(s) de trabajo') : (node.adversary_text || node.own_position || 'Sin desarrollo todavía'), open = actionIcon(active ? 'hide' : 'show', active ? 'Ocultar cuestión' : 'Mostrar cuestión');
    const toggleQuestion = () => { expandedNodeId = expandedNodeId === node.id ? null : node.id; render({cases: caseList}); if (expandedNodeId) setTimeout(() => { const box = document.querySelector('.question-row-active'); if (box) box.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 0); };
    open.addEventListener('click', toggleQuestion);
    const canAddChild = Object.values(node.blocks || {}).some(blocks => (blocks || []).some(block => (block.highlights || []).length));
    const addChild = actionIcon('add', canAddChild ? 'Agregar subcuestión' : 'Agregá primero un resaltado a esta cuestión');
    addChild.disabled = !canAddChild;
    addChild.addEventListener('click', () => openQuestionDialog(snapshot, node.id));
    const row = el('div', {className: 'question-row' + (active ? ' question-row-active' : '')}, el('div', {className: 'branch-mark question-number', textContent: numberLabel || '1'}), el('div', {style: 'flex:1;min-width:0'}, el('strong', {textContent: node.title}), el('small', {textContent: preview})), open, addChild);
    if (active) {
      const edit = actionIcon('edit', 'Editar nombre de la cuestión'), remove = actionIcon('remove', 'Eliminar cuestión', 'cases-danger');
      edit.addEventListener('click', async () => { const title = prompt('Nombre de la cuestión jurídica:', node.title); if (title === null) return; try { await updateNode(Object.assign({}, node, {title, adversary_text: node.adversary_text || '', own_position: node.own_position || ''})); } catch (error) { alert(error.message); } });
      remove.addEventListener('click', () => removeNode(node, 'Se eliminarán también sus bloques, resaltados y resultado de IA.'));
      row.append(edit, remove);
    }
    enableDoubleClickToggle(row, toggleQuestion);
    const article = el('article', {});
    article.append(row);
    if (active) article.append(workspace(snapshot, node, true));
    const children = el('div', {style: 'margin-left:22px'});
    (node.children || []).forEach((child, index) => children.append(questionRow(snapshot, child, (numberLabel || '1') + '.' + (index + 1))));
    article.append(children);
    return article;
  }
  function questionForm(snapshot, parentId, close) {
    const form = el('form', {className: 'branch-form'}), title = el('input', {placeholder: 'Título de la cuestión', required: 'required'}), adversary = el('textarea', {placeholder: 'Planteo o afirmación de la contraparte.'}), position = el('textarea', {placeholder: 'Nuestra postura inicial.'});
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: 'Agregar cuestión'}), cancel = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'});
    cancel.addEventListener('click', close);
    form.append(el('div', {className: 'cases-form-grid'}, field('Enunciado', title, true), field('Planteo de la contraparte', adversary, true), field('Nuestra postura', position, true)), el('div', {className: 'cases-form-actions'}, cancel, submit));
    form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { await createNode({case_id: snapshot.case.id, node_kind: 'cuestion', parent_id: parentId, title: title.value, adversary_text: adversary.value, own_position: position.value}); close(); } finally { submit.disabled = false; } });
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
  function primaryDocumentIds(nodes, result) {
    const ids = result || new Set();
    (nodes || []).forEach(item => { if (item.primary_document_id) ids.add(Number(item.primary_document_id)); primaryDocumentIds(item.children || [], ids); });
    return ids;
  }
  async function deleteCaseDocument(snapshot, document) {
    if (!confirm('¿Eliminar “' + document.document_name + '” del caso?\n\nSe quitarán también sus resaltados y referencias locales. Si fue cargado en Escritos\\Casos, se eliminará el archivo físico.')) return;
    try {
      const response = await api('/api/cases/document/delete', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, case_document_id: document.id, confirmed: true})});
      currentCase = response.case; await loadCases(false);
      if ((response.pending_cleanup || []).length) alert('El archivo fue quitado del caso, pero su eliminación física quedó pendiente porque LexIA estaba ocupada.');
    } catch (error) { alert(error.message); }
  }
  async function reprocessPdfDocument(document, button) {
    if (!confirm('¿Reprocesar este PDF con OCR?\n\nSe corregirá el texto indexado y luego podrá usarse en búsqueda e IA.')) return;
    button.disabled = true;
    const actions = button.closest('.result-actions,.source-actions');
    let statusLabel = actions && actions.querySelector('[data-lexia-ocr-status]');
    if (!statusLabel && actions) {
      statusLabel = el('span', {'data-lexia-ocr-status': '1', className: 'lexia-ocr-status'});
      actions.append(statusLabel);
    }
    const showStatus = state => {
      const message = String((state || {}).status || 'Procesando OCR…');
      button.title = message;
      if (statusLabel) statusLabel.textContent = message;
    };
    try {
      const started = await api('/api/navigator-operation', {method: 'POST', body: JSON.stringify({operation: 'reprocess_file', path: document.document_path})});
      const jobId = String(started.job_id || '');
      showStatus((started || {}).state);
      const startedAt = Date.now();
      while (Date.now() - startedAt < 20 * 60 * 1000) {
        await new Promise(resolve => setTimeout(resolve, 1200));
        const response = await api('/api/navigator-operation-status?ts=' + Date.now());
        const state = (response || {}).state || {};
        if (jobId && state.job_id && String(state.job_id) !== jobId) continue;
        showStatus(state);
        if (state.phase === 'completed') {
          if (statusLabel) statusLabel.textContent = 'OCR actualizado';
          alert('OCR completado para “' + document.document_name + '”. Ya podés abrir la vista rápida o armar el árbol con IA.');
          return;
        }
        if (state.phase === 'error') throw new Error(state.error || state.status || 'El OCR no se pudo completar.');
      }
      throw new Error('El OCR sigue trabajando. Consultá este archivo nuevamente en unos minutos.');
    } catch (error) { alert('No se pudo iniciar el OCR.\n\n' + error.message); }
    finally {
      button.disabled = false;
      button.title = 'Reprocesar OCR de este PDF';
      if (statusLabel) setTimeout(() => statusLabel.remove(), 5000);
    }
  }
  function replacePrimaryDocument(snapshot, node) {
    const choices = (snapshot.documents || []).filter(document => Number(document.id) !== Number(node.primary_document_id));
    if (!choices.length) return alert('Primero cargá otro archivo en el caso y luego elegilo como reemplazo.');
    const dialog = el('dialog', {className: 'lexia-evidence-dialog'}), select = el('select', {className: 'workspace-enunciado'});
    choices.forEach(document => select.append(el('option', {value: String(document.id), textContent: document.document_name + ' · ' + (document.category || 'Documento')})));
    const close = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cancelar'}), confirmReplace = el('button', {type: 'button', className: 'cases-button', textContent: 'Reemplazar'});
    close.addEventListener('click', () => { dialog.close(); dialog.remove(); });
    confirmReplace.addEventListener('click', async () => {
      confirmReplace.disabled = true;
      try {
        const response = await api('/api/cases/node/replace-primary-document', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: node.id, replacement_document_id: Number(select.value)})});
        currentCase = response.case; dialog.close(); dialog.remove(); await loadCases(false);
        if ((response.pending_cleanup || []).length) alert('El documento inicial fue reemplazado; el archivo anterior quedó pendiente de limpieza porque LexIA estaba ocupada.');
      } catch (error) { alert(error.message); confirmReplace.disabled = false; }
    });
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Reemplazar documento inicial'}), close), el('div', {className: 'evidence-dialog-body'}, el('p', {className: 'source-help', textContent: 'Elegí el archivo que pasará a ser el documento inicial de esta rama. El anterior se conserva sólo si todavía se usa en otra parte del caso.'}), select, el('div', {className: 'evidence-dialog-actions'}, confirmReplace))); document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open');
  }
  function compactSection(label, open, content) {
    const details = el('details', {className: 'argument-section'}); details.open = !!open;
    const summary = el('summary', {textContent: label});
    details.append(summary, el('div', {className: 'argument-section-body'}, content));
    enableDoubleClickToggle(details, () => { details.open = !details.open; });
    return details;
  }
  function workspace(snapshot, node, inline) {
    const box = el('section', {className: 'cases-card case-workspace'}), edit = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Editar'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Eliminar'}), hide = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Ocultar'});
    edit.addEventListener('click', async () => { const title = prompt('Nombre de la cuestión jurídica:', node.title); if (title === null) return; try { await updateNode(Object.assign({}, node, {title, adversary_text: node.adversary_text || '', own_position: node.own_position || ''})); } catch (error) { alert(error.message); } });
    remove.addEventListener('click', () => removeNode(node, 'Se eliminarán también sus bloques, resaltados y resultado de IA.')); hide.addEventListener('click', () => { expandedNodeId = null; render({cases: caseList}); });
    if (inline) box.classList.add('case-workspace-inline');
    else box.append(el('header', {className: 'workspace-head'}, el('div', {}, el('small', {textContent: 'Cuestión jurídica'}), el('h2', {textContent: node.title})), el('div', {className: 'case-actions'}, edit, remove, hide)));
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
    // Estos dos sectores representan posiciones contradictorias: pueden
    // compararse en paralelo y no funcionan como un acordeón exclusivo.
    const details = compactSection(label + ' · ' + blocks.length + ' bloque(s)', true, body);
    details.addEventListener('toggle', () => { if (details.open) activeWorkspaceSide = side; }); return details;
  }
  function argumentBlock(snapshot, node, side, block, number) {
    const text = el('textarea', {value: block.content || '', placeholder: side === 'contraparte' ? 'Desarrollá este planteo de la contraparte.' : 'Desarrollá este fundamento propio.'});
    const resizeText = () => {
      text.style.height = '27px';
      text.style.height = Math.max(27, text.scrollHeight) + 'px';
    };
    const selectBlock = () => { activeEvidenceBlockId = block.id; activeWorkspaceSide = side; };
    text.addEventListener('focus', selectBlock); text.addEventListener('pointerdown', selectBlock);
    text.addEventListener('input', () => {
      resizeText();
      scheduleAutosave('block:' + block.id, async () => {
        const response = await api('/api/cases/block/update', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, block_id: block.id, content: text.value, title: block.title || ''})}); currentCase = response.case;
      });
    });
    const evidence = actionIcon('add', 'Agregar fuente al párrafo'), remove = actionIcon('remove', 'Eliminar párrafo', 'cases-danger');
    evidence.addEventListener('click', () => { selectBlock(); openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node)); });
    remove.addEventListener('click', async () => { if (!confirm('¿Eliminar este bloque y sus resaltados?\n\nLos archivos importados que no se usen en ninguna otra parte del caso también se eliminarán.')) return; try { const response = await api('/api/cases/block/delete', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, block_id: block.id, confirmed: true})}); currentCase = response.case; await loadCases(false); if ((response.pending_cleanup || []).length) alert('El bloque fue eliminado, pero uno o más archivos quedaron pendientes de limpieza porque LexIA estaba ocupada. Podés reintentar cuando AutoSync finalice.'); } catch (error) { alert(error.message); } });
    const body = el('div', {className: 'argument-block-body'}, text);
    (block.highlights || []).forEach(highlight => {
      const excerpt = el('blockquote', {
        className: 'argument-evidence',
        textContent: highlight.selected_text,
        title: 'Abrir y revisar este resaltado · ' + highlight.document_name + (highlight.page_start ? ' · pág. ' + highlight.page_start : ''),
        tabindex: '0',
        role: 'button',
        'aria-label': 'Abrir el resaltado en Seleccionar evidencia para el bloque',
      });
      // El texto insertado en el párrafo representa un resaltado guardado: el
      // clic principal debe abrir su editor, no el visor de sólo lectura.
      excerpt.addEventListener('click', () => openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node), highlight));
      excerpt.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openEvidenceDialog(snapshot, node, block, availableDocuments(snapshot, node), highlight);
        }
      });
      body.append(excerpt);
    });
    const article = el('article', {className: 'argument-block'}); article.addEventListener('pointerdown', selectBlock); article.append(el('span', {className: 'argument-paragraph-number', textContent: String(number)}), body, el('div', {className: 'argument-block-actions'}, evidence, remove)); requestAnimationFrame(resizeText); return article;
  }
  function sources(snapshot, node, side) {
    const panel = el('aside', {className: 'workspace-sources'}, el('h3', {className: 'source-title', textContent: 'Archivos del caso'}), el('p', {className: 'source-help', textContent: 'Elegí un archivo para seleccionar el pasaje que querés incorporar al párrafo activo. Los resaltados ya incorporados se editan directamente desde el párrafo.'}));
    const blocks = Object.values(node.blocks || {}).flat(), candidates = availableDocuments(snapshot, node);
    const protectedDocuments = primaryDocumentIds(snapshot.nodes || []);
    if (!candidates.length) panel.append(el('p', {className: 'sources-empty', textContent: 'Cargá un archivo en la rama para poder crear una cuestión respaldada.'}));
    candidates.forEach(doc => {
      const choose = actionIcon('add', 'Seleccionar un pasaje de este archivo');
      choose.addEventListener('click', () => {
        const block = blocks.find(item => item.id === activeEvidenceBlockId);
        if (!block) return alert('Primero hacé clic dentro del párrafo al que querés vincular este pasaje.');
        openEvidenceDialog(snapshot, node, block, [doc]);
      });
      const actions = [choose];
      if (!protectedDocuments.has(Number(doc.id))) {
        const remove = actionIcon('remove', 'Eliminar archivo del caso', 'cases-danger');
        remove.addEventListener('click', () => deleteCaseDocument(snapshot, doc)); actions.push(remove);
      }
      panel.append(el('div', {className: 'evidence-candidate'}, el('b', {textContent: doc.document_name, title: protectedDocuments.has(Number(doc.id)) ? 'Documento inicial de una rama: se reemplaza desde su cabecera.' : ''}), ...actions));
    });
    panel.append(el('p', {className: 'sources-drop-help', textContent: 'Para incorporar un archivo nuevo, seleccioná primero el bloque y arrastrá aquí el archivo.'}));
    panel.addEventListener('dragover', event => { event.preventDefault(); panel.classList.add('drop-target'); });
    panel.addEventListener('dragleave', event => { if (!panel.contains(event.relatedTarget)) panel.classList.remove('drop-target'); });
    panel.addEventListener('drop', event => {
      event.preventDefault(); panel.classList.remove('drop-target');
      const block = blocks.find(item => item.id === activeEvidenceBlockId);
      if (!block) return alert('Primero hacé clic dentro del bloque al que querés vincular el archivo.');
      if (event.dataTransfer?.files?.length) importBlockFiles(snapshot, node, block, event.dataTransfer.files, panel);
    });
    return panel;
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
    const raw = selection.toString(), leading = raw.length - raw.trimStart().length;
    const text = raw.trim(); if (!text) return null;
    const start = prefix.toString().length + leading;
    return {text, start, end: start + text.length};
  }
  function evidenceDomRange(reader, start, end) {
    const range = document.createRange(), walker = document.createTreeWalker(reader, NodeFilter.SHOW_TEXT);
    let node, offset = 0, startNode = null, endNode = null, startOffset = 0, endOffset = 0;
    while ((node = walker.nextNode())) {
      const next = offset + node.data.length;
      if (!startNode && start >= offset && start <= next) { startNode = node; startOffset = Math.min(node.data.length, start - offset); }
      if (end >= offset && end <= next) { endNode = node; endOffset = Math.min(node.data.length, end - offset); break; }
      offset = next;
    }
    if (!startNode || !endNode) return null;
    range.setStart(startNode, startOffset); range.setEnd(endNode, endOffset); return range;
  }
  function clearEvidenceHighlights() {
    if (window.CSS?.highlights) {
      CSS.highlights.delete('lexia-evidence-current');
      CSS.highlights.delete('lexia-evidence-new');
    }
  }
  function paintEvidenceHighlights(reader, currentRanges, newRanges) {
    clearEvidenceHighlights();
    const source = String(reader.textContent || ''), tagged = [], scrollTop = reader.scrollTop;
    currentRanges.forEach(item => tagged.push(Object.assign({kind: 'current'}, item)));
    newRanges.forEach(item => tagged.push(Object.assign({kind: 'new'}, item)));
    const boundaries = [...new Set([0, source.length, ...tagged.flatMap(item => [item.start, item.end])])].filter(value => value >= 0 && value <= source.length).sort((a, b) => a - b);
    const nodes = [];
    for (let index = 0; index < boundaries.length - 1; index += 1) {
      const start = boundaries[index], end = boundaries[index + 1], active = tagged.filter(item => item.start < end && item.end > start);
      const text = source.slice(start, end); if (!text) continue;
      if (!active.length) nodes.push(document.createTextNode(text));
      else nodes.push(el('mark', {className: active.some(item => item.kind === 'new') ? 'evidence-new-mark' : 'evidence-existing-mark', textContent: text}));
    }
    reader.replaceChildren(...nodes);
    reader.scrollTop = scrollTop;
  }
  function revealExistingHighlight(reader, savedText) {
    const source = String(reader.textContent || ''), exact = String(savedText || '').trim();
    if (!exact) return false;
    let start = source.indexOf(exact), length = exact.length;
    if (start < 0) {
      const words = exact.split(/\s+/).filter(Boolean).map(word => word.replace(/[|\\{}()[\]^$+*?.-]/g, '\\$&'));
      if (words.length) {
        const match = source.match(new RegExp(words.join('\\s+')));
        if (match && Number.isInteger(match.index)) { start = match.index; length = match[0].length; }
      }
    }
    if (start < 0) {
      const keyWithPositions = value => {
        const chars = [], positions = [];
        Array.from(String(value || '')).forEach((char, index) => {
          char.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().split('').forEach(normalized => {
            if (/[a-z0-9]/i.test(normalized)) { chars.push(normalized); positions.push(index); }
          });
        });
        return {key: chars.join(''), positions};
      };
      const sourceKey = keyWithPositions(source), exactKey = keyWithPositions(exact).key;
      const keyStart = exactKey ? sourceKey.key.indexOf(exactKey) : -1;
      if (keyStart >= 0) {
        start = sourceKey.positions[keyStart];
        const last = sourceKey.positions[keyStart + exactKey.length - 1];
        length = last - start + 1;
      }
    }
    if (start < 0) return false;
    const located = {text: source.slice(start, start + length), start, end: start + length};
    paintEvidenceHighlights(reader, [located], []);
    requestAnimationFrame(() => {
      const range = evidenceDomRange(reader, located.start, located.end); if (!range) return;
      const readerBox = reader.getBoundingClientRect(), rangeBox = range.getBoundingClientRect();
      reader.scrollTop += rangeBox.top - readerBox.top - Math.max(0, (reader.clientHeight - rangeBox.height) / 2);
    });
    return located;
  }
  function formatEvidenceText(rawText, path) {
    const raw = String(rawText || '').replace(/\r\n?/g, '\n');
    if (!/\.(doc|docx|rtf)$/i.test(String(path || ''))) return {text: raw, reformatted: false};
    const existingLines = (raw.match(/\n/g) || []).length;
    if (existingLines >= 3) return {text: raw, reformatted: false};
    // Algunos extractores de Word devuelven todos los párrafos como una sola
    // línea. Sólo para leer y elegir el pasaje, se recompone una presentación
    // con cortes semánticos; el archivo y su texto de catálogo no se modifican.
    const text = raw.replace(/[ \t]+/g, ' ')
      .replace(/\s+(?=(?:Expediente|Fecha|Usuario|Código|Descripcion|Descripción|Email|Teléfono|Telefono|Referencia|Carátula|Caratula|CUIT|Domicilio)\s*:)/gi, '\n')
      .replace(/([.;!?])\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])/g, '$1\n\n')
      .trim();
    return {text, reformatted: text !== raw};
  }
  function openEvidenceDialog(snapshot, node, block, documents, existing) {
    if (!documents.length) return alert('Primero cargá o vinculá un archivo a la rama del caso.');
    const dialog = el('dialog', {className: 'lexia-evidence-dialog evidence-selection-dialog'}), select = el('select', {className: 'workspace-enunciado'}), reader = el('div', {className: 'evidence-reader', tabindex: '0', contenteditable: 'true', role: 'textbox', 'aria-multiline': 'true', spellcheck: 'false', textContent: 'Elegí un documento para cargar su texto indexado.'}), status = el('p', {className: 'evidence-selection-status', textContent: 'Seleccioná con el mouse el pasaje exacto que querés conservar. Mantené Shift para sumar otro pasaje separado.'}), selectionList = el('div', {className: 'evidence-selection-list', 'aria-label': 'Pasajes seleccionados', hidden: 'hidden'});
    reader.style.cssText = 'box-sizing:border-box;display:block;width:100%;max-width:100%;min-width:0;white-space:pre-wrap;overflow-x:hidden;overflow-y:auto;overflow-wrap:anywhere;word-break:break-word;';
    documents.forEach(doc => select.append(el('option', {value: String(doc.id), textContent: doc.document_name})));
    if (existing) select.value = String(existing.case_document_id);
    const close = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cerrar'}), changeSelection = existing ? el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cambiar selección'}) : null, save = el('button', {type: 'button', className: 'cases-button', textContent: existing ? 'Reemplazar resaltado' : 'Incorporar resaltado'});
    let selectedRanges = [], existingRange = null, preview = null, displayWasReformatted = false, changingSelection = !existing, selectionStartedWithShift = false;
    const selectedDocument = () => documents.find(item => String(item.id) === select.value);
    const enableNewSelection = () => {
      changingSelection = true; selectedRanges = [];
      paintEvidenceHighlights(reader, existingRange ? [existingRange] : [], selectedRanges);
      selectionList.replaceChildren(); selectionList.hidden = true;
      const selection = window.getSelection(); if (selection) selection.removeAllRanges();
      reader.classList.add('evidence-reader-editing');
      status.textContent = 'El resaltado anterior se conserva como referencia. Marcá el nuevo pasaje; mantené Shift para sumar otros separados.';
      reader.focus({preventScroll: true});
    };
    const load = async () => {
      selectedRanges = []; existingRange = null; changingSelection = !existing; clearEvidenceHighlights(); selectionList.replaceChildren(); selectionList.hidden = true; reader.classList.toggle('evidence-reader-editing', !existing); status.textContent = 'Cargando el texto indexado de LexIA…'; reader.textContent = '';
      try {
        const doc = selectedDocument(), data = await api('/api/catalog-text-preview?path=' + encodeURIComponent(doc.document_path));
        preview = data;
        const formatted = formatEvidenceText(data.text || '', doc.document_path);
        displayWasReformatted = formatted.reformatted; reader.textContent = formatted.text;
        status.textContent = displayWasReformatted
          ? 'La vista de Word fue separada en párrafos para facilitar la selección. Seleccioná el pasaje exacto que querés conservar.'
          : 'Seleccioná con el mouse el pasaje exacto que querés conservar.';
        if (existing) requestAnimationFrame(() => {
          let anchor = {};
          try { anchor = JSON.parse(existing.anchor_data || '{}') || {}; } catch (_) { anchor = {}; }
          const viewerText = String(anchor.viewer_text || existing.selected_text || '').trim();
          existingRange = revealExistingHighlight(reader, viewerText) || null;
          if (existingRange) {
            status.textContent = anchor.user_approved_ai && anchor.viewer_text
              ? 'LexIA resaltó el pasaje OCR más cercano para compararlo con la cita elegida de la IA. Podés seleccionar otro texto y reemplazarlo.'
              : 'Este es el pasaje actualmente incorporado. Podés seleccionar otro texto y reemplazarlo.';
          } else {
            status.textContent = 'No se pudo ubicar automáticamente el pasaje anterior. Seleccioná el texto que querés conservar.';
          }
        });
      } catch (error) { preview = null; reader.textContent = ''; status.textContent = 'No se pudo cargar texto seleccionable: ' + error.message; }
    };
    const mergeSelectedRanges = values => {
      const source = String(reader.textContent || ''), sorted = values.slice().sort((a, b) => a.start - b.start), merged = [];
      sorted.forEach(item => {
        const previous = merged[merged.length - 1];
        if (previous && item.start <= previous.end) previous.end = Math.max(previous.end, item.end);
        else merged.push({start: item.start, end: item.end});
      });
      return merged.map(item => ({start: item.start, end: item.end, text: source.slice(item.start, item.end).trim()})).filter(item => item.text);
    };
    const refreshSelectedRanges = () => {
      paintEvidenceHighlights(reader, existingRange ? [existingRange] : [], selectedRanges);
      selectionList.replaceChildren(); selectionList.hidden = !selectedRanges.length;
      selectedRanges.forEach((item, index) => {
        const excerpt = item.text.replace(/\s+/g, ' ').trim();
        const remove = el('button', {type: 'button', className: 'evidence-selection-chip', textContent: 'Pasaje ' + (index + 1) + ' ×', title: 'Quitar esta selección: ' + excerpt.slice(0, 140), 'aria-label': 'Quitar pasaje seleccionado ' + (index + 1)});
        remove.addEventListener('click', event => {
          event.preventDefault(); event.stopPropagation(); selectedRanges.splice(index, 1); refreshSelectedRanges(); reader.focus({preventScroll: true});
        });
        selectionList.append(remove);
      });
      const total = selectedRanges.reduce((sum, item) => sum + item.text.length, 0);
      status.textContent = selectedRanges.length
        ? selectedRanges.length + ' pasaje(s) seleccionado(s), ' + total + ' caracteres. Usá la × para quitar uno o mantené Shift para sumar otro.'
        : existingRange
          ? 'El resaltado anterior se conserva como referencia. Marcá uno o más pasajes nuevos.'
          : 'No hay pasajes seleccionados. Marcá uno con el mouse; mantené Shift para sumar otros separados.';
    };
    const capture = append => {
      const range = selectionOffsets(reader); if (!range) return false;
      changingSelection = true;
      reader.classList.add('evidence-reader-editing');
      selectedRanges = mergeSelectedRanges(append ? selectedRanges.concat(range) : [range]);
      refreshSelectedRanges();
      const selection = window.getSelection(); if (selection) selection.removeAllRanges();
      return true;
    };
    const stopSelectionTracking = clearEvidenceHighlights;
    reader.addEventListener('beforeinput', event => event.preventDefault());
    reader.addEventListener('paste', event => event.preventDefault());
    reader.addEventListener('drop', event => event.preventDefault());
    reader.addEventListener('selectstart', event => event.stopPropagation());
    reader.addEventListener('mousedown', event => { selectionStartedWithShift = event.shiftKey; });
    reader.addEventListener('mouseup', event => capture(event.shiftKey || selectionStartedWithShift));
    reader.addEventListener('keyup', event => { if (event.shiftKey) capture(true); });
    select.addEventListener('change', load);
    if (changeSelection) changeSelection.addEventListener('click', enableNewSelection);
    save.addEventListener('pointerdown', () => capture(false)); save.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') capture(false); });
    close.addEventListener('click', () => { stopSelectionTracking(); dialog.close(); dialog.remove(); });
    dialog.addEventListener('close', stopSelectionTracking, {once: true});
    save.addEventListener('click', async () => {
      const live = selectionOffsets(reader); if (live) capture(false);
      if (!selectedRanges.length) return alert('Seleccioná uno o más pasajes del documento antes de incorporarlos.');
      const doc = selectedDocument();
      const payloadFor = selected => {
        const overlaps = displayWasReformatted ? [] : (preview?.segments || []).filter(item => selected.start < Number(item.end_char || 0) && selected.end > Number(item.start_char || 0));
        return {case_id: snapshot.case.id, selected_text: selected.text, page_start: overlaps[0]?.page_start || null, page_end: overlaps[overlaps.length - 1]?.page_end || overlaps[0]?.page_start || null, anchor_data: JSON.stringify({start_char: selected.start, end_char: selected.end, display_reformatted: displayWasReformatted, multi_selection: selectedRanges.length > 1})};
      };
      save.disabled = true;
      try {
        let response;
        for (let index = 0; index < selectedRanges.length; index += 1) {
          const payload = payloadFor(selectedRanges[index]);
          response = existing && index === 0
            ? await api('/api/cases/block/highlight/update', {method: 'POST', body: JSON.stringify(Object.assign(payload, {highlight_id: existing.id}))})
            : await api('/api/cases/block/highlight', {method: 'POST', body: JSON.stringify(Object.assign(payload, {block_id: block.id, case_document_id: doc.id}))});
        }
        stopSelectionTracking(); currentCase = response.case; dialog.close(); dialog.remove(); await loadCases(false);
      } catch (error) { alert(error.message); } finally { save.disabled = false; }
    });
    const actions = el('div', {className: 'evidence-dialog-actions'});
    if (changeSelection) actions.append(changeSelection);
    actions.append(save);
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Seleccionar evidencia para el bloque'}), close), el('div', {className: 'evidence-dialog-body'}, field('Documento del caso', select), reader, status, selectionList, actions));
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
    return 'LEXIA — CONTESTACIÓN DEFINITIVA DE LA RAMA\n\nTAREA\nRedactá una única contestación definitiva de nuestra parte para la rama indicada. Integrá todas las cuestiones seleccionadas en un escrito coherente: exponé sintéticamente cada planteo de la contraparte, contestalo con nuestra postura y desarrollá exclusivamente los fundamentos y evidencias incorporados en LexIA. No entregues un análisis preliminar, un esquema ni recomendaciones: devolvé el texto final de la contestación.\n\nREGLAS ESTRICTAS\n1. No uses conocimiento externo ni inventes hechos, normas, antecedentes o citas.\n2. No omitas cuestiones seleccionadas ni mezcles fundamentos pertenecientes a cuestiones diferentes.\n3. Diferenciá con claridad lo afirmado por la contraparte de nuestra respuesta.\n4. Conservá literalmente las citas documentales cuando las utilices.\n5. Si un fundamento necesario no surge del material, indicá: “No surge de las fuentes aportadas”.\n6. Usá títulos con “# ”, subtítulos con “## ” y párrafos completos, para que LexIA pueda convertir la respuesta a Word.\n7. Devolvé solamente la contestación definitiva, sin explicar el procedimiento seguido.\n\nRAMA PRINCIPAL\n' + root.title + '\n\n' + questions.map((question, index) => '=== CUESTIÓN ' + (index + 1) + ' ===\n' + questionAiMaterial(question)).join('\n\n');
  }
  function branchAiSection(snapshot, root) {
    const questions = descendantQuestions(root), selected = branchSelection(root, questions), output = root.ai_output;
    const details = el('details', {className: 'branch-ai'}); details.open = !!output;
    enableDoubleClickToggle(details, () => { details.open = !details.open; });
    const body = el('div', {}), options = el('div', {className: 'branch-ai-options'});
    questions.forEach(question => {
      const check = el('input', {type: 'checkbox'}); check.checked = selected.has(question.id);
      check.addEventListener('change', () => { if (check.checked) selected.add(question.id); else selected.delete(question.id); });
      options.append(el('label', {className: 'branch-ai-option', title: question.title}, check, el('span', {textContent: question.title})));
    });
    if (questions.length) body.append(options);
    else body.append(el('p', {className: 'sources-empty', textContent: 'Agregá al menos una cuestión antes de preparar una consulta.'}));
    let outputId = output ? output.id : null;
    const text = el('textarea', {value: output ? output.content : '', placeholder: 'Pegá aquí la contestación definitiva generada por la IA. LexIA la conservará en esta rama y podrá exportarla a Word.'});
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
    const prepare = el('button', {type: 'button', className: 'cases-button', textContent: 'Preparar contestación para IA'}), exportDocx = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Exportar contestación a Word'}), exportStatus = el('span', {className: 'case-ai-status'});
    prepare.addEventListener('click', () => {
      const chosen = questions.filter(question => selected.has(question.id));
      if (!chosen.length) return alert('Seleccioná al menos una cuestión.');
      const unsupported = chosen.some(question => ((question.blocks && question.blocks.contraparte) || []).some(block => !(block.highlights || []).length));
      if (unsupported) return alert('Cada bloque del planteo de la contraparte debe contener al menos un pasaje resaltado antes de consultar a la IA.');
      showAiPackage(buildBranchAiPackage(root, chosen));
    });
    exportDocx.addEventListener('click', async () => {
      if (!text.value.trim()) return alert('Pegá primero la contestación definitiva generada por la IA.');
      clearTimeout(autosaveTimers.get('branch-ai:' + root.id)); autosaveTimers.delete('branch-ai:' + root.id);
      exportDocx.disabled = true; exportStatus.textContent = 'Generando Word…';
      try {
        const result = await api('/api/cases/node/ai-output/export', {method: 'POST', body: JSON.stringify({case_id: snapshot.case.id, node_id: root.id, title: 'Contestación · ' + root.title, content: text.value})});
        currentCase = result.case; outputId = findNode(result.case.nodes || [], root.id)?.ai_output?.id || outputId;
        exportStatus.textContent = 'Word creado en ' + result.export_path;
      } catch (error) { exportStatus.textContent = error.message; }
      finally { exportDocx.disabled = false; }
    });
    body.append(el('div', {className: 'argument-block-actions'}, prepare, exportDocx), exportStatus, text);
    details.append(el('summary', {textContent: output ? 'Contestación definitiva con IA · borrador guardado' : 'Contestación definitiva con IA'}), body);
    return details;
  }
  function showAiPackage(packageText) {
    const dialog = el('dialog', {className: 'lexia-evidence-dialog'}), area = el('textarea', {className: 'evidence-reader', value: packageText}); area.style.height = '52vh';
    const close = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Cerrar'}), copy = el('button', {type: 'button', className: 'cases-button', textContent: 'Copiar'});
    close.addEventListener('click', () => { dialog.close(); dialog.remove(); }); copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(packageText); copy.textContent = 'Copiado'; } catch (_) { area.select(); document.execCommand('copy'); copy.textContent = 'Copiado'; } });
    dialog.append(el('header', {className: 'evidence-dialog-head'}, el('b', {textContent: 'Paquete para generar la contestación definitiva'}), close), el('div', {className: 'evidence-dialog-body'}, area, el('div', {className: 'evidence-dialog-actions'}, copy))); document.body.append(dialog); if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', 'open');
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
    try { const response = await api('/api/cases'); caseList = response.cases || []; updateHomeCaseCount(caseList.length); if (refresh && currentCase && currentCase.case) { const selected = caseList.find(item => item.id === currentCase.case.id); if (selected) return loadCase(selected.id, response); currentCase = null; expandedNodeId = null; } render(response); } catch (error) { page().querySelector('.cases-main').textContent = 'No se pudieron cargar los casos: ' + error.message; }
  }
  async function loadCase(caseId, alreadyLoaded) {
    try { const response = await api('/api/cases/' + caseId); currentCase = response.case; expandedNodeId = null; editingCase = false; render(alreadyLoaded || await api('/api/cases')); } catch (error) { alert(error.message); }
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
  let activeResultActionMenu = null;
  function closeResultActionMenu() {
    if (!activeResultActionMenu) return;
    activeResultActionMenu.popover.hidden = true;
    activeResultActionMenu.toggle.setAttribute('aria-expanded', 'false');
    activeResultActionMenu = null;
  }
  function resultMenuAction(button) {
    if (button.matches('.search-open-file,.open-source-real')) return {kind: 'open', label: 'Abrir archivo', order: 10};
    if (button.matches('.search-investigate-file')) return {kind: 'investigate', label: 'Investigar', order: 20};
    if (button.matches('[data-lexia-case-link]')) return {kind: 'case', label: 'Agregar al caso', order: 30};
    if (button.matches('.search-file-info')) return {kind: 'info', label: 'Ver detalles', order: 40};
    if (button.matches('[data-lexia-ocr-reprocess]')) return {kind: 'ocr', label: 'Reprocesar OCR', order: 50};
    if (button.matches('.search-delete-file')) return {kind: 'delete', label: 'Eliminar', order: 90};
    return {kind: 'info', label: button.getAttribute('aria-label') || button.textContent.trim() || 'Acción', order: 70};
  }
  function placeResultActionMenu(toggle, popover) {
    popover.hidden = false;
    popover.style.visibility = 'hidden';
    const anchor = toggle.getBoundingClientRect();
    const width = popover.offsetWidth || 220;
    const height = popover.offsetHeight || 220;
    const left = Math.max(8, Math.min(window.innerWidth - width - 8, anchor.right - width));
    const below = anchor.bottom + 6;
    const top = below + height <= window.innerHeight - 8 ? below : Math.max(8, anchor.top - height - 6);
    popover.style.left = left + 'px';
    popover.style.top = top + 'px';
    popover.style.visibility = 'visible';
  }
  function installResultActionMenu(card, actions) {
    if (!card.matches('.result-card') || !card.closest('#realSearchResults')) return;
    let menu = actions.querySelector(':scope > .result-action-menu');
    let toggle = menu?.querySelector(':scope > .result-menu-toggle');
    let popover = menu?.querySelector(':scope > .result-menu-popover');
    if (!menu) {
      menu = el('div', {className: 'result-action-menu'});
      toggle = el('button', {type: 'button', className: 'result-menu-toggle', textContent: '⋯', title: 'Acciones del archivo', 'aria-label': 'Acciones del archivo', 'aria-expanded': 'false'});
      popover = el('div', {className: 'result-menu-popover', role: 'menu'});
      popover.hidden = true;
      toggle.addEventListener('click', event => {
        event.preventDefault(); event.stopPropagation();
        const wasOpen = activeResultActionMenu?.menu === menu;
        closeResultActionMenu();
        if (wasOpen) return;
        activeResultActionMenu = {menu, toggle, popover};
        toggle.setAttribute('aria-expanded', 'true');
        placeResultActionMenu(toggle, popover);
      });
      popover.addEventListener('click', event => {
        if (event.target.closest('button.result-menu-item')) setTimeout(closeResultActionMenu, 0);
      });
      menu.append(toggle, popover);
      actions.prepend(menu);
    }
    const buttons = Array.from(actions.children).filter(node => node.tagName === 'BUTTON');
    buttons.map(button => ({button, action: resultMenuAction(button)})).sort((a, b) => a.action.order - b.action.order).forEach(({button, action}) => {
      button.classList.add('result-menu-item', 'result-menu-' + action.kind);
      button.textContent = action.label;
      button.setAttribute('aria-label', action.label);
      button.setAttribute('role', 'menuitem');
      popover.append(button);
    });
    Array.from(popover.querySelectorAll(':scope > button.result-menu-item'))
      .sort((a, b) => resultMenuAction(a).order - resultMenuAction(b).order)
      .forEach(button => popover.append(button));
  }
  function installDocumentActions(root) {
    const cards = [];
    if (root?.nodeType === 1 && root.matches('.result-card,.source-item')) cards.push(root);
    if (root?.querySelectorAll) cards.push(...root.querySelectorAll('.result-card,.source-item'));
    cards.forEach(card => {
      const actions = card.querySelector('.result-actions,.source-actions');
      if (!actions) return;
      if (!actions.querySelector('[data-lexia-case-link]')) {
        const button = el('button', {type: 'button', 'data-lexia-case-link': '1', className: 'lexia-case-link', textContent: 'Al caso', title: 'Vincular esta fuente y su extracto a un caso'});
        button.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); addCardToCase(card, button); });
        actions.append(button);
      }
      if (!actions.querySelector('[data-lexia-ocr-reprocess]')) {
        const ocr = el('button', {type: 'button', 'data-lexia-ocr-reprocess': '1', className: 'lexia-ocr-reprocess', textContent: 'OCR', title: 'Reprocesar OCR de este PDF'});
        ocr.addEventListener('click', async event => {
          event.preventDefault(); event.stopPropagation();
          try {
            const document = await cardDocument(card);
            if (!/\.pdf$/i.test(String(document.name || document.path || ''))) return alert('El reproceso OCR sólo está disponible para archivos PDF.');
            await reprocessPdfDocument({document_name: document.name, document_path: document.path}, ocr);
          } catch (error) { alert('No se pudo preparar el OCR.\n\n' + error.message); }
        });
        actions.append(ocr);
      }
      const help = [
        ['.search-open-file', 'Abrir archivo'],
        ['.search-investigate-file', 'Cargar contenido en Investigación'],
        ['.search-file-info', 'Ver detalles del archivo'],
        ['.search-delete-file', 'Eliminar archivo'],
        ['[data-lexia-case-link]', 'Agregar al caso'],
        ['[data-lexia-ocr-reprocess]', 'Reprocesar OCR del PDF'],
      ];
      help.forEach(([selector, label]) => actions.querySelectorAll(selector).forEach(button => {
        button.dataset.lexiaTooltip = label;
        button.setAttribute('aria-label', label);
        button.removeAttribute('title');
      }));
      installResultActionMenu(card, actions);
    });
  }
  function installQuickActionTooltips() {
    let tip = null, shownFor = null, timer = null;
    const selector = '#searchpage .result-actions .search-open-file,#searchpage .result-actions .search-investigate-file,#searchpage .result-actions .search-file-info,#searchpage .result-actions .search-delete-file,#searchpage .result-actions [data-lexia-case-link],#searchpage .result-actions [data-lexia-ocr-reprocess]';
    const hide = () => {
      if (timer) { clearTimeout(timer); timer = null; }
      if (tip) tip.classList.remove('is-visible');
      shownFor = null;
    };
    const place = target => {
      if (!tip || !target) return;
      const box = target.getBoundingClientRect();
      tip.style.left = Math.max(6, Math.min(window.innerWidth - tip.offsetWidth - 6, box.left + box.width / 2 - tip.offsetWidth / 2)) + 'px';
      tip.style.top = Math.max(6, box.top - tip.offsetHeight - 6) + 'px';
    };
    document.addEventListener('pointerover', event => {
      const target = event.target.closest?.(selector);
      if (!target || target.classList.contains('result-menu-item') || target === shownFor || target.disabled) return;
      hide(); shownFor = target;
      timer = setTimeout(() => {
        if (shownFor !== target) return;
        const label = target.dataset.lexiaTooltip || target.getAttribute('aria-label');
        if (!label) return;
        if (!tip) { tip = el('div', {className: 'lexia-action-tooltip', role: 'tooltip'}); document.body.append(tip); }
        tip.textContent = label; tip.classList.add('is-visible'); place(target);
      }, 120);
    });
    document.addEventListener('pointerout', event => {
      const target = event.target.closest?.(selector);
      if (target && (!event.relatedTarget || !target.contains(event.relatedTarget))) hide();
    });
  }
  function initialize() {
    style(); createPage(); navigation(); navigationExit(); installHomeCasesCard();
    installQuickActionTooltips();
    installDocumentActions(document);
    document.addEventListener('click', event => {
      if (activeResultActionMenu && !activeResultActionMenu.menu.contains(event.target)) closeResultActionMenu();
    });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeResultActionMenu(); });
    window.addEventListener('resize', closeResultActionMenu);
    document.addEventListener('scroll', closeResultActionMenu, true);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === 1) installDocumentActions(node);
    }))).observe(document.body, {childList: true, subtree: true});
    if ((location.hash || '').slice(1) === PAGE_ID) show();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true}); else initialize();
})();
