/* LexIA UI2 — inserción robusta del menú Estándares. */
(function(){
  'use strict';

  const norm=value=>String(value||'').replace(/\s+/g,' ').trim().toLowerCase();

  function clickableFromLabel(label){
    if(!label)return null;
    return label.closest('button,a,[role="button"],li') || label.parentElement;
  }

  function findMenuItem(labelText){
    const wanted=norm(labelText);
    const all=[...document.querySelectorAll('body *')];
    const exact=all.find(node=>{
      if(node.children.length>4)return false;
      return norm(node.textContent)===wanted;
    });
    return clickableFromLabel(exact);
  }

  function install(){
    if(document.querySelector('[data-lexia-standards-nav="1"]'))return true;
    const shell=document.getElementById('lexiaStandardsShell');
    if(!shell)return false;

    const maintenance=findMenuItem('Mantenimiento');
    const investigation=findMenuItem('Investigación') || findMenuItem('Investigacion');
    const anchor=maintenance || investigation;
    if(!anchor || !anchor.parentNode)return false;

    const item=anchor.cloneNode(true);
    item.dataset.lexiaStandardsNav='1';
    item.removeAttribute('id');
    item.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));

    const textNodes=[];
    const walker=document.createTreeWalker(item,NodeFilter.SHOW_TEXT);
    while(walker.nextNode())textNodes.push(walker.currentNode);
    const label=textNodes.find(node=>['mantenimiento','investigación','investigacion'].includes(norm(node.nodeValue)));
    if(label)label.nodeValue='Estándares';
    else item.textContent='Estándares';

    item.addEventListener('click',event=>{
      event.preventDefault();
      event.stopPropagation();
      shell.classList.add('open');
      item.classList.add('active');
      item.setAttribute('aria-current','page');
      const searchButton=document.getElementById('stdSearch');
      if(searchButton)searchButton.click();
    },true);

    if(maintenance && maintenance.parentNode===anchor.parentNode){
      maintenance.parentNode.insertBefore(item,maintenance);
    }else{
      anchor.parentNode.insertBefore(item,anchor.nextSibling);
    }
    return true;
  }

  function boot(){
    install();
    const observer=new MutationObserver(()=>install());
    observer.observe(document.body,{childList:true,subtree:true});
    window.setTimeout(install,250);
    window.setTimeout(install,1000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
