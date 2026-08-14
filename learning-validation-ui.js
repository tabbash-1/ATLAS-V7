(() => {
const $=id=>document.getElementById(id);
const fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
function sym(){return String(window.ATLAS_STATE?.selectedAsset?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'').toUpperCase();}
async function refreshValidation(){
 const badge=$('validationBadge'),grid=$('validationMetrics'),body=$('validationRulesBody'),note=$('validationNotes');if(!grid||!body)return;
 badge.textContent='VALIDATING';badge.className='pill working';
 try{
   const j=await fetch(`/api/learning/validation?symbol=${encodeURIComponent(sym())}&horizon=24`).then(r=>r.json());
   const b=j.validation_baseline||{},c=j.combined_validation||{},k=c.kept_after_promoted_filters||{};
   grid.innerHTML=[
    ['Matured',j.matured||0],['Discovery N',j.discovery_n||0],['Validation N',j.validation_n||0],
    ['Candidates',j.candidate_rules||0],['Promoted',j.promoted_rules?.length||0],
    ['Validation avg',b.avg_return_pct==null?'—':`${fmt(b.avg_return_pct)}%`],
    ['Filtered avg',k.avg_return_pct==null?'—':`${fmt(k.avg_return_pct)}%`],
    ['Filtered max DD proxy',k.max_drawdown_proxy==null?'—':fmt(k.max_drawdown_proxy)],
    ['Kept fraction',c.kept_fraction_pct==null?'—':`${fmt(c.kept_fraction_pct,1)}%`]
   ].map(([a,v])=>`<div><span>${a}</span><b>${v}</b></div>`).join('');
   const rows=j.evaluated_rules||[];
   body.innerHTML=rows.length?rows.slice(0,15).map(x=>`<tr><td>${x.tag}</td><td>${x.discovery_n}</td><td>${x.validation_tagged?.n||0}</td><td>${fmt(x.validation_tagged?.avg_return_pct)}%</td><td>${fmt(x.validation_hit_drop_pct,2)}%</td><td>${x.stable_bad_out_of_sample?'YES':'NO'}</td><td>${x.filter_improves_out_of_sample?'YES':'NO'}</td><td>${x.promoted?'PROMOTED':'REJECTED/WAIT'}</td></tr>`).join(''):'<tr><td colspan="8">No validation candidates yet.</td></tr>';
   note.innerHTML=`<div><b>Status:</b> ${j.status}</div><div><b>Combined expectancy improved:</b> ${j.combined_improves_expectancy?'YES':'NO'}</div><div class="muted tiny">Chronological split only. Promotions remain shadow-only and still cannot change Final Score.</div>`;
   badge.textContent=(j.promoted_rules?.length||0)?`${j.promoted_rules.length} PROMOTED · SHADOW`:j.status==='INSUFFICIENT_FOR_DISCOVERY_VALIDATION'?'COLLECTING':'NO PROMOTION';
   badge.className=`pill ${(j.promoted_rules?.length||0)?'buy':'neutral'}`;
   window.ATLAS_VALIDATION=j;
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
$('validationRefreshBtn')?.addEventListener('click',refreshValidation);
window.refreshLearningValidation=refreshValidation;
setTimeout(refreshValidation,3100);
})();