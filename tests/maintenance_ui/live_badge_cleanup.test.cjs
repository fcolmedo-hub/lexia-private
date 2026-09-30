const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const assets=path.resolve(__dirname,'../../app/ui2/assets');

function surface(){
  const {window,document}=parseHTML('<html><head></head><body><div id="liveBadge">LIVE · BÚSQUEDA REAL</div><section id="home"><div class="hr-card"><div class="hr-scroll-list"><div class="hr-row">Investigación reciente</div></div></div></section></body></html>');
  document.querySelectorAll=()=>{throw Error('Unexpected whole-page scan');};
  window.MutationObserver=class{constructor(){throw Error('Unexpected observer');}};
  window.setInterval=()=>{throw Error('Unexpected polling');};
  return {window,document};
}

test('Windows badge removal touches only the badge and preserves recent rows',()=>{
  const {window,document}=surface();
  const code=fs.readFileSync(path.join(assets,'windows_live_badge_cleanup.js'),'utf8');
  vm.runInNewContext(code,{window,document,MutationObserver:window.MutationObserver});
  assert.equal(document.getElementById('liveBadge'),null);
  assert.match(document.getElementById('home').textContent,/Investigación reciente/);
});

test('shared runtime does not rescan the page when recent rows change',()=>{
  const {window,document}=surface();
  const source=fs.readFileSync(path.join(assets,'app_runtime.js'),'utf8');
  const start=source.indexOf('  function removeLiveSearchBadge(){');
  const end=source.indexOf('  function installNavigatorExactFolderFilter(){',start);
  assert.ok(start>=0&&end>start);
  const context={window,document,MutationObserver:window.MutationObserver};
  vm.createContext(context);
  vm.runInContext(source.slice(start,end)+'\ninstallLiveSearchBadgeRemoval();',context);
  assert.equal(document.getElementById('liveBadge'),null);
  const row=document.createElement('div');row.className='hr-row';row.textContent='Otra consulta reciente';
  document.querySelector('#home .hr-scroll-list').appendChild(row);
  assert.match(document.getElementById('home').textContent,/Otra consulta reciente/);
});
