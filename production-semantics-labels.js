(() => {
  const $ = id => document.getElementById(id);
  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const fmt = (v,d=2) => finite(v) ? Number(v).toLocaleString(undefined,{maximumFractionDigits:d}) : '—';
  const humanize = v => String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();

  function currentDecision(){
    return window.ATLAS_PRODUCTION_SNAPSHOT_GUARD?.current?.()
      || (window.ATLAS_PRODUCTION_DECISION && typeof window.ATLAS_PRODUCTION_DECISION === 'object'
        ? window.ATLAS_PRODUCTION_DECISION : null);
  }

  function regimeLabel(d){
    if(!d) return '—';
    const raw=String(d.regime||'').toUpperCase();
    const pb=String(d.playbook_primary||'').toUpperCase();
    const dir=String(d.candidate_direction||'').toUpperCase();
    const votes=finite(d.direction_votes)?Number(d.direction_votes):null;
    if(raw==='TREND_UP' && dir==='LONG'){
      if(pb.includes('PULLBACK_LONG')) return `LONG BIAS · PULLBACK${votes!=null?` · ${votes}/4 votes`:''}`;
      return `TREND UP · LONG BIAS${votes!=null?` · ${votes}/4 votes`:''}`;
    }
    if(raw==='TREND_DOWN' && dir==='SHORT'){
      if(pb.includes('PULLBACK_SHORT')) return `SHORT BIAS · PULLBACK${votes!=null?` · ${votes}/4 votes`:''}`;
      return `TREND DOWN · SHORT BIAS${votes!=null?` · ${votes}/4 votes`:''}`;
    }
    return humanize(d.regime||d.candidate_direction||'MIXED').toUpperCase();
  }

  function riskLabel(d){
    if(!d) return null;
    const p=d.trade_plan||{};
    const bits=[];
    if(d.geometry_gate?.status==='BLOCK') bits.push(`Current geometry blocked: ${humanize(d.geometry_gate.reason)}`);
    if(finite(p.rr_tp2)) bits.push(`Canonical Production R:R ${fmt(p.rr_tp2,2)}`);
    else if(finite(d.risk_reward)) bits.push(`Candidate / qualification R:R ${fmt(d.risk_reward,2)}`);
    const obstacle=Number(d.score_attribution?.obstacle_adjustment);
    if(Number.isFinite(obstacle)&&obstacle<0) bits.push(`Obstacle penalty ${fmt(obstacle,0)}`);
    if(d.futures_available===false) bits.push('Futures confirmation unavailable');
    return bits.length?bits.join(' · '):null;
  }

  function geometryLabel(d){
    if(!d) return null;
    const p=d.trade_plan||{};
    if(p.entry!=null) return null;
    if(finite(d.risk_reward)) return `Candidate geometry R:R ${fmt(d.risk_reward,2)} failed the execution gate · no canonical Production trade plan`;
    return 'No canonical Production trade geometry';
  }

  function apply(){
    const d=currentDecision();
    if(!d||d.ok===false) return;
    const regime=regimeLabel(d);
    if($('apsRegime') && $('apsRegime').textContent!==regime) $('apsRegime').textContent=regime;
    const commandRegime=$('cmdRegimeValue');
    if(commandRegime && commandRegime.textContent!==regime) commandRegime.textContent=regime;
    const risks=riskLabel(d);
    if(risks && $('apsRisks') && $('apsRisks').textContent!==risks) $('apsRisks').textContent=risks;
    const geometry=geometryLabel(d);
    if(geometry && $('apsAiGeometry') && $('apsAiGeometry').textContent!==geometry) $('apsAiGeometry').textContent=geometry;
  }

  let queued=false;
  function queueApply(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{queued=false;apply();});
  }

  function boot(){
    apply();
    const shell=$('atlasProductShell');
    if(shell && shell.dataset.productionSemanticsLabels!=='1'){
      shell.dataset.productionSemanticsLabels='1';
      new MutationObserver(queueApply).observe(shell,{subtree:true,childList:true,characterData:true});
    }
    window.addEventListener('atlas:ai-ready',queueApply);
    window.addEventListener('atlas:production-updated',queueApply);
  }

  window.ATLAS_PRODUCTION_SEMANTICS={apply,regimeLabel,riskLabel,geometryLabel};
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,700),{once:true});
  else setTimeout(boot,700);
})();
