const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const assets=path.resolve(__dirname,'../../app/ui2/assets');
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};

async function setup({deferMaintenance=false,fail="",mismatch=false,running=false,count=3,holdDeletion=false,queuedPolls=0}={}){
  const {window,document}=parseHTML('<html><head></head><body><div class="app"><section id="maintenance"></section></div></body></html>');
  const requests=[],opened=[],confirmations=[];
  let approve=false,duplicateError=false;
  let sync={phase:'idle'};
  let rows=Array.from({length:count},(_,i)=>({document_path:'/library/'+i+'.pdf',document_name:i+'.pdf',status:'pending'}));
  const duplicates=[{path:'/library/copy.pdf',name:'copy.pdf',duplicate_of:'/library/original.pdf',original_name:'original.pdf'}];
  let deleted='',deletePaths=[],completedPaths=[];
  const attempts=[];
  let releaseMaintenance,releaseDeletion;
  const snapshot=()=>({ok:true,live:{autosync:sync,ocr:{running,pending:rows.length,error:0},catalog:{documents:4}},autosync_config:{mode:'manual'},history:Array.from({length:8},(_,i)=>({action:'autosync-scan',message:'Scan '+i,created_at:'2026-09-25'}))});
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
    }else if(body?.action==='ocr-list'){
      const filtered=rows.filter(row=>row.status===body.status);
      payload={ok:true,items:filtered.slice(body.offset,body.offset+body.limit),total:filtered.length,offset:body.offset,limit:body.limit};
    }else if(url==='/api/delete-file'||body?.action==='ocr-delete-selected'){
      deletePaths=body?.paths||[body.path];completedPaths=[];
      deleted=deletePaths[0];payload={ok:true,started:true,state:{operation_id:'op',path:deleted,status:'queued'}};
    }else if(url==='/api/delete-file-status'){
      if(holdDeletion)await new Promise(resolve=>{releaseDeletion=resolve;});
      const next=deletePaths[completedPaths.length];
      if(mismatch)payload={ok:true,state:{operation_id:'other',path:'/library/unrelated.pdf',status:'completed'}};
      else if(queuedPolls-->0)payload={ok:true,state:{operation_id:'op',status:'queued',stage:'Esperando punto seguro de AutoSync',deleted_paths:[]}};
      else {
        attempts.push({body:{path:next,confirm_name:next.split('/').pop()}});
        if(next===fail)payload={ok:true,state:{operation_id:'op',path:next,deleted_paths:[...completedPaths],status:'error',error:'Archivo bloqueado'}};
        else {
          completedPaths.push(next);rows=rows.filter(row=>row.document_path!==next);
          payload={ok:true,state:{operation_id:'op',path:next,deleted_paths:[...completedPaths],status:completedPaths.length===deletePaths.length?'completed':'running'}};
        }
      }
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

  window.lexiaMaintenanceOpen();await tick();
  const click=async selector=>{const element=document.querySelector(selector);assert.ok(element,selector);element.click();await tick();};
  const select=async file=>{const element=[...document.querySelectorAll('[data-ocr-select]')].find(e=>e.dataset.ocrSelect===file);assert.ok(element);element.checked=true;element.dispatchEvent(new window.Event('change',{bubbles:true}));await tick();};
  return {window,document,requests,attempts,opened,confirmations,click,select,
    releaseMaintenance:()=>releaseMaintenance?.(),
    releaseDeletion:()=>{holdDeletion=false;releaseDeletion?.();},
    approve:()=>approve=true,failDuplicates:()=>duplicateError=true,setRows:value=>rows=value,setSync:value=>sync=value};
}


async function ocr(options){
 const a=await setup(options);await a.click('[data-maint-tab="ocr"]');await a.click('[data-ocr-filter="pending"]');return a;
}
const deletes=a=>a.attempts;
const submissions=a=>a.requests.filter(r=>r.url==='/api/delete-file'||r.body?.action==='ocr-delete-selected');

test('Cancel sends no deletion and confirms physical files and count',async()=>{
 const a=await ocr();assert.ok(a.document.querySelector('#mOcrDeleteSelected').hasAttribute('disabled'));
 await a.select('/library/1.pdf');await a.click('#mOcrDeleteSelected');
 assert.equal(deletes(a).length,0);assert.match(a.confirmations[0],/1 archivos seleccionados/);assert.match(a.confirmations[0],/archivos físicos/);
});
test('Deletes only the selected files once, with one confirmation and completed progress',async()=>{
 const a=await ocr();await a.select('/library/0.pdf');await a.select('/library/2.pdf');a.approve();await a.click('#mOcrDeleteSelected');await tick();
 assert.deepEqual(deletes(a).map(r=>r.body),[{path:'/library/0.pdf',confirm_name:'0.pdf'},{path:'/library/2.pdf',confirm_name:'2.pdf'}]);
 assert.equal(a.confirmations.length,1);
 assert.equal(a.document.querySelectorAll('[data-ocr-select]').length,1);
 assert.equal(a.document.querySelector('[data-ocr-select]').dataset.ocrSelect,'/library/1.pdf');
 assert.match(a.document.querySelector('#mOcrDeleteProgress').textContent,/2 de 2 · 100%/);
 assert.ok(a.document.querySelector('#mOcrDeleteSelected').hasAttribute('disabled'));
});
test('Failure stops and retains failed and unattempted selections',async()=>{
 const a=await ocr({fail:'/library/1.pdf'});await a.click('#mOcrSelectPage');a.approve();await a.click('#mOcrDeleteSelected');await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf','/library/1.pdf']);
 assert.equal(a.document.querySelectorAll('[data-ocr-select][checked]').length,2);
 assert.match(a.document.querySelector('#mOcrDeleteProgress').textContent,/1 de 3 completados.*Archivo bloqueado/);
});
test('Selections across pages are counted and deleted',async()=>{
 const a=await ocr({count:51});await a.select('/library/0.pdf');await a.click('#mOcrNext');await a.select('/library/50.pdf');
 assert.match(a.document.querySelector('#mOcrDeleteSelected').textContent,/\(2\)/);
 a.approve();await a.click('#mOcrDeleteSelected');await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf','/library/50.pdf']);
});
test('Unrelated completion cannot delete the rest or clear selection',async()=>{
 const a=await ocr({mismatch:true});await a.click('#mOcrSelectPage');a.approve();await a.click('#mOcrDeleteSelected');await tick();
 assert.equal(submissions(a).length,1);
 assert.equal(deletes(a).length,0);
 assert.equal(a.document.querySelectorAll('[data-ocr-select][checked]').length,3);
 assert.match(a.document.querySelector('#mOcrDeleteProgress').textContent,/0 de 3 completados/);
});
test('Pending files can be queued for deletion while OCR is running',async()=>{
 const a=await ocr({running:true});assert.equal(a.document.querySelector('[data-ocr-select]').hasAttribute('disabled'),false);
 await a.select('/library/0.pdf');assert.equal(a.document.querySelector('#mOcrDeleteSelected').hasAttribute('disabled'),false);
 assert.ok(a.document.querySelector('#mOcrRetrySelected').hasAttribute('disabled'));
 a.approve();await a.click('#mOcrDeleteSelected');await tick();assert.equal(submissions(a).length,1);
});


test('Select next files during deletion without modifying the active batch',async()=>{
 const a=await ocr({holdDeletion:true});await a.select('/library/0.pdf');a.approve();await a.click('#mOcrDeleteSelected');
 assert.ok(a.document.querySelector('[data-ocr-select="/library/0.pdf"]').hasAttribute('disabled'));
 assert.equal(a.document.querySelector('[data-ocr-select="/library/1.pdf"]').hasAttribute('disabled'),false);
 await a.select('/library/1.pdf');
 assert.match(a.document.querySelector('#mOcrDeleteSelected').textContent,/\(1\)/);
 assert.ok(a.document.querySelector('#mOcrDeleteSelected').hasAttribute('disabled'));
 await a.click('#mOcrDeleteSelected');
 assert.equal(submissions(a).length,1);
 a.releaseDeletion();await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf']);
 assert.ok(a.document.querySelector('[data-ocr-select="/library/1.pdf"]').hasAttribute('checked'));
 assert.equal(a.document.querySelector('#mOcrDeleteSelected').hasAttribute('disabled'),false);
});
test('Select page and clear affect only the next batch while deletion runs',async()=>{
 const a=await ocr({holdDeletion:true});await a.select('/library/0.pdf');a.approve();await a.click('#mOcrDeleteSelected');
 await a.click('#mOcrSelectPage');assert.match(a.document.querySelector('#mOcrDeleteSelected').textContent,/\(2\)/);
 await a.click('#mOcrClearSelection');assert.match(a.document.querySelector('#mOcrDeleteSelected').textContent,/\(0\)/);
 a.releaseDeletion();await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf']);
});
test('Failure preserves both new selections and unconfirmed batch files',async()=>{
 const a=await ocr({holdDeletion:true,fail:'/library/0.pdf'});await a.select('/library/0.pdf');a.approve();await a.click('#mOcrDeleteSelected');
 await a.select('/library/2.pdf');a.releaseDeletion();await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf']);
 assert.ok(a.document.querySelector('[data-ocr-select="/library/0.pdf"]').hasAttribute('checked'));
 assert.ok(a.document.querySelector('[data-ocr-select="/library/2.pdf"]').hasAttribute('checked'));
});
test('Individual deletion also allows preparing the next selection',async()=>{
 const a=await ocr({holdDeletion:true});a.approve();await a.click('[data-ocr-delete="/library/0.pdf"]');
 await a.select('/library/2.pdf');a.releaseDeletion();await tick();
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf']);
 assert.ok(a.document.querySelector('[data-ocr-select="/library/2.pdf"]').hasAttribute('checked'));
});

test('Queued job is submitted once and resumes without manual retry',async()=>{
 const a=await ocr({queuedPolls:8});await a.select('/library/0.pdf');await a.select('/library/2.pdf');a.approve();
 await a.click('#mOcrDeleteSelected');await tick();await tick();
 assert.equal(submissions(a).length,1);
 assert.deepEqual(submissions(a)[0].body.paths,['/library/0.pdf','/library/2.pdf']);
 assert.deepEqual(deletes(a).map(r=>r.body.path),['/library/0.pdf','/library/2.pdf']);
 assert.match(a.document.querySelector('#mOcrDeleteProgress').textContent,/2 de 2 · 100%/);
});
