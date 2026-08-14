(()=>{
 const $=id=>document.getElementById(id); const f=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
 function render(x){
   const badge=$('liquidityBadge'),grid=$('liquidityMetrics'),note=$('liquidityNotes'); if(!badge||!grid||!x)return;
   badge.textContent=x.available?`${x.score}/100`:'WAITING';badge.className=`pill ${x.score>=65?'buy':x.score<=40?'sell':'neutral'}`;
   const o=x.observed_liquidity||{},p=x.liquidation_pressure||{};
   const items=[['Liquidity score',`${x.score}/100`],['Nearest bid wall',o.nearest_bid?`${f(o.nearest_bid.distance_pct)}% · ${o.nearest_bid.strength}/100`:'—'],['Nearest ask wall',o.nearest_ask?`${f(o.nearest_ask.distance_pct)}% · ${o.nearest_ask.strength}/100`:'—'],['Long liq. pressure',p.available?`${p.long_pressure}/100`:'—'],['Short liq. pressure',p.available?`${p.short_pressure}/100`:'—'],['Order book source',x.source_quality?.orderbook_levels||'—'],['Liquidations source','ESTIMATED'],['Status','RESEARCH ONLY']];
   grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
   if(note)note.textContent=(x.notes||[]).join(' · ')||'No special liquidity condition.';
 }
 window.refreshLiquidityIntelligence=function(confluence=null){
   const x=analyzeLiquidityLiquidation({snapshot:window.ATLAS_LATEST_FUTURES_SNAPSHOT||null,futures:window.ATLAS_LATEST_FUTURES||null,confluence:confluence||window.ATLAS_LATEST_CONFLUENCE||null});
   window.ATLAS_LIQUIDITY=x;render(x);return x;
 };
 setTimeout(()=>window.refreshLiquidityIntelligence(),1300);
})();
