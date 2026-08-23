(() => {
  const $=id=>document.getElementById(id);
  const clean=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const lower=v=>clean(v).toLowerCase();
  const arr=v=>Array.isArray(v)?v:[];
  const master=()=>window.ATLAS_MASTER&&typeof window.ATLAS_MASTER==='object'?window.ATLAS_MASTER:null;
  const text=(id,f='')=>($(id)?.textContent||f).trim();

  function supportSignals(){
    const out=[];
    const regime=lower(text('apsRegime'));
    const trend=lower(text('apsTrend'));
    const momentum=lower(text('apsMomentum'));
    const volume=lower(text('apsVolume'));
    const structure=lower(text('apsStructure'));
    if(/trend up/.test(regime)) out.push('uptrend regime');
    if(/trend down/.test(regime)) out.push('downtrend regime');
    if(/bullish/.test(trend)) out.push('bullish trend');
    if(/bearish/.test(trend)) out.push('bearish trend');
    if(/bullish/.test(momentum)) out.push('bullish momentum');
    if(/bearish/.test(momentum)) out.push('bearish momentum');
    if(/confirmed|strong/.test(volume)) out.push('volume confirmation');
    if(/above mean|breakout/.test(structure)) out.push('constructive structure');
    if(/below mean|breakdown/.test(structure)) out.push('weak structure');
    return [...new Set(out)];
  }

  function cautionSignals(){
    const out=[];
    const liq=lower(text('apsLiquidity'));
    const momentum=lower(text('apsMomentum'));
    const volume=lower(text('apsVolume'));
    const regime=lower(text('apsRegime'));
    if(/long crowding/.test(liq)) out.push('long crowding creates downside squeeze risk');
    if(/short crowding/.test(liq)) out.push('short crowding creates upside squeeze risk');
    if(/ask liquidity wall/.test(liq)) out.push('nearby ask liquidity can cap upside');
    if(/bid liquidity wall/.test(liq)) out.push('nearby bid liquidity can support downside rejection');
    if(/futures conflict/.test(lower(text('masterNotes')))) out.push('futures context conflicts with the spot setup');
    if(/overbought/.test(momentum)) out.push('momentum is overbought');
    if(/oversold/.test(momentum)) out.push('momentum is oversold');
    if(/normal|weak/.test(volume)) out.push('volume is not providing strong confirmation');
    if(/high volatility/.test(regime)) out.push('volatility is elevated');
    return [...new Set(out)];
  }

  function blockers(){
    const m=master();
    const b=arr(m?.blockers).map(clean).filter(Boolean);
    const notes=lower(text('masterNotes'));
    if(/research only not validated/.test(notes)&&!b.some(x=>/research only/i.test(x))) b.push('research only not validated');
    if(/historical evidence not ready/.test(notes)&&!b.some(x=>/historical evidence/i.test(x))) b.push('historical evidence not ready');
    return [...new Set(b)];
  }

  function directionHint(){
    const s=supportSignals().join(' ');
    const trend=lower(text('apsTrend'));
    const momentum=lower(text('apsMomentum'));
    if(/bullish/.test(trend)||/bullish/.test(momentum)||/uptrend/.test(s)) return 'LONG';
    if(/bearish/.test(trend)||/bearish/.test(momentum)||/downtrend/.test(s)) return 'SHORT';
    return 'directional';
  }

  function explain(){
    if(!$('apsWhy')) return;
    const decision=text('apsDecision','WAIT').toUpperCase();
    const supports=supportSignals();
    const cautions=cautionSignals();
    const blocks=blockers();
    const score=clean(text('apsConfidence'))||'not scored';
    const side=directionHint();

    let why;
    if(decision==='LONG'||decision==='SHORT'){
      why=`${decision} candidate with setup score ${score}. Supporting evidence: ${supports.length?supports.join(', '):'directional alignment is active'}.`;
    }else{
      why=`WAIT with setup score ${score}. ${supports.length?`Supporting evidence exists (${supports.join(', ')}), but it is not sufficient for execution.`:'No complete directional confirmation is active.'}`;
      if(cautions.length) why+=` Main cautions: ${cautions.join('; ')}.`;
    }

    let risk=cautions.length?cautions.join(' · '):'No exceptional live risk flag beyond the standard ATLAS risk gate.';
    const portfolio=text('cmdRiskValue','');
    if(portfolio&&portfolio!=='—') risk=`Portfolio risk: ${clean(portfolio)} · ${risk}`;

    let next;
    if(decision==='WAIT'){
      const parts=[];
      if(blocks.length) parts.push(`remove blockers (${blocks.join(', ')})`);
      if(!supports.some(x=>/volume confirmation/.test(x))) parts.push('obtain stronger volume confirmation');
      if(cautions.some(x=>/crowding|liquidity|futures/.test(x))) parts.push('clear the adverse liquidity/futures context');
      parts.push(`maintain ${side==='directional'?'clear directional':side} alignment across trend, momentum and structure`);
      next=`WAIT changes only when ATLAS can ${parts.join('; ')}.`;
    }else{
      next=`Invalidate the ${decision} candidate if trend/momentum alignment breaks, structure reverses, or liquidity/futures context turns adverse.`;
    }

    $('apsWhy').textContent=why;
    $('apsRisks').textContent=risk;
    $('apsChanges').textContent=next;
  }

  let queued=false;
  const queue=()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;explain()})};
  new MutationObserver(queue).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','value','disabled']});
  window.addEventListener('atlas:product-shell-ready',queue);
  window.addEventListener('atlas:ai-ready',queue);
  setTimeout(queue,0);
  window.ATLAS_DECISION_EXPLANATION={refresh:explain};
})();
