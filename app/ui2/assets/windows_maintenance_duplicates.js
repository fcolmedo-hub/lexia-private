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
      #${PANEL_ID}{display:block;margin-top:14px}
      .lexia-dup-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
      .lexia-dup-head h3{margin:0 0 4px}.lexia-dup-head p{margin:0;color:#6d7691;font-size:11px}
      .lexia-dup-list{display:grid;gap:8px;max-height:65vh;overflow:auto;overscroll-behavior:contain}
      .lexia-dup-row{border:1px solid #e0e3ef;border-radius:10px;background:#fff;padding:10px 12px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center}
      .lexia-dup-row strong{display:block;color:#283253;font-size:12px;overflow-wrap:anywhere}
      .lexia-dup-row small{display:block;margin-top:3px;color:#727b96;font-size:11px;overflow-wrap:anywhere}
      .lexia-dup-origin{margin-top:6px;padding:6px 8px;border-radius:7px;background:#f5f4ff;color:#5146f6;font-size:9.5px}
      .lexia-dup-origin button{border:0;background:transparent;padding:0;color:#5146f6;font:inherit;font-weight:800;text-decoration:underline;cursor:pointer}
      .lexia-dup-origin button:hover{color:#352bc7}
      .lexia-dup-actions{display:flex;gap:6px;align-items:center}
      .lexia-dup-actions button{font:inherit;font-size:12px;padding:6px 8px;border-radius:6px;cursor:pointer}
      .lexia-dup-actions button:disabled{opacity:.58;cursor:wait}
      .lexia-dup-open{border:1px solid #cfcbea;background:#fff;color:#4036b4}
      .lexia-dup-delete{border:1px solid #9a3b8f;background:#9a3b8f;color:#fff}
      .lexia-dup-delete:hover{background:#7f2f76;border-color:#7f2f76}
      .lexia-dup-empty{padding:18px;border:1px dashed #ccd2e3;border-radius:10px;color:#6d7691;text-align:center;font-size:11px;background:#fafbfe}
      @media(max-width:760px){.lexia-dup-row{grid-template-columns:1fr}.lexia-dup-actions{justify-content:flex-end}}
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
    const rows=duplicates.map((item,index)=>`
      <div class="lexia-dup-row">
        <div>
          <strong>${esc(item.name||shortName(item.path)||'Documento')}</strong>
          <small>${esc(item.category||'Sin categoría')} · ${esc(bytes(item.size))}</small>
          <small title="${esc(item.path)}">${esc(item.path)}</small>
          <div class="lexia-dup-origin">Duplicado de: <button type="button" data-dup-open-original="${index}" title="Abrir documento principal">${esc(item.original_name||shortName(item.duplicate_of)||'Documento original')}</button><br>${esc(item.duplicate_of||'')}</div>
        </div>
        <div class="lexia-dup-actions">
          <button type="button" class="lexia-dup-open" data-dup-open="${index}">Abrir duplicado</button>
          <button type="button" class="lexia-dup-delete" data-dup-delete="${index}" ${loading||deleting?'disabled':''}>Eliminar</button>
        </div>
      </div>`).join('');
    panel.innerHTML=`
      <div class="lexia-dup-head"><div><h3>Archivos duplicados</h3><p>LexIA no elimina nada automáticamente. Abrí el duplicado y el principal para compararlos antes de decidir.</p></div><button type="button" class="maint-btn secondary" data-dup-refresh ${loading||deleting?'disabled':''}>${loading?'Actualizando…':'Actualizar lista'}</button></div>
      ${loadError?'<p class="maint-toast-error" role="alert">'+esc(loadError)+'</p>':''}
      ${loading?'<p class="maint-note" role="status">Buscando duplicados en el catálogo…</p>':''}
      ${rows?'<div class="lexia-dup-list">'+rows+'</div>':!loading&&!loadError?'<div class="lexia-dup-empty">No hay archivos marcados como duplicados.</div>':''}`;
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
    const open=target.closest('[data-dup-open]');if(open){openDuplicate(Number(open.dataset.dupOpen));return;}
    const original=target.closest('[data-dup-open-original]');if(original){openOriginal(Number(original.dataset.dupOpenOriginal));return;}
  },true);
  function activate(){
    if(!ensure())return;
    if(!loaded&&!loading)load();else render();
  }
  window.lexiaMaintenanceDuplicates={load};
  window.addEventListener('lexia:maintenance-render',activate);
  activate();
})();
