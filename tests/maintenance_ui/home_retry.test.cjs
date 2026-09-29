const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const source=fs.readFileSync(require('node:path').resolve(__dirname,'../../app/ui2/assets/jurisprudence_search.js'),'utf8');
const extracted=source.slice(source.indexOf('  function installHomeLiveDataFix(){'),source.indexOf('  function installPersistentResearchHistory(){'));
const dom={window:parseHTML(`<html><head></head><body><div id="home"><div class="hr-metrics"><article data-home-target="search-file"><strong></strong><div class="hr-line"><span></span><em></em></div><div class="hr-progress"><i></i></div><small></small><p></p></article><article data-home-target="search-professional"><strong></strong><div class="hr-line"><span></span><em></em></div><div class="hr-progress"><i></i></div><small></small><p></p></article><article data-home-target="contextpage"><strong></strong><div class="hr-line"><span></span><em></em></div><div class="hr-progress"><i></i></div><small></small><p></p></article><article data-home-target="search-fragments"><strong></strong><div class="hr-line"><span></span><em></em></div><div class="hr-progress"><i></i></div></article><article data-home-target="activitypage"><strong></strong><div class="hr-line"><span></span><em></em></div><div class="hr-progress"><i></i></div><small></small><p></p></article></div><div class="hr-lower"><section class="hr-card"><div class="hr-card-title"><b></b></div></section><section class="hr-card"><div class="hr-card-title"><b></b></div></section></div></div></body></html>`)};
const timers=[];let calls=0;
dom.window.__lexiaWindowsFastStartupV1=true;dom.window.__lexiaWindowsStartupDocuments=86787;
dom.window.setTimeout=(fn,delay)=>{const id=timers.length;timers.push({fn,delay});return id;};
dom.window.clearTimeout=id=>{if(timers[id])timers[id].cleared=true;};
const fetch=async()=>{
  calls++;
  if(calls<=7)throw Error('service loading');
  return {ok:true,json:async()=>({ok:true,catalog:{documents:86787,fragments:1,recent_documents:[{name:'Fallo reciente',path:'a',category:'Jurisprudencia'}]},searches:{count:0},contexts:{count:1,recent:[{query:'Responsabilidad estatal',objective:'Investigación'}]},autosync:{}})};
};
const context={window:dom.window,document:dom.window.document,fetch,AbortController,esc:x=>x,Intl,Number,String,Date,Math,encodeURIComponent};
vm.createContext(context);vm.runInContext(extracted+'\ninstallHomeLiveDataFix();',context);
async function run(){
 assert.match(dom.window.document.querySelector('.hr-scroll-list').textContent,/Esperando/);
 for(let step=0;step<8;step++){
  const next=timers.find(t=>!t.ran&&!t.cleared);
  assert.ok(next,'retry stopped after '+calls+' requests');next.ran=true;await next.fn();
 }
 assert.equal(calls,8);
 assert.match(dom.window.document.querySelector('[data-home-target="contextpage"] strong').textContent,/1/);
 assert.match(dom.window.document.querySelector('.hr-scroll-list').textContent,/Responsabilidad estatal/);
 assert.ok(timers.some(t=>t.delay===30000),'success schedules later refresh');
 console.log('Windows home continues beyond six failed attempts and displays recents OK');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
