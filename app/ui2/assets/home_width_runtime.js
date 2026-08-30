/* LexIA UI2 — runtime width guard for Home */
(function(){
  'use strict';
  const PROPS=['margin-left','width','max-width','min-width','padding-left','padding-right','overflow-x','box-sizing'];
  const INNER_PROPS=['width','max-width','min-width','margin-left','margin-right','box-sizing'];

  function clearImportant(el,props){
    if(!el)return;
    props.forEach(p=>el.style.removeProperty(p));
  }

  function apply(){
    const home=document.getElementById('home');
    if(!home)return;
    const real=home.querySelector('.home-real');
    const main=home.querySelector('.hr-main');
    const content=home.querySelector('.hr-content');
    const app=document.querySelector('.app');
    const narrow=window.innerWidth<=900;

    if(!narrow){
      clearImportant(home,PROPS);
      clearImportant(real,INNER_PROPS);
      clearImportant(main,INNER_PROPS.concat(['display']));
      clearImportant(content,INNER_PROPS.concat(['padding-left','padding-right']));
      if(app){app.style.removeProperty('width');app.style.removeProperty('max-width');}
      return;
    }

    if(app){
      app.style.setProperty('width','100vw','important');
      app.style.setProperty('max-width','100vw','important');
    }

    home.style.setProperty('margin-left','0','important');
    home.style.setProperty('width','100vw','important');
    home.style.setProperty('max-width','100vw','important');
    home.style.setProperty('min-width','0','important');
    home.style.setProperty('padding-left','0','important');
    home.style.setProperty('padding-right','0','important');
    home.style.setProperty('overflow-x','hidden','important');
    home.style.setProperty('box-sizing','border-box','important');

    [real,main,content].forEach(el=>{
      if(!el)return;
      el.style.setProperty('width','100%','important');
      el.style.setProperty('max-width','100%','important');
      el.style.setProperty('min-width','0','important');
      el.style.setProperty('margin-left','0','important');
      el.style.setProperty('margin-right','0','important');
      el.style.setProperty('box-sizing','border-box','important');
    });
    if(main)main.style.setProperty('display','block','important');
    if(content){
      const pad=window.innerWidth<=560?'10px':'18px';
      content.style.setProperty('padding-left',pad,'important');
      content.style.setProperty('padding-right',pad,'important');
    }
  }

  let raf=0;
  function schedule(){
    cancelAnimationFrame(raf);
    raf=requestAnimationFrame(apply);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});
  else apply();
  window.addEventListener('resize',schedule,{passive:true});
  new MutationObserver(schedule).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
})();
