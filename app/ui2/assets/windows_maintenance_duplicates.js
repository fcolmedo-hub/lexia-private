/* LexIA Windows — revisión explícita de archivos duplicados desde Mantenimiento. */
(function(){
  'use strict';
  if(window.__lexiaWindowsMaintenanceDuplicatesV2)return;
  window.__lexiaWindowsMaintenanceDuplicatesV2=true;

  const SIDECAR='http://127.0.0.1:8516';
  const PANEL_ID='lexiaMaintenanceDuplicatesPanel';
  const TAB_ID='lexiaMaintenanceDuplicatesTab';
  const STYLE_ID='lexiaMaintenanceDuplicatesStyleV2';
  let duplicates=[];
  let loading=false;

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
      #${TAB_ID}{white-space:nowrap}
      #maintenance.lexia-duplicates-open .maint-grid,
      #maintenance.lexia-duplicates-open .maint-monitor-card,
      #maintenance.lexia-duplicates-open .maint-about{display:none!important}
      #${PANEL_ID}{display:none;margin-top:14px}
      #maintenance.lexia-duplicates-open #${PANEL_ID}{display:block}
      .lexia-dup-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
      .lexia-dup-head h3{margin:0 0 4px}.lexia-dup-head p{margin:0;color:#6d7691;font-size:11px}
      .lexia-dup-list{display:grid;gap:8px}
      .lexia-dup-row{border:1px solid #e0e3ef;border-radius:10px;background:#fff;padding:10px 12px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center}
      .lexia-dup-row strong{display:block;color:#283253;font-size:11px;overflow-wrap:anywhere}
      .lexia-dup-row small{display:block;margin-top:3px;color:#727b96;font-size:9.5px;overflow-wrap:anywhere}
      .lexia-dup-origin{margin-top:6px;padding:6px 8px;border-radius:7px;background:#f5f4ff;color:#5146f6;font-size:9.5px}
      .lexia-dup-origin button{border:0;background:transparent;padding:0;color:#5146f6;font:inherit;font-weight:800;text-decoration:underline;cursor:pointer}
      .lexia-dup-origin button:hover{color:#352bc7}
      .lexia-dup-actions{display:flex;gap:6px;align-items:center}
      .lexia-dup-actions button{font-size:9px;padding:6px 8px;border-radius:6px;cursor:pointer}
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
    const page=document.getElementById('maintenance');
    const tabs=page?.querySelector('.maint-tabs');
    const kpis=page?.querySelector('.maint-kpis');
    if(!page||!tabs||!kpis)return false;

    let tab=document.getElementById(TAB_ID);
    if(!tab){
      tab=document.createElement('button');
      tab.type='button';tab.id=TAB_ID;tab.className='maint-tab';tab.textContent='Duplicados';
      tabs.appendChild(tab);
      tab.addEventListener('click',()=>openPanel());
    }

    let panel=document.getElementById(PANEL_ID);
    if(!panel){
      panel=document.createElement('section');panel.id=PANEL_ID;panel.className='maint-card';
      kpis.insertAdjacentElement('afterend',panel);
    }
    return true;
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
          <button type="button" class="lexia-dup-delete" data-dup-delete="${index}">Eliminar</button>
        </div>
      </div>`).join('');
    panel.innerHTML=`
      <div class="lexia-dup-head"><div><h3>Archivos duplicados</h3><p>LexIA no elimina nada automáticamente. Abrí el duplicado y el principal para compararlos antes de decidir.</p></div><button type="button" class="maint-btn secondary" data-dup-refresh>${loading?'Actualizando…':'Actualizar lista'}</button></div>
      ${loading?'<div class="lexia-dup-empty">Buscando duplicados en el catálogo…</div>':rows?'<div class="lexia-dup-list">'+rows+'</div>':'<div class="lexia-dup-empty">No hay archivos marcados como duplicados.</div>'}`;
  }

  async function load(){
    loading=true;render();
    try{
      const data=await sidecar('/duplicates');
      duplicates=Array.isArray(data.duplicates)?data.duplicates:[];
    }catch(error){
      duplicates=[];
      const panel=document.getElementById(PANEL_ID);
      if(panel)panel.innerHTML='<div class="lexia-dup-empty">No se pudo leer la lista de duplicados: '+esc(error.message||String(error))+'</div>';
      loading=false;return;
    }
    loading=false;render();
  }

  function openPanel(){
    if(!ensure())return;
    const page=document.getElementById('maintenance');
    page.classList.add('lexia-duplicates-open');
    page.querySelectorAll('.maint-tab').forEach(button=>button.classList.toggle('active',button.id===TAB_ID));
    load();
  }

  async function deleteDuplicate(index,button){
    const item=duplicates[index];if(!item?.path)return;
    if(!confirm('¿Eliminar este archivo duplicado de LexIA?\n\n'+(item.name||shortName(item.path))+'\n\nEl documento original se conservará.'))return;
    const previous=button.textContent;button.disabled=true;button.textContent='Eliminando…';
    try{
      const data=await sidecar('/delete-duplicate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:item.path})});
      duplicates=Array.isArray(data.duplicates)?data.duplicates:[];
      render();
    }catch(error){
      alert('No se pudo eliminar el duplicado.\n\n'+(error.message||String(error)));
      button.disabled=false;button.textContent=previous;
    }
  }

  function openPath(path){
    if(!path)return;
    if(typeof window.lexiaQuickViewerOpen==='function')window.lexiaQuickViewerOpen(path,1,'');
    else window.open('/api/file-preview?path='+encodeURIComponent(path),'_blank','noopener');
  }

  function openDuplicate(index){const item=duplicates[index];if(item?.path)openPath(item.path);}
  function openOriginal(index){const item=duplicates[index];if(item?.duplicate_of)openPath(item.duplicate_of);}

  function leaveCustomTab(){
    const page=document.getElementById('maintenance');
    if(page)page.classList.remove('lexia-duplicates-open');
  }

  document.addEventListener('click',event=>{
    const target=event.target instanceof Element?event.target:null;if(!target)return;
    if(target.closest('[data-dup-refresh]')){load();return;}
    const remove=target.closest('[data-dup-delete]');if(remove){deleteDuplicate(Number(remove.dataset.dupDelete),remove);return;}
    const open=target.closest('[data-dup-open]');if(open){openDuplicate(Number(open.dataset.dupOpen));return;}
    const original=target.closest('[data-dup-open-original]');if(original){openOriginal(Number(original.dataset.dupOpenOriginal));return;}
    if(target.closest('.maint-tab')&&!target.closest('#'+TAB_ID)){leaveCustomTab();window.setTimeout(ensure,0);}
    if(target.closest('[data-route="maintenance"],#liveOperationRefresh,#mRefresh')){
      [0,100,350,800].forEach(delay=>window.setTimeout(()=>{ensure();if(document.getElementById('maintenance')?.classList.contains('lexia-duplicates-open'))render();},delay));
    }
  },true);

  const originalOpen=window.lexiaMaintenanceOpen;
  if(typeof originalOpen==='function'){
    window.lexiaMaintenanceOpen=function(){const result=originalOpen.apply(this,arguments);[0,120,420].forEach(delay=>window.setTimeout(ensure,delay));return result;};
  }
  [0,250,800,1800].forEach(delay=>window.setTimeout(ensure,delay));
})();
