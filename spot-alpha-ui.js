
(() => {
const $=id=>document.getElementById(id);
const universe=[
 {name:'Bitcoin',symbol:'BTCUSDT'},{name:'Ethereum',symbol:'ETHUSDT'},{name:'Solana',symbol:'SOLUSDT'},
 {name:'XRP',symbol:'XRPUSDT'},{name:'BNB',symbol:'BNBUSDT'},{name:'Dogecoin',symbol:'DOGEUSDT'},{name:'Zcash',symbol:'ZECUSDT'}
];
async function candles(sym,limit=220){
 const u=`https://api.binance.com/api/v3/klines?symbol=${sym}&interval=1d&limit=${limit}`;
 const r=await fetch(u); if(!r.ok)throw new Error(`${sym} ${r.status}`);
 return (await r.json()).map(x=>({time:x[0],open:+x[1],high:+x[2],low:+x[3],close:+x[4],volume:+x[5]}));
}
const f=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
async function run(){
 $('spotAlphaBadge').textContent='RUNNING';
 const cost=+$('spotCostBps').value||20, rows=[];
 for(const a of universe){
   try{
    const cs=await candles(a.symbol), feat=ATLAS_SPOT_ALPHA.features(cs), sc=ATLAS_SPOT_ALPHA.score(feat), dec=ATLAS_SPOT_ALPHA.decision(sc,cost);
    rows.push({...a,...feat,score:sc,...dec});
   }catch(e){rows.push({...a,error:e.message})}
 }
 rows.sort((a,b)=>(b.net??-999)-(a.net??-999));
 $('spotAlphaBody').innerHTML=rows.map((r,i)=>`<tr><td>${i+1}</td><td>${r.name}<small>${r.symbol}</small></td>
 <td>${f(r.r30)}%</td><td>${f(r.r90)}%</td><td>${f(r.trend)}%</td><td>${f(r.vol)}%</td>
 <td>${f(r.score,1)}</td><td>${r.error?'ERROR':r.action}</td><td>${r.error?'—':f(r.net)}%</td><td>${r.error?'—':f(r.allocation,1)}%</td></tr>`).join('');
 $('spotAlphaBadge').textContent='RESEARCH';
 $('spotAlphaMeta').textContent=`Universe ${rows.length} · Daily timeframe · estimated round-trip friction ${cost} bps · ranking is research-only and not yet forward-return calibrated.`;
 window.__ATLAS_SPOT_ROWS=rows;
}
$('runSpotAlphaBtn')?.addEventListener('click',run);
$('exportSpotAlphaBtn')?.addEventListener('click',()=>{
 const payload={project:'ATLAS',stage:'SPOT_ALPHA_LAB_V1',generated_at:new Date().toISOString(),research_only:true,live_execution:false,rows:window.__ATLAS_SPOT_ROWS||[]};
 const b=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');
 a.href=u;a.download='ATLAS_SPOT_ALPHA_LAB.json';a.click();URL.revokeObjectURL(u);
});
})();
