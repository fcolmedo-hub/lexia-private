(()=>{
  'use strict';

  const simplify=value=>String(value||'')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,' ')
    .trim()
    .toLowerCase();

  const isLiveBadgeText=value=>{
    const text=simplify(value);
    return (
      text.length>0
      && text.length<500
      && text.includes('live')
      && text.includes('real')
      && (text.includes('busqueda')||text.includes('squeda'))
    );
  };

  function removeLiveBadge(){
    const nodes=[...document.querySelectorAll('body *')]
      .filter(node=>isLiveBadgeText(node.textContent))
      .sort((left,right)=>
        simplify(left.textContent).length-simplify(right.textContent).length
      );

    for(const node of nodes){
      let candidate=node;
      let fallback=node;

      for(let depth=0;depth<7&&candidate&&candidate!==document.body;depth+=1){
        const text=simplify(candidate.textContent);
        if(!isLiveBadgeText(text))break;

        const style=window.getComputedStyle(candidate);
        const rect=candidate.getBoundingClientRect();
        const nearBottomRight=(
          rect.width>0
          && rect.width<650
          && rect.height>0
          && rect.height<320
          && rect.right>=window.innerWidth-80
          && rect.bottom>=window.innerHeight-80
        );

        fallback=candidate;
        if(style.position==='fixed'||style.position==='sticky'||nearBottomRight){
          candidate.remove();
          return true;
        }
        candidate=candidate.parentElement;
      }

      fallback.remove();
      return true;
    }
    return false;
  }

  function install(){
    removeLiveBadge();

    const observer=new MutationObserver(removeLiveBadge);
    observer.observe(document.body,{
      childList:true,
      subtree:true,
      characterData:true
    });

    let attempts=0;
    const timer=window.setInterval(()=>{
      removeLiveBadge();
      attempts+=1;
      if(attempts>=40)window.clearInterval(timer);
    },250);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',install,{once:true});
  }else{
    install();
  }
})();
