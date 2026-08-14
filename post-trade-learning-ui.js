(() => {
const $=id=>document.getElementById(id);
const fmt=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
function sym(){return String(window.ATLAS_STATE?.selectedAsset?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'').toUpperCase();}
function currentPayload(){
 const c=window.ATLAS_LATEST_CONFLUENCE||{}, f=window.ATLAS_LATEST_FUTURES||{}, l=window.ATLAS_LIQUIDITY||{}, a=window.ATLAS_ANOMALY_STATE||{}, m=window.ATLAS_MASTER||{}, p=window.ATLAS_TRADE_PLAN||{};
 const rows=window.ATLAS_OPPORTUNITY_ROWS||[],o=rows.find(x=>String(x.symbol||'')===sym())||{};
 return {
  symbol:sym(),base_signal:c.base_signal,signal:c.signal,confidence:c.confidence,gate_state:c.gate?.state,gate_reason:c.gate?.reason,
  support_strength:c.nearest_support?.strength,support_distance_pct:c.nearest_support?.distance_pct,
  resistance_strength:c.nearest_resistance?.strength,resistance_distance_pct:c.nearest_resistance?.distance_pct,
  relative_volume:c.volume?.relative_volume,volume_quality:c.volume?.quality_score,volume_flow:c.volume?.flow,
  breakout_score:c.breakout_up?.score,breakdown_score:c.breakout_down?.score,
  futures_score:f.score,futures_bias:f.bias,futures_crowding:f.crowding,futures_squeeze:f.squeeze,
  funding_rate:f.funding_rate,oi_change_pct:f.oi_change_pct,taker_ratio:f.taker_ratio,orderbook_imbalance:f.orderbook_imbalance,
  liquidity_score:l.score,anomaly_score:a.score,anomaly_level:a.level,master_score:m.score,master_decision:m.decision,
  trade_plan_status:p.status,trade_plan_quality:p.quality_score,rr_tp1:p.rr_tp1,rr_tp2:p.rr_tp2,
  first_obstacle_strength:p.first_obstacle?.strength,first_obstacle_type:p.first_obstacle?.type,
  regime:o.regime?.regime,relative_strength_score:o.relative?.score,opportunity_score:o.opp?.score
 };
}
async function refresh(){
 const badge=$('learningBadge'),grid=$('learningMetrics'),body=$('learningRulesBody'),note=$('learningNotes');if(!grid||!body)return;
 badge.textContent='LEARNING';badge.className='pill working';
 try{
  const symbol=sym();
  const [rules,assess]=await Promise.all([
   fetch(`/api/learning/failure-rules?symbol=${encodeURIComponent(symbol)}&horizon=24`).then(r=>r.json()),
   fetch('/api/learning/assess',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...currentPayload(),horizon:24})}).then(r=>r.json())
  ]);
  const b=rules.baseline||{},qualified=rules.qualified_rules||[];
  grid.innerHTML=[
   ['Matured setups',rules.matured_directional_setups||0],['Baseline hit',b.hit_rate_pct==null?'—':`${fmt(b.hit_rate_pct)}%`],
   ['Baseline avg 24h',b.avg_directional_return_pct==null?'—':`${fmt(b.avg_directional_return_pct,3)}%`],
   ['Qualified failure rules',qualified.length],['Current shadow penalty',`${fmt(assess.shadow_penalty,2)} pts`],
   ['Applied to Final Score','NO']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  body.innerHTML=qualified.length?qualified.slice(0,12).map(x=>`<tr><td>${x.tag}</td><td>${x.n}</td><td>${fmt(x.hit_rate_pct)}%</td><td>${fmt(x.baseline_hit_rate_pct)}%</td><td>${fmt(x.avg_directional_return_pct,3)}%</td><td>${x.stable_across_halves?'YES':'NO'}</td><td>${x.promotion_ready?'CANDIDATE':'SHADOW'}</td><td>${fmt(x.shadow_penalty,2)}</td></tr>`).join(''):'<tr><td colspan="8">No statistically mature failure rule yet.</td></tr>';
  const matched=assess.matched_rules||[], selected=assess.selected_nonoverlapping_rules||[];
  note.innerHTML=`<div><b>Current tags:</b> ${(assess.current_tags||[]).join(' · ')||'None'}</div><div><b>Matched learned risks:</b> ${matched.map(x=>x.tag).join(' · ')||'None'}</div><div><b>Non-overlapping penalties used in shadow:</b> ${selected.map(x=>`${x.tag} (-${x.shadow_penalty})`).join(' · ')||'None'}</div><div class="muted tiny">Shadow only. Rules must also pass split-half stability before they can even become promotion candidates.</div>`;
  badge.textContent=qualified.length?`${qualified.length} RULES · SHADOW`:'COLLECTING';badge.className=`pill ${qualified.length?'working':'neutral'}`;
  window.ATLAS_LEARNING={rules,assessment:assess};
 }catch(e){
  badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;
 }
}
$('learningRefreshBtn')?.addEventListener('click',refresh);
window.refreshPostTradeLearning=refresh;
setTimeout(refresh,2600);
})();
