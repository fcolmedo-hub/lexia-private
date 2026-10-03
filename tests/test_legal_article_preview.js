const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/ui2/assets/legal_article_preview.js'),'utf8');

function harness(fetcher){
  const calls=[],notes=[];
  const frame={src:'http://localhost:8512/api/file-preview?path=ley#page=1'};
  let open=true;
  const pane={prepend:n=>notes.push(n),querySelector:s=>s==='iframe.lexia-qv-frame'?frame:null};
  const shown={textContent:''};
  const document={readyState:'complete',
    getElementById:id=>({lexiaQvBody:pane,lexiaQuickViewer:{classList:{contains:()=>open}},lexiaQvPath:shown}[id]),
    createElement:()=>({setAttribute(){}}),
  };
  const window={location:{href:'http://localhost:8512/'},
    lexiaQuickViewerOpen:async(...args)=>{calls.push(args);shown.textContent=args[0];},
  };
  vm.runInNewContext(source,{window,document,fetch:fetcher,AbortController,URL,URLSearchParams});
  return {window,calls,frame,notes,close:()=>{open=false;}};
}

const law='D:/Biblioteca/Legislación/Ley 7055.pdf';
const excerpt='ARTÍCULO 5º. Este es el contenido solicitado.';
const response=()=>({ok:true,json:async()=>({ok:true,found:true,page:4,page_height:842,top:160})});

test('statutory preview uses verified page and preserves the native viewer',async()=>{
  let request;
  const h=harness(async(url,options)=>{request={url,body:JSON.parse(options.body)};return response();});
  await h.window.lexiaQuickViewerOpen(law,1,excerpt);
  assert.equal(request.url,'/api/legal-article-location');
  assert.equal(request.body.snippet,excerpt);
  assert.equal(h.calls.at(-1)[1],4);
  assert.equal(new URLSearchParams(new URL(h.frame.src).hash.slice(1)).get('page'),'4');
  assert.equal(new URLSearchParams(new URL(h.frame.src).hash.slice(1)).get('view'),'FitH,160');
});

test('ordinary PDF previews do not call the article endpoint',async()=>{
  const h=harness(()=>{throw new Error('unexpected request');});
  await h.window.lexiaQuickViewerOpen('/Jurisprudencia/fallo.pdf',2,'El art. 5 es citado.');
  assert.equal(h.calls.length,1);
  assert.equal(h.calls[0][1],2);
  assert.equal(h.notes.length,0);
});

test('a delayed article lookup cannot reopen a different document',async()=>{
  let resolve;
  const h=harness(()=>new Promise(r=>{resolve=r;}));
  const first=h.window.lexiaQuickViewerOpen(law,1,excerpt);
  await new Promise(setImmediate);
  await h.window.lexiaQuickViewerOpen('/Jurisprudencia/otro.pdf',2,'Otro pasaje');
  resolve(response());
  await first;
  assert.equal(h.calls.length,2);
  assert.equal(h.calls.at(-1)[0],'/Jurisprudencia/otro.pdf');
});

test('a closed viewer stays closed when location arrives',async()=>{
  let resolve;
  const h=harness(()=>new Promise(r=>{resolve=r;}));
  const first=h.window.lexiaQuickViewerOpen(law,1,excerpt);
  await new Promise(setImmediate);
  h.close();resolve(response());await first;
  assert.equal(h.calls.length,1);
});

test('an unresolved heading is reported instead of inventing a page',async()=>{
  const h=harness(async()=>({ok:true,json:async()=>({ok:true,found:false})}));
  await h.window.lexiaQuickViewerOpen(law,3,excerpt);
  assert.equal(h.calls.length,1);
  assert.match(h.notes[0].textContent,/No se pudo localizar/);
});
