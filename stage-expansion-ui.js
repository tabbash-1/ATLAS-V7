(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(apply=false){
 const badge=$('stageBadge'),grid=$('stageMetrics'),body=$('stageBody'),note=$('stageNotes');if(!grid||!body)return;
 try{
  let j;
  if(apply) j=await fetch('/api/canary/stages/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({horizon:24})}).then(r=>r.json());
  else j=await fetch('/api/canary/stages?horizon=24').then(r=>r.json());
  const cur=j.current_stage_report||{};
  grid.innerHTML=[
   ['Active stage',`${j.active_stage_pct}%`],['Current verdict',cur.verdict||'—'],['Recommended',`${j.recommended_stage_pct}%`],
   ['Action',j.recommended_action],['Canary N',cur.canary_n||0],['Control N',cur.control_n||0],
   ['Paired Δ avg',cur.paired_delta_avg_pct==null?'—':`${fmt(cur.paired_delta_avg_pct)}%`],
   ['Risk-adj Δ',fmt(cur.paired_risk_adjusted_delta)],['DD worsening',fmt(cur.paired_dd_worsening)],
   ['Safety hold',j.safety_hold?'YES':'NO']
  ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const rows=Object.values(j.stage_reports||{});
  body.innerHTML=rows.map(x=>`<tr><td>${x.stage_pct}%</td><td>${x.canary_n}</td><td>${x.control_n}</td><td>${x.paired_delta_avg_pct==null?'—':fmt(x.paired_delta_avg_pct)+'%'}</td><td>${fmt(x.paired_risk_adjusted_delta)}</td><td>${fmt(x.paired_dd_worsening)}</td><td>${x.verdict}</td></tr>`).join('')||'<tr><td colspan="7">No stage data yet.</td></tr>';
  note.innerHTML=`<div><b>State:</b> ${j.state?.status||'—'}</div><div><b>Safety:</b> Drift ${j.drift_status} · Data ${j.data_quality_status}</div><div><b>Transitions:</b> ${(j.state?.transitions||[]).slice(-5).map(x=>`${x.from}%→${x.to}% ${x.action}`).join(' · ')||'None'}</div><div class="muted tiny">Expansion/rollback is automatic only inside Shadow research. Live activation remains impossible.</div>`;
  badge.textContent=`STAGE ${j.active_stage_pct}% · ${j.recommended_action}`;
  badge.className=`pill ${j.recommended_action==='ROLLBACK'?'sell':j.recommended_action==='EXPAND'?'buy':'neutral'}`;
  window.ATLAS_STAGE_EXPANSION=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('stageRefreshBtn')?.addEventListener('click',()=>refresh(false));
$('stageApplyBtn')?.addEventListener('click',()=>refresh(true));
window.refreshStageExpansion=()=>refresh(false);
setTimeout(()=>refresh(false),7600);setInterval(()=>refresh(false),180000);
})();