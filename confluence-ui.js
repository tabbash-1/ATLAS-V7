function confluenceValue(v,suffix=''){ return v==null?'—':`${v}${suffix}`; }
function resetConfluence(){
  const el=document.getElementById('confluenceMetrics'); if(!el) return;
  el.innerHTML=[['Decision','READY'],['Support','—'],['Resistance','—'],['Rel. Volume','—'],['Volume Flow','—'],['Breakout ↑','—'],['Breakdown ↓','—'],['Gate reason','—']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  const b=document.getElementById('confluenceBadge'); if(b){ b.textContent='READY'; b.className='pill neutral'; }
}
function renderConfluence(r){
  window.ATLAS_LATEST_CONFLUENCE=r;
  const badge=document.getElementById('confluenceBadge'), grid=document.getElementById('confluenceMetrics'); if(!badge||!grid) return;
  badge.textContent=r.signal==='WAIT'&&r.base_signal!=='WAIT'?'BLOCKED':r.signal; badge.className=`pill ${r.signal==='BUY'?'buy':r.signal==='SELL'?'sell':r.gate.state==='BLOCK'?'working':'neutral'}`;
  const s=r.nearest_support, z=r.nearest_resistance;
  const items=[
    ['Decision',`${r.base_signal} → ${r.signal} · ${r.confidence}%`],
    ['Support',s?`${priceFmt(s.price)} · ${s.strength}/100 · ${s.distance_pct}%`:'—'],
    ['Resistance',z?`${priceFmt(z.price)} · ${z.strength}/100 · ${z.distance_pct}%`:'—'],
    ['Rel. Volume',`${r.volume.relative_volume}× · Q${r.volume.quality_score}`],
    ['Volume Flow',r.volume.flow],
    ['Breakout ↑',`${r.breakout_up.state} · ${r.breakout_up.score}/100`],
    ['Breakdown ↓',`${r.breakout_down.state} · ${r.breakout_down.score}/100`],
    ['Gate reason',r.gate.reason]
  ];
  grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
}
