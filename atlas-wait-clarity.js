(() => {
  const VERSION='ATLAS_WAIT_CLARITY_V1';
  const $=id=>document.getElementById(id);
  const human=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const fmt=(v,d=2)=>finite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const set=(id,v)=>{const el=$(id);if(el)el.textContent=String(v??'—');};

  function snapshot(){
    const d=window.ATLAS_PRODUCTION_SNAPSHOT_GUARD?.current?.()||window.ATLAS_PRODUCTION_DECISION;
    const c=d?.canonical_decision;
    const a=d?.analyst_output;
    if(!d?.ok||c?.schema!=='ATLAS_CANONICAL_DECISION_TRUTH_V1'||c?.source_of_truth!=='FINAL_TRADE_GATE')return null;
    return {d,c,a};
  }

  function levelFrom(obj,keys){for(const k of keys){const v=obj?.[k];if(finite(v))return Number(v);}return null;}
  function nextRequirement(d,c,a){
    const raw=[c?.raw_wait_reason,c?.wait_reason,d?.final_trade_gate?.primary_blocker,...(d?.final_trade_gate?.blockers||[])].filter(Boolean).join(' ').toUpperCase();
    const items=[];
    if(raw.includes('HTF')||raw.includes('4H_12H')){
      const d4=human(d?.htf_4h_direction||d?.market_map?.['4H']?.direction||d?.timeframes?.['4H']?.direction||'');
      const d12=human(d?.htf_12h_direction||d?.market_map?.['12H']?.direction||d?.timeframes?.['12H']?.direction||'');
      items.push(`4H and 12H must align${d4||d12?` (now 4H ${d4||'—'} · 12H ${d12||'—'})`:''}`);
    }
    if(raw.includes('BREAKOUT')||raw.includes('CONFIRM')){
      const level=levelFrom(a,['structural_obstacle_price','breakout_level','trigger_price'])??levelFrom(d,['structural_obstacle_price','breakout_level','trigger_price']);
      const side=norm(d?.product_direction||d?.candidate_direction||a?.direction);
      if(level!==null)items.push(`1H must close and hold ${side==='SHORT'?'below':'above'} ${fmt(level,level>=100?2:6)}`);
      else items.push('1H must provide a confirmed structure break and hold');
    }
    if(raw.includes('1D_MACRO'))items.push('1D macro opposition must clear');
    const score=finite(c?.score)?Math.round(Number(c.score)):null,threshold=finite(c?.threshold)?Math.round(Number(c.threshold)):68;
    if(score!==null&&score<threshold)items.push(`Analysis score must reach ${threshold}/${threshold} (now ${score}/${threshold})`);
    if(!items.length)items.push(human(c?.raw_wait_reason||c?.wait_reason||a?.what_changes_status?.[0]||'New verified Final Trade Gate evidence is required'));
    return items.join(' · ');
  }

  function render(){
    const x=snapshot();if(!x)return;const {d,c,a}=x;
    const actionable=c?.trade_ready===true&&['LONG','SHORT'].includes(norm(c?.decision));
    const threshold=finite(c?.threshold)?Math.round(Number(c.threshold)):68;
    const score=finite(c?.score)?Math.round(Number(c.score)):null;
    if(!actionable){
      // A missing candidate score is not zero. Keep the UI semantically honest.
      set('apsConfidence',score===null?`N/A · threshold ${threshold}`:`${score}/${threshold}`);
      set('apsTrend',human(d?.product_direction||d?.candidate_direction||'UNRESOLVED'));
      set('apsChanges',nextRequirement(d,c,a));
      set('apsAiTrigger',nextRequirement(d,c,a));
      const quality=a?.data_degraded===true?'DEGRADED':human(a?.evidence_profile?.quality||'PASS');
      set('apsLiquidity',`Data quality: ${quality} · Trade setup: NOT READY`);
      const status=$('apsStatus');if(status)status.textContent=`WAIT · ${human(c?.wait_reason||c?.raw_wait_reason||'FINAL TRADE GATE')}`;
    } else {
      set('apsLiquidity',`Data quality: ${a?.data_degraded===true?'DEGRADED':human(a?.evidence_profile?.quality||'PASS')} · Trade setup: READY`);
    }
  }

  let queued=false;
  const queue=()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;render();});};
  new MutationObserver(queue).observe(document.body,{subtree:true,childList:true,characterData:true});
  window.addEventListener('atlas:product-shell-ready',queue);
  window.addEventListener('atlas:ai-ready',queue);
  setInterval(queue,1500);
  setTimeout(queue,0);
  window.ATLAS_WAIT_CLARITY={version:VERSION,refresh:render};
})();
