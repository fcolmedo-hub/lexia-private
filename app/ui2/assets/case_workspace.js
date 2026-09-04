/* LexIA Casos / Bitácora 1.0 — local and auditable; no AI calls. */
(function () {
  'use strict';

  const PAGE_ID = 'casespage';
  let currentCase = null;

  const entryTypes = [
    'apunte propio', 'hecho', 'argumento', 'duda', 'tarea',
    'decisión', 'extracto documental', 'investigación',
  ];

  function element(tag, properties, ...children) {
    const node = document.createElement(tag);
    Object.entries(properties || {}).forEach(([key, value]) => {
      if (key === 'className') node.className = value;
      else if (key === 'textContent') node.textContent = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    });
    children.flat().filter(Boolean).forEach(child => node.append(child));
    return node;
  }

  async function request(url, options) {
    const response = await fetch(url, {
      cache: 'no-store',
      headers: {'Content-Type': 'application/json'},
      ...options,
    });
    const body = await response.json();
    if (!response.ok || body.ok === false) throw new Error(body.error || `HTTP ${response.status}`);
    return body;
  }

  function installStyle() {
    const style = element('style', {textContent: `
      #${PAGE_ID}{display:none;min-height:100vh;background:#f7f8fc;color:#202a48;margin-left:var(--global-side,0px)!important;width:calc(100vw - var(--global-side,0px))!important;padding-top:var(--global-top,0px)!important;box-sizing:border-box!important;overflow-x:hidden}
      #${PAGE_ID} .cases-main{padding:24px 28px 36px;max-width:1500px;margin:0 auto;width:100%}
      .cases-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:18px}.cases-head h1{margin:0;font-size:24px}.cases-head p{margin:5px 0 0;color:#697394;font-size:13px}
      .cases-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:16px}.cases-card{background:#fff;border:1px solid #e2e5ef;border-radius:13px;padding:15px;box-shadow:0 3px 12px rgba(28,37,71,.04)}
      .cases-card h2{margin:0 0 12px;font-size:14px}.cases-card h3{margin:0 0 7px;font-size:12px}.cases-list{display:flex;flex-direction:column;gap:6px;max-height:520px;overflow:auto}.case-select{border:1px solid #e1e5ef;background:#fff;text-align:left;border-radius:8px;padding:10px;cursor:pointer}.case-select:hover,.case-select.active{border-color:#5b4cf3;background:#f4f2ff}.case-select b{display:block;font-size:12px;color:#293158}.case-select small{display:block;margin-top:3px;font-size:10px;color:#74809e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .case-form{display:grid;gap:8px}.case-form input,.case-form textarea,.case-form select{box-sizing:border-box;width:100%;border:1px solid #dce1ed;border-radius:8px;padding:9px 10px;font:inherit;font-size:12px;background:#fff}.case-form textarea{min-height:86px;resize:vertical}.case-form label{font-size:10px;font-weight:800;color:#5e6989}.case-form button,.cases-head button{border:0;border-radius:8px;background:#5146f6;color:#fff;padding:9px 12px;font-size:11px;font-weight:800;cursor:pointer}.case-form button:disabled{opacity:.6;cursor:wait}.case-empty{color:#77819f;font-size:12px;padding:12px 0}
      .case-overview{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:16px}.case-title{font-size:18px;font-weight:800;margin:0 0 4px}.case-description{margin:0;color:#687394;font-size:12px;white-space:pre-wrap}.case-metric{padding:10px;border:1px solid #e7e9f1;border-radius:9px;margin-bottom:8px}.case-metric b{display:block;font-size:18px;color:#3f34d1}.case-metric small{font-size:10px;color:#71809d}
      .case-bitacora{margin-top:16px}.entry{border-left:3px solid #6558f5;padding:10px 12px;margin:0 0 8px;background:#fbfbff;border-radius:0 8px 8px 0}.entry-head{display:flex;gap:8px;align-items:center;font-size:10px;color:#697394}.entry-type{font-weight:800;color:#5146f6;text-transform:capitalize}.entry h4{font-size:12px;margin:6px 0 4px}.entry p{white-space:pre-wrap;font-size:12px;line-height:1.4;margin:0;color:#333e60}.entry-source{font-size:10px;margin-top:7px;color:#697394}.entry-source button{border:0;background:transparent;padding:0;color:#5146f6;text-decoration:underline;cursor:pointer;font:inherit}
      .case-documents{margin-top:16px}.case-documents ul{padding:0;margin:0;list-style:none}.case-documents li{padding:7px 0;border-top:1px solid #eef0f5;font-size:11px}.case-documents small{color:#74809e}
      @media(max-width:900px){.cases-main{padding:16px!important}.cases-layout,.case-overview{grid-template-columns:1fr}.cases-list{max-height:190px}.cases-head{align-items:flex-start;flex-direction:column}}
    `});
    document.head.appendChild(style);
  }

  function page() { return document.getElementById(PAGE_ID); }
  function showCasePage() {
    const targets = ['home','library','searchpage','contextpage','activitypage','systempage','maintenance', PAGE_ID];
    targets.forEach(id => { const node = document.getElementById(id); if (node) node.style.setProperty('display', 'none', 'important'); });
    page().style.setProperty('display', 'grid', 'important');
    const nav = document.querySelector('#globalSidebar .nav');
    if (nav) {
      nav.querySelectorAll('button').forEach(item => item.classList.remove('active'));
      nav.querySelector('[data-lexia-cases]')?.classList.add('active');
    }
    history.replaceState(null, '', '#' + PAGE_ID);
    window.scrollTo(0, 0);
    loadCases();
  }

  function addNavigation() {
    const sidebar = document.getElementById('globalSidebar');
    const nav = sidebar && sidebar.querySelector('.nav');
    if (!nav || nav.querySelector('[data-lexia-cases]')) return;
    const button = element('button', {type: 'button', 'data-lexia-cases': '1'});
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = '<rect x="3" y="7" width="18" height="13" rx="2"></rect><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M3 12h18"></path><path d="M10 12v2h4v-2"></path>';
    button.append(icon, document.createTextNode('Casos'));
    button.addEventListener('click', () => {
      nav.querySelectorAll('button').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
    });
    button.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); showCasePage(); }, true);
    const context = nav.querySelector('button[data-route="contextpage"]') || Array.from(nav.querySelectorAll('button')).find(button => button.textContent.trim() === 'Investigación');
    context ? context.insertAdjacentElement('beforebegin', button) : nav.appendChild(button);
  }

  function createPage() {
    const section = element('section', {id: PAGE_ID, className: 'casespage'});
    section.appendChild(element('main', {className: 'cases-main'}));
    document.body.appendChild(section);
  }

  function render(data) {
    const root = page().querySelector('.cases-main');
    root.replaceChildren();
    const head = element('header', {className: 'cases-head'},
      element('div', {}, element('h1', {textContent: 'Casos'}), element('p', {textContent: 'Memoria estratégica local, verificable y evolutiva de cada expediente.'})),
    );
    root.appendChild(head);
    const layout = element('div', {className: 'cases-layout'});
    const left = element('aside', {className: 'cases-card'});
    left.append(element('h2', {textContent: 'Mis casos'}));
    const list = element('div', {className: 'cases-list'});
    const cases = data.cases || [];
    if (!cases.length) list.append(element('div', {className: 'case-empty', textContent: 'Todavía no hay casos creados.'}));
    cases.forEach(item => {
      const button = element('button', {type: 'button', className: 'case-select' + (currentCase?.case?.id === item.id ? ' active' : '')},
        element('b', {textContent: item.name}), element('small', {textContent: item.description || 'Sin descripción'}));
      button.addEventListener('click', () => loadCase(item.id));
      list.append(button);
    });
    left.append(list, createCaseForm());
    const content = element('section', {className: 'cases-content'});
    if (currentCase?.case) renderCase(content, currentCase);
    else content.append(element('div', {className: 'cases-card case-empty', textContent: 'Creá o elegí un caso para comenzar la bitácora.'}));
    layout.append(left, content); root.append(layout);
  }

  function createCaseForm() {
    const form = element('form', {className: 'case-form'});
    const name = element('input', {placeholder: 'Carátula o nombre del caso', required: 'required'});
    const description = element('textarea', {placeholder: 'Descripción breve: pretensión, etapa o asunto principal.'});
    const submit = element('button', {type: 'submit', textContent: 'Crear caso'});
    form.append(element('h3', {textContent: 'Nuevo caso'}), name, description, submit);
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try { const response = await request('/api/cases', {method: 'POST', body: JSON.stringify({name: name.value, description: description.value})}); currentCase = response.case; await loadCases(false); }
      catch (error) { alert(error.message); }
      finally { submit.disabled = false; }
    });
    return form;
  }

  function renderCase(target, snapshot) {
    const details = snapshot.case;
    const documents = snapshot.documents || [];
    const entries = snapshot.entries || [];
    const overview = element('div', {className: 'cases-card case-overview'},
      element('div', {}, element('h2', {className: 'case-title', textContent: details.name}), element('p', {className: 'case-description', textContent: details.description || 'Sin descripción aún.'})),
      element('div', {}, element('div', {className: 'case-metric'}, element('b', {textContent: String(documents.length)}), element('small', {textContent: 'documentos vinculados'})), element('div', {className: 'case-metric'}, element('b', {textContent: String(entries.length)}), element('small', {textContent: 'entradas de bitácora'}))),
    );
    target.append(overview, entryForm());
    const docs = element('section', {className: 'cases-card case-documents'}, element('h2', {textContent: 'Documentos vinculados'}));
    if (!documents.length) docs.append(element('p', {className: 'case-empty', textContent: 'Todavía no hay documentos vinculados. Próximamente se incorporarán desde Buscar e Investigaciones.'}));
    else {
      const list = element('ul');
      documents.forEach(doc => {
        list.append(element(
          'li', {},
          element('b', {textContent: doc.document_name}),
          element('br'),
          element('small', {textContent: `${doc.category || 'Sin categoría'} · ${doc.relation_kind}`}),
        ));
      });
      docs.append(list);
    }
    target.append(docs);
    const journal = element('section', {className: 'cases-card case-bitacora'}, element('h2', {textContent: 'Bitácora del caso'}));
    if (!entries.length) journal.append(element('p', {className: 'case-empty', textContent: 'Aún no hay entradas. Registrá hechos, ideas, tareas o argumentos para construir la memoria del caso.'}));
    entries.forEach(entry => journal.append(renderEntry(entry)));
    target.append(journal);
  }

  function entryForm() {
    const form = element('form', {className: 'cases-card case-form'});
    const type = element('select'); entryTypes.forEach(value => type.append(element('option', {value, textContent: value[0].toUpperCase() + value.slice(1)})));
    const title = element('input', {placeholder: 'Título opcional'});
    const content = element('textarea', {placeholder: 'Escribí la entrada de la bitácora…', required: 'required'});
    const submit = element('button', {type: 'submit', textContent: 'Agregar a la bitácora'});
    form.append(element('h2', {textContent: 'Nueva entrada'}), element('label', {textContent: 'Tipo'}), type, title, content, submit);
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try { const response = await request('/api/cases/entry', {method: 'POST', body: JSON.stringify({case_id: currentCase.case.id, entry_type: type.value, title: title.value, content: content.value})}); currentCase = response.case; await loadCases(false); }
      catch (error) { alert(error.message); }
      finally { submit.disabled = false; }
    });
    return form;
  }

  function renderEntry(entry) {
    const item = element('article', {className: 'entry'});
    item.append(element('div', {className: 'entry-head'}, element('span', {className: 'entry-type', textContent: entry.entry_type}), element('span', {textContent: entry.created_at})));
    if (entry.title) item.append(element('h4', {textContent: entry.title}));
    item.append(element('p', {textContent: entry.content}));
    if (entry.document_name) {
      const source = element('div', {className: 'entry-source'});
      const open = element('button', {
        type: 'button',
        textContent: `${entry.document_name}${entry.page_start ? ` · pág. ${entry.page_start}` : ''}`,
        title: 'Abrir la fuente original de esta entrada',
      });
      open.addEventListener('click', () => openEvidence(entry));
      source.append(open);
      item.append(source);
    }
    return item;
  }

  function openEvidence(entry) {
    const path = String(entry.document_path || '').trim();
    if (!path) return alert('Esta entrada no conserva una ruta local de fuente.');
    const page = Number(entry.page_start || 0) || 1;
    const snippet = String(entry.source_excerpt || entry.content || '').trim();
    if (typeof window.lexiaQuickViewerOpen === 'function') {
      window.lexiaQuickViewerOpen(path, page, snippet);
      return;
    }
    window.open('/api/file-preview?path=' + encodeURIComponent(path), '_blank', 'noopener');
  }

  async function loadCases(refreshSelection = true) {
    try {
      const response = await request('/api/cases');
      if (refreshSelection && currentCase?.case?.id) {
        const selected = response.cases.find(item => item.id === currentCase.case.id);
        if (selected) await loadCase(selected.id, response); else { currentCase = null; render(response); }
      } else render(response);
    } catch (error) { page().querySelector('.cases-main').textContent = 'No se pudieron cargar los casos: ' + error.message; }
  }

  async function loadCase(caseId, alreadyLoaded) {
    try { const response = await request('/api/cases/' + caseId); currentCase = response.case; render(alreadyLoaded || await request('/api/cases')); }
    catch (error) { alert(error.message); }
  }

  function categoryFromCard(card) {
    const meta = card.querySelector('.result-meta,.source-meta small')?.textContent || '';
    return meta.split('·')[0].trim() || 'Documento';
  }

  async function documentFromCard(card) {
    const name = card.querySelector('.result-title,.result-title-btn,.source-name-link,strong')?.textContent?.trim() || 'Documento';
    const snippet = card.querySelector('p,.source-snippet')?.textContent?.trim() || '';
    const clickable = card.querySelector('[data-path]');
    let path = clickable?.dataset.path || '';
    try { path = decodeURIComponent(path); } catch (_) {}
    if (!path) {
      const response = await request('/api/resolve-document', {
        method: 'POST', body: JSON.stringify({name, snippet}),
      });
      path = response.path;
    }
    const page = Number(card.querySelector('[data-page]')?.dataset.page || 0) || null;
    return {name, path, snippet, page, category: categoryFromCard(card)};
  }

  async function chooseCase() {
    const response = await request('/api/cases');
    const cases = response.cases || [];
    if (!cases.length) throw new Error('Primero creá un caso en la sección Casos.');
    if (currentCase?.case?.id && cases.some(item => item.id === currentCase.case.id)) return currentCase.case.id;
    const options = cases.map((item, index) => `${index + 1}. ${item.name}`).join('\n');
    const selected = Number(window.prompt(`¿A qué caso querés incorporarlo?\n\n${options}`, '1'));
    if (!Number.isInteger(selected) || selected < 1 || selected > cases.length) throw new Error('No se seleccionó un caso válido.');
    return cases[selected - 1].id;
  }

  async function linkCardToCase(card, button) {
    button.disabled = true;
    const original = button.textContent;
    button.textContent = 'Incorporando…';
    try {
      const document = await documentFromCard(card);
      const caseId = await chooseCase();
      const linked = await request('/api/cases/link-document', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseId,
          document_name: document.name,
          document_path: document.path,
          category: document.category,
          relation_kind: 'fuente vinculada',
        }),
      });
      if (document.snippet) {
        await request('/api/cases/entry', {
          method: 'POST',
          body: JSON.stringify({
            case_id: caseId,
            entry_type: 'extracto documental',
            title: document.name,
            content: document.snippet,
            document_name: document.name,
            document_path: document.path,
            page_start: document.page,
            source_excerpt: document.snippet,
          }),
        });
      }
      currentCase = linked.case;
      button.textContent = 'Incorporado';
      setTimeout(() => { button.textContent = original; button.disabled = false; }, 1200);
    } catch (error) {
      alert('No se pudo incorporar la fuente al caso.\n\n' + error.message);
      button.textContent = original;
      button.disabled = false;
    }
  }

  function installCaseActions(root = document) {
    const cards = [];
    if (root.nodeType === 1 && root.matches('.result-card,.source-item')) cards.push(root);
    cards.push(...root.querySelectorAll('.result-card,.source-item'));
    cards.forEach(card => {
      const actions = card.querySelector('.result-actions,.source-actions');
      if (!actions || actions.querySelector('[data-lexia-case-link]')) return;
      const button = element('button', {
        type: 'button', 'data-lexia-case-link': '1', className: 'lexia-case-link',
        textContent: 'Al caso', title: 'Vincular esta fuente y su extracto a un caso',
      });
      button.addEventListener('click', event => {
        event.preventDefault(); event.stopPropagation(); linkCardToCase(card, button);
      });
      actions.append(button);
    });
  }

  function initialize() {
    installStyle(); createPage(); addNavigation();
    installCaseActions();
    new MutationObserver(records => records.forEach(record => {
      record.addedNodes.forEach(node => {
        if (node.nodeType === 1) installCaseActions(node);
      });
    })).observe(document.body, {childList: true, subtree: true});
    if ((location.hash || '').slice(1) === PAGE_ID) showCasePage();
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', initialize, {once: true}) : initialize();
})();
