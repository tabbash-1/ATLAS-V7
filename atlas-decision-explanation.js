(() => {
  const $=id=>document.getElementById(id);
  const clean=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const lower=v=>clean(v).toLowerCase();
  const arr=v=>Array.isArray(v)?v:[];
  const uniq=v=>[...new Set(v.filter(Boolean))];
  const master=()=>window.ATLAS_MASTER&&typeof window.ATLAS_MASTER==='object'?window.ATLAS_MASTER:null;
  const text=(id,f='')=>($(id)?.textContent||f).trim();

  function state(){return {regime:lower(text('apsRegime')),trend:lower(text('apsTrend')),momentum:lower(text('apsMomentum')),volume:lower(text('apsVolume')),structure:lower(text('apsStructure')),liquidity:lower(text('apsLiquidity')),notes:lower(text('masterNotes'))};}

  function supportSignals(){
    const s=state(),out=[];
    if(/trend up/.test(s.regime))out.push('uptrend regime');
    if(/trend down/.test(s.regime))out.push('downtrend regime');
    if(/bullish/.test(s.trend))out.push('bullish trend');
    if(/bearish/.test(s.trend))out.push('bearish trend');
    if(/bullish/.test(s.momentum))out.push('bullish momentum');
    if(/bearish/.test(s.momentum))out.push('bearish momentum');
    if(/confirmed|strong/.test(s.volume))out.push('strong volume confirmation');
    if(/above mean|breakout/.test(s.structure))out.push('constructive structure');
    if(/below mean|breakdown/.test(s.structure))out.push('weak structure');
    return uniq(out);
  }

  function cautionSignals(){
    const s=state(),out=[];
    if(/long crowding/.test(s.liquidity))out.push('long crowding creates downside squeeze risk');
    if(/short crowding/.test(s.liquidity))out.push('short crowding creates upside squeeze risk');
    if(/ask liquidity wall/.test(s.liquidity))out.push('nearby ask liquidity can cap upside');
    if(/bid liquidity wall/.test(s.liquidity))out.push('nearby bid liquidity can distort downside continuation');
    if(/futures conflict/.test(s.notes))out.push('futures positioning conflicts with the spot setup');
    if(/overbought/.test(s.momentum))out.push('momentum is overbought');
    if(/oversold/.test(s.momentum))out.push('momentum is oversold');
    if(/normal|weak/.test(s.volume))out.push('volume is not providing strong confirmation');
    if(/high volatility/.test(s.regime))out.push('volatility is elevated');
    if(/mixed/.test(s.trend))out.push('trend is mixed');
    if(/neutral/.test(s.momentum))out.push('momentum is neutral');
    return uniq(out);
  }

  function hardBlockers(){return uniq(arr(master()?.blockers).map(clean));}

  function validationStatus(){
    const m=master(); if(!m)return null;
    const h=m.historical||{};
    const n=Number(h.n||0);
    const label=clean(h.label||'INSUFFICIENT');
    const capital=clean(m.capital_status||'RESEARCH ONLY');
    return {n,label,capital,researchOnly:m.research_only!==false};
  }

  function directionHint(){const s=state();if(/bullish/.test(s.trend)||/bullish/.test(s.momentum)||/trend up/.test(s.regime))return'LONG';if(/bearish/.test(s.trend)||/bearish/.test(s.momentum)||/trend down/.test(s.regime))return'SHORT';return'directional';}

  function riskNarrative(cautions){
    const s=state(),risks=[]; const portfolio=text('cmdRiskValue','');
    if(portfolio&&portfolio!=='—')risks.push(`Portfolio gate: ${clean(portfolio)}.`);
    if(/high volatility/.test(s.regime))risks.push('High volatility increases stop-out and slippage risk.');
    if(/normal|weak/.test(s.volume))risks.push('Volume confirmation is insufficient, so continuation risk is higher.');
    if(/long crowding/.test(s.liquidity))risks.push('Long crowding raises downside squeeze or liquidation-cascade risk.');
    if(/short crowding/.test(s.liquidity))risks.push('Short crowding raises upside squeeze risk.');
    if(/ask liquidity wall/.test(s.liquidity))risks.push('A nearby ask wall may limit upside follow-through.');
    if(/bid liquidity wall/.test(s.liquidity))risks.push('A nearby bid wall may distort downside continuation.');
    if(/futures conflict/.test(s.notes))risks.push('Futures positioning is not aligned with the spot setup.');
    if(/overbought/.test(s.momentum))risks.push('Overbought momentum increases pullback risk.');
    if(/oversold/.test(s.momentum))risks.push('Oversold momentum increases rebound risk.');
    if(!risks.length&&cautions.length)risks.push(cautions.join(' · ')+'.');
    if(!risks.length)risks.push('No exceptional live risk flag beyond the standard ATLAS risk gate.');
    return risks.join(' ');
  }

  function nextConditions(decision,blocks,score){
    const s=state(),must=[]; const side=directionHint();
    if(decision!=='WAIT')return `Invalidate the ${decision} candidate if trend and momentum lose alignment, structure reverses, volume confirmation deteriorates, or liquidity/futures context turns adverse.`;
    if(score<82)must.push(`raise Master Conviction by ${82-score} points to the 82/100 candidate threshold`);
    if(/normal|weak/.test(s.volume))must.push('volume strengthens to confirmed');
    if(/high volatility/.test(s.regime))must.push('volatility remains controlled enough for the risk gate');
    if(/long crowding|short crowding|ask liquidity wall|bid liquidity wall/.test(s.liquidity))must.push('adverse liquidity/crowding pressure clears');
    if(/futures conflict/.test(s.notes))must.push('futures positioning realigns with spot');
    if(/mixed/.test(s.trend))must.push('trend becomes clearly directional');
    if(/neutral/.test(s.momentum))must.push('momentum becomes directional');
    if(side==='LONG')must.push('bullish trend, momentum and structure remain aligned');
    else if(side==='SHORT')must.push('bearish trend, momentum and structure remain aligned');
    else must.push('trend, momentum and structure align in one direction');
    if(blocks.length)must.push(`clear hard blocker${blocks.length>1?'s':''}: ${blocks.join(', ')}`);
    return `WAIT changes only if ${uniq(must).join('; ')}.`;
  }

  function explain(){
    if(!$('apsWhy'))return;
    const m=master(); const decision=text('apsDecision','WAIT').toUpperCase();
    const supports=supportSignals(),cautions=cautionSignals(),blocks=hardBlockers();
    const rawScore=Number(m?.score); const score=Number.isFinite(rawScore)?rawScore:Number(String(text('apsConfidence')).replace(/[^0-9.]/g,''))||0;
    const scoreLabel=Number.isFinite(score)?`${Math.round(score)}/100`:'not scored';
    const validation=validationStatus();

    let why;
    if(decision==='LONG'||decision==='SHORT'){
      why=`${decision} candidate with setup score ${scoreLabel}. Supporting evidence: ${supports.length?supports.join(', '):'directional alignment is active'}.`;
      if(cautions.length)why+=` Remaining cautions: ${cautions.join('; ')}.`;
    }else{
      why=`WAIT with setup score ${scoreLabel}. ${supports.length?`Supporting evidence exists (${supports.join(', ')}), but the Master Conviction threshold for a candidate is 82/100.`:'No complete directional confirmation is active.'}`;
      if(cautions.length)why+=` Main cautions: ${cautions.join('; ')}.`;
      if(blocks.length)why+=` Hard blockers: ${blocks.join('; ')}.`;
      else why+=' No hard decision blocker is active; this WAIT is score/evidence driven.';
    }
    if(validation?.researchOnly){why+=` Research status: ${validation.capital}; historical 24h sample n=${validation.n} (${validation.label}). This status limits validation/capital use, but it is not itself a hard decision blocker.`;}

    $('apsWhy').textContent=why;
    $('apsRisks').textContent=riskNarrative(cautions);
    $('apsChanges').textContent=nextConditions(decision,blocks,score);
  }

  let queued=false;const queue=()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;explain()})};
  new MutationObserver(queue).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','value','disabled']});
  window.addEventListener('atlas:product-shell-ready',queue);window.addEventListener('atlas:ai-ready',queue);setTimeout(queue,0);
  window.ATLAS_DECISION_EXPLANATION={refresh:explain};
})();
