(() => {
const $=id=>document.getElementById(id);
const f=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
function render(plan){
 const badge=$('tradeMgmtBadge'),grid=$('tradeMgmtMetrics'),note=$('tradeMgmtNotes');if(!badge||!grid)return;
 if(!plan?.available){badge.textContent='WAITING';badge.className='pill neutral';grid.innerHTML='<div><span>Status</span><b>No directional plan</b></div>';return;}
 badge.textContent=`${plan.quality_score}/100 ${plan.status}`;badge.className=`pill ${plan.status==='PLAN_READY'?'buy':plan.status.includes('NO_TRADE')?'sell':'working'}`;
 const items=[
  ['Direction',plan.direction],['Entry zone',`${f(plan.entry_zone_low,8)} → ${f(plan.entry_zone_high,8)}`],['Stop',`${f(plan.stop,8)} · ${plan.stop_source}`],
  ['TP1',f(plan.tp1,8)],['TP2',f(plan.tp2,8)],['R:R TP1',plan.rr_tp1],['R:R TP2',plan.rr_tp2],
  ['First obstacle',plan.first_obstacle?`${plan.first_obstacle.type} · ${f(plan.first_obstacle.price,8)} · ${f(plan.first_obstacle.strength,0)}/100`:'—'],
  ['Plan quality',`${plan.quality_score}/100`]
 ];
 grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
 if(note)note.innerHTML=`<div><b>After TP1:</b> ${plan.management.after_tp1}</div><div><b>Trailing:</b> ${plan.management.trailing}</div><div><b>Cautions:</b> ${(plan.cautions||[]).join(' · ')||'None'}</div><div class="muted tiny">Research-only plan. Not an execution instruction.</div>`;
}
window.refreshTradeManagement=function(base=null,confluence=null){
 const b=base||window.ATLAS_LATEST_BASE,c=confluence||window.ATLAS_LATEST_CONFLUENCE;
 const plan=ATLAS_TRADE_MANAGEMENT.buildTradePlan({base:b,confluence:c,liquidity:window.ATLAS_LIQUIDITY||null,final:window.ATLAS_MASTER||null});
 window.ATLAS_TRADE_PLAN=plan;render(plan);return plan;
};
async function runExitLab(){
 const btn=$('runExitLabBtn'),badge=$('exitLabBadge'),grid=$('exitLabMetrics'),meta=$('exitLabMeta');if(!btn||!grid)return;
 btn.disabled=true;badge.textContent='TESTING';badge.className='pill working';
 try{
  const state=window.ATLAS_APP_STATE,asset=state.assets[state.active],r=await fetchMarketCandles(asset,state.interval,state.apiKey);
  if(r.candles.length<130)throw new Error('Need at least 130 candles for Exit Lab.');
  const costBps=Number($('exitCostBps')?.value||20);const x=ATLAS_EXIT_LAB.runExitResearch(r.candles,{step:3,maxBars:24,costBps});window.ATLAS_EXIT_LAB_RESULT=x;
  const a=x.fixed_atr,b=x.sr_managed,d=x.delta;
  grid.innerHTML=[
   ['Trades',x.trades],['Fixed ATR avg R',a.avg_r],['S/R managed avg R',b.avg_r],['Δ avg R',d.avg_r],
   ['Fixed win rate',a.win_rate_pct==null?'—':`${a.win_rate_pct}%`],['Managed win rate',b.win_rate_pct==null?'—':`${b.win_rate_pct}%`],
   ['Δ win rate',d.win_rate_pct==null?'—':`${d.win_rate_pct}%`],['Δ total R',d.total_r]
  ].map(([k,v])=>`<div><span>${k}</span><b>${v??'—'}</b></div>`).join('');
  badge.textContent=x.trades?`${x.trades} TRADES`:'NO TRADES';badge.className=`pill ${d.avg_r>0?'buy':d.avg_r<0?'sell':'neutral'}`;
  meta.textContent=`${r.provider} · ${r.candles.length} candles · ${x.cost_bps} bps round-trip cost proxy · conservative same-bar stop priority.`;
 }catch(e){badge.textContent='ERROR';badge.className='pill sell';meta.textContent=e.message;}
 finally{btn.disabled=false;}
}
$('runExitLabBtn')?.addEventListener('click',runExitLab);
window.renderTradeManagement=render;
setTimeout(()=>window.refreshTradeManagement(),1700);
})();