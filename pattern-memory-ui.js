(() => {
  const $=id=>document.getElementById(id);
  const num=v=>v==null||Number.isNaN(Number(v))?'—':Number(v).toFixed(2);
  const pct=v=>v==null?'—':`${Number(v).toFixed(2)}%`;
  function normalizeSymbol(raw){ return String(raw||'BTCUSDT').replace(/^BINANCE:/,'').toUpperCase(); }
  function payloadFrom(symbol,price,r){
    return {
      symbol:normalizeSymbol(symbol), price,
      signal:r.signal, base_signal:r.base_signal, confidence:r.confidence,
      gate_state:r.gate?.state, gate_reason:r.gate?.reason,
      support_strength:r.nearest_support?.strength, support_distance_pct:r.nearest_support?.distance_pct,
      resistance_strength:r.nearest_resistance?.strength, resistance_distance_pct:r.nearest_resistance?.distance_pct,
      relative_volume:r.volume?.relative_volume, volume_zscore:r.volume?.volume_zscore,
      volume_trend_ratio:r.volume?.volume_trend_ratio, volume_flow:r.volume?.flow, volume_quality:r.volume?.quality_score,
      breakout_score:r.breakout_up?.score, breakout_state:r.breakout_up?.state,
      breakdown_score:r.breakout_down?.score, breakdown_state:r.breakout_down?.state
    };
  }
  async function post(path,payload){
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok) throw new Error((await r.json().catch(()=>({}))).error||`HTTP ${r.status}`);
    return r.json();
  }
  async function refreshMemory(symbol,currentPayload=null){
    const sym=normalizeSymbol(symbol);
    try{
      const stats=await fetch(`/api/confluence/memory-stats?symbol=${encodeURIComponent(sym)}`).then(r=>r.json());
      const obs=stats.observations||0, m=stats.matured||{};
      const badge=$('memoryBadge');
      if(badge){ badge.textContent=obs?'LEARNING':'WAITING'; badge.className=`pill ${obs?'working':'neutral'}`; }
      const grid=$('memoryMetrics');
      if(grid){
        const items=[['Observations',obs],['1h matured',m['1']||0],['4h matured',m['4']||0],['12h matured',m['12']||0],['24h matured',m['24']||0],['Status',(m['24']||0)>=100?'VALIDATION READY':(m['24']||0)>=30?'EARLY EDGE':'COLLECTING']];
        grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
      }
      const rows=(stats.setups||[]).slice(0,6);
      const box=$('memorySetupStats');
      if(box) box.innerHTML=rows.length?rows.map(x=>{ const h=x.horizons?.['24']||{}; return `<div class="v42-factor"><b>${x.setup}</b> · 24h n=${h.n||0} · hit=${pct(h.hit_rate_pct)} · avg=${pct(h.avg_directional_return_pct)}</div>`; }).join(''):'Waiting for matured setup outcomes.';
      if(currentPayload){
        const sim=await post('/api/confluence/similar',{...currentPayload,limit:20});
        const h=sim.horizons?.['24']||{};
        const sb=$('similarityResult');
        if(sb) sb.innerHTML=`<b>Pattern Memory:</b> ${sim.matches||0} similar matured setups · 24h hit ${pct(h.hit_rate_pct)} · avg directional return ${pct(h.avg_directional_return_pct)} <span class="muted">(research only)</span>`;
      }
    }catch(e){
      const badge=$('memoryBadge'); if(badge){ badge.textContent='OFFLINE'; badge.className='pill sell'; }
      const sb=$('similarityResult'); if(sb) sb.textContent='Pattern memory collector unavailable: '+e.message;
    }
  }
  window.recordConfluenceObservation=async function(asset,candles,r){
    const p=payloadFrom(asset?.symbol,candles?.at(-1)?.close,r);
    try{
      if(window.refreshFuturesIntelligence){
        const fx=await window.refreshFuturesIntelligence(r);
        if(fx?.futures){ Object.assign(p,{futures_score:fx.futures.score,futures_bias:fx.futures.bias,futures_crowding:fx.futures.crowding,futures_squeeze:fx.futures.squeeze,funding_rate:fx.futures.funding_rate,oi_change_pct:fx.futures.oi_change_pct,taker_ratio:fx.futures.taker_ratio,orderbook_imbalance:fx.futures.orderbook_imbalance,futures_alignment:fx.alignment?.state}); }
      }
      // Persist richer context for Alpha 13 failure attribution.
      const liq=window.ATLAS_LIQUIDITY||null, an=window.ATLAS_ANOMALY_STATE||null, m=window.ATLAS_MASTER||null, plan=window.ATLAS_TRADE_PLAN||null;
      const oppRows=window.ATLAS_OPPORTUNITY_ROWS||[], currentOpp=oppRows.find(x=>String(x.symbol||'')===p.symbol)||null;
      Object.assign(p,{
        liquidity_score:liq?.score, liquidity_long_pressure:liq?.liquidation_pressure?.long_pressure, liquidity_short_pressure:liq?.liquidation_pressure?.short_pressure,
        anomaly_score:an?.score, anomaly_level:an?.level, anomaly_bias:an?.bias,
        master_score:m?.score, master_decision:m?.decision,
        final_score:currentOpp?.final?.score, final_decision:currentOpp?.execution_decision||currentOpp?.final?.decision,
        trade_plan_status:plan?.status, trade_plan_quality:plan?.quality_score, rr_tp1:plan?.rr_tp1, rr_tp2:plan?.rr_tp2,
        first_obstacle_strength:plan?.first_obstacle?.strength, first_obstacle_type:plan?.first_obstacle?.type,
        regime:currentOpp?.regime?.regime, relative_strength_score:currentOpp?.relative?.score, opportunity_score:currentOpp?.opp?.score
      });
      await post('/api/confluence/observe',p);
    }catch(e){ console.warn('ATLAS pattern observation:',e.message); }
    await refreshMemory(p.symbol,p);
    if(window.refreshPostTradeLearning) setTimeout(()=>window.refreshPostTradeLearning(),100);
  };
  window.refreshAtlasPatternMemory=refreshMemory;
  setTimeout(()=>{
    const a=window.ATLAS_STATE?.selectedAsset;
    refreshMemory(a?.symbol||'BTCUSDT');
  },1200);
})();
