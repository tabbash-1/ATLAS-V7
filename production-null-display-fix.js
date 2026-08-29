(() => {
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=0)=>finite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const set=(id,value)=>{const el=document.getElementById(id);if(el&&el.textContent!==value)el.textContent=value;};
  let applying=false;

  function apply(){
    if(applying)return;
    const p=window.ATLAS_PRODUCTION_DECISION;
    if(!p||typeof p!=='object')return;
    applying=true;
    try{
      const threshold=finite(p.signal_threshold)?fmt(p.signal_threshold,0):'68';
      const score=finite(p.score)?fmt(p.score,0):'—';
      set('apsConfidence',`${score}/${threshold}`);

      if(!finite(p.score)){
        const reason=String(p.wait_reason||p.opportunity_state_reason||'NOT SCORED').replace(/_/g,' ');
        set('apsStructure',`${reason} · score —/${threshold}`);
        set('apsWhy',`Production WAIT. Score unavailable because no directional Production candidate was scored. Reason: ${reason}.`);
      }

      const plan=p.trade_plan||{};
      const rr=plan.rr_tp2??p.risk_reward;
      if(!finite(rr)){
        const bits=['No Production trade geometry · R:R unavailable'];
        const obstacle=p.score_attribution?.obstacle_adjustment;
        if(finite(obstacle)&&Number(obstacle)<0)bits.push(`Obstacle penalty ${fmt(obstacle,0)}`);
        if(p.futures_available===false)bits.push('Futures confirmation unavailable');
        set('apsRisks',bits.join(' · '));
      }
    }finally{applying=false;}
  }

  const observer=new MutationObserver(()=>queueMicrotask(apply));
  function boot(){
    apply();
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    setInterval(apply,1000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  window.ATLAS_NULL_DISPLAY_FIX={version:'V1_NULL_IS_NOT_ZERO',refresh:apply};
})();
