(() => {
const $=id=>document.getElementById(id),fmt=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
function currentContext(){
 const state=window.ATLAS_APP_STATE||{},asset=state.assets?.[state.active],sym=String(asset?.symbol||'').replace(/^BINANCE:/,'');
 const row=(window.ATLAS_OPPORTUNITY_ROWS||[]).find(x=>x.symbol===sym);
 return row||{base:window.ATLAS_LATEST_BASE,confluence:window.ATLAS_LATEST_CONFLUENCE,futures:window.ATLAS_LATEST_FUTURES,liquidity:window.ATLAS_LIQUIDITY,
  anomaly:window.ATLAS_ANOMALY_STATE,plan:window.ATLAS_TRADE_PLAN,final:window.ATLAS_MASTER};
}
function render(){
 const x=ATLAS_PLAYBOOK.detectPlaybooks(currentContext());window.ATLAS_CURRENT_PLAYBOOK=x;
 const badge=$('playbookBadge'),grid=$('playbookMetrics'),note=$('playbookNotes');
 if(!badge||!grid)return;
 if(!x.available){badge.textContent='NO PLAYBOOK';badge.className='pill neutral';grid.innerHTML='<div><span>Status</span><b>No current playbook match</b></div>';return;}
 const p=x.primary;
 badge.textContent=`${p.id} ${p.score}/100`;badge.className='pill working';
 grid.innerHTML=[
  ['Primary',p.id],['Score',`${p.score}/100`],['Bias',p.bias],['Matches',x.playbooks.length],
  ['Management',p.management],['Avoid',p.avoid?.join(' · ')||'—']
 ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
 note.innerHTML=`<div><b>Why:</b> ${(p.why||[]).join(' · ')}</div><div><b>All matches:</b> ${x.playbooks.map(y=>`${y.id} (${y.score})`).join(' · ')}</div><div class="muted tiny">Playbook labels are hypotheses; they do not alter Final Score.</div>`;
}
async function stats(){
 const body=$('playbookStatsBody'),meta=$('playbookStatsMeta');if(!body)return;
 try{
  await fetch('/api/forward/update',{method:'POST'}).catch(()=>null);
  const j=await fetch('/api/playbooks/stats?horizon=24').then(r=>r.json());
  const rows=j.playbooks||[];
  body.innerHTML=rows.length?rows.map(x=>`<tr><td>${x.playbook}</td><td>${x.n}</td><td>${x.hit_rate_pct==null?'—':fmt(x.hit_rate_pct)+'%'}</td><td>${x.avg_return_pct==null?'—':fmt(x.avg_return_pct,3)+'%'}</td><td>${x.profit_factor_proxy==null?'—':fmt(x.profit_factor_proxy,2)}</td><td>${x.max_drawdown_proxy==null?'—':fmt(x.max_drawdown_proxy,3)}</td></tr>`).join(''):'<tr><td colspan="6">No matured playbook observations yet.</td></tr>';
  meta.textContent=`${j.matured_observations||0} matured forward observations · early read ≥${j.minimum_for_early_read} per playbook · stronger read ≥${j.minimum_for_stronger_read}.`;
 }catch(e){meta.textContent=e.message;}
}
$('playbookRefreshBtn')?.addEventListener('click',()=>{render();stats();});
window.refreshPlaybookResearch=render;
setTimeout(()=>{render();stats();},3900);
})();