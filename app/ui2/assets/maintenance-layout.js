/* >>> LEXIA UI2 3.3.3u3 MANTENIMIENTO INTEGRADO */
(function(){
  const page=document.getElementById('maintenance');
  const app=document.querySelector('.app');
  if(page&&app&&page.parentElement!==app) app.appendChild(page);
  window.lexiaMaintenanceOpen=function(){
    const current=document.getElementById('maintenance');
    if(current) current.style.display='block';
    document.getElementById('mRefresh')?.click();
  };
})();
/* <<< LEXIA UI2 3.3.3u3 MANTENIMIENTO INTEGRADO */
