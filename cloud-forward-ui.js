(() => {
const $=id=>document.getElementById(id),fmt=(v,d=0)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('cloudForwardBadge'),grid=$('cloudForwardMetrics'),note=$('cloudForwardNotes');if(!grid)return;
 try{
  const j=await fetch('/api/cloud-forward/status').then(r=>r.json());
  grid.innerHTML=[
   ['Enabled',j.enabled?'YES':'NO'],['Running now',j.running?'YES':'NO'],['Cycles',j.cycles||0],['Stored',j.stored||0],
   ['Deduped',j.deduped||0],['Errors',j.errors||0],['Interval',`${Math.round((j.interval_seconds||3600)/60)} min`],
   ['Min score',fmt(j.min_score,0)],['Max / cycle',j.max_per_cycle||0]
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const cs=(j.last_candidates||[]).map(x=>`${x.symbol} ${x.direction} ${x.score} · ${x.playbook||'NO_PLAYBOOK'}`).join('<br>')||'No stored candidate in the last cycle.';
  note.innerHTML=`<div><b>Last finish:</b> ${j.last_finished_at||'—'}</div><div><b>Last candidates:</b><br>${cs}</div><div><b>Last error:</b> ${j.last_error||'None'}</div><div class="muted tiny">Server-side research loop; no browser is required after cloud deployment.</div>`;
  badge.textContent=j.running?'RUNNING':j.enabled?'24/7 ENABLED':'DISABLED';
  badge.className=`pill ${j.enabled?'buy':'neutral'}`;
  window.ATLAS_CLOUD_FORWARD_STATUS=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
async function runNow(){
 const b=$('cloudForwardRunBtn');if(b)b.disabled=true;
 try{await fetch('/api/cloud-forward/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json());await refresh();if(window.refreshPerformanceDashboard)window.refreshPerformanceDashboard();}
 finally{if(b)b.disabled=false;}
}
$('cloudForwardRefreshBtn')?.addEventListener('click',refresh);
$('cloudForwardRunBtn')?.addEventListener('click',runNow);
window.refreshCloudForward=refresh;
setTimeout(refresh,4700);setInterval(refresh,120000);
})();