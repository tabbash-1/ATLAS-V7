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

  async function loadScript(src){
    if(document.querySelector(`script[src="${src}"]`)) return;
    await new Promise((resolve,reject)=>{
      const s=document.createElement('script');s.src=src;s.defer=true;s.onload=resolve;s.onerror=()=>reject(new Error(`Failed to load ${src}`));document.body.appendChild(s);
    });
  }

  // Existing analysis layers load first. The product shell is strictly additive:
  // it mirrors their source-of-truth state and never moves/deletes engine nodes.
  const scripts=['atlas-timeframe-engine.js','atlas-ai-analysis-layer.js','atlas-decision-quality.js','atlas-ai-ui.js','atlas-product-shell.js'];
  (async()=>{
    for(const src of scripts) await loadScript(src);
    window.dispatchEvent(new CustomEvent('atlas:ai-ready'));
    window.dispatchEvent(new CustomEvent('atlas:product-shell-ready'));
  })().catch(err=>console.error('ATLAS bootstrap failed:',err));
})();