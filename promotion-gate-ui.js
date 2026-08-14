(() => {
const $=id=>document.getElementById(id),fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
async function refresh(){
 const badge=$('promotionGateBadge'),grid=$('promotionGateMetrics'),body=$('promotionGateBody'),note=$('promotionGateNotes');if(!grid||!body)return;
 try{
   const j=await fetch('/api/promotion-gate?horizon=24').then(r=>r.json());
   const a=j.adaptive||{},checks=a.checks||[];
   grid.innerHTML=[
    ['Overall',j.overall_status],['Adaptive',a.status||'—'],['Eligible rules',j.eligible_rules?.length||0],
    ['Data quality',j.data_quality?.status||'—'],['Drift',j.drift?.status||'—'],
    ['Auto activation','NO'],['Next step',j.next_step_if_eligible||'—']
   ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
   body.innerHTML=checks.length?checks.map(x=>`<tr><td>${x.name}</td><td>${x.passed?'PASS':'FAIL'}</td><td>${x.value==null?'—':typeof x.value==='object'?JSON.stringify(x.value):x.value}</td><td>${x.threshold==null?'—':x.threshold}</td><td>${x.detail==null?'—':typeof x.detail==='object'?JSON.stringify(x.detail):x.detail}</td></tr>`).join(''):'<tr><td colspan="5">No gate checks yet.</td></tr>';
   const eligible=(j.eligible_rules||[]).map(x=>x.tag).join(' · ')||'None';
   note.innerHTML=`<div><b>Eligible learned rules:</b> ${eligible}</div><div><b>Policy:</b> N≥${j.policy?.min_adaptive_n}, Δ expectancy≥${j.policy?.min_delta_avg_pct}, risk-adjusted Δ≥${j.policy?.min_risk_adjusted_delta}, quality≥${j.policy?.min_quality_score}</div><div class="muted tiny">Passing the gate means controlled canary eligibility only. Nothing is activated automatically.</div>`;
   badge.textContent=j.overall_status;badge.className=`pill ${j.overall_status==='PROMOTION_ELIGIBLE'?'buy':'neutral'}`;
   window.ATLAS_PROMOTION_GATE=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('promotionGateRefreshBtn')?.addEventListener('click',refresh);
window.refreshPromotionGate=refresh;
setTimeout(refresh,6600);setInterval(refresh,180000);
})();