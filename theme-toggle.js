(() => {
  const KEY='atlas.v7.theme';
  const btn=document.getElementById('themeToggleBtn');
  const icon=document.getElementById('themeToggleIcon');
  const text=document.getElementById('themeToggleText');

  function preferred(){
    const saved=localStorage.getItem(KEY);
    if(saved==='light'||saved==='dark') return saved;
    return 'dark';
  }

  function apply(theme,persist=true){
    const light=theme==='light';
    document.documentElement.dataset.theme=light?'light':'dark';
    document.body.classList.toggle('atlas-light',light);
    if(icon) icon.textContent=light?'🌙':'☀️';
    if(text) text.textContent=light?'Dark':'Light';
    if(btn){
      btn.setAttribute('aria-pressed',String(light));
      btn.title=light?'Switch to Dark Mode':'Switch to Light Mode';
    }
    if(persist) localStorage.setItem(KEY,light?'light':'dark');
    window.dispatchEvent(new CustomEvent('atlas:theme-change',{detail:{theme:light?'light':'dark'}}));
  }

  apply(preferred(),false);
  btn?.addEventListener('click',()=>{
    const next=document.documentElement.dataset.theme==='light'?'dark':'light';
    apply(next,true);
  });

  window.ATLAS_THEME={get:()=>document.documentElement.dataset.theme||'dark',set:apply};

  function loadScript(src,key=src){
    if(document.querySelector(`script[data-atlas-loader="${key}"]`)) return Promise.resolve();
    return new Promise((resolve,reject)=>{
      const s=document.createElement('script');
      s.src=src;
      s.defer=true;
      s.dataset.atlasLoader=key;
      s.onload=resolve;
      s.onerror=()=>reject(new Error(`Failed to load ${src}`));
      document.body.appendChild(s);
    });
  }

  loadScript('atlas-decision-explanation.js?v=3','atlas-decision-explanation')
    .then(()=>window.ATLAS_DECISION_EXPLANATION?.refresh?.())
    .catch(err=>console.error('ATLAS decision explanation layer failed:',err));

  // Keep the product shell additive: it loads after the existing decision/AI
  // layers and delegates to their APIs/state rather than replacing any engine.
  const scripts=['atlas-timeframe-engine.js','atlas-ai-analysis-layer.js','atlas-decision-quality.js','atlas-ai-ui.js','atlas-product-shell.js','production-null-display-fix.js'];
  (async()=>{
    for(const src of scripts){
      try{ await loadScript(src,src); }
      catch(err){ console.error('ATLAS optional layer failed:',src,err); }
    }
    window.dispatchEvent(new CustomEvent('atlas:ai-ready'));
  })();
})();
