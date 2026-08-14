(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('adaptiveBadge'),grid=$('adaptiveMetrics'),body=$('adaptiveBody'),note=$('adaptiveNotes');if(!grid||!body)return;
 try{
  const j=await fetch('/api/adaptive/edge-table?horizon=24&min_n=20').then(r=>r.json());
  grid.innerHTML=[
    ['Matured',j.matured||0],['Global avg',j.global?.avg_return_pct==null?'—':`${fmt(j.global.avg_return_pct)}%`],
    ['Global hit',j.global?.hit_rate_pct==null?'—':`${fmt(j.global.hit_rate_pct,1)}%`],
    ['Groups',j.groups?.length||0],['Applied to live risk','NO'],['Applied to score','NO']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const rows=j.groups||[];
  body.innerHTML=rows.length?rows.slice(0,20).map(x=>`<tr><td>${x.regime}</td><td>${x.playbook}</td><td>${x.n}</td><td>${fmt(x.avg_return_pct)}%</td><td>${fmt(x.recent_avg_return_pct)}%</td><td>${fmt(x.blended_hit_rate_pct,1)}%</td><td>${fmt(x.shadow_allocation_multiplier,2)}×</td><td>${x.status}</td></tr>`).join(''):'<tr><td colspan="8">Not enough matured data yet.</td></tr>';
  note.innerHTML=`<div><b>Status:</b> ${j.status}</div><div class="muted tiny">Allocation multipliers are shadow-only. Drift or degraded data quality can only reduce the shadow multiplier.</div>`;
  badge.textContent=j.status==='READY'?'SHADOW READY':'COLLECTING';badge.className=`pill ${j.status==='READY'?'working':'neutral'}`;
  window.ATLAS_ADAPTIVE=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('adaptiveRefreshBtn')?.addEventListener('click',refresh);
window.refreshAdaptiveEdge=refresh;
setTimeout(refresh,5600);setInterval(refresh,180000);
})();