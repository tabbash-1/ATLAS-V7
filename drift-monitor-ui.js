(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('driftBadge'),grid=$('driftMetrics'),note=$('driftNotes'),body=$('driftPlaybookBody');
 if(!grid||!body)return;
 try{
  const [q,d]=await Promise.all([
   fetch('/api/data-quality').then(r=>r.json()),
   fetch('/api/drift?horizon=24&recent=30&prior=60').then(r=>r.json())
  ]);
  grid.innerHTML=[
   ['Data quality',`${q.quality_score}/100`],['Quality status',q.status],['Forward rows',q.forward_rows||0],
   ['Drift status',d.status],['Recent avg',d.recent?.avg_return_pct==null?'—':`${fmt(d.recent.avg_return_pct)}%`],
   ['Prior avg',d.prior?.avg_return_pct==null?'—':`${fmt(d.prior.avg_return_pct)}%`],
   ['Δ expectancy',d.avg_delta_pct==null?'—':`${fmt(d.avg_delta_pct)}%`],
   ['Δ hit rate',d.hit_delta_pct==null?'—':`${fmt(d.hit_delta_pct,2)}%`],
   ['Recommendation',d.recommendation||'—']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const p=d.playbook_drift||{};
  const rows=Object.entries(p).map(([k,v])=>({name:k,...v})).sort((a,b)=>(a.drift==='NEGATIVE'?-1:1)-(b.drift==='NEGATIVE'?-1:1));
  body.innerHTML=rows.length?rows.map(x=>`<tr><td>${x.name}</td><td>${x.recent?.n||0}</td><td>${x.prior?.n||0}</td><td>${x.recent?.avg_return_pct==null?'—':fmt(x.recent.avg_return_pct)+'%'}</td><td>${x.prior?.avg_return_pct==null?'—':fmt(x.prior.avg_return_pct)+'%'}</td><td>${x.avg_delta_pct==null?'—':fmt(x.avg_delta_pct)+'%'}</td><td>${x.drift}</td></tr>`).join(''):'<tr><td colspan="7">Not enough matured playbook data yet.</td></tr>';
  const alerts=(d.alerts||[]).join(' · ')||'None';
  note.innerHTML=`<div><b>Alerts:</b> ${alerts}</div><div><b>Data issues:</b> ${(q.issues||[]).join(' · ')||'None'}</div><div class="muted tiny">Drift is a warning layer only. It does not halt or change scoring automatically in Alpha 19.</div>`;
  badge.textContent=d.status==='EDGE_RISK'?'EDGE RISK':q.status==='DEGRADED'?'DATA DEGRADED':'STABLE';
  badge.className=`pill ${d.status==='EDGE_RISK'||q.status==='DEGRADED'?'sell':q.status==='WATCH'?'working':'buy'}`;
  window.ATLAS_DRIFT={quality:q,drift:d};
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('driftRefreshBtn')?.addEventListener('click',refresh);
window.refreshDriftMonitor=refresh;
setTimeout(refresh,5200);setInterval(refresh,180000);
})();