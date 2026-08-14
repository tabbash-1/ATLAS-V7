(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
function rowsHtml(rows){return (rows||[]).slice(0,12).map(x=>`<tr><td>${x.group}</td><td>${x.n}</td><td>${x.hit_rate_pct==null?'—':fmt(x.hit_rate_pct,1)+'%'}</td><td>${x.avg_return_pct==null?'—':fmt(x.avg_return_pct)+'%'}</td><td>${x.profit_factor_proxy==null?'—':fmt(x.profit_factor_proxy,2)}</td><td>${x.max_drawdown_proxy==null?'—':fmt(x.max_drawdown_proxy)}</td></tr>`).join('');}
async function refresh(){
 const badge=$('performanceBadge'),grid=$('performanceMetrics'),body=$('performanceBreakdownBody'),meta=$('performanceMeta');if(!grid||!body)return;
 badge.textContent='UPDATING';badge.className='pill working';
 try{
  await fetch('/api/forward/update',{method:'POST'}).catch(()=>null);
  const j=await fetch('/api/performance/dashboard?horizon=24').then(r=>r.json()),o=j.overall_champion||{};
  grid.innerHTML=[
   ['Matured',j.matured||0],['Hit rate',o.hit_rate_pct==null?'—':`${fmt(o.hit_rate_pct,1)}%`],['Avg 24h',o.avg_return_pct==null?'—':`${fmt(o.avg_return_pct)}%`],
   ['PF proxy',fmt(o.profit_factor_proxy,2)],['Total return proxy',fmt(o.total_return_proxy)],['Max DD proxy',fmt(o.max_drawdown_proxy)]
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const mode=$('performanceGroup')?.value||'by_symbol',rows=j[mode]||[];
  body.innerHTML=rows.length?rowsHtml(rows):'<tr><td colspan="6">No matured observations yet.</td></tr>';
  meta.textContent=`24h forward lab · ${j.matured||0} matured observations · research-only directional-return proxies, not realized P&L.`;
  badge.textContent=(j.matured||0)>=100?'MATURE DATA':(j.matured||0)>=30?'EARLY READ':'COLLECTING';badge.className=`pill ${(j.matured||0)>=100?'buy':'neutral'}`;
  window.ATLAS_PERFORMANCE=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';meta.textContent=e.message;}
}
$('performanceRefreshBtn')?.addEventListener('click',refresh);
$('performanceGroup')?.addEventListener('change',refresh);
window.refreshPerformanceDashboard=refresh;
setTimeout(refresh,4300);
})();