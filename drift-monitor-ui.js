(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
function classifyQuality(q){
 const issues=q?.issues||[];
 const hard=Boolean((q?.missing_entry||0)>0 || (q?.missing_direction||0)>0 || (q?.duplicate_buckets||0)>0 || (q?.stale_smart_money||[]).length>0);
 const onlySample=issues.length>0 && issues.every(x=>/^insufficient (forward sample|core smart-money coverage)/i.test(String(x)));
 if(hard) return {label:'DATA DEGRADED',tone:'sell',kind:'DEGRADED'};
 if(onlySample || (q?.forward_rows||0)<30) return {label:'COLLECTING',tone:'working',kind:'COLLECTING'};
 if(q?.status==='WATCH') return {label:'WATCH',tone:'working',kind:'WATCH'};
 if(q?.status==='HEALTHY') return {label:'STABLE',tone:'buy',kind:'HEALTHY'};
 return {label:'COLLECTING',tone:'working',kind:'COLLECTING'};
}
async function refresh(){
 const badge=$('driftBadge'),grid=$('driftMetrics'),note=$('driftNotes'),body=$('driftPlaybookBody');
 if(!grid||!body)return;
 try{
  const [q,d]=await Promise.all([
   fetch('/api/data-quality',{cache:'no-store'}).then(r=>r.json()),
   fetch('/api/drift?horizon=24&recent=30&prior=60',{cache:'no-store'}).then(r=>r.json())
  ]);
  const qc=classifyQuality(q);
  grid.innerHTML=[
   ['Data quality',`${q.quality_score}/100`],['Research state',qc.kind],['Forward rows',q.forward_rows||0],
   ['Smart-money rows',q.smart_money_rows||0],['Drift status',d.status],['Recent avg',d.recent?.avg_return_pct==null?'—':`${fmt(d.recent.avg_return_pct)}%`],
   ['Prior avg',d.prior?.avg_return_pct==null?'—':`${fmt(d.prior.avg_return_pct)}%`],
   ['Δ expectancy',d.avg_delta_pct==null?'—':`${fmt(d.avg_delta_pct)}%`],
   ['Δ hit rate',d.hit_delta_pct==null?'—':`${fmt(d.hit_delta_pct,2)}%`],
   ['Recommendation',d.recommendation||'—']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const p=d.playbook_drift||{};
  const rows=Object.entries(p).map(([k,v])=>({name:k,...v})).sort((a,b)=>(a.drift==='NEGATIVE'?-1:1)-(b.drift==='NEGATIVE'?-1:1));
  body.innerHTML=rows.length?rows.map(x=>`<tr><td>${x.name}</td><td>${x.recent?.n||0}</td><td>${x.prior?.n||0}</td><td>${x.recent?.avg_return_pct==null?'—':fmt(x.recent.avg_return_pct)+'%'}</td><td>${x.prior?.avg_return_pct==null?'—':fmt(x.prior.avg_return_pct)+'%'}</td><td>${x.avg_delta_pct==null?'—':fmt(x.avg_delta_pct)+'%'}</td><td>${x.drift}</td></tr>`).join(''):'<tr><td colspan="7">Not enough matured playbook data yet.</td></tr>';
  const alerts=(d.alerts||[]).join(' · ')||'None';
  const sampleIssues=(q.issues||[]).filter(x=>/^insufficient /i.test(String(x)));
  const hardIssues=(q.issues||[]).filter(x=>!/^insufficient /i.test(String(x)));
  note.innerHTML=`<div><b>Alerts:</b> ${alerts}</div><div><b>Collection:</b> ${sampleIssues.join(' · ')||'Sample thresholds reached'}</div><div><b>Integrity issues:</b> ${hardIssues.join(' · ')||'None'}</div><div class="muted tiny">Insufficient sample size is shown as COLLECTING, not as a production failure. Real integrity/staleness problems still surface as DATA DEGRADED.</div>`;
  if(d.status==='EDGE_RISK'){
    badge.textContent='EDGE RISK'; badge.className='pill sell';
  }else{
    badge.textContent=qc.label; badge.className=`pill ${qc.tone}`;
  }
  window.ATLAS_DRIFT={quality:q,drift:d,ui_quality:qc};
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('driftRefreshBtn')?.addEventListener('click',refresh);
window.refreshDriftMonitor=refresh;
setTimeout(refresh,5200);setInterval(refresh,180000);
})();