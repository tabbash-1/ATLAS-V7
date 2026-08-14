(() => {
const $=id=>document.getElementById(id);
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function render(x){
 const badge=$('anomalyBadge'),grid=$('anomalyMetrics'),note=$('anomalyNotes');if(!badge||!grid)return;
 if(!x?.available){badge.textContent='WAITING';badge.className='pill neutral';return;}
 badge.textContent=`${x.level} ${x.score}/100`;badge.className=`pill ${x.level==='HOT'?'sell':x.level==='ELEVATED'?'working':'neutral'}`;
 grid.innerHTML=[
  ['Anomaly score',`${x.score}/100`],['Level',x.level],['Bias',x.bias],
  ['Volume Z',fmt(x.price?.volume_z)],['Range Z',fmt(x.price?.range_z)],['Return Z',fmt(x.price?.return_z)],
  ['OI Δ',x.derivatives?.oi_change_pct==null?'—':`${fmt(x.derivatives.oi_change_pct)}%`],
  ['Taker ratio',fmt(x.derivatives?.taker_ratio,3)],['Book imbalance',fmt(x.derivatives?.book_imbalance,3)]
 ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
 note.innerHTML=`<div><b>Triggers:</b> ${(x.reasons||[]).join(' · ')||'None'}</div><div class="muted tiny">HOT WATCH is an early-warning flag, not a trade signal.</div>`;
}
window.refreshAnomaly=function(candles=null,confluence=null){
 const x=ATLAS_ANOMALY.combineAnomaly({candles:candles||window.ATLAS_LATEST_CANDLES||[],confluence:confluence||window.ATLAS_LATEST_CONFLUENCE||null,
  futures:window.ATLAS_LATEST_FUTURES||null,snapshot:window.ATLAS_LATEST_FUTURES_SNAPSHOT||null});
 window.ATLAS_ANOMALY_STATE=x;render(x);return x;
};
setTimeout(()=>window.refreshAnomaly(),1800);
})();