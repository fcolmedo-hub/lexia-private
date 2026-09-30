(()=>{
  'use strict';

  function removeLiveBadge(){
    const badge=document.getElementById('liveBadge');
    if(badge)badge.remove();
  }

  // The badge belongs to the static index and precedes this script. A global
  // observer and repeated full-page text scans blocked large WebView screens.
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',removeLiveBadge,{once:true});
  }else{
    removeLiveBadge();
  }
})();
