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

  // Product shell is a first-class production surface and must not depend on
  // optional analysis layers loading successfully. Load it independently and
  // use a version token so Safari cannot remain pinned to an older shell.
  const PRODUCT_SHELL_VERSION='0dd4112-bootstrap1';
  loadScript(`atlas-product-shell.js?v=${PRODUCT_SHELL_VERSION}`,'atlas-product-shell')
    .then(()=>window.dispatchEvent(new CustomEvent('atlas:product-shell-ready')))
    .catch(err=>console.error('ATLAS product shell bootstrap failed:',err));

  // Optional/additive analysis layers: one failure must never block the rest.
  const scripts=['atlas-timeframe-engine.js','atlas-ai-analysis-layer.js','atlas-decision-quality.js','atlas-ai-ui.js'];
  (async()=>{
    for(const src of scripts){
      try{ await loadScript(src,src); }
      catch(err){ console.error('ATLAS optional layer failed:',src,err); }
    }
    window.dispatchEvent(new CustomEvent('atlas:ai-ready'));
  })();
})();