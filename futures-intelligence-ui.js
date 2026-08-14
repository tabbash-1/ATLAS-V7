(() => {
 const $=id=>document.getElementById(id); const fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
 function sym(){const a=window.ATLAS_STATE?.selectedAsset;return String(a?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'').toUpperCase();}
 async function load(confluence=null){
   const symbol=sym(), badge=$('futuresIntelBadge'), grid=$('futuresIntelMetrics'); if(!badge||!grid)return null;
   try{
     const j=await fetch(`/api/smart-money/latest?symbol=${encodeURIComponent(symbol)}`).then(r=>r.json());
     const f=analyzeFuturesIntelligence(j.snapshot), a=confluence?futuresAlignment(confluence,f):{state:'WAITING_FOR_CHART',adjustment:0};
     window.ATLAS_LATEST_FUTURES=f; window.ATLAS_LATEST_FUTURES_SNAPSHOT=j.snapshot||null;
     if(window.refreshLiquidityIntelligence) setTimeout(()=>window.refreshLiquidityIntelligence(confluence),0);
     badge.textContent=f.available?f.bias:'WAITING';badge.className=`pill ${f.bias==='BULLISH'?'buy':f.bias==='BEARISH'?'sell':'neutral'}`;
     const items=[['Futures score',`${f.score}/100`],['Alignment',a.state],['Crowding',f.crowding],['Squeeze',f.squeeze],['Funding',f.funding_rate==null?'—':`${fmt(f.funding_rate*100,4)}%`],['OI Δ',f.oi_change_pct==null?'—':`${fmt(f.oi_change_pct,2)}%`],['Taker ratio',fmt(f.taker_ratio,3)],['Book imbalance',f.orderbook_imbalance==null?'—':`${fmt(f.orderbook_imbalance*100,1)}%`]];
     grid.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join(''); return {futures:f,alignment:a};
   }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';grid.innerHTML=`<div><span>Error</span><b>${e.message}</b></div>`;return null;}
 }
 window.refreshFuturesIntelligence=load;
 setTimeout(()=>load(),1000);setInterval(()=>load(),60000);
})();
