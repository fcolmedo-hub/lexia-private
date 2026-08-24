/* LEXIA UI2 3.3.0i INVESTIGATION AND DOCUMENT STUDY NAVIGATOR */
(function(){
  const state={
    active:false,initialized:false,selections:new Map(),
    query:'',sort:'name_asc',offset:0,total:0,selectedPath:'',selectedDocument:null,
    listRequest:0,previewRequest:0,previewTimer:null,documents:new Map(),nodes:new Map(),
    selectedFiles:new Set(),operationTimer:null,folderMenuTimer:null,statusTimer:null,browsed:null
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
    if(state.statusTimer){clearTimeout(state.statusTimer);state.statusTimer=null;}
    host.textContent=String(message||'');
    host.className='lexia-nav-import-status show '+type;
    // Success and error notices must not block the navigator indefinitely.
    if(type!=='info'){
      state.statusTimer=setTimeout(()=>{
        host.textContent='';
        host.className='lexia-nav-import-status';
        state.statusTimer=null;
      },6000);
    }
  }

  function selectedFilePaths(){return Array.from(state.selectedFiles);}
  function visibleFilePaths(){
    return Array.from(document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card'),card=>decodePath(card.dataset.navPath)).filter(Boolean);
  }
  function refreshFileSelection(){
    document.querySelectorAll('#lexiaNavigatorFiles .lexia-nav-file-card').forEach(card=>{
      card.classList.toggle('multi-selected',state.selectedFiles.has(decodePath(card.dataset.navPath)));
    });
    const count=state.selectedFiles.size;
    const selectAll=$('lexiaNavigatorSelectAll');
    if(selectAll){
      selectAll.textContent=count?'Deseleccionar ('+number(count)+')':'Seleccionar todo';
      selectAll.title=count?'Quitar la selección de los archivos':'Seleccionar todos los archivos visibles';
    }
    const button=$('lexiaNavigatorFileAction');
    if(button){
      button.hidden=false;
      button.disabled=!count;
      button.textContent='Acciones';
      button.title=count?'Acciones para '+number(count)+' archivo'+(count===1?'':'s')+' seleccionado'+(count===1?'':'s'):'Seleccioná archivos para habilitar las acciones';
    }
  }
  function clearFileSelection(){state.selectedFiles.clear();refreshFileSelection();}

  async function waitNavigatorOperation(jobId){
    if(state.operationTimer){clearTimeout(state.operationTimer);state.operationTimer=null;}
    const check=async()=>{
      const data=await get('/api/navigator-operation-status');
      const current=data.state||{};
      if(current.job_id!==jobId)throw new Error('La operación del navegador fue reemplazada.');
      const total=Number(current.total||0),processed=Number(current.processed||0);
      const progress=total?(' '+number(processed)+'/'+number(total)) : '';
      importStatus((current.status||'Procesando…')+progress,'info');
      if(current.phase==='completed')return current.result||{};
      if(current.phase==='error')throw new Error(current.error||current.status||'La operación no se pudo completar.');
      await new Promise(resolve=>{state.operationTimer=setTimeout(resolve,350);});
      return check();
    };
    return check();
  }
  async function runNavigatorOperation(operation,doneMessage,beforeRefresh,options={}){
    const data=await post('/api/navigator-operation',operation);
    const result=await waitNavigatorOperation(data.job_id||data.state?.job_id);
    if(typeof beforeRefresh==='function')beforeRefresh(result);
    importStatus(doneMessage||'Operación completada.','success');
    clearFileSelection();
    emptyPreview();
    if(!options.preserveTree)await buildTree();
    return result;
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
    if(state.browsed){
      const labels=state.browsed.labels||['Biblioteca'];
      breadcrumb.textContent=labels.join('  ›  ');
      breadcrumb.title=labels.join(' › ');
      return;
    }
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

  function browseTreeNode(node,labels,libraryRoot=false){
    state.browsed={
      category:libraryRoot?'':String(node.category||''),
      folder:libraryRoot?'':String(node.folder||''),
      labels:labels&&labels.length?labels:['Biblioteca'],
      libraryRoot:Boolean(libraryRoot)
    };
    updateSelectionBreadcrumb();
    state.offset=0;
    emptyPreview();
    loadDocuments(false);
  }

  function toggleTreeNode(node,labels,libraryRoot=false){
    state.browsed=null;
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
      }
    }
    refreshTreeSelection();
    updateSelectionBreadcrumb();
    state.offset=0;
    emptyPreview();
    loadDocuments(false);
  }

  function closeFolderMenu(){
    if(state.folderMenuTimer){clearTimeout(state.folderMenuTimer);state.folderMenuTimer=null;}
    document.getElementById('lexiaNavigatorFolderMenu')?.remove();
  }
  function appendCreatedFolder(parent,folder,name){
    const parentKey=selectionKey(parent.category||'',parent.folder||'');
    const parentRow=document.querySelector('#lexiaNavigatorTree .lexia-nav-tree-row[data-selection-key="'+CSS.escape(parentKey)+'"]');
    const container=parentRow?.nextElementSibling;
    const parentState=state.nodes.get(parentKey);
    if(!container||!parentState)return false;
    const childKey=selectionKey(parent.category||'',folder);
    if(state.nodes.has(childKey))return true;
    const depth=Number(parentRow.style.getPropertyValue('--depth')||0)+1;
    const labels=(parentState.labels||['Biblioteca',String(parent.category||'')]).concat([String(name||'Carpeta').trim()]);
    const child={kind:'folder',name:String(name||'Carpeta').trim(),category:parent.category||'',folder,count:0,has_children:false,parent:parent.folder||''};
    container.appendChild(makeTreeRow(child,depth,labels));
    container.hidden=false;
    const arrow=parentRow.querySelector('.lexia-nav-arrow');
    if(arrow){arrow.disabled=false;arrow.textContent='▾';}
    return true;
  }

  async function createFolderAt(node){
    const name=window.prompt('Nombre de la nueva carpeta:');
    if(name===null)return;
    try{
      const category=String(node.category||'').trim();
      let createdFolder='';
      await runNavigatorOperation({operation:'create_folder',category,parent:node.folder||'',name},'Carpeta creada.',result=>{
        const folder=String(result?.created_folder||'').trim();
        if(!folder)return;
        // La nueva carpeta sustituye completamente cualquier selección anterior.
        state.selections.clear();
        state.selections.set(selectionKey(category,folder),{
          category,folder,labels:['Biblioteca',category,String(name).trim()]
        });
        createdFolder=folder;
      },{preserveTree:true});
      if(!createdFolder)return;
      // Se incorpora el nodo creado sin reconstruir el árbol ni promover al padre.
      if(!appendCreatedFolder(node,createdFolder,name))await buildTree();
      refreshTreeSelection();
      updateSelectionBreadcrumb();
      state.offset=0;
      emptyPreview();
      await loadDocuments(false);
    }catch(error){importStatus(error.message||String(error),'error');}
  }
  async function deleteFolderAt(node){
    const name=String(node.name||'esta carpeta');
    if(!window.confirm('¿Eliminar la carpeta “'+name+'”? Sólo se permite si no contiene archivos.'))return;
    try{
      await runNavigatorOperation({operation:'delete_folder',category:node.category||'',folder:node.folder||''},'Carpeta eliminada.');
    }catch(error){importStatus(error.message||String(error),'error');}
  }
  function showFolderMenu(event,node){
    closeFolderMenu();
    const menu=document.createElement('div');
    menu.id='lexiaNavigatorFolderMenu';menu.className='lexia-nav-folder-menu';
    const create=document.createElement('button');create.type='button';create.textContent='Nueva carpeta aquí';
    create.addEventListener('click',()=>{closeFolderMenu();createFolderAt(node);});menu.appendChild(create);
    if(node.folder){
      const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='Eliminar carpeta';
      remove.addEventListener('click',()=>{closeFolderMenu();deleteFolderAt(node);});menu.appendChild(remove);
      const note=document.createElement('small');note.textContent='Para moverla, arrastrala sobre la carpeta de destino.';menu.appendChild(note);
    }
    menu.style.left=Math.min(event.clientX,window.innerWidth-190)+'px';
    menu.style.top=Math.min(event.clientY,window.innerHeight-110)+'px';
    document.body.appendChild(menu);
    const scheduleClose=()=>{
      if(state.folderMenuTimer)clearTimeout(state.folderMenuTimer);
      state.folderMenuTimer=setTimeout(closeFolderMenu,700);
    };
    menu.addEventListener('pointerenter',()=>{if(state.folderMenuTimer){clearTimeout(state.folderMenuTimer);state.folderMenuTimer=null;}});
    menu.addEventListener('pointerleave',scheduleClose);
    state.folderMenuTimer=setTimeout(closeFolderMenu,6000);
  }
  async function moveFolderTo(source,target){
    if(!source?.folder||!target)return;
    try{
      await runNavigatorOperation({
        operation:'move_folder',source_category:source.category||'',source_folder:source.folder,
        destination_category:target.category||'',destination_folder:target.folder||''
      },'Carpeta movida y referencias de LexIA actualizadas.');
    }catch(error){importStatus(error.message||String(error),'error');}
  }
  async function moveSelectedFilesTo(target){
    const paths=selectedFilePaths();
    if(!paths.length||!target)return;
    try{
      await runNavigatorOperation({
        operation:'move_files',paths,destination_category:target.category||'',destination_folder:target.folder||''
      },number(paths.length)+' archivo'+(paths.length===1?' movido':'s movidos')+' y relocalizados por LexIA.');
    }catch(error){importStatus(error.message||String(error),'error');}
  }
  async function deleteSelectedFiles(){
    const paths=selectedFilePaths();
    if(!paths.length)return;
    if(!window.confirm('¿Eliminar definitivamente '+number(paths.length)+' archivo'+(paths.length===1?'':'s')+' de LexIA? Esta acción también elimina sus índices y referencias.'))return;
    try{await runNavigatorOperation({operation:'delete_files',paths},number(paths.length)+' archivo'+(paths.length===1?' eliminado':'s eliminados')+' de LexIA.');}
    catch(error){importStatus(error.message||String(error),'error');}
  }
  function showFileActionMenu(anchor){
    closeFolderMenu();
    const menu=document.createElement('div');menu.id='lexiaNavigatorFolderMenu';menu.className='lexia-nav-folder-menu';
    const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='Eliminar archivos seleccionados';
    remove.addEventListener('click',()=>{closeFolderMenu();deleteSelectedFiles();});menu.appendChild(remove);
    const note=document.createElement('small');note.textContent='Para mover archivos, arrastralos sobre la carpeta de destino.';menu.appendChild(note);
    const rect=anchor.getBoundingClientRect();menu.style.left=Math.max(8,rect.right-180)+'px';menu.style.top=(rect.bottom+4)+'px';document.body.appendChild(menu);
  }

  function makeTreeRow(node,depth,labels){
    const wrap=document.createElement('div');
    const row=document.createElement('div');
    row.className='lexia-nav-tree-row';
    row.style.setProperty('--depth',String(depth));
    row.dataset.category=node.category||'';
    row.dataset.folder=node.folder||'';
    row.dataset.selectionKey=selectionKey(node.category||'',node.folder||'');
    row.draggable=Boolean(node.folder);
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

    // El nombre identifica la carpeta; la selección pertenece exclusivamente al checkbox.
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

    const select=event=>{
      event.preventDefault();
      event.stopPropagation();
      toggleTreeNode(node,labels,false);
    };
    selector.addEventListener('click',select);
    const browseAndToggle=async event=>{
      event.preventDefault();
      event.stopImmediatePropagation();
      browseTreeNode(node,labels,false);
      if(arrow.disabled)return;
      if(children.dataset.loaded==='1'){
        children.hidden=!children.hidden;
        arrow.textContent=children.hidden?'▸':'▾';
        return;
      }
      arrow.disabled=true;
      arrow.textContent='…';
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
        arrow.textContent=childNodes.length?'▾':'';
        arrow.disabled=!childNodes.length;
      }catch(error){
        arrow.textContent='!';
        arrow.title=error.message||String(error);
        arrow.disabled=false;
      }
    };
    name.addEventListener('click',browseAndToggle);
    row.addEventListener('contextmenu',event=>{event.preventDefault();event.stopPropagation();showFolderMenu(event,node);});
    row.addEventListener('dragstart',event=>{
      if(!node.folder)return;
      event.dataTransfer?.setData('application/x-lexia-folder',JSON.stringify({category:node.category||'',folder:node.folder||'',name:node.name||''}));
      if(event.dataTransfer)event.dataTransfer.effectAllowed='move';
    });
    row.addEventListener('dragover',event=>{
      const types=Array.from(event.dataTransfer?.types||[]);
      if(!(node.folder||node.category)||(!types.includes('application/x-lexia-folder')&&!types.includes('application/x-lexia-files')))return;
      event.preventDefault();row.classList.add('lexia-nav-drop-target');
      if(event.dataTransfer)event.dataTransfer.dropEffect='move';
    });
    row.addEventListener('dragleave',()=>row.classList.remove('lexia-nav-drop-target'));
    row.addEventListener('drop',event=>{
      row.classList.remove('lexia-nav-drop-target');
      if(!(node.folder||node.category))return;
      const transfer=event.dataTransfer;
      const rawFolder=transfer?.getData('application/x-lexia-folder');
      const rawFiles=transfer?.getData('application/x-lexia-files');
      if(!rawFolder&&!rawFiles)return;
      event.preventDefault();event.stopPropagation();
      if(rawFolder){try{moveFolderTo(JSON.parse(rawFolder),node);}catch(_){}}
      else if(rawFiles){try{const paths=JSON.parse(rawFiles);state.selectedFiles=new Set(paths||[]);moveSelectedFilesTo(node);}catch(_){}}
    });

    arrow.addEventListener('click',browseAndToggle);

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
    // El nombre identifica la biblioteca; la selección pertenece exclusivamente al checkbox.
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
    const select=event=>{
      event.preventDefault();
      event.stopPropagation();
      toggleTreeNode({category:'',folder:''},['Biblioteca'],true);
    };
    const browseAndToggle=event=>{
      event.preventDefault();
      event.stopImmediatePropagation();
      browseTreeNode({category:'',folder:''},['Biblioteca'],true);
      children.hidden=!children.hidden;
      arrow.textContent=children.hidden?'▸':'▾';
    };
    selector.addEventListener('click',select);
    name.addEventListener('click',browseAndToggle);
    arrow.addEventListener('click',browseAndToggle);
    row.append(arrow,selector,name,count);
    wrap.append(row,children);
    return {wrap,children};
  }

  async function buildTree(){
    const host=$('lexiaNavigatorTree');
    if(!host)return;
    // Se descartan nodos previos: evita que una carpeta madre conserve estado visual antiguo.
    state.nodes.clear();
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
    const rawPath=String(document.document_path||'');
    const extension=String(document.extension||'').replace(/^\./,'').toUpperCase()||'DOC';
    const pages=Number(document.total_pages||0);
    const menuId='lexiaNavMenu'+(state.offset+index+1);
    return '<div class="result-card card lexia-nav-file-card'+(state.selectedFiles.has(rawPath)?' multi-selected':'')+'" draggable="true" data-nav-path="'+path+'">'+
      '<div class="result-rank">'+(state.offset+index+1)+'</div>'+
      '<div class="result-body">'+
        '<button type="button" class="result-title lexia-nav-file-title lexia-nav-open-file" data-path="'+path+'" data-nav-path="'+path+'" title="Abrir · '+esc(document.document_path||'')+'">'+
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
      const scope=state.browsed;
      const data=await post('/api/navigator-documents',{
        query:state.query,selections:scope?.libraryRoot?[]:(scope?[{category:scope.category,folder:scope.folder}]:selectedFoldersPayload()),
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
      refreshFileSelection();
      state.offset+=items.length;
      if(count){
        const suffix=state.query?' · filtro: “'+state.query+'”':'';
        const scopeLabel=scope?(' · ubicación: '+(scope.labels||['Biblioteca']).join(' › ')):(state.selections.size?(' · alcance: '+number(state.selections.size)+' carpeta'+(state.selections.size===1?'':'s')):' · alcance: toda la biblioteca');
        count.textContent=number(state.total)+' documento'+(state.total===1?'':'s')+suffix+scopeLabel;
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
    const missingText=!String(document.text||'').trim();
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
        (missingText?'<button type="button" class="lexia-nav-quick" data-nav-reprocess="'+path+'">Reprocesar e indexar</button>':'')+
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
    if(['.doc','.docx','.rtf','.odt'].includes(extension)&&snippet){
      try{
        const response=await fetch('/api/office-preview-page?path='+encodeURIComponent(path)+
          '&snippet='+encodeURIComponent(snippet),{cache:'no-store'});
        const data=await response.json();
        if(response.ok&&data.ok&&Number(data.page)>0)page=Number(data.page);
      }catch(_){}
    }
    window.lexiaQuickViewerOpen(path,page,snippet);
  }

  async function reprocessNavigatorFile(path,button){
    path=String(path||'');
    if(!path)return;
    const old=button?.textContent||'Reprocesar e indexar';
    if(button){button.disabled=true;button.textContent='Procesando…';}
    try{
      await runNavigatorOperation(
        {operation:'reprocess_file',path:path},
        'Documento reprocesado e indexado.'
      );
    }catch(error){
      importStatus(error.message||String(error),'error');
    }finally{
      if(button){button.disabled=false;button.textContent=old;}
    }
  }

  async function openNavigatorFile(path,button){
    path=String(path||'');
    if(!path)return;
    const old=button?.textContent||'';
    if(button){button.disabled=true;button.textContent='Abriendo…';}
    try{
      const response=await fetch('/api/open-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
      const data=await response.json().catch(()=>({}));
      if(!response.ok||!data.ok)throw new Error(data.error||('HTTP '+response.status));
    }catch(error){importStatus(error.message||String(error),'error');}
    finally{if(button){button.disabled=false;button.textContent=old;}}
  }

  function activate(){
    state.active=true;
    const searchPage=$('searchpage');
    const grid=document.querySelector('#searchpage .search-grid');
    const view=$('lexiaNavigatorView');
    // La clase prevalece sobre las reglas responsive de Buscar: ningún
    // resultado puede volver a aparecer al achicar la ventana.
    searchPage?.classList.add('navigator-active');
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
    $('searchpage')?.classList.remove('navigator-active');
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
    if(!event.target.closest?.('#lexiaNavigatorFolderMenu')&&!event.target.closest?.('.lexia-nav-file-action'))closeFolderMenu();
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
    const reprocess=event.target.closest?.('[data-nav-reprocess]');
    if(reprocess){
      event.preventDefault();
      event.stopPropagation();
      reprocessNavigatorFile(
        decodePath(reprocess.dataset.navReprocess),
        reprocess
      );
      return;
    }
    const quick=event.target.closest?.('[data-nav-quick]');
    if(quick){
      event.preventDefault();
      event.stopPropagation();
      quickOpen(decodePath(quick.dataset.navQuick));
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){closeFileMenus();closeFolderMenu();}
    if((event.key==='Delete'||event.key==='Backspace')&&state.active&&state.selectedFiles.size&&!event.target?.matches?.('input,textarea,select')){
      event.preventDefault();deleteSelectedFiles();
    }
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
  $('lexiaNavigatorSelectAll')?.addEventListener('click',function(){
    if(state.selectedFiles.size){clearFileSelection();return;}
    state.selectedFiles=new Set(visibleFilePaths());
    refreshFileSelection();
  });
  $('lexiaNavigatorFileAction')?.addEventListener('click',function(event){event.preventDefault();event.stopPropagation();showFileActionMenu(this);});
  const filesHost=$('lexiaNavigatorFiles');
  filesHost?.addEventListener('click',event=>{
    const card=event.target.closest('.lexia-nav-file-card');
    if(!card)return;
    if(event.ctrlKey||event.metaKey){
      if(event.target.closest('.lexia-nav-file-menu-trigger,.result-actions,input,a'))return;
      event.preventDefault();event.stopPropagation();
      const path=decodePath(card.dataset.navPath);
      if(state.selectedFiles.has(path))state.selectedFiles.delete(path);
      else state.selectedFiles.add(path);
      refreshFileSelection();
      return;
    }
    const open=event.target.closest('.lexia-nav-open-file');
    if(open){event.preventDefault();event.stopPropagation();openNavigatorFile(decodePath(open.dataset.navPath||open.dataset.path),open);}
  });
  filesHost?.addEventListener('dragstart',event=>{
    const card=event.target.closest('.lexia-nav-file-card');
    if(!card)return;
    const path=decodePath(card.dataset.navPath);
    if(!state.selectedFiles.has(path)){state.selectedFiles=new Set([path]);refreshFileSelection();}
    event.dataTransfer?.setData('application/x-lexia-files',JSON.stringify(selectedFilePaths()));
    if(event.dataTransfer)event.dataTransfer.effectAllowed='move';
  });
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
