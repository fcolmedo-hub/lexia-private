/* LEXIA UI2 3.3.0i INVESTIGATION AND DOCUMENT STUDY NAVIGATOR */
(function(){
  const state={
    active:false,initialized:false,selections:new Map(),
    query:'',sort:'name_asc',offset:0,total:0,selectedPath:'',selectedDocument:null,
    listRequest:0,previewRequest:0,previewTimer:null,documents:new Map(),nodes:new Map()
  };
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const decodePath=value=>{try{return decodeURIComponent(String(value||''));}catch(_){return '';}};
  const selectionKey=(category,folder)=>
    encodeURIComponent(String(category||''))+'|'+encodeURIComponent(String(folder||''));
  const number=value=>Number(value||0).toLocaleString('es-AR');
  const size=value=>{
    let n=Number(value||0);
    if(!n)return 'Tamaño no informado';
    const units=['B','KB','MB','GB'];
    let i=0;
    while(n>=1024&&i<units.length-1){n/=1024;i++;}
    return n.toLocaleString('es-AR',{maximumFractionDigits:i?1:0})+' '+units[i];
  };
  const date=value=>{
    const raw=String(value||'').trim();
    if(!raw)return 'Sin fecha';
    const match=raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if(match)return Number(match[3])+'/'+Number(match[2])+'/'+match[1];
    return raw.slice(0,10);
  };
  const post=async(url,body)=>{
    const response=await fetch(url,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok||!data.ok)throw new Error(data.error||('HTTP '+response.status));
    return data;
  };
  const get=async url=>{
    const response=await fetch(url,{cache:'no-store'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok||!data.ok)throw new Error(data.error||('HTTP '+response.status));
    return data;
  };

  function emptyPreview(){
    state.selectedPath='';
    state.selectedDocument=null;
    const host=$('lexiaNavigatorPreview');
    if(host)host.innerHTML='<div class="lexia-nav-preview-empty"><div><b>Ningún documento seleccionado</b>Pasá el puntero sobre una fila para leer su primer fragmento indexado.</div></div>';
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card.selected').forEach(
      card=>card.classList.remove('selected')
    );
  }

  function selectedFoldersPayload(){
    return Array.from(state.selections.values(),item=>({
      category:item.category,folder:item.folder
    }));
  }

  function importDestination(){
    if(state.selections.size!==1){
      throw new Error('Para importar archivos debe haber una sola carpeta seleccionada.');
    }
    const selected=state.selections.values().next().value;
    if(!String(selected.folder||'').trim()){
      throw new Error('Seleccioná una única carpeta concreta, no la biblioteca ni sólo la categoría.');
    }
    return selected;
  }

  function importStatus(message,type='info'){
    const host=$('lexiaNavigatorImportStatus');
    if(!host)return;
    host.textContent=String(message||'');
    host.className='lexia-nav-import-status show '+type;
  }

  async function importFiles(fileList){
    let destination;
    try{destination=importDestination();}
    catch(error){importStatus(error.message,'error');return;}
    const files=Array.from(fileList||[]);
    if(!files.length)return;
    const button=$('lexiaNavigatorImport');
    if(button)button.disabled=true;
    importStatus('Importando '+number(files.length)+' archivo'+(files.length===1?'':'s')+'…');
    try{
      const form=new FormData();
      form.append('category',destination.category);
      form.append('destination',destination.folder);
      files.forEach(file=>form.append('files',file,file.name));
      const response=await fetch('/api/navigator-import',{method:'POST',body:form});
      const data=await response.json().catch(()=>({}));
      if(!response.ok||!data.ok)throw new Error(data.error||('HTTP '+response.status));
      const imported=(data.imported||[]).length;
      const skipped=(data.skipped||[]).length;
      const errors=(data.errors||[]);
      let message=number(imported)+' archivo'+(imported===1?' importado':'s importados');
      if(skipped)message+=' · '+number(skipped)+' omitido'+(skipped===1?'':'s')+' porque ya existían';
      if(errors.length)message+=' · '+number(errors.length)+' con error';
      importStatus(message,errors.length&&!imported?'error':'success');
      await buildTree();
    }catch(error){importStatus(error.message||String(error),'error');}
    finally{if(button)button.disabled=false;const input=$('lexiaNavigatorImportInput');if(input)input.value='';}
  }

  function refreshTreeSelection(){
    document.querySelectorAll('#lexiaNavigatorTree .lexia-nav-tree-row').forEach(item=>{
      const selected=item.dataset.libraryRoot==='1'?
        state.selections.size===0:
        isTreeNodeSelected(item.dataset.selectionKey||'');
      item.classList.toggle('selected',selected);
      const selector=item.querySelector('.lexia-nav-tree-select');
      if(selector)selector.setAttribute('aria-pressed',selected?'true':'false');
    });
  }

  function isTreeNodeSelected(key){
    if(state.selections.has(key))return true;
    let current=state.nodes.get(key);
    while(current&&current.parentKey){
      if(state.selections.has(current.parentKey))return true;
      current=state.nodes.get(current.parentKey);
    }
    return false;
  }

  function descendantsOf(key){
    const result=[];
    for(const [candidate,node] of state.nodes){
      let current=node;
      while(current&&current.parentKey){
        if(current.parentKey===key){result.push(candidate);break;}
        current=state.nodes.get(current.parentKey);
      }
    }
    return result;
  }

  function promoteLoadedAncestors(key){
    let current=state.nodes.get(key);
    while(current&&current.parentKey){
      const parent=state.nodes.get(current.parentKey);
      if(!parent)break;
      const children=Array.from(state.nodes.values()).filter(node=>node.parentKey===parent.key);
      if(children.length&&children.every(child=>isTreeNodeSelected(child.key))){
        children.forEach(child=>state.selections.delete(child.key));
        state.selections.set(parent.key,{category:parent.category,folder:parent.folder,labels:parent.labels});
      }
      current=parent;
    }
  }

  function updateSelectionBreadcrumb(){
    const breadcrumb=$('lexiaNavigatorBreadcrumb');
    if(!breadcrumb)return;
    if(!state.selections.size){
      breadcrumb.textContent='Biblioteca';
      breadcrumb.title='Toda la Biblioteca';
      return;
    }
    if(state.selections.size===1){
      const selected=state.selections.values().next().value;
      breadcrumb.textContent=selected.labels.join('  ›  ');
      breadcrumb.title=selected.labels.join(' › ');
      return;
    }
    breadcrumb.textContent=number(state.selections.size)+' carpetas seleccionadas';
    breadcrumb.title=Array.from(
      state.selections.values(),item=>item.labels.join(' › ')
    ).join('\n');
  }

  function toggleTreeNode(node,labels,libraryRoot=false){
    if(libraryRoot){
      state.selections.clear();
    }else{
      const category=String(node.category||'');
      const folder=String(node.folder||'');
      const key=selectionKey(category,folder);
      if(state.selections.has(key)){
        state.selections.delete(key);
        descendantsOf(key).forEach(childKey=>state.selections.delete(childKey));
      }else{
        // Una selección de carpeta representa todo su subárbol.
        Array.from(state.selections.keys()).forEach(selectedKey=>{
          if(descendantsOf(selectedKey).includes(key))state.selections.delete(selectedKey);
        });
        descendantsOf(key).forEach(childKey=>state.selections.delete(childKey));
        state.selections.set(key,{
        category,folder,labels:labels&&labels.length?labels:['Biblioteca']
        });
        promoteLoadedAncestors(key);
      }
    }
    refreshTreeSelection();
    updateSelectionBreadcrumb();
    state.offset=0;
    emptyPreview();
    loadDocuments(false);
  }

  function makeTreeRow(node,depth,labels){
    const wrap=document.createElement('div');
    const row=document.createElement('div');
    row.className='lexia-nav-tree-row';
    row.style.setProperty('--depth',String(depth));
    row.dataset.category=node.category||'';
    row.dataset.folder=node.folder||'';
    row.dataset.selectionKey=selectionKey(node.category||'',node.folder||'');
    const nodeKey=row.dataset.selectionKey;
    const parentKey=depth>1?selectionKey(node.category||'',String(node.parent||'')):'';
    state.nodes.set(nodeKey,{key:nodeKey,category:String(node.category||''),folder:String(node.folder||''),labels:labels||[],parentKey});

    const arrow=document.createElement('button');
    arrow.type='button';
    arrow.className='lexia-nav-arrow';
    arrow.textContent=node.has_children?'▸':'';
    arrow.disabled=!node.has_children;
    arrow.title=node.has_children?'Expandir carpeta':'Sin subcarpetas';

    const selector=document.createElement('button');
    selector.type='button';
    selector.className='lexia-nav-tree-select';
    selector.setAttribute('aria-pressed','false');
    selector.setAttribute('aria-label','Seleccionar '+String(node.name||'carpeta'));

    const name=document.createElement('button');
    name.type='button';
    name.className='lexia-nav-tree-name';
    name.textContent=node.name||'Carpeta';
    name.title=node.folder||node.name||'Carpeta';

    const count=document.createElement('span');
    count.className='lexia-nav-tree-count';
    count.textContent=number(node.count);

    const children=document.createElement('div');
    children.className='lexia-nav-children';
    children.hidden=true;
    children.dataset.loaded='0';

    const choose=event=>{
      event.preventDefault();
      event.stopPropagation();
      toggleTreeNode(node,labels,false);
    };
    name.addEventListener('click',choose);
    selector.addEventListener('click',choose);

    arrow.addEventListener('click',async function(event){
      event.preventDefault();
      event.stopPropagation();
      if(this.disabled)return;
      if(children.dataset.loaded==='1'){
        children.hidden=!children.hidden;
        this.textContent=children.hidden?'▸':'▾';
        return;
      }
      this.disabled=true;
      this.textContent='…';
      try{
        const params=new URLSearchParams({category:node.category||''});
        if(node.folder)params.set('parent',node.folder);
        const data=await get('/api/navigator-children?'+params.toString());
        children.innerHTML='';
        const childNodes=data.nodes||[];
        childNodes.forEach(child=>{
          child.parent=node.folder||'';
          children.appendChild(
            makeTreeRow(child,depth+1,labels.concat([child.name||'Carpeta']))
          );
        });
        children.dataset.loaded='1';
        children.hidden=false;
        refreshTreeSelection();
        this.textContent=childNodes.length?'▾':'';
        this.disabled=!childNodes.length;
      }catch(error){
        this.textContent='!';
        this.title=error.message||String(error);
        this.disabled=false;
      }
    });

    row.append(arrow,selector,name,count);
    wrap.append(row,children);
    return wrap;
  }

  function makeLibraryRoot(total){
    const wrap=document.createElement('div');
    const row=document.createElement('div');
    row.className='lexia-nav-tree-row selected';
    row.style.setProperty('--depth','0');
    row.dataset.libraryRoot='1';
    const arrow=document.createElement('button');
    arrow.type='button';
    arrow.className='lexia-nav-arrow';
    arrow.textContent='▾';
    arrow.title='Contraer categorías';
    const selector=document.createElement('button');
    selector.type='button';
    selector.className='lexia-nav-tree-select';
    selector.setAttribute('aria-pressed','true');
    selector.setAttribute('aria-label','Seleccionar Biblioteca');
    const name=document.createElement('button');
    name.type='button';
    name.className='lexia-nav-tree-name';
    name.textContent='Biblioteca';
    const count=document.createElement('span');
    count.className='lexia-nav-tree-count';
    count.textContent=number(total);
    const children=document.createElement('div');
    children.className='lexia-nav-children';
    children.dataset.loaded='1';
    const choose=event=>{
      event.preventDefault();
      event.stopPropagation();
      toggleTreeNode({category:'',folder:''},['Biblioteca'],true);
    };
    name.addEventListener('click',choose);
    selector.addEventListener('click',choose);
    arrow.addEventListener('click',function(event){
      event.preventDefault();
      event.stopPropagation();
      children.hidden=!children.hidden;
      this.textContent=children.hidden?'▸':'▾';
    });
    row.append(arrow,selector,name,count);
    wrap.append(row,children);
    return {wrap,children};
  }

  async function buildTree(){
    const host=$('lexiaNavigatorTree');
    if(!host)return;
    host.innerHTML='<div class="lexia-nav-tree-status">Leyendo la estructura real…</div>';
    try{
      const data=await get('/api/navigator-children');
      host.innerHTML='';
      const root=makeLibraryRoot(data.total||0);
      (data.nodes||[]).forEach(node=>{
        root.children.appendChild(
          makeTreeRow(node,1,['Biblioteca',node.name||'Categoría'])
        );
      });
      host.appendChild(root.wrap);
      refreshTreeSelection();
      updateSelectionBreadcrumb();
      await loadDocuments(false);
    }catch(error){
      host.innerHTML='<div class="lexia-nav-error"><b>No se pudo leer el árbol.</b><br>'+
        esc(error.message||error)+'</div>';
      if($('lexiaNavigatorCount'))$('lexiaNavigatorCount').textContent='Árbol no disponible';
    }
  }

  function fileCard(document,index){
    const path=encodeURIComponent(document.document_path||'');
    const extension=String(document.extension||'').replace(/^\./,'').toUpperCase()||'DOC';
    const pages=Number(document.total_pages||0);
    const menuId='lexiaNavMenu'+(state.offset+index+1);
    return '<div class="result-card card lexia-nav-file-card" data-nav-path="'+path+'">'+
      '<div class="result-rank">'+(state.offset+index+1)+'</div>'+
      '<div class="result-body">'+
        '<button type="button" class="result-title lexia-nav-file-title search-open-file" data-path="'+path+'" data-nav-path="'+path+'" title="Abrir · '+esc(document.document_path||'')+'">'+
          esc(document.document_name||'Documento')+'</button>'+
        '<div class="result-meta">'+esc(extension)+' · '+esc(size(document.size))+
          (pages?' · '+number(pages)+' pág.':'')+' · '+esc(date(document.updated_at))+'</div>'+
      '</div>'+
      '<button type="button" class="lexia-nav-file-menu-trigger" data-nav-menu="'+menuId+
        '" aria-controls="'+menuId+'" aria-haspopup="menu" aria-expanded="false" title="Opciones del archivo">⋯</button>'+
      '<div id="'+menuId+'" class="result-actions" role="menu" aria-label="Opciones del archivo">'+
        '<button type="button" role="menuitem" class="search-file-info" data-path="'+path+'">Detalles</button>'+
        '<button type="button" role="menuitem" class="search-delete-file" data-path="'+path+
          '" title="Eliminar el archivo y sus derivados">Eliminar</button>'+
      '</div>'+
    '</div>';
  }

  function closeFileMenus(exceptTrigger){
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-menu-trigger').forEach(trigger=>{
      if(trigger===exceptTrigger)return;
      trigger.setAttribute('aria-expanded','false');
      const menu=document.getElementById(trigger.dataset.navMenu||'');
      menu?.classList.remove('actions-open');
    });
  }

  async function loadDocuments(append){
    const host=$('lexiaNavigatorFiles');
    const count=$('lexiaNavigatorCount');
    const more=$('lexiaNavigatorMore');
    if(!host)return;
    const request=++state.listRequest;
    if(!append){
      state.offset=0;
      state.documents.clear();
      host.innerHTML='<div class="lexia-nav-tree-status">Cargando documentos…</div>';
      if(more)more.style.display='none';
    }else if(more){
      more.disabled=true;
      more.textContent='Cargando…';
    }
    try{
      const data=await post('/api/navigator-documents',{
        query:state.query,selections:selectedFoldersPayload(),
        include_subfolders:true,sort:state.sort,limit:200,offset:state.offset
      });
      if(request!==state.listRequest)return;
      const items=data.items||[];
      state.total=Number(data.total||0);
      items.forEach(item=>state.documents.set(item.document_path||'',item));
      if(!append)host.innerHTML='';
      if(!state.total){
        host.innerHTML='<div class="lexia-nav-empty">'+
          (state.query?'No hay archivos cuyo nombre coincida con “'+esc(state.query)+
          '” en esta ubicación.':'Esta ubicación no contiene documentos indexados.')+'</div>';
      }else{
        host.insertAdjacentHTML('beforeend',items.map(fileCard).join(''));
      }
      state.offset+=items.length;
      if(count){
        const suffix=state.query?' · filtro: “'+state.query+'”':'';
        const scope=state.selections.size?(' · alcance: '+number(state.selections.size)+' carpeta'+(state.selections.size===1?'':'s')):' · alcance: toda la biblioteca';
        count.textContent=number(state.total)+' documento'+(state.total===1?'':'s')+suffix+scope;
      }
      if(more){
        more.style.display=data.has_more?'block':'none';
        more.disabled=false;
        more.textContent='Cargar más';
      }
    }catch(error){
      if(request!==state.listRequest)return;
      if(!append)host.innerHTML='<div class="lexia-nav-error"><b>No se pudieron cargar los documentos.</b><br>'+
        esc(error.message||error)+'</div>';
      if(count)count.textContent='Listado no disponible';
      if(more){more.style.display='none';more.disabled=false;more.textContent='Cargar más';}
    }
  }

  function previewMarkup(document){
    const path=encodeURIComponent(document.path||'');
    const pages=Number(document.total_pages||0);
    const pageStart=Number(document.page_start||0);
    const pageEnd=Number(document.page_end||0);
    const pageLabel=pageStart?('Pág. '+number(pageStart)+
      (pageEnd&&pageEnd!==pageStart?'–'+number(pageEnd):'')):'Sin página informada';
    const text=document.text||'LexIA todavía no dispone de texto indexado para este archivo.';
    return '<div class="result-card lexia-nav-preview-document">'+
      '<div class="result-title">'+esc(document.name||'Documento')+'</div>'+
      '<div class="lexia-nav-preview-meta">'+
        '<span>'+esc(document.category||'Documento')+'</span>'+
        '<span>'+esc(String(document.extension||'').replace(/^\./,'').toUpperCase()||'DOC')+'</span>'+
        (pages?'<span>'+number(pages)+' pág.</span>':'')+
        '<span>'+number(document.fragment_count||0)+' fragmentos</span>'+
        '<span>'+esc(pageLabel)+'</span>'+
      '</div>'+
      '<div class="lexia-nav-preview-text">'+esc(text)+'</div>'+
      '<div class="lexia-nav-preview-path">'+esc(document.path||'')+'</div>'+
      '<div class="lexia-nav-preview-actions">'+
        '<button type="button" class="lexia-nav-quick" data-nav-quick="'+path+'">Vista rápida</button>'+
        '<button type="button" class="search-file-info" data-path="'+path+'">Detalles</button>'+
        '<button type="button" class="search-delete-file" data-path="'+path+'">Eliminar</button>'+
      '</div>'+
    '</div>';
  }

  async function selectDocument(path){
    path=String(path||'');
    if(!path)return;
    if(path===state.selectedPath&&state.selectedDocument)return;
    state.selectedPath=path;
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card').forEach(card=>{
      card.classList.toggle('selected',decodePath(card.dataset.navPath)===path);
    });
    const host=$('lexiaNavigatorPreview');
    if(host)host.innerHTML='<div class="lexia-nav-tree-status">Leyendo el primer fragmento…</div>';
    const request=++state.previewRequest;
    try{
      const data=await post('/api/navigator-preview',{path:path});
      if(request!==state.previewRequest||state.selectedPath!==path)return;
      state.selectedDocument=data.document||null;
      if(host)host.innerHTML=previewMarkup(data.document||{path:path});
    }catch(error){
      if(request!==state.previewRequest)return;
      if(host)host.innerHTML='<div class="lexia-nav-error"><b>No se pudo generar la vista previa.</b><br>'+
        esc(error.message||error)+'</div>';
    }
  }

  async function quickOpen(path){
    path=String(path||'');
    if(!path||typeof window.lexiaQuickViewerOpen!=='function')return;
    const document=state.selectedDocument&&state.selectedDocument.path===path?
      state.selectedDocument:null;
    const snippet=String(document?.text||'').replace(/\s+/g,' ').trim().slice(0,700);
    let page=Number(document?.page_start||0);
    const extension=(path.toLowerCase().match(/(\.[^.\\/]+)$/)||[])[1]||'';
    if(['.doc','.docx','.rtf','.odt','.html','.htm'].includes(extension)&&snippet){
      try{
        const response=await fetch('/api/office-preview-page?path='+encodeURIComponent(path)+
          '&snippet='+encodeURIComponent(snippet),{cache:'no-store'});
        const data=await response.json();
        if(response.ok&&data.ok&&Number(data.page)>0)page=Number(data.page);
      }catch(_){}
    }
    window.lexiaQuickViewerOpen(path,page,snippet);
  }

  function activate(){
    state.active=true;
    const grid=document.querySelector('#searchpage .search-grid');
    const view=$('lexiaNavigatorView');
    const input=document.querySelector('#searchpage .search-large input');
    if(grid)grid.style.display='none';
    if(view)view.hidden=false;
    if(input)input.value=state.query;
    $('searchRecentHistory')?.classList.remove('open');
    if(!state.initialized){
      state.initialized=true;
      buildTree();
    }
  }
  function deactivate(){
    state.active=false;
    closeFileMenus();
    const grid=document.querySelector('#searchpage .search-grid');
    if(grid)grid.style.display='';
    if($('lexiaNavigatorView'))$('lexiaNavigatorView').hidden=true;
  }
  function search(query){
    state.query=String(query||'').trim();
    state.offset=0;
    loadDocuments(false);
  }

  document.addEventListener('click',event=>{
    const menuTrigger=event.target.closest?.('#lexiaNavigatorFiles .lexia-nav-file-menu-trigger');
    if(menuTrigger){
      event.preventDefault();
      event.stopPropagation();
      const willOpen=menuTrigger.getAttribute('aria-expanded')!=='true';
      closeFileMenus(menuTrigger);
      menuTrigger.setAttribute('aria-expanded',willOpen?'true':'false');
      document.getElementById(menuTrigger.dataset.navMenu||'')?.classList.toggle('actions-open',willOpen);
      return;
    }
    const menuAction=event.target.closest?.('#lexiaNavigatorFiles .result-actions button');
    if(menuAction)closeFileMenus();
    else if(!event.target.closest?.('#lexiaNavigatorFiles .result-actions'))closeFileMenus();
    const quick=event.target.closest?.('[data-nav-quick]');
    if(quick){
      event.preventDefault();
      event.stopPropagation();
      quickOpen(decodePath(quick.dataset.navQuick));
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape')closeFileMenus();
  });
  document.addEventListener('pointerover',event=>{
    const card=event.target.closest?.('#lexiaNavigatorFiles .lexia-nav-file-card');
    if(!card||(event.relatedTarget&&card.contains(event.relatedTarget)))return;
    const previewPanel=document.querySelector('#lexiaNavigatorView .lexia-nav-preview-panel');
    if(previewPanel&&getComputedStyle(previewPanel).display==='none')return;
    if(state.previewTimer)clearTimeout(state.previewTimer);
    const path=decodePath(card.dataset.navPath);
    state.previewTimer=setTimeout(()=>{
      state.previewTimer=null;
      selectDocument(path);
    },260);
  });
  document.addEventListener('pointerout',event=>{
    const card=event.target.closest?.('#lexiaNavigatorFiles .lexia-nav-file-card');
    if(!card||(event.relatedTarget&&card.contains(event.relatedTarget)))return;
    if(state.previewTimer){
      clearTimeout(state.previewTimer);
      state.previewTimer=null;
    }
  });
  $('lexiaNavigatorMore')?.addEventListener('click',()=>loadDocuments(true));
  $('lexiaNavigatorImport')?.addEventListener('click',()=>{
    try{importDestination();$('lexiaNavigatorImportInput')?.click();}
    catch(error){importStatus(error.message,'error');}
  });
  $('lexiaNavigatorImportInput')?.addEventListener('change',function(){importFiles(this.files);});
  const filesHost=$('lexiaNavigatorFiles');
  filesHost?.addEventListener('dragenter',event=>{event.preventDefault();filesHost.classList.add('lexia-nav-drop-ready');});
  filesHost?.addEventListener('dragover',event=>{event.preventDefault();if(event.dataTransfer)event.dataTransfer.dropEffect='copy';filesHost.classList.add('lexia-nav-drop-ready');});
  filesHost?.addEventListener('dragleave',event=>{if(!filesHost.contains(event.relatedTarget))filesHost.classList.remove('lexia-nav-drop-ready');});
  filesHost?.addEventListener('drop',event=>{
    event.preventDefault();filesHost.classList.remove('lexia-nav-drop-ready');
    importFiles(event.dataTransfer?.files);
  });
  $('lexiaNavigatorSort')?.addEventListener('change',function(){
    state.sort=this.value||'name_asc';
    state.offset=0;
    emptyPreview();
    loadDocuments(false);
  });
  $('lexiaNavigatorRefresh')?.addEventListener('click',function(){
    this.disabled=true;
    buildTree().finally(()=>{this.disabled=false;});
  });
  window.addEventListener('lexia:document-deleted',event=>{
    const path=String(event.detail?.path||'');
    if(path&&state.selectedPath===path)emptyPreview();
    if(state.initialized)loadDocuments(false);
  });
  window.lexiaNavigator330i={activate,deactivate,search,refresh:buildTree,importFiles};
})();
