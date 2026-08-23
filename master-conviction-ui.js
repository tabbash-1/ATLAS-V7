(() => {
 const $=id=>document.getElementById(id); const fmt=v=>v==null?'—':Number(v).toFixed(0);
 function render(m){
   const badge=$('masterBadge'),grid=$('masterMetrics'),notes=$('masterNotes'); if(!badge||!grid||!m)return;
   const productDecision=/_CANDIDATE$/i.test(String(m.decision||''))?String(m.decision):'WAIT';
   badge.textContent=`${productDecision} · ${m.score}/100 ${m.tier}`; badge.className=`pill ${m.tier==='HIGH'?'buy':m.tier==='MEDIUM'?'working':'neutral'}`;
   const c=m.components||{};
   const items=[['Master decision',m.decision],['Conviction',`${m.score}/100`],['Base',fmt(c.base)],['S/R + confluence',fmt(c.confluence)],['Volume',fmt(c.volume)],['Breakout/Breakdown',fmt(c.breakout_or_breakdown)],['Futures',fmt(c.futures)],['Liquidity',fmt(c.liquidity)],['Historical',fmt(c.historical)]];
   grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
   const productScore=$('apsConfidence');
   if(productScore){
     productScore.textContent=`${m.score}/100`;
     const label=productScore.parentElement?.querySelector('.aps-label');
     if(label) label.textContent='Setup score';
   }
   if(notes){
     const ok=(m.confirmations||[]).join(' · ')||'None yet';
     const caution=(m.cautions||[]).join(' · ')||'None';
     const block=(m.blockers||[]).join(' · ')||'None';
     notes.innerHTML=`<div><b>Confirmations:</b> ${ok}</div><div><b>Cautions:</b> ${caution}</div><div><b>Blockers:</b> ${block}</div><div class="muted tiny">${m.capital_status} · Historical evidence is sample-size weighted.</div>`;
   }
 }
 window.renderMasterConviction=render;
 window.computeMasterConviction=async function(base,confluence,symbol){
   let futures=window.ATLAS_LATEST_FUTURES||null, similarity=null;
   try{
     const p={symbol:String(symbol||'BTCUSDT').replace(/^BINANCE:/,''),signal:confluence.signal,base_signal:confluence.base_signal,confidence:confluence.confidence,gate_state:confluence.gate?.state,gate_reason:confluence.gate?.reason,support_strength:confluence.nearest_support?.strength,support_distance_pct:confluence.nearest_support?.distance_pct,resistance_strength:confluence.nearest_resistance?.strength,resistance_distance_pct:confluence.nearest_resistance?.distance_pct,relative_volume:confluence.volume?.relative_volume,volume_trend_ratio:confluence.volume?.volume_trend_ratio,volume_quality:confluence.volume?.quality_score,breakout_score:confluence.breakout_up?.score,breakdown_score:confluence.breakdown_down?.score,futures_score:futures?.score,oi_change_pct:futures?.oi_change_pct,taker_ratio:futures?.taker_ratio,orderbook_imbalance:futures?.orderbook_imbalance,limit:30};
     const r=await fetch('/api/confluence/similar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}); if(r.ok) similarity=await r.json();
   }catch(e){console.warn('Master similarity unavailable',e.message);}
   const liquidity=window.refreshLiquidityIntelligence?window.refreshLiquidityIntelligence(confluence):(window.ATLAS_LIQUIDITY||null);
   const m=analyzeMasterConviction({base,confluence,futures,liquidity,similarity}); window.ATLAS_MASTER=m; render(m); return m;
 };
})();
