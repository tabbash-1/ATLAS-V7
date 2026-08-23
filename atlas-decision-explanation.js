(() => {
  const $=id=>document.getElementById(id);
  const clean=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const lower=v=>clean(v).toLowerCase();
  const arr=v=>Array.isArray(v)?v:[];
  const uniq=v=>[...new Set(v.filter(Boolean))];
  const master=()=>window.ATLAS_MASTER&&typeof window.ATLAS_MASTER==='object'?window.ATLAS_MASTER:null;
  const text=(id,f='')=>($(id)?.textContent||f).trim();

  function state(){
    return {
      regime:lower(text('apsRegime')),
      trend:lower(text('apsTrend')),
      momentum:lower(text('apsMomentum')),
      volume:lower(text('apsVolume')),
      structure:lower(text('apsStructure')),
      liquidity:lower(text('apsLiquidity')),
      notes:lower(text('masterNotes'))
    };
  }

  function supportSignals(){
    const s=state(),out=[];
    if(/trend up/.test(s.regime)) out.push('uptrend regime');
    if(/trend down/.test(s.regime)) out.push('downtrend regime');
    if(/bullish/.test(s.trend)) out.push('bullish trend');
    if(/bearish/.test(s.trend)) out.push('bearish trend');
    if(/bullish/.test(s.momentum)) out.push('bullish momentum');
    if(/bearish/.test(s.momentum)) out.push('bearish momentum');
    if(/confirmed|strong/.test(s.volume)) out.push('strong volume confirmation');
    if(/above mean|breakout/.test(s.structure)) out.push('constructive structure');
    if(/below mean|breakdown/.test(s.structure)) out.push('weak structure');
    return uniq(out);
  }

  function cautionSignals(){
    const s=state(),out=[];
    if(/long crowding/.test(s.liquidity)) out.push('long crowding creates downside squeeze risk');
    if(/short crowding/.test(s.liquidity)) out.push('short crowding creates upside squeeze risk');
    if(/ask liquidity wall/.test(s.liquidity)) out.push('nearby ask liquidity can cap upside');
    if(/bid liquidity wall/.test(s.liquidity)) out.push('nearby bid liquidity can accelerate downside rejection');
    if(/futures conflict/.test(s.notes)) out.push('futures positioning conflicts with the spot setup');
    if(/overbought/.test(s.momentum)) out.push('momentum is overbought');
    if(/oversold/.test(s.momentum)) out.push('momentum is oversold');
    if(/normal|weak/.test(s.volume)) out.push('volume is not providing strong confirmation');
    if(/high volatility/.test(s.regime)) out.push('volatility is elevated');
    if(/mixed/.test(s.trend)) out.push('trend is mixed');
    if(/neutral/.test(s.momentum)) out.push('momentum is neutral');
    return uniq(out);
  }

  function blockers(){
    const m=master();
    const b=arr(m?.blockers).map(clean).filter(Boolean);
    const notes=lower(text('masterNotes'));
    if(/research only not validated/.test(notes)&&!b.some(x=>/research only/i.test(x))) b.push('research only not validated');
    if(/historical evidence not ready/.test(notes)&&!b.some(x=>/historical evidence/i.test(x))) b.push('historical evidence not ready');
    if(/no directional base signal/.test(notes)&&!b.some(x=>/directional base/i.test(x))) b.push('no directional base signal');
    return uniq(b);
  }

  function directionHint(){
    const s=state();
    if(/bullish/.test(s.trend)||/bullish/.test(s.momentum)||/trend up/.test(s.regime)) return 'LONG';
    if(/bearish/.test(s.trend)||/bearish/.test(s.momentum)||/trend down/.test(s.regime)) return 'SHORT';
    return 'directional';
  }

  function riskNarrative(cautions){
    const s=state();
    const risks=[];
    const portfolio=text('cmdRiskValue','');
    if(portfolio&&portfolio!=='—') risks.push(`Portfolio gate: ${clean(portfolio)}.`);
    if(/high volatility/.test(s.regime)) risks.push('High volatility increases stop-out and slippage risk.');
    if(/normal|weak/.test(s.volume)) risks.push('Volume confirmation is insufficient, so continuation risk is higher.');
    if(/long crowding/.test(s.liquidity)) risks.push('Long crowding raises the risk of a downside squeeze or liquidation cascade.');
    if(/short crowding/.test(s.liquidity)) risks.push('Short crowding raises the risk of an upside squeeze.');
    if(/ask liquidity wall/.test(s.liquidity)) risks.push('A nearby ask wall may limit upside follow-through.');
    if(/bid liquidity wall/.test(s.liquidity)) risks.push('A nearby bid wall may distort downside continuation.');
    if(/futures conflict/.test(s.notes)) risks.push('Futures positioning is not aligned with the spot setup.');
    if(/overbought/.test(s.momentum)) risks.push('Overbought momentum increases pullback risk.');
    if(/oversold/.test(s.momentum)) risks.push('Oversold momentum increases rebound risk.');
    if(!risks.length&&cautions.length) risks.push(cautions.join(' · ')+'.');
    if(!risks.length) risks.push('No exceptional live risk flag beyond the standard ATLAS risk gate.');
    return risks.join(' ');
  }

  function nextConditions(decision,blocks,cautions){
    const s=state();
    if(decision!=='WAIT'){
      return `Invalidate the ${decision} candidate if trend and momentum lose alignment, structure reverses, volume confirmation deteriorates, or liquidity/futures context turns adverse.`;
    }

    const side=directionHint();
    const must=[];
    if(/normal|weak/.test(s.volume)) must.push('volume strengthens from normal/weak to confirmed');
    if(/high volatility/.test(s.regime)) must.push('volatility remains controlled enough for the risk gate');
    if(/long crowding|short crowding|ask liquidity wall|bid liquidity wall/.test(s.liquidity)) must.push('adverse liquidity/crowding pressure clears');
    if(/futures conflict/.test(s.notes)) must.push('futures positioning realigns with spot');
    if(/mixed/.test(s.trend)) must.push('trend becomes clearly directional');
    if(/neutral/.test(s.momentum)) must.push('momentum becomes directional');
    if(side==='LONG') must.push('bullish trend, momentum and structure remain aligned');
    else if(side==='SHORT') must.push('bearish trend, momentum and structure remain aligned');
    else must.push('trend, momentum and structure align in one direction');

    const maturity=[];
    if(blocks.some(x=>/historical evidence/i.test(x))) maturity.push('historical evidence matures');
    if(blocks.some(x=>/research only/i.test(x))) maturity.push('research validation clears the research-only blocker');
    if(blocks.some(x=>/directional base/i.test(x))) maturity.push('a directional base signal appears');
    for(const b of blocks){
      if(!/historical evidence|research only|directional base/i.test(b)) maturity.push(clean(b));
    }

    let msg=`WAIT changes only if ${uniq(must).join('; ')}.`;
    if(maturity.length) msg+=` Validation gates still required: ${uniq(maturity).join('; ')}.`;
    return msg;
  }

  function explain(){
    if(!$('apsWhy')) return;
    const decision=text('apsDecision','WAIT').toUpperCase();
    const supports=supportSignals();
    const cautions=cautionSignals();
    const blocks=blockers();
    const score=clean(text('apsConfidence'))||'not scored';

    let why;
    if(decision==='LONG'||decision==='SHORT'){
      why=`${decision} candidate with setup score ${score}. Supporting evidence: ${supports.length?supports.join(', '):'directional alignment is active'}.`;
      if(cautions.length) why+=` Remaining cautions: ${cautions.join('; ')}.`;
    }else{
      why=`WAIT with setup score ${score}. ${supports.length?`Supporting evidence exists (${supports.join(', ')}), but it is not sufficient for execution.`:'No complete directional confirmation is active.'}`;
      if(cautions.length) why+=` Main cautions: ${cautions.join('; ')}.`;
      if(blocks.length) why+=` Active blockers: ${blocks.join('; ')}.`;
    }

    $('apsWhy').textContent=why;
    $('apsRisks').textContent=riskNarrative(cautions);
    $('apsChanges').textContent=nextConditions(decision,blocks,cautions);
  }

  let queued=false;
  const queue=()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;explain()})};
  new MutationObserver(queue).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','value','disabled']});
  window.addEventListener('atlas:product-shell-ready',queue);
  window.addEventListener('atlas:ai-ready',queue);
  setTimeout(queue,0);
  window.ATLAS_DECISION_EXPLANATION={refresh:explain};
})();
