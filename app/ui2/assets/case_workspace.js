/* LexIA Casos 2.0 — estructura procesal local, sin llamadas a IA. */
(function () {
  'use strict';
  const PAGE_ID = 'casespage';
  let currentCase = null, caseList = [], expandedNodeId = null;
  let showNewCase = false, showNewBranch = false, questionParentId = null, editingCase = false;

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
      '#' + PAGE_ID + ' .cases-main{box-sizing:border-box;width:100%;max-width:1560px;margin:0 auto;padding:22px 28px 42px}',
      '.cases-toolbar{display:flex;gap:10px;margin-bottom:16px}.cases-picker{flex:1;min-width:180px}.cases-picker input{box-sizing:border-box;width:100%;padding:11px 13px;border:1px solid #dce1ed;border-radius:10px;background:#fff;font:inherit;font-size:13px;color:#263154}',
      '.cases-button,.cases-button-secondary,.cases-icon{font:inherit;font-size:10px;font-weight:800;cursor:pointer;border-radius:8px;padding:7px 9px}.cases-button{background:#5146f6;color:#fff;border:1px solid #5146f6}.cases-button:hover{background:#4136df}.cases-button-secondary{background:#fff;color:#465176;border:1px solid #d8deed}.cases-button-secondary:hover{border-color:#6459f4;color:#493de2}.cases-icon{background:transparent;color:#5f6989;border:0;padding:5px 6px}.cases-icon:hover{background:#f0efff;color:#493de2}.cases-danger{border-color:#f0c7ce;color:#b23848}.cases-danger:hover{background:#fff4f5;border-color:#df7786;color:#9d2939}',
      '.cases-card{background:#fff;border:1px solid #e0e5ef;border-radius:14px;box-shadow:0 3px 14px rgba(31,39,76,.045)}.cases-empty{padding:22px;color:#74809d;font-size:13px;text-align:center}.cases-create{margin-bottom:16px;padding:16px}.cases-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cases-field{display:grid;gap:5px}.cases-field.wide{grid-column:1/-1}.cases-field label{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.035em;color:#6b7593}.cases-field input,.cases-field textarea,.cases-field select{box-sizing:border-box;width:100%;border:1px solid #dce1ed;border-radius:8px;padding:9px 10px;font:inherit;font-size:12px;color:#273153;background:#fff}.cases-field textarea{min-height:74px;resize:vertical}.cases-form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}',
      '.case-identification{padding:18px 20px;margin-bottom:16px}.case-identification-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.case-identification h1{margin:0;font-size:21px}.case-summary{margin:9px 0 0;max-width:930px;white-space:pre-wrap;color:#5f6b8c;font-size:13px;line-height:1.45}.case-actions{display:flex;gap:7px;flex-wrap:wrap}.case-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px;padding-top:14px;border-top:1px solid #edf0f5}.case-fact small{display:block;font-size:10px;font-weight:800;color:#7a84a0;text-transform:uppercase;letter-spacing:.035em;margin-bottom:3px}.case-fact span{display:block;font-size:12px;color:#313b5e;overflow-wrap:anywhere}',
      '.case-tree{padding:16px 18px}.case-tree-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:13px}.case-tree-head h2{font-size:15px;margin:0}.case-tree-head p{font-size:11px;color:#74809d;margin:3px 0 0}.branch-form{margin:0 0 12px;padding:13px;background:#f8f8fd;border:1px dashed #cbd2e6;border-radius:10px}.branch-form h3{font-size:12px;margin:0 0 10px}.branch-list{display:grid;gap:10px}.primary-branch{border:1px solid #dce2f0;border-radius:11px;overflow:hidden}.primary-branch.drop-target{border-color:#6558f5;box-shadow:0 0 0 3px rgba(101,88,245,.14)}.primary-head{display:flex;align-items:center;gap:9px;padding:10px 11px;background:#fbfbff}.branch-mark{display:grid;place-items:center;width:24px;height:24px;border-radius:7px;background:#eeeaff;color:#5548ef;font-size:13px;font-weight:900}.branch-title{flex:1;min-width:0}.branch-title b{display:block;font-size:12px;color:#283257}.branch-title small{display:block;margin-top:2px;color:#75809b;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.branch-actions{display:flex;gap:2px;align-items:center}.branch-questions{padding:8px 10px 10px;border-top:1px solid #edf0f6}.question-row{display:flex;align-items:center;gap:9px;border:1px solid #e4e8f2;border-radius:8px;padding:8px 9px;margin-top:6px;background:#fff}.question-row:first-child{margin-top:0}.question-row:hover{border-color:#bcb5ff;background:#fcfbff}.question-row strong{display:block;font-size:11px;color:#303a60;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row small{display:block;margin-top:2px;max-width:580px;font-size:10px;color:#78839e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.question-row .cases-icon{border:1px solid #dbe0ee;padding:5px 8px;font-size:10px}.question-add{margin-top:8px;background:transparent;border:0;color:#5146f6;font-size:10px;font-weight:800;cursor:pointer;padding:4px 1px}.question-add:hover{text-decoration:underline}',
      '.case-workspace{margin-top:16px;min-height:520px;overflow:hidden}.workspace-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:15px 18px;border-bottom:1px solid #e6eaf2}.workspace-head small{display:block;color:#78829c;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}.workspace-head h2{margin:0;font-size:16px;color:#263156}.workspace-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(285px,.42fr);min-height:460px}.workspace-editor{padding:18px;border-right:1px solid #e8ebf3}.workspace-sources{padding:16px;background:#fbfbfe}.workspace-section{margin-bottom:16px}.workspace-section h3{font-size:11px;text-transform:uppercase;letter-spacing:.035em;color:#687492;margin:0 0 7px}.workspace-section textarea,.workspace-section input{box-sizing:border-box;width:100%;font:inherit;font-size:13px;line-height:1.5;color:#293357;border:1px solid #dce2ee;border-radius:9px;padding:10px;background:#fff}.workspace-section textarea{min-height:112px;resize:vertical}.workspace-section textarea.own-position{min-height:180px}.workspace-save{display:flex;justify-content:flex-end}.source-title{font-size:13px;margin:0 0 8px;color:#2b3559}.source-help{font-size:11px;line-height:1.4;color:#74809d;margin:0 0 10px}.source-accordion{border:1px solid #e0e5ef;border-radius:9px;background:#fff;margin:8px 0}.source-accordion summary{cursor:pointer;list-style:none;padding:9px 10px;font-size:11px;font-weight:800;color:#354064}.source-accordion summary::-webkit-details-marker{display:none}.source-accordion summary:before{content:"▸";display:inline-block;color:#5b4ff1;margin-right:7px}.source-accordion[open] summary:before{transform:rotate(90deg)}.source-body{border-top:1px solid #edf0f5;padding:9px 10px}.source-body p{white-space:pre-wrap;font-size:11px;line-height:1.45;color:#56617e;margin:0 0 9px}.source-actions{display:flex;gap:7px;justify-content:flex-end}.source-link-form{margin-top:13px;padding-top:13px;border-top:1px solid #e4e8f1}.source-link-form select{margin-bottom:7px}.source-link-form .cases-button{width:100%;margin-top:7px}.sources-empty{padding:13px 4px;color:#7b85a1;font-size:11px;line-height:1.4}',
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
    const add = el('button', {type: 'button', className: 'cases-button', textContent: '+ Nuevo caso'});
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
    const edit = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Modificar datos'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Eliminar caso'});
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
    const card = el('section', {className: 'cases-card case-tree'}), add = el('button', {type: 'button', className: 'cases-button', textContent: '+ Agregar rama principal'});
    add.addEventListener('click', () => { showNewBranch = !showNewBranch; questionParentId = null; render({cases: caseList}); });
    card.append(el('header', {className: 'case-tree-head'}, el('div', {}, el('h2', {textContent: 'Estructura del caso'}), el('p', {textContent: 'Ramas principales y cuestiones jurídicas. Abrí una cuestión para trabajar sus argumentos y fuentes.'})), add));
    if (showNewBranch) card.append(branchForm(snapshot));
    const roots = snapshot.nodes || [];
    if (!roots.length) card.append(el('p', {className: 'cases-empty', textContent: 'Agregá la primera rama principal: por ejemplo, Demanda, Actuación administrativa o Sentencia.'}));
    const list = el('div', {className: 'branch-list'}); roots.forEach(node => list.append(primary(snapshot, node))); card.append(list);
    if (expandedNodeId) { const node = findNode(roots, expandedNodeId); if (node) card.append(workspace(snapshot, node)); }
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
    const upload = el('button', {type: 'button', className: 'cases-icon', textContent: 'Cargar archivos', title: 'Elegir archivos o arrastrarlos sobre esta rama'});
    const addQuestion = el('button', {type: 'button', className: 'cases-icon', textContent: '+ Cuestión'}), edit = el('button', {type: 'button', className: 'cases-icon', textContent: 'Editar'}), remove = el('button', {type: 'button', className: 'cases-icon cases-danger', textContent: 'Eliminar'});
    upload.addEventListener('click', () => input.click());
    input.addEventListener('change', () => { if (input.files?.length) importBranchFiles(snapshot, node, input.files, upload); input.value = ''; });
    addQuestion.addEventListener('click', () => { questionParentId = node.id; showNewBranch = false; render({cases: caseList}); });
    edit.addEventListener('click', async () => { const titleValue = prompt('Nombre de la rama principal:', node.title); if (titleValue === null) return; try { await updateNode(Object.assign({}, node, {title: titleValue, primary_document_id: node.primary_document_id || null})); } catch (error) { alert(error.message); } });
    remove.addEventListener('click', () => removeNode(node, node.children && node.children.length ? 'También se eliminarán sus cuestiones y vínculos locales.' : ''));
    article.addEventListener('dragover', event => { event.preventDefault(); article.classList.add('drop-target'); });
    article.addEventListener('dragleave', event => { if (!article.contains(event.relatedTarget)) article.classList.remove('drop-target'); });
    article.addEventListener('drop', event => { event.preventDefault(); article.classList.remove('drop-target'); if (event.dataTransfer?.files?.length) importBranchFiles(snapshot, node, event.dataTransfer.files, upload); });
    article.append(input, el('header', {className: 'primary-head'}, el('span', {className: 'branch-mark', textContent: '↳'}), title, el('div', {className: 'branch-actions'}, upload, addQuestion, edit, remove)));
    const questions = el('div', {className: 'branch-questions'}); (node.children || []).forEach(question => questions.append(questionRow(snapshot, question)));
    if (questionParentId === node.id) questions.append(questionForm(snapshot, node.id));
    const add = el('button', {type: 'button', className: 'question-add', textContent: '+ Agregar cuestión jurídica'}); add.addEventListener('click', () => { questionParentId = node.id; showNewBranch = false; render({cases: caseList}); }); questions.append(add); article.append(questions);
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
    const preview = node.adversary_text || node.own_position || 'Sin desarrollo todavía', open = el('button', {type: 'button', className: 'cases-icon', textContent: expandedNodeId === node.id ? 'Reducir' : 'Abrir'});
    open.addEventListener('click', () => { expandedNodeId = expandedNodeId === node.id ? null : node.id; render({cases: caseList}); if (expandedNodeId) setTimeout(() => { const box = document.querySelector('.case-workspace'); if (box) box.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 0); });
    const addChild = el('button', {type: 'button', className: 'cases-icon', textContent: '+ Subrama'});
    addChild.addEventListener('click', () => { questionParentId = node.id; render({cases: caseList}); });
    const row = el('div', {className: 'question-row'}, el('div', {className: 'branch-mark', textContent: '§'}), el('div', {style: 'flex:1;min-width:0'}, el('strong', {textContent: node.title}), el('small', {textContent: preview})), addChild, open);
    const article = el('article', {});
    article.append(row);
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
  function workspaceField(label, control) { return el('div', {className: 'workspace-section'}, el('h3', {textContent: label}), control); }
  function workspace(snapshot, node) {
    const box = el('section', {className: 'cases-card case-workspace'}), reduce = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Reducir'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Eliminar cuestión'});
    reduce.addEventListener('click', () => { expandedNodeId = null; render({cases: caseList}); }); remove.addEventListener('click', () => removeNode(node, 'Se eliminarán también los vínculos de fuentes de esta cuestión.'));
    box.append(el('header', {className: 'workspace-head'}, el('div', {}, el('small', {textContent: 'Cuestión jurídica'}), el('h2', {textContent: node.title})), el('div', {className: 'case-actions'}, reduce, remove)));
    const title = el('input', {value: node.title}), adversary = el('textarea', {value: node.adversary_text || '', placeholder: 'Describí la cuestión, pretensión o afirmación de la contraparte.'}), position = el('textarea', {className: 'own-position', value: node.own_position || '', placeholder: 'Desarrollá nuestra postura, argumentos y estrategia.'});
    const save = el('button', {type: 'button', className: 'cases-button', textContent: 'Guardar cambios'});
    save.addEventListener('click', async () => { save.disabled = true; try { await updateNode(Object.assign({}, node, {title: title.value, adversary_text: adversary.value, own_position: position.value})); } catch (error) { alert(error.message); } finally { save.disabled = false; } });
    const editor = el('section', {className: 'workspace-editor'}, workspaceField('Enunciado de la cuestión', title), workspaceField('Planteo de la contraparte', adversary), workspaceField('Nuestra postura y fundamentos', position), el('div', {className: 'workspace-save'}, save));
    box.append(el('div', {className: 'workspace-layout'}, editor, sources(snapshot, node))); return box;
  }
  function sources(snapshot, node) {
    const panel = el('aside', {className: 'workspace-sources'}, el('h3', {className: 'source-title', textContent: 'Fuentes vinculadas'}), el('p', {className: 'source-help', textContent: 'Documentos y fragmentos que respaldan o deben ser analizados dentro de esta cuestión.'}));
    const current = node.sources || []; if (!current.length) panel.append(el('p', {className: 'sources-empty', textContent: 'Todavía no hay fuentes vinculadas a esta cuestión.'})); current.forEach(source => panel.append(sourceItem(snapshot.case.id, source)));
    const form = el('form', {className: 'source-link-form'}), source = evidenceSelect(snapshot), stance = el('select');
    ['fundamento', 'postura contraria', 'a verificar', 'contexto'].forEach(value => stance.append(el('option', {value, textContent: value[0].toUpperCase() + value.slice(1)})));
    const submit = el('button', {type: 'submit', className: 'cases-button', textContent: '+ Vincular fuente'}); form.append(field('Fuente del caso', source), field('Uso', stance), submit);
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (!source.value) return alert('Elegí un documento o fragmento.'); submit.disabled = true;
      try { const pieces = source.value.split(':'), payload = {case_id: snapshot.case.id, node_id: node.id, stance: stance.value}; if (pieces[0] === 'document') payload.case_document_id = Number(pieces[1]); else payload.case_entry_id = Number(pieces[1]); const response = await api('/api/cases/node/source', {method: 'POST', body: JSON.stringify(payload)}); currentCase = response.case; await loadCases(false); } catch (error) { alert(error.message); } finally { submit.disabled = false; }
    }); panel.append(form); return panel;
  }
  function sourceItem(caseId, source) {
    const name = source.document_name || source.entry_document_name || source.entry_title || 'Fuente vinculada', text = source.source_excerpt || source.entry_content || source.note || 'Sin extracto guardado. Abrí el documento para consultarlo.', details = el('details', {className: 'source-accordion'});
    const open = el('button', {type: 'button', className: 'cases-button-secondary', textContent: 'Abrir'}), remove = el('button', {type: 'button', className: 'cases-button-secondary cases-danger', textContent: 'Quitar'});
    open.addEventListener('click', () => openSource(source)); remove.addEventListener('click', async () => { if (!confirm('¿Quitar esta fuente de la cuestión? El documento o fragmento seguirá existiendo en el caso.')) return; try { const response = await api('/api/cases/node/source/delete', {method: 'POST', body: JSON.stringify({case_id: caseId, source_id: source.id, confirmed: true})}); currentCase = response.case; await loadCases(false); } catch (error) { alert(error.message); } });
    details.append(el('summary', {textContent: name + ' · ' + (source.stance || 'fundamento')}), el('div', {className: 'source-body'}, el('p', {textContent: text}), el('div', {className: 'source-actions'}, open, remove))); return details;
  }
  function openSource(source) {
    const path = String(source.document_path || source.entry_document_path || '').trim(); if (!path) return alert('Esta fuente no conserva una ruta local.');
    const pageNumber = Number(source.page_start || 0) || 1, snippet = String(source.source_excerpt || source.entry_content || '').trim();
    if (typeof window.lexiaQuickViewerOpen === 'function') return window.lexiaQuickViewerOpen(path, pageNumber, snippet);
    window.open('/api/file-preview?path=' + encodeURIComponent(path), '_blank', 'noopener');
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
      alert(imported + ' archivo(s) incorporado(s) en Escritos\\' + snapshot.case.name + suffix + '.');
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
