/* LexIA Mac/Windows — data panel for the native Maintenance duplicates tab. */
(function(){
  'use strict';
  if(window.__lexiaWindowsMaintenanceDuplicatesV2)return;
  window.__lexiaWindowsMaintenanceDuplicatesV2=true;

  const SIDECAR='http://127.0.0.1:8516';
  const PANEL_ID='lexiaMaintenanceDuplicatesPanel';
  const STYLE_ID='lexiaMaintenanceDuplicatesStyleV2';
  let duplicates=[];
  let loading=false;
  let loaded=false;
  let deleting=false;
  let loadError='';

  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const shortName=value=>{const parts=String(value||'').replace(/\\/g,'/').split('/').filter(Boolean);return parts[parts.length-1]||'';};
  const bytes=value=>{
    const n=Number(value||0);if(!n)return '—';
    if(n<1024)return n+' B';if(n<1024*1024)return (n/1024).toFixed(1)+' KB';
    return (n/(1024*1024)).toFixed(1)+' MB';
  };

  function installStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      html body #maintenance .maint-content[data-maint-view="duplicates"]{overflow:hidden}
      html body #maintenance #${PANEL_ID}{display:flex;flex-direction:column;height:100%;min-height:0;box-sizing:border-box;margin:0;padding:12px;overflow:hidden}
      #${PANEL_ID} .lexia-dup-head{flex:none;margin-bottom:8px}
      #${PANEL_ID} .lexia-dup-head p{margin:6px 0;color:#66708f;font-size:12px;line-height:1.35}
      #${PANEL_ID} .lexia-dup-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex:none;margin:2px 0 6px}
      #${PANEL_ID} .lexia-dup-count{font-size:12px;color:#66708f}
      #${PANEL_ID} .lexia-dup-list{display:block}
      html body #maintenance #${PANEL_ID} .lexia-dup-row{grid-template-columns:minmax(0,1fr) auto;align-items:center}
      html body #maintenance #${PANEL_ID} .lexia-dup-info{grid-column:1}
      html body #maintenance #${PANEL_ID} .lexia-dup-actions{grid-column:2;grid-row:1}
      #${PANEL_ID} .lexia-dup-info small{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
      #${PANEL_ID} .lexia-dup-file-link{color:#4338cb;text-decoration:underline;text-underline-offset:2px;font:inherit;font-weight:750}
      #${PANEL_ID} .lexia-dup-file-link:hover,#${PANEL_ID} .lexia-dup-file-link:focus-visible{color:#2e249f}
      #${PANEL_ID} .lexia-dup-original-link{color:#168451}
      #${PANEL_ID} .lexia-dup-original-link:hover,#${PANEL_ID} .lexia-dup-original-link:focus-visible{color:#0d6840}
      #${PANEL_ID} .lexia-dup-actions .lexia-dup-open-copy{color:#4338cb;border-color:#ccc5ff;background:#f3f1ff}
      #${PANEL_ID} .lexia-dup-actions .lexia-dup-open-copy:hover{background:#e8e4ff}
      #${PANEL_ID} .lexia-dup-actions .lexia-dup-open-original{color:#137246;border-color:#b8dec9;background:#eaf8f0}
      #${PANEL_ID} .lexia-dup-actions .lexia-dup-open-original:hover{background:#d9f1e4}
      #${PANEL_ID} .lexia-dup-empty{padding:16px 0;color:#66708f;font-size:12px}
      @media(max-width:840px){
        html body #maintenance #${PANEL_ID} .lexia-dup-row{grid-template-columns:minmax(0,1fr)}
        html body #maintenance #${PANEL_ID} .lexia-dup-actions{grid-column:1;grid-row:auto;justify-content:flex-start;flex-wrap:wrap}
      }
    `;
    document.head.appendChild(style);
  }

  async function sidecar(path,options){
    const response=await fetch(SIDECAR+path,Object.assign({cache:'no-store'},options||{}));
    let data={};try{data=await response.json();}catch(_){}
    if(!response.ok||data.ok===false)throw new Error(data.error||('HTTP '+response.status));
    return data;
  }

  function ensure(){
    installStyle();
    return Boolean(document.getElementById(PANEL_ID));
  }

  function render(){
    if(!ensure())return;
    const panel=document.getElementById(PANEL_ID);if(!panel)return;
    const scroll=panel.querySelector('.lexia-dup-list')?.scrollTop||0;
    const rows=duplicates.map((item,index)=>`
      <div class="maint-ocr-queue-item lexia-dup-row">
        <div class="maint-ocr-item-info lexia-dup-info">
          <strong><a class="lexia-dup-file-link" href="/api/file-preview?path=${esc(encodeURIComponent(item.path||''))}" target="_blank" rel="noopener" title="Abrir duplicado: ${esc(item.path)}" data-dup-open="${index}">${esc(item.name||shortName(item.path)||'Documento')}</a></strong>
          <span title="${esc(item.path)}">${esc(item.path)}</span>
          <small>${esc(item.category||'Sin categoría')} · ${esc(bytes(item.size))}</small>
          <span title="${esc(item.duplicate_of||'')}">Original: ${item.duplicate_of?`<a class="lexia-dup-file-link lexia-dup-original-link" href="/api/file-preview?path=${esc(encodeURIComponent(item.duplicate_of))}" target="_blank" rel="noopener" data-dup-open-original="${index}">${esc(item.original_name||shortName(item.duplicate_of)||'Documento original')}</a>`:esc(item.original_name||'Documento original')} · ${esc(item.duplicate_of||'')}</span>
        </div>
        <div class="maint-ocr-item-actions lexia-dup-actions">
          <button type="button" class="maint-btn lexia-dup-open-copy" data-dup-open="${index}">Abrir duplicado</button>
          <button type="button" class="maint-btn lexia-dup-open-original" data-dup-open-original="${index}" ${item.duplicate_of?'':'disabled'}>Abrir original</button>
          <button type="button" class="maint-btn danger" data-dup-delete="${index}" ${loading||deleting?'disabled':''}>Eliminar de LexIA</button>
        </div>
      </div>`).join('');
    panel.innerHTML=`
      <div class="lexia-dup-head"><h3>Archivos duplicados</h3><p>LexIA no elimina nada automáticamente. Abrí el duplicado y el principal para compararlos antes de decidir.</p></div>
      <div class="maint-ocr-queue">
        <div class="lexia-dup-toolbar"><span class="lexia-dup-count">${loaded?duplicates.length.toLocaleString('es-AR')+' duplicado'+(duplicates.length===1?'':'s'):''}</span><button type="button" class="maint-btn secondary" data-dup-refresh ${loading||deleting?'disabled':''}>${loading?'Actualizando…':'Actualizar lista'}</button></div>
        ${loadError?'<p class="maint-toast-error" role="alert">'+esc(loadError)+'</p>':''}
        ${loading?'<p class="maint-note" role="status">Buscando duplicados en el catálogo…</p>':''}
        <div class="maint-ocr-items lexia-dup-list">${rows||(!loading&&!loadError?'<div class="lexia-dup-empty">No hay archivos marcados como duplicados.</div>':'')}</div>
      </div>`;
    panel.querySelector('.lexia-dup-list').scrollTop=scroll;

  }

  async function load(){
    if(loading||deleting)return;
    loading=true;loadError='';render();
    try{
      const data=await sidecar('/duplicates');
      duplicates=Array.isArray(data.duplicates)?data.duplicates:[];
    }catch(error){
      loadError='No se pudo actualizar la lista de duplicados: '+(error.message||String(error));
    }
    loading=false;loaded=true;render();
  }

  async function deleteDuplicate(index,button){
    if(loading||deleting)return;
    const item=duplicates[index];if(!item?.path)return;
    if(!confirm('¿Eliminar este archivo duplicado de LexIA?\n\n'+(item.name||shortName(item.path))+'\n'+item.path+'\n\nSe eliminará el archivo físico duplicado y sus datos en LexIA. El documento original se conservará.'))return;
    deleting=true;loadError='';
    const previous=button.textContent;button.disabled=true;button.textContent='Eliminando…';
    render();
    try{
      const data=await sidecar('/delete-duplicate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:item.path})});
      duplicates=Array.isArray(data.duplicates)?data.duplicates:[];
      render();
    }catch(error){
      alert('No se pudo eliminar el duplicado.\n\n'+(error.message||String(error)));
      button.disabled=false;button.textContent=previous;
    }
    finally{deleting=false;render();}
  }

  function openPath(path){
    if(!path)return;
    if(typeof window.lexiaQuickViewerOpen==='function')window.lexiaQuickViewerOpen(path,1,'');
    else window.open('/api/file-preview?path='+encodeURIComponent(path),'_blank','noopener');
  }

  function openDuplicate(index){const item=duplicates[index];if(item?.path)openPath(item.path);}
  function openOriginal(index){const item=duplicates[index];if(item?.duplicate_of)openPath(item.duplicate_of);}

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;if(!target)return;
    if(target.closest('[data-dup-refresh]')){load();return;}
    const remove=target.closest('[data-dup-delete]');if(remove){deleteDuplicate(Number(remove.dataset.dupDelete),remove);return;}
    const open=target.closest('[data-dup-open]');if(open){event.preventDefault();openDuplicate(Number(open.dataset.dupOpen));return;}
    const original=target.closest('[data-dup-open-original]');if(original){event.preventDefault();openOriginal(Number(original.dataset.dupOpenOriginal));return;}
  },true);
  function activate(){
    if(!ensure())return;
    if(!loaded&&!loading)load();else render();
  }
  window.lexiaMaintenanceDuplicates={load};
  window.addEventListener('lexia:maintenance-render',activate);
  activate();
})();
