(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('canaryBadge'),grid=$('canaryMetrics'),note=$('canaryNotes');if(!grid)return;
 try{
  await fetch('/api/forward/update').catch(()=>null);
  const j=await fetch('/api/canary/report?horizon=24').then(r=>r.json());
  grid.innerHTML=[
   ['Eligible rows',j.eligible_rows||0],['Control N',j.control_n||0],['Canary N',j.canary_n||0],
   ['Observed Canary %',j.observed_canary_share_pct==null?'—':`${fmt(j.observed_canary_share_pct,1)}%`],
   ['Control avg',j.control_fixed?.avg_return_pct==null?'—':`${fmt(j.control_fixed.avg_return_pct)}%`],
   ['Canary avg',j.canary_applied_shadow?.avg_return_pct==null?'—':`${fmt(j.canary_applied_shadow.avg_return_pct)}%`],
   ['Paired Δ avg',j.paired_delta_avg_pct==null?'—':`${fmt(j.paired_delta_avg_pct)}%`],
   ['Paired risk-adj Δ',fmt(j.paired_risk_adjusted_delta)],
   ['Paired DD worsening',fmt(j.paired_drawdown_worsening)],
   ['Auto expansion','NO']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  note.innerHTML=`<div><b>Verdict:</b> ${j.verdict}</div><div><b>Safety:</b> Drift ${j.drift_status} · Data ${j.data_quality_status}</div><div><b>Next if pass:</b> ${j.next_step_if_pass}</div><div class="muted tiny">Canary remains shadow-only. Assignment is frozen and deterministic at entry; no automatic expansion or activation.</div>`;
  badge.textContent=j.verdict;badge.className=`pill ${j.verdict==='CANARY_PASS'?'buy':j.verdict==='CANARY_FAIL'?'sell':'neutral'}`;
  window.ATLAS_CANARY=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('canaryRefreshBtn')?.addEventListener('click',refresh);
window.refreshCanary=refresh;
setTimeout(refresh,7100);setInterval(refresh,180000);
})();