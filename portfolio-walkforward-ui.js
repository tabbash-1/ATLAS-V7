
(() => {
const $=id=>document.getElementById(id);
const universe=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT'];
async function fetchHistory(sym,limit=1000){
 const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${sym}&interval=1d&limit=${limit}`);
 if(!r.ok) throw new Error(`${sym}: HTTP ${r.status}`);
 return (await r.json()).map(x=>({time:+x[0],open:+x[1],high:+x[2],low:+x[3],close:+x[4],volume:+x[5]}));
}
function val(id){return +$(id).value}
function metric(name,v,suffix=''){return `<div><span>${name}</span><b>${v==null?'—':v}${suffix}</b></div>`}
async function run(){
 $('wfBadge').textContent='RUNNING'; $('wfMeta').textContent='Downloading synchronized daily spot history…';
 try{
  const pairs=await Promise.all(universe.map(async s=>[s,await fetchHistory(s)]));
  const data=Object.fromEntries(pairs);
  const res=ATLAS_PORTFOLIO_WF.simulate(data,{
   capital:val('wfCapital'),topN:val('wfTopN'),rebalanceDays:val('wfRebalanceDays'),
   roundTripBps:val('wfCostBps'),minScore:val('wfMinScore'),maxAssetWeightPct:val('wfMaxWeight')
  });
  window.__ATLAS_WF=res; const m=res.metrics;
  $('wfMetrics').innerHTML=[
   metric('Final equity',m.finalEquity),metric('Net return',m.netReturnPct,'%'),metric('CAGR',m.cagrPct,'%'),
   metric('Max DD',m.maxDrawdownPct,'%'),metric('Sharpe',m.sharpe),metric('Fees paid',m.feesPaid),
   metric('Turnover',m.turnoverX,'×'),metric('Cash days',m.cashDayPct,'%'),metric('Rebalances',m.rebalances),
   metric('BTC Buy & Hold',m.btcBuyHoldReturnPct,'%'),metric('BTC Max DD',m.btcMaxDrawdownPct,'%'),metric('Alpha vs BTC',m.alphaVsBtcPct,'%')
  ].join('');
  $('wfMeta').textContent=`OOS-style rolling simulation: ${res.period.start.slice(0,10)} → ${res.period.end.slice(0,10)} · decisions use past data only and execute at next-day open.`;
  $('wfBadge').textContent=(m.netReturnPct>0 && m.sharpe>0 && m.maxDrawdownPct<35)?'RESEARCH PASS':'RESEARCH FAIL';
  $('wfBadge').className='pill '+(m.netReturnPct>0?'working':'neutral');
  $('wfExportBtn').disabled=false; $('wfShowLogBtn').disabled=false;
 }catch(e){$('wfBadge').textContent='ERROR';$('wfMeta').textContent=e.message;}
}
$('wfRunBtn')?.addEventListener('click',run);
$('wfExportBtn')?.addEventListener('click',()=>{
 const b=new Blob([JSON.stringify(window.__ATLAS_WF||{},null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');
 a.href=u;a.download='ATLAS_SPOT_PORTFOLIO_WALKFORWARD.json';a.click();URL.revokeObjectURL(u);
});
$('wfShowLogBtn')?.addEventListener('click',()=>{
 const r=window.__ATLAS_WF;if(!r)return;
 $('wfLog').hidden=!$('wfLog').hidden;
 $('wfLog').innerHTML=r.logs.slice(-20).reverse().map(x=>`<div><b>${new Date(x.execution_time).toLocaleDateString()}</b> · selected: ${x.selected.join(', ')||'CASH'} · fee ${x.fee.toFixed(2)} · top: ${x.ranked.map(y=>`${y.symbol.replace('USDT','')} ${y.score}`).join(' | ')}</div>`).join('');
});
})();
