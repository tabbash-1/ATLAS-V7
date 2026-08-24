(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
function sym(){return String(window.ATLAS_STATE?.selectedAsset?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'').toUpperCase();}
function payload(){
 const c=window.ATLAS_LATEST_CONFLUENCE||{},f=window.ATLAS_LATEST_FUTURES||{},l=window.ATLAS_LIQUIDITY||{},a=window.ATLAS_ANOMALY_STATE||{},m=window.ATLAS_MASTER||{},p=window.ATLAS_TRADE_PLAN||{};
 const direction=p.direction||m.direction;if(!p.available||!['LONG','SHORT'].includes(direction))return null;
 return {symbol:sym(),direction,entry:p.entry,champion_score:m.score||0,champion_take:(m.score||0)>=60,
   trade_plan_status:p.status,rr_tp1:p.rr_tp1,rr_tp2:p.rr_tp2,anomaly_score:a.score,futures_score:f.score,liquidity_score:l.score,
   volume_quality:c.volume?.quality_score,relative_volume:c.volume?.relative_volume,
   base_signal:c.base_signal,signal:c.signal,resistance_strength:c.nearest_resistance?.strength,resistance_distance_pct:c.nearest_resistance?.distance_pct,
   support_strength:c.nearest_support?.strength,support_distance_pct:c.nearest_support?.distance_pct,breakout_score:c.breakout_up?.score,breakdown_score:c.breakout_down?.score,
   playbook_primary:window.ATLAS_CURRENT_PLAYBOOK?.primary?.id,playbook_score:window.ATLAS_CURRENT_PLAYBOOK?.primary?.score,
   playbook_all:(window.ATLAS_CURRENT_PLAYBOOK?.playbooks||[]).map(x=>x.id),
   funding_rate:f.funding_rate,oi_change_pct:f.oi_change_pct,taker_ratio:f.taker_ratio,orderbook_imbalance:f.orderbook_imbalance,futures_crowding:f.crowding,futures_squeeze:f.squeeze,
   relative_strength_score:(window.ATLAS_OPPORTUNITY_ROWS||[]).find(x=>x.symbol===sym())?.relative?.score};
}
async function stats(){
 const badge=$('forwardBadge'),grid=$('forwardMetrics'),note=$('forwardNotes');if(!grid)return;
 try{
  await fetch('/api/forward/update',{method:'POST'}).then(r=>r.json()).catch(()=>null);
  const j=await fetch(`/api/forward/stats?symbol=${encodeURIComponent(sym())}&horizon=24`).then(r=>r.json());
  grid.innerHTML=[
   ['Matured',j.matured_observations||0],['Research Champion N',j.champion?.n||0],['Research Challenger N',j.challenger?.n||0],
   ['Champion avg',j.champion?.avg_return_pct==null?'—':`${fmt(j.champion.avg_return_pct)}%`],
   ['Challenger avg',j.challenger?.avg_return_pct==null?'—':`${fmt(j.challenger.avg_return_pct)}%`],
   ['Δ expectancy',j.delta_avg_return_pct==null?'—':`${fmt(j.delta_avg_return_pct)}%`],
   ['Champion DD proxy',fmt(j.champion?.max_drawdown_proxy)],['Challenger DD proxy',fmt(j.challenger?.max_drawdown_proxy)],
   ['Avoided setups avg',j.avoided_by_challenger?.avg_return_pct==null?'—':`${fmt(j.avoided_by_challenger.avg_return_pct)}%`]
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  badge.textContent=j.verdict;badge.className=`pill ${j.verdict==='CHALLENGER_LEADING'?'buy':j.verdict==='CHAMPION_LEADING'?'sell':'neutral'}`;
  note.innerHTML=`<div><b>Research verdict:</b> ${j.verdict}</div><div class="muted tiny">Forward research observations only. Champion/Challenger uses the legacy Research /100 lane and never changes Production qualification (68-point Production score + Geometry Gate).</div>`;
  window.ATLAS_FORWARD_STATS=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
async function record(){
 const x=payload(),note=$('forwardNotes');if(!x){note.textContent='No valid current research trade plan to freeze.';return;}
 const r=await fetch('/api/forward/observe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(x)}).then(r=>r.json());
 note.innerHTML=`Frozen research observation ${r.symbol} ${r.direction}: Champion ${r.champion_score}/100 → Challenger ${r.challenger_score}/100; matched rules: ${(r.matched_promoted_tags||[]).join(' · ')||'none'}. Production qualification is separate.`;
 await stats();
}
$('forwardRecordBtn')?.addEventListener('click',record);
$('forwardRefreshBtn')?.addEventListener('click',stats);
window.refreshForwardComparison=stats;
setTimeout(stats,3500);
})();