(() => {
const $=id=>document.getElementById(id);
const universe=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT'];
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function parseOpen(){
 try{return JSON.parse(localStorage.getItem('atlas.openPositions')||'[]')}catch{return []}
}
function saveOpen(xs){localStorage.setItem('atlas.openPositions',JSON.stringify(xs));}
async function loadSeries(interval){
 const out={};
 await Promise.all(universe.map(async s=>{
  try{const a={name:s,symbol:`BINANCE:${s}`,cls:'Crypto'},r=await fetchMarketCandles(a,interval,'');out[s]=r.candles;}catch{}
 }));
 return out;
}
function renderPositions(){
 const body=$('portfolioPositionsBody');if(!body)return;
 const xs=parseOpen();
 body.innerHTML=xs.length?xs.map((x,i)=>`<tr><td>${x.symbol}</td><td>${x.direction}</td><td>${fmt(x.risk_pct,2)}%</td><td>${fmt(x.entry,8)}</td><td>${fmt(x.stop,8)}</td><td><button data-i="${i}" class="remove-pos">Remove</button></td></tr>`).join(''):'<tr><td colspan="6">No research positions added.</td></tr>';
 body.querySelectorAll('.remove-pos').forEach(b=>b.addEventListener('click',()=>{const xs=parseOpen();xs.splice(Number(b.dataset.i),1);saveOpen(xs);renderPositions();runRisk().catch(()=>{});}));
}
async function runRisk(){
 const badge=$('portfolioRiskBadge'),grid=$('portfolioRiskMetrics'),note=$('portfolioRiskNotes');if(!grid)return;
 badge.textContent='CALCULATING';badge.className='pill working';
 const state=window.ATLAS_APP_STATE||{},interval=state.interval||'D',series=await loadSeries(interval),cm=ATLAS_PORTFOLIO_RISK.correlationMatrix(series);
 window.ATLAS_CORRELATIONS=cm.matrix;
 const plan=window.ATLAS_TRADE_PLAN||null,asset=state.assets?.[state.active],symbol=String(asset?.symbol||'').replace(/^BINANCE:/,'');
 const final=window.ATLAS_MASTER||null,candidate={symbol,direction:plan?.direction||final?.direction||'NONE'};
 const equity=Number($('portfolioEquity')?.value||10000),baseRisk=Number($('portfolioBaseRisk')?.value||1),open=parseOpen();
 const a=ATLAS_PORTFOLIO_RISK.assessPortfolio({candidate,openPositions:open,correlations:cm.matrix,equity,baseRiskPct:baseRisk,maxPortfolioRiskPct:Number($('portfolioMaxRisk')?.value||4),maxCorrelatedRiskPct:Number($('portfolioCorrRisk')?.value||2.25)});
 let size=null;if(plan?.available&&a.suggested_risk_pct>0)size=ATLAS_PORTFOLIO_RISK.positionSize({equity,riskPct:a.suggested_risk_pct,entry:plan.entry,stop:plan.stop,leverage:Number($('portfolioLeverage')?.value||1)});
 let adaptive=null;
 try{
   const row=(window.ATLAS_OPPORTUNITY_ROWS||[]).find(x=>x.symbol===symbol)||{},pb=row.playbook?.primary?.id||window.ATLAS_CURRENT_PLAYBOOK?.primary?.id;
   adaptive=await fetch('/api/adaptive/assess',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({regime:row.regime?.regime||'UNKNOWN',playbook_primary:pb||'NO_PLAYBOOK',base_risk_pct:a.suggested_risk_pct,horizon:24})}).then(r=>r.json());
 }catch(e){}
 window.ATLAS_PORTFOLIO_ASSESSMENT={assessment:a,size,correlations:cm,adaptive};
 grid.innerHTML=[
  ['Open portfolio risk',`${fmt(a.open_portfolio_risk_pct)}%`],['Suggested risk',`${fmt(a.suggested_risk_pct,3)}%`],['Remaining risk',`${fmt(a.remaining_portfolio_risk_pct)}%`],
  ['Max correlation',fmt(a.max_effective_correlation,2)],['Correlated risk',`${fmt(a.correlated_risk_pct)}%`],['Suggested notional',size?fmt(size.notional,2):'—'],
  ['Risk cash',size?fmt(size.risk_cash,2):'—'],['Units',size?fmt(size.units,8):'—'],
  ['Adaptive shadow ×',adaptive?fmt(adaptive.shadow_multiplier,2):'—'],['Shadow risk %',adaptive?`${fmt(adaptive.shadow_suggested_risk_pct,3)}%`:'—']
 ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
 note.innerHTML=`<div><b>Cautions:</b> ${(a.cautions||[]).join(' · ')||'None'}</div><div><b>Blockers:</b> ${(a.blockers||[]).join(' · ')||'None'}</div><div><b>Adaptive shadow:</b> ${adaptive?`${adaptive.regime} / ${adaptive.playbook} → ${fmt(adaptive.shadow_multiplier,2)}× (NOT APPLIED)`:'unavailable'}</div><div class="muted tiny">Position size is a research calculation only; Adaptive Alpha 20 never changes actual research size yet.</div>`;
 badge.textContent=a.blockers.length?'BLOCKED':a.cautions.length?'REDUCED RISK':'RISK OK';badge.className=`pill ${a.blockers.length?'sell':a.cautions.length?'working':'buy'}`;
 return a;
}
function addCurrent(){
 const plan=window.ATLAS_TRADE_PLAN,ass=window.ATLAS_PORTFOLIO_ASSESSMENT?.assessment,state=window.ATLAS_APP_STATE,asset=state?.assets?.[state.active];if(!plan?.available||!asset||!ass)return;
 const xs=parseOpen(),symbol=String(asset.symbol).replace(/^BINANCE:/,'');xs.push({symbol,direction:plan.direction,risk_pct:Number(ass.suggested_risk_pct||0),entry:plan.entry,stop:plan.stop});saveOpen(xs);renderPositions();runRisk().catch(()=>{});
}
$('portfolioRunBtn')?.addEventListener('click',()=>runRisk().catch(e=>{$('portfolioRiskNotes').textContent=e.message;}));
$('portfolioAddBtn')?.addEventListener('click',addCurrent);
renderPositions();setTimeout(()=>runRisk().catch(()=>{}),2200);
window.refreshPortfolioRisk=runRisk;
})();