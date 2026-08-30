(() => {
  const VERSION='ATLAS_PRODUCTION_UI_AUTHORITY_V1';
  const PROD_TF='1H';
  const $=id=>document.getElementById(id);
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=2)=>finite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const norm=v=>String(v||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  const human=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  let rendering=false;
  let queued=false;

  function currentSymbol(){
    const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active],raw=norm(a?.symbol);
    if(raw)return raw;
    const t=($('activeTitle')?.textContent||'').toUpperCase();
    for(const x of ['BTC','ETH','SOL','XRP','BNB','DOGE','ZEC','HYPE'])if(t.includes(x))return x+'USDT';
    return '';
  }
  function snapshot(){
    const g=window.ATLAS_PRODUCTION_SNAPSHOT_GUARD;
    const d=g?.current?.();
    if(!d||!d.ok)return null;
    if(norm(g?.symbol?.())!==currentSymbol())return null;
    return d;
  }
  function state(d){
    const p=d?.trade_plan||{};
    if(p.status==='ACTIONABLE'&&d?.production_signal_qualified&&d?.execution_ready)return 'ACTIONABLE';
    if(p.status==='CONDITIONAL'&&d?.production_signal_qualified)return 'ARMED';
    return 'WAIT';
  }
  function set(id,value){const el=$(id);if(el&&el.textContent!==String(value))el.textContent=String(value);}
  function ensureContextLabel(){
    const tf=$('apsTimeframe');if(!tf)return;
    if(!tf.dataset.researchLabelled){tf.dataset.researchLabelled='1';tf.setAttribute('aria-label','Research chart timeframe');}
    let note=$('apsContextAuthority');
    if(!note){
      note=document.createElement('div');note.id='apsContextAuthority';note.className='aps-note';
      note.style.flexBasis='100%';note.style.marginTop='6px';
      tf.closest('.aps-controls')?.appendChild(note);
    }
    const research=tf.options[tf.selectedIndex]?.textContent||tf.value||'—';
    note.textContent=`Research chart: ${research} · Canonical Production: ${PROD_TF}`;
  }
  function renderNoSnapshot(){
    set('apsDecision','WAIT');
    const de=$('apsDecision');if(de)de.className='aps-value wait';
    set('apsConfidence','—/68');set('apsEntry','—');set('apsStop','—');set('apsTarget','—');
    set('apsRegime','VERIFYING');set('apsTrend','—');set('apsMomentum','—');set('apsVolume','—');
    set('apsStructure','Production verification pending');
    set('apsStatus','Verifying canonical Production…');
    set('apsAiProd','WAIT');set('apsAiBest','WAIT');set('apsAiState','Waiting for canonical Production');
    set('apsWhy','No accepted Production snapshot for this asset yet.');
    set('apsRisks','Do not use local/research output as a Production trade decision.');
    set('apsChanges','Wait for the canonical Production verifier to finish.');
  }
  function render(){
    if(rendering)return;rendering=true;
    try{
      ensureContextLabel();
      const d=snapshot();if(!d){renderNoSnapshot();return;}
      const p=d.trade_plan||{},st=state(d),dir=p.direction||d.candidate_direction||'NONE';
      const score=finite(d.score)?Math.round(Number(d.score)):null;
      const threshold=finite(d.signal_threshold)?Math.round(Number(d.signal_threshold)):68;
      const actionable=st==='ACTIONABLE',armed=st==='ARMED';
      set('apsDecision',actionable?dir:'WAIT');
      const de=$('apsDecision');if(de)de.className='aps-value '+(actionable?dir.toLowerCase():'wait');
      set('apsConfidence',`${score===null?'—':score}/${threshold}`);
      set('apsEntry',actionable?fmt(p.entry,8):'—');
      set('apsStop',actionable?fmt(p.stop_loss,8):'—');
      set('apsTarget',actionable?`${fmt(p.tp2,8)}${finite(p.rr_tp2)?` · R:R ${fmt(p.rr_tp2,2)}`:''}`:'—');
      set('apsRegime',d.regime||'MIXED');
      set('apsTrend',d.candidate_direction||'NONE');
      set('apsMomentum',`Votes L${d.direction_votes_long??'—'}/S${d.direction_votes_short??'—'}`);
      set('apsVolume',d.relative_volume==null?'—':`RV ${fmt(d.relative_volume,2)}`);
      const reason=d.wait_reason||d.actionable_reason||d.playbook||'Production verified';
      set('apsStructure',`${human(reason)} · score ${score===null?'—':score}/${threshold} · Production ${PROD_TF}`);
      set('apsStatus',actionable?'Canonical Production trade plan ready':armed?'ARMED = wait for Production trigger':'WAIT = no trade now');
      set('apsAiProd',actionable?`${dir} · ${score===null?'—':score}/${threshold}`:armed?`ARMED · ${dir} · ${score===null?'—':score}/${threshold}`:`WAIT${score===null?'':` · ${score}/${threshold}`}`);
      set('apsAiBest',actionable?`${p.action||dir} NOW → ${dir}`:armed?`ARMED · ${human(p.action||'WAIT')} → ${dir}`:'WAIT');
      set('apsAiState',actionable?'Production canonical decision':armed?'ARMED — verified trigger defined':'WAIT');
      if(actionable){
        set('apsWhy',`Production ${dir} is qualified and execution geometry passed on the canonical ${PROD_TF} lane.`);
        set('apsChanges','Manage the canonical plan and reassess only if its structure is invalidated.');
      }else if(armed){
        set('apsWhy',`Production ${dir} reached ${score}/${threshold}, but entry is conditional; no immediate trade.`);
        set('apsChanges',p.entry_trigger||'Wait for the defined Production trigger.');
      }else{
        set('apsWhy',score===null?`Production WAIT: no directional consensus on the canonical ${PROD_TF} lane.`:`Production WAIT. Score ${score}/${threshold}. Reason: ${human(reason)}.`);
        const gap=Number(d.score_gap_to_signal);set('apsChanges',Number.isFinite(gap)&&gap>0?`Needs ${fmt(gap,0)} more score points or stronger geometry/evidence.`:'Wait for a qualified and executable Production setup.');
      }
      const risks=[];
      if(d.geometry_gate?.status==='BLOCK')risks.push(`Geometry: ${human(d.geometry_gate.reason)}`);
      if(finite(d.risk_reward))risks.push(`Candidate R:R ${fmt(d.risk_reward,2)}`);
      if(Number(d.score_attribution?.obstacle_adjustment)<0)risks.push(`Obstacle ${fmt(d.score_attribution.obstacle_adjustment,0)}`);
      set('apsRisks',risks.length?risks.join(' · '):'No additional canonical Production block.');
    } finally {rendering=false;}
  }
  function schedule(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;render();});}
  function install(){
    ensureContextLabel();render();
    const shell=$('atlasProductShell');if(shell&&!shell.dataset.singleAuthorityV1){
      shell.dataset.singleAuthorityV1='1';new MutationObserver(schedule).observe(shell,{subtree:true,childList:true,characterData:true});
    }
    const tf=$('apsTimeframe');tf?.addEventListener('change',()=>setTimeout(schedule,0));
    const interval=$('intervalSelect');interval?.addEventListener('change',()=>setTimeout(schedule,0));
    const title=$('activeTitle');if(title)new MutationObserver(()=>setTimeout(schedule,0)).observe(title,{subtree:true,childList:true,characterData:true});
    setInterval(schedule,1500);
    window.ATLAS_PRODUCTION_UI_AUTHORITY={version:VERSION,productionTimeframe:PROD_TF,render,snapshot,state};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(install,900),{once:true});else setTimeout(install,900);
})();
