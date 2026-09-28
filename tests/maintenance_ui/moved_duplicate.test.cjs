const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const assets=path.resolve(__dirname,'../../app/ui2/assets');
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};

async function setup({deferMaintenance=false}={}){
  const {window,document}=parseHTML('<html><head></head><body><div class="app"><section id="maintenance"></section></div></body></html>');
  const requests=[],opened=[],confirmations=[];
  let approve=false,duplicateError=false;
  let sync={phase:'idle'};
  let rows=[{document_path:'/library/one.pdf',document_name:'one.pdf',status:'pending'},
    {document_path:'/library/two.pdf',document_name:'two.pdf',status:'pending'},
    {document_path:'/library/error.pdf',document_name:'error.pdf',status:'error',error:'Unreadable'}];
  const duplicates=[{path:'/library/copy.pdf',name:'copy.pdf',duplicate_of:'/library/original.pdf',original_name:'original.pdf',can_delete:true},{path:'/library/moved.pdf',name:'moved.pdf',duplicate_of:'/old/moved.pdf',original_name:'moved.pdf',can_delete:false,can_reconcile:true,problem:'El original ya no está'}];
  let deleted='';
  let releaseMaintenance;
  const snapshot=()=>({ok:true,live:{autosync:sync,ocr:{running:false,pending:2,error:1},catalog:{documents:4}},autosync_config:{mode:'manual'},history:Array.from({length:8},(_,i)=>({action:'autosync-scan',message:'Scan '+i,created_at:'2026-09-25'}))});
  const fetch=async(url,options={})=>{
    const body=options.body?JSON.parse(options.body):null;
    requests.push({url,body});
    let payload={ok:true},status=200;
    if(url==='/api/maintenance'){
      if(deferMaintenance)await new Promise(resolve=>{releaseMaintenance=resolve;});
      payload=snapshot();
    }
    else if(url==='/api/maintenance-live')payload={ok:true,...snapshot().live};
    else if(url.endsWith('/duplicates')){
      if(duplicateError){payload={ok:false,error:'Service unavailable'};status=503;}
      else payload={ok:true,duplicates};
    }else if(url.endsWith('/reconcile-duplicate')){
      const i=duplicates.findIndex(x=>x.path===body.path);if(i>=0)duplicates.splice(i,1);payload={ok:true,backup:'/backup',warnings:[]};
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
    releaseMaintenance:()=>releaseMaintenance?.(),
    approve:()=>approve=true,failDuplicates:()=>duplicateError=true,setRows:value=>rows=value,setSync:value=>sync=value};
}


test('Moved file is protected and repaired without a deletion request',async()=>{
 const a=await setup();await a.click('[data-maint-tab="duplicates"]');
 assert.ok(a.document.querySelector('[data-dup-delete="1"]').hasAttribute('disabled'));
 assert.match(a.document.querySelector('#lexiaMaintenanceDuplicatesPanel').textContent,/El original ya no está/);
 await a.click('[data-dup-delete="1"]');
 assert.equal(a.requests.some(r=>r.url.endsWith('/delete-duplicate')),false);
 await a.click('[data-dup-reconcile="1"]');
 assert.equal(a.requests.filter(r=>r.url.endsWith('/reconcile-duplicate')).length,1);
 assert.equal(a.requests.some(r=>r.url.includes('/delete-duplicate')),false);
 assert.match(a.document.querySelector('#lexiaMaintenanceDuplicatesPanel').textContent,/Ubicación corregida/);
 assert.equal(a.document.querySelector('[data-dup-reconcile]'),null);
});
test('Bulk request excludes protected moved files',async()=>{
 const a=await setup();await a.click('[data-maint-tab="duplicates"]');a.approve();
 await a.click('[data-dup-delete-all]');
 const request=a.requests.find(r=>r.url.endsWith('/delete-duplicates'));
 assert.deepEqual(request.body.paths,['/library/copy.pdf']);
});
