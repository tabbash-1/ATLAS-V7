(() => {
  const VERSION='ATLAS_PRODUCTION_LABEL_LOCK_V1';

  function enforce(){
    const score=document.getElementById('apsConfidence');
    const label=score?.parentElement?.querySelector('.aps-label');
    if(label && label.textContent.trim()!=='Production score'){
      label.textContent='Production score';
    }
  }

  document.addEventListener('DOMContentLoaded',enforce,{once:true});
  window.addEventListener('atlas:product-shell-ready',enforce);
  const observer=new MutationObserver(()=>enforce());
  observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  enforce();
  window.ATLAS_PRODUCTION_LABEL_LOCK={version:VERSION,enforce};
})();
