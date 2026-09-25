const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const assets=path.resolve(__dirname,'../../app/ui2/assets');
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};

async function setup(){
  const {window,document}=parseHTML('<html><head></head><body><div class="app"><section id="maintenance"></section></div></body></html>');
  const requests=[],opened=[],confirmations=[];
  let approve=false,duplicateError=false;
  let sync={phase:'idle'};
  let rows=[{document_path:'/library/one.pdf',document_name:'one.pdf',status:'pending'},
    {document_path:'/library/two.pdf',document_name:'two.pdf',status:'pending'},
    {document_path:'/library/error.pdf',document_name:'error.pdf',status:'error',error:'Unreadable'}];
  const duplicates=[{path:'/library/copy.pdf',name:'copy.pdf',duplicate_of:'/library/original.pdf',original_name:'original.pdf'}];
  let deleted='';
  const snapshot=()=>({ok:true,live:{autosync:sync,ocr:{running:false,pending:2,error:1},catalog:{documents:4}},autosync_config:{mode:'manual'},history:Array.from({length:8},(_,i)=>({action:'autosync-scan',message:'Scan '+i,created_at:'2026-09-25'}))});
  const fetch=async(url,options={})=>{
    const body=options.body?JSON.parse(options.body):null;
    requests.push({url,body});
    let payload={ok:true},status=200;
    if(url==='/api/maintenance')payload=snapshot();
    else if(url==='/api/maintenance-live')payload={ok:true,...snapshot().live};
    else if(url.endsWith('/duplicates')){
      if(duplicateError){payload={ok:false,error:'Service unavailable'};status=503;}
      else payload={ok:true,duplicates};
    }else if(body?.action==='ocr-list'){
      const filtered=rows.filter(row=>row.status===body.status);
      payload={ok:true,items:filtered.slice(body.offset,body.offset+body.limit),total:filtered.length,offset:body.offset,limit:body.limit};
    }else if(url==='/api/delete-file'){
      deleted=body.path;payload={ok:true,started:true,state:{path:deleted,status:'running'}};
    }else if(url==='/api/delete-file-status'){
      rows=rows.filter(row=>row.document_path!==deleted);
      payload={ok:true,state:{path:deleted,status:'completed'}};
    }
    return {ok:status===200,status,json:async()=>payload};
  };
  const timeout=(callback,delay)=>{if(delay===800)setImmediate(callback);return 1;};
  window.matchMedia=()=>({matches:false,addEventListener(){}});
  // LinkeDOM's defaultView delegates unknown properties to Node's global object.
  window.__lexiaWindowsMaintenanceDuplicatesV2=false;
  window.lexiaQuickViewerOpen=(...args)=>opened.push(args);
  window.open=()=>{};
  const context=vm.createContext({window,document,Element:window.Element,CustomEvent:window.CustomEvent,fetch,
    location:{hash:''},requestAnimationFrame:callback=>callback(),setTimeout:timeout,clearTimeout(){},setInterval(){},
    confirm:message=>{confirmations.push(message);return approve;},alert(){},console});
  vm.runInContext(fs.readFileSync(path.join(assets,'maintenance.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(assets,'windows_maintenance_duplicates.js'),'utf8'),context);
  window.lexiaMaintenanceOpen();await tick();
  const click=async selector=>{const element=document.querySelector(selector);assert.ok(element,selector);element.click();await tick();};
  const select=async file=>{const element=[...document.querySelectorAll('[data-ocr-select]')].find(e=>e.dataset.ocrSelect===file);assert.ok(element);element.checked=true;element.dispatchEvent(new window.Event('change',{bubbles:true}));await tick();};
  return {window,document,requests,opened,confirmations,click,select,
    approve:()=>approve=true,failDuplicates:()=>duplicateError=true,setRows:value=>rows=value,setSync:value=>sync=value};
}

test('Duplicates remains a single active native tab across repeated status renders',async()=>{
  const app=await setup();
  await app.click('[data-maint-tab="duplicates"]');
  for(let i=0;i<4;i++){
    app.window.lexiaMaintenanceOpen();await tick();
    assert.equal(app.document.querySelectorAll('[data-maint-tab="duplicates"]').length,1);
    assert.ok(app.document.querySelector('[data-maint-tab="duplicates"].active'));
    assert.match(app.document.querySelector('#lexiaMaintenanceDuplicatesPanel').textContent,/copy.pdf/);
  }
  assert.equal(app.requests.filter(r=>r.url.endsWith('/duplicates')).length,1);
  await app.click('[data-maint-tab="ocr"]');
  assert.equal(app.document.querySelector('#lexiaMaintenanceDuplicatesPanel'),null);
  assert.ok(app.document.querySelector('.maint-ocr-card'));
});

test('Duplicate service errors retain the last list and error during maintenance updates',async()=>{
  const app=await setup();await app.click('[data-maint-tab="duplicates"]');app.failDuplicates();
  await app.click('[data-dup-refresh]');
  app.window.lexiaMaintenanceOpen();await tick();
  const panel=app.document.querySelector('#lexiaMaintenanceDuplicatesPanel');
  assert.match(panel.textContent,/copy.pdf/);assert.match(panel.textContent,/Service unavailable/);
  assert.doesNotMatch(panel.textContent,/No hay archivos marcados/);
});

test('OCR selections persist through refresh and send only the selected paths',async()=>{
  const app=await setup();await app.click('[data-maint-tab="ocr"]');await app.click('[data-ocr-filter="pending"]');
  await app.select('/library/two.pdf');await app.click('#mRefresh');
  assert.match(app.document.querySelector('#mOcrRetrySelected').textContent,/\(1\)/);
  const selected=[...app.document.querySelectorAll('[data-ocr-select]')].filter(element=>element.hasAttribute('checked'));
  assert.deepEqual(selected.map(e=>e.dataset.ocrSelect),['/library/two.pdf']);
  await app.click('#mOcrRetrySelected');
  const operation=app.requests.find(r=>r.body?.action==='ocr-start-selected');
  assert.deepEqual(operation.body.paths,['/library/two.pdf']);
  assert.equal(app.requests.some(r=>r.body?.action==='ocr-start-all'),false);
});

test('Opening and reprocesing an individual error use that exact file',async()=>{
  const app=await setup();await app.click('[data-maint-tab="ocr"]');await app.click('[data-ocr-filter="error"]');
  await app.click('[data-ocr-open]');assert.equal(app.opened[0][0],'/library/error.pdf');
  await app.click('[data-ocr-retry]');
  assert.deepEqual(app.requests.find(r=>r.body?.action==='ocr-start-selected').body.paths,['/library/error.pdf']);
});

test('Deletion requires physical-file confirmation and removes only the chosen row',async()=>{
  const app=await setup();await app.click('[data-maint-tab="ocr"]');await app.click('[data-ocr-filter="pending"]');
  await app.click('[data-ocr-delete]');assert.equal(app.requests.some(r=>r.url==='/api/delete-file'),false);
  assert.match(app.confirmations[0],/archivo físico/);
  app.approve();await app.click('[data-ocr-delete]');
  const deletion=app.requests.find(r=>r.url==='/api/delete-file');
  assert.deepEqual(deletion.body,{path:'/library/one.pdf',confirm_name:'one.pdf'});
  assert.equal(app.document.querySelectorAll('[data-ocr-select]').length,1);
  assert.equal(app.document.querySelector('[data-ocr-select]').dataset.ocrSelect,'/library/two.pdf');
});

test('OCR pages reach records after 100 and filter changes clear hidden selections',async()=>{
  const app=await setup();
  app.setRows(Array.from({length:103},(_,i)=>({document_path:'/library/'+i+'.pdf',document_name:i+'.pdf',status:'pending'})));
  await app.click('[data-maint-tab="ocr"]');await app.click('[data-ocr-filter="pending"]');
  await app.select('/library/0.pdf');await app.click('#mOcrNext');await app.click('#mOcrNext');
  assert.equal(app.document.querySelectorAll('[data-ocr-select]').length,3);
  assert.equal(app.document.querySelector('[data-ocr-select]').dataset.ocrSelect,'/library/100.pdf');
  await app.click('[data-ocr-filter="error"]');
  assert.match(app.document.querySelector('#mOcrRetrySelected').textContent,/\(0\)/);
});


test('Background refresh preserves history and OCR scroll, including tab returns',async()=>{
  const app=await setup();
  app.document.querySelector('.maint-history').scrollTop=174;
  await app.click('#mRefresh');
  assert.equal(app.document.querySelector('.maint-history').scrollTop,174);
  await app.click('[data-maint-target="ocr"]');
  assert.ok(app.document.querySelector('[data-maint-tab="ocr"].active'));
  assert.ok(app.document.querySelector('[data-ocr-select]'));
  app.document.querySelector('.maint-ocr-items').scrollTop=209;
  await app.click('#mRefresh');
  assert.equal(app.document.querySelector('.maint-ocr-items').scrollTop,209);
  await app.click('[data-maint-tab="activity"]');
  assert.equal(app.document.querySelector('.maint-history').scrollTop,174);
});

test('AutoSync reports unknown and known totals without fabricating progress',async()=>{
  const app=await setup();
  app.setSync({phase:'scanning',processed:130,total:0,progress_total_known:false,progress_label:'Explorando documentos',recent_files:[{path:'/library/moved.pdf',source:'/old/moved.pdf',action:'Ruta actualizada',status:'Revisado'}]});
  await app.click('#mRefresh');
  assert.match(app.document.querySelector('.maint-sync-summary').textContent,/130 archivos revisados/);
  assert.doesNotMatch(app.document.querySelector('.maint-sync-summary').textContent,/%/);
  assert.match(app.document.querySelector('.maint-sync-files').textContent,/old\/moved.pdf → \/library\/moved.pdf/);
  app.setSync({phase:'scanning',processed:12,total:40,progress_total_known:true,progress_label:'Comparando ubicaciones'});
  await app.click('#mRefresh');
  assert.match(app.document.querySelector('.maint-sync-summary').textContent,/12 de 40 · 30%/);
});

test('Advanced tools stay accessible and AutoSync configuration is separate from OCR',async()=>{
  const app=await setup();
  await app.click('[data-maint-tab="automation"]');
  assert.ok(app.document.querySelector('#mSaveMode'));
  assert.equal(app.document.querySelector('.maint-ocr-card'),null);
  await app.click('[data-maint-tab="advanced"]');
  assert.ok(app.document.querySelector('#mDiagnose'));
  await app.click('[data-maint-tab="monitor"]');
  assert.ok(app.document.querySelector('#mTerminal'));
  await app.click('[data-maint-tab="about"]');
  assert.ok(app.document.querySelector('.maint-about'));
});
