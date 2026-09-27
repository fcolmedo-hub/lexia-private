/* LexIA Windows — quitar la insignia estática sin observar el DOM. */
(()=>{
  'use strict';

  function removeLiveBadge(){
    document.getElementById('liveBadge')?.remove();
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',removeLiveBadge,{once:true});
  }else{
    removeLiveBadge();
  }
})();
