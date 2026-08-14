(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('adaptiveForwardBadge'),grid=$('adaptiveForwardMetrics'),note=$('adaptiveForwardNotes');if(!grid)return;
 try{
  await fetch('/api/forward/update').catch(()=>null);
  const j=await fetch('/api/adaptive/forward-comparison?horizon=24').then(r=>r.json());
  const f=j.fixed||{},a=j.adaptive_shadow||{};
  grid.innerHTML=[
   ['Usable N',j.usable_n||0],['Fixed avg',f.avg_return_pct==null?'—':`${fmt(f.avg_return_pct)}%`],
   ['Adaptive avg',a.avg_return_pct==null?'—':`${fmt(a.avg_return_pct)}%`],
   ['Δ weighted avg',j.delta_avg_weighted_return_pct==null?'—':`${fmt(j.delta_avg_weighted_return_pct)}%`],
   ['Fixed DD',fmt(f.max_drawdown_proxy)],['Adaptive DD',fmt(a.max_drawdown_proxy)],
   ['DD improvement',fmt(j.drawdown_improvement_proxy)],['Fixed risk-adj',fmt(j.fixed_risk_adjusted_proxy)],
   ['Adaptive risk-adj',fmt(j.adaptive_risk_adjusted_proxy)],['Risk-adj Δ',fmt(j.risk_adjusted_delta)]
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  note.innerHTML=`<div><b>Verdict:</b> ${j.verdict}</div><div class="muted tiny">Adaptive sizing remains frozen shadow research. It does not alter Portfolio Risk or execution in Alpha 21.</div>`;
  badge.textContent=j.verdict;badge.className=`pill ${j.verdict==='ADAPTIVE_LEADING_SHADOW'?'buy':j.verdict==='FIXED_LEADING'?'sell':'neutral'}`;
  window.ATLAS_ADAPTIVE_FORWARD=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('adaptiveForwardRefreshBtn')?.addEventListener('click',refresh);
window.refreshAdaptiveForwardComparison=refresh;
setTimeout(refresh,6100);setInterval(refresh,180000);
})();