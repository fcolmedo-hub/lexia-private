const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.LEXIA_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
const browser=await chromium.launch({headless:true,...(process.env.LEXIA_CHROMIUM_PATH?{executablePath:process.env.LEXIA_CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const root=path.resolve(__dirname,'../..'),index=fs.readFileSync(root+'/app/ui2/index.html','utf8');
const styles=[...index.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
const html='<html><head><style>'+styles+'</style><style>'+fs.readFileSync(root+'/app/ui2/assets/maintenance.css','utf8')+'</style><style>'+fs.readFileSync(root+'/app/ui2/assets/shared_ui_consistency.css','utf8')+'</style></head><body><div id="globalSidebar" class="global-sidebar"><div class="nav"></div></div><div class="app"><section id="searchpage" style="display:none"><div class="search-modes"><button class="mode active">Nombre de archivo</button><button class="mode">Contenido</button></div></section><section id="maintenance"></section></div></body></html>';
await page.setContent(html);
await page.evaluate(()=>{
window.fixture={ok:true,live:{autosync:{phase:'scanning',progress_label:'Actualizando rutas en el catálogo',progress_total_known:true,processed:120,total:360,recent_files:Array.from({length:50},(_,i)=>({path:'/Biblioteca/Jurisprudencia/Fallo '+i+'.pdf',source:'/Biblioteca/Anterior/Fallo '+i+'.pdf',action:'Ruta actualizada',status:'Revisado'}))},ocr:{pending:39,error:0,running:false},catalog:{documents:86791}},autosync_config:{mode:'automatic'},history:Array.from({length:8},(_,i)=>({action:'autosync-scan',message:'Revisión de archivos y cambios de la biblioteca '+i,created_at:'25/09/2026 16:21'}))};
window.fetch=async(url,opts)=>({ok:true,json:async()=>url==='/api/maintenance'?window.fixture:url==='/api/maintenance-live'?{ok:true,...window.fixture.live}:url.endsWith('/duplicates')?{ok:true,duplicates:Array.from({length:50},(_,i)=>({path:'/Biblioteca/Escritos/Tributario/Carpeta con nombre largo para comprobar el ajuste/'+i+' - CONTESTACION RECURSO DE APELACION.pdf',name:i+' - CONTESTACION RECURSO DE APELACION.pdf',duplicate_of:'/Biblioteca/Escritos/Administrativos/Carpeta con nombre largo/'+i+' - CONTESTACION RECURSO DE APELACION.pdf',original_name:i+' - CONTESTACION RECURSO DE APELACION.pdf',category:'Escritos',size:13248}))}:JSON.parse(opts?.body||'{}').action==='ocr-list'?{ok:true,total:39,offset:0,items:Array.from({length:39},(_,i)=>({document_path:'/Biblioteca/Jurisprudencia/Tribunales/Segunda instancia/Carpeta muy larga para comprobar truncamiento/Sentencia '+i+'.pdf',document_name:'Sentencia laboral '+i+'.pdf',status:'pending',total_pages:47}))}:{ok:true}});
});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addScriptTag({content:fs.readFileSync(root+'/app/ui2/assets/maintenance.js','utf8')});
await page.evaluate(()=>window.lexiaMaintenanceOpen());await page.locator('.maint-history').waitFor();

await page.locator('.maint-history').evaluate(e=>e.scrollTop=160);
await page.locator('#mRefresh').click();await page.waitForTimeout(80);
assert.equal(await page.locator('.maint-history').evaluate(e=>e.scrollTop),160);
await page.locator('[data-maint-target="ocr"]').click();await page.locator('[data-ocr-select]').first().waitFor();
for(const [width,height] of [[1440,900],[1280,720],[1024,768],[390,844],[1280,650]]){
await page.setViewportSize({width,height});await page.waitForTimeout(50);
const layout=await page.evaluate(()=>{
  const p=document.querySelector('#maintenance'),l=document.querySelector('.maint-ocr-items'),b=document.querySelector('#mOcrStart');
  const properties=['fontFamily','fontSize','fontWeight','lineHeight','padding','borderRadius','color','backgroundColor'];
  const style=element=>Object.fromEntries(properties.map(key=>[key,getComputedStyle(element)[key]]));
  return {outer:p.scrollHeight-p.clientHeight,horizontal:p.scrollWidth-p.clientWidth,list:l.scrollHeight-l.clientHeight,listHeight:l.clientHeight,footer:b.getBoundingClientRect().bottom,tab:style(document.querySelector('.maint-tab.active')),reference:style(document.querySelector('#searchpage .mode.active'))};
});
assert.equal(layout.outer,0,JSON.stringify({width,height,layout}));
assert.equal(layout.horizontal,0);
assert.ok(layout.list>0);assert.ok(layout.listHeight>=90);
assert.ok(layout.footer<=height);
assert.deepEqual(layout.tab,layout.reference);
console.log('Layout OK',width,height);

}
await page.setViewportSize({width:1280,height:720});
await page.locator('.maint-ocr-items').evaluate(e=>e.scrollTop=280);
await page.locator('#mRefresh').click();await page.waitForTimeout(80);
assert.equal(await page.locator('.maint-ocr-items').evaluate(e=>e.scrollTop),280);
await page.evaluate(()=>{window.fixture.live.ocr={pending:38,processing:1,running:true,total:39,document_name:'Escaneado.pdf',current_file:'/library/Escaneado.pdf',total_pages:47,current_page:12};});
await page.locator('#mRefresh').click();await page.waitForTimeout(80);
assert.ok(await page.locator('.maint-ocr-items').evaluate(e=>e.clientHeight>=50));
assert.ok(await page.locator('#mOcrStop').evaluate(e=>e.getBoundingClientRect().bottom<=innerHeight));
// Duplicates reuse OCR row typography and buttons, with only the list scrolling.
const ocrStyles=await page.locator('[data-ocr-delete]').first().evaluate(e=>{
  const s=getComputedStyle(e);return [s.fontSize,s.fontWeight,s.height,s.color,s.backgroundColor,s.borderColor,s.padding];
});
await page.addScriptTag({content:fs.readFileSync(root+'/app/ui2/assets/windows_maintenance_duplicates.js','utf8')});
await page.locator('[data-maint-tab="duplicates"]').click();
await page.locator('[data-dup-open-original]').first().waitFor();
for(const [width,height] of [[1440,900],[1280,720],[1024,768],[390,844]]){
  await page.setViewportSize({width,height});
  const dimensions=await page.evaluate(()=>{
    const outer=document.querySelector('#maintenance'),content=document.querySelector('.maint-content'),list=document.querySelector('.lexia-dup-list');
    return {outer:outer.scrollHeight-outer.clientHeight,content:content.scrollHeight-content.clientHeight,horizontal:outer.scrollWidth-outer.clientWidth,list:list.scrollHeight-list.clientHeight};
  });
  assert.equal(dimensions.outer,0);assert.equal(dimensions.content,0);assert.equal(dimensions.horizontal,0);assert.ok(dimensions.list>0);
  const actual=await page.locator('[data-dup-delete]').first().evaluate(e=>{const s=getComputedStyle(e);return [s.fontSize,s.fontWeight,s.height,s.color,s.backgroundColor,s.borderColor,s.padding];});
  assert.deepEqual(actual,ocrStyles);
  if(process.env.LEXIA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LEXIA_SCREENSHOT_DIR,'duplicates-'+width+'.png')});
}
await page.locator('.lexia-dup-list').evaluate(e=>e.scrollTop=350);
await page.locator('[data-dup-refresh]').click();await page.waitForTimeout(80);
assert.equal(await page.locator('.lexia-dup-list').evaluate(e=>e.scrollTop),350);
await page.locator('#mRefresh').click();await page.waitForTimeout(80);
assert.equal(await page.locator('.lexia-dup-list').evaluate(e=>e.scrollTop),350);
console.log('Duplicates match OCR; internal scrolling and refresh OK');
await page.setViewportSize({width:1280,height:720});
// Real event propagation: the old capture router must never receive the root click.
await page.evaluate(()=>{
  document.querySelector('#maintenance').style.display='none';
  const search=document.querySelector('#searchpage');search.style.display='block';
  search.insertAdjacentHTML('beforeend','<div id="lexiaNavigatorView"><div id="lexiaNavigatorTree"></div><div id="lexiaNavigatorFiles"></div><div id="lexiaNavigatorCount"></div><div id="lexiaNavigatorBreadcrumb"></div><div id="lexiaNavigatorPreview"></div></div>');
  window.oldRouteOpened=false;window.navCalls=[];
  document.addEventListener('click',event=>{if(event.target.closest('button')?.textContent==='Biblioteca'){window.oldRouteOpened=true;event.stopImmediatePropagation();}},true);
  window.fetch=async(url,options)=>{window.navCalls.push(url);return {ok:true,json:async()=>url==='/api/navigator-children'?{ok:true,total:1,nodes:[{name:'Legislación',category:'legislacion',count:1}]}:{ok:true,total:1,items:[{document_path:'/library/ley.pdf',document_name:'Ley.pdf'}]}};};
});
await page.addScriptTag({content:fs.readFileSync(root+'/app/ui2/navigator_3_3_4a.js','utf8')});
await page.evaluate(()=>window.lexiaNavigator330i.activate());
await page.locator('[data-library-root] .lexia-nav-tree-name').click();
await page.locator('.lexia-nav-file-title').waitFor();
assert.equal(await page.evaluate(()=>window.oldRouteOpened),false);
assert.equal(await page.evaluate(()=>window.navCalls.filter(url=>url==='/api/navigator-children').length),2);
assert.equal(await page.evaluate(()=>window.navCalls.filter(url=>url==='/api/navigator-documents').length),2);
assert.deepEqual(errors,[]);
console.log('History, OCR refresh, active OCR and library root routing OK');
await browser.close();
})();
