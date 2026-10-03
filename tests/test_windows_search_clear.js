const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const calls=[];
const handlers={};
const elements={};
const makeNode=()=>({innerHTML:'',textContent:'',value:'',style:{},dataset:{},handlers:{},
  addEventListener(k,fn){this.handlers[k]=fn},removeAttribute(){},setAttribute(){},
  before(node){elements[node.id]=node},focus(){this.focused=true},classList:{remove(){},add(){}}});
for(const id of ['legalQuery','runLegalSearch','realSearchResults','realSearchSummary','realSearchQuery','homeQuickSearchInput'])elements[id]=makeNode();
let resolveSearch;
const searchResponse=new Promise(resolve=>resolveSearch=resolve);
let first=true;
const sandbox={
  document:{readyState:'loading',getElementById:id=>elements[id]||null,
    querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>makeNode(),
    addEventListener:(key,fn)=>(handlers[key]??=[]).push(fn)},
  window:{},setTimeout,performance,
  fetch:(url)=>{calls.push(url);if(url==='/api/search-filename'&&first){first=false;return searchResponse}
    if(url==='/api/search-result-meta')return Promise.resolve({ok:true,json:async()=>({ok:false})});
    return Promise.resolve({ok:true,json:async()=>({ok:true,results:[]})});}
};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),sandbox);
for(const fn of handlers.DOMContentLoaded||[])fn();
assert(elements.clearLegalSearch,'clear button exists');
elements.legalQuery.value='Fallo previo';
const pending=sandbox.window.lexiaSearch320Run();
elements.clearLegalSearch.handlers.click({preventDefault(){},stopPropagation(){}});
assert.equal(elements.legalQuery.value,'');
assert.equal(elements.homeQuickSearchInput.value,'');
resolveSearch({ok:true,json:async()=>({ok:true,results:[{document_name:'Fallo previo'}]})});
pending.then(()=>{
  assert(!elements.realSearchResults.innerHTML.includes('Fallo previo'));
  sandbox.window.lexiaSearch320SetMode('professional');
  sandbox.window.lexiaSearch320SetMode('filename');
  assert.equal(elements.legalQuery.value,'');
  elements.legalQuery.value='otra consulta';
  elements.legalQuery.value='';
  for(const fn of handlers.input||[])fn({target:elements.legalQuery});
  sandbox.window.lexiaSearch320SetMode('professional');
  sandbox.window.lexiaSearch320SetMode('filename');
  assert.equal(elements.legalQuery.value,'');
  console.log('OK: botón, borrado manual, pestañas y respuesta pendiente');
}).catch(err=>{console.error(err);process.exitCode=1});
