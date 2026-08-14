(() => {
const $=id=>document.getElementById(id);
const universe=[
 {name:'Bitcoin',symbol:'BTCUSDT'},{name:'Ethereum',symbol:'ETHUSDT'},{name:'Solana',symbol:'SOLUSDT'},
 {name:'XRP',symbol:'XRPUSDT'},{name:'BNB',symbol:'BNBUSDT'},{name:'Dogecoin',symbol:'DOGEUSDT'},{name:'Zcash',symbol:'ZECUSDT'}
];
const asset=s=>({name:s.name,symbol:`BINANCE:${s.symbol}`,cls:'Crypto'});
async function getCandles(a,interval){return (await fetchMarketCandles(asset(a),interval,'')).candles;}
function fmt(v,d=0){return v==null?'—':Number(v).toFixed(d);}
function regimeLabel(r){return `${r.regime} / ${r.volatility}`;}
async function collectorSnapshot(symbol){
 try{
   let j=await fetch(`/api/smart-money/latest?symbol=${encodeURIComponent(symbol)}`).then(r=>r.json());
   if(!j.snapshot){
     const r=await fetch(`/api/smart-money/capture?symbol=${encodeURIComponent(symbol)}`,{method:'POST'});
     if(r.ok)j=await r.json();
   }
   return j.snapshot||null;
 }catch(e){return null;}
}
async function similarityFor(r,f){
 try{
  const c=r.confluence,p={symbol:r.symbol,signal:c.signal,base_signal:c.base_signal,confidence:c.confidence,gate_state:c.gate?.state,gate_reason:c.gate?.reason,
   support_strength:c.nearest_support?.strength,support_distance_pct:c.nearest_support?.distance_pct,resistance_strength:c.nearest_resistance?.strength,resistance_distance_pct:c.nearest_resistance?.distance_pct,
   relative_volume:c.volume?.relative_volume,volume_trend_ratio:c.volume?.volume_trend_ratio,volume_quality:c.volume?.quality_score,breakout_score:c.breakout_up?.score,breakdown_score:c.breakout_down?.score,
   futures_score:f?.score,oi_change_pct:f?.oi_change_pct,taker_ratio:f?.taker_ratio,orderbook_imbalance:f?.orderbook_imbalance,limit:30};
  const x=await fetch('/api/confluence/similar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});return x.ok?await x.json():null;
 }catch(e){return null;}
}
async function enrich(r){
 const snap=await collectorSnapshot(r.symbol), futures=analyzeFuturesIntelligence(snap);
 const liquidity=analyzeLiquidityLiquidation({snapshot:snap,futures,confluence:r.confluence});
 const similarity=await similarityFor(r,futures);
 const final=ATLAS_FINAL_RANKING.finalOpportunityRank({opportunity:r.opp,futures,liquidity,similarity});
 const plan=ATLAS_TRADE_MANAGEMENT.buildTradePlan({base:r.base,confluence:r.confluence,liquidity,final});
 const playbook=ATLAS_PLAYBOOK.detectPlaybooks({base:r.base,confluence:r.confluence,futures,liquidity,regime:r.regime,relative:r.relative,anomaly:r.anomaly,plan,final,opp:r.opp});
 let execution_decision=final.decision;
 if(plan?.status==='NO_TRADE_RISK_GEOMETRY')execution_decision='NO_TRADE';
 else if(plan?.status==='WATCH_POOR_RR'&&String(final.decision).includes('CANDIDATE'))execution_decision=final.direction==='LONG'?'LONG_WATCH':'SHORT_WATCH';
 return {...r,snapshot:snap,futures,liquidity,similarity,final,plan,playbook,execution_decision,enriched:true};
}
async function run(){
 const btn=$('opportunityScanBtn'),badge=$('opportunityBadge'),body=$('opportunityBody'),meta=$('opportunityMeta');if(!btn||!body)return;
 btn.disabled=true;badge.textContent='SCANNING';badge.className='pill working';body.innerHTML='<tr><td colspan="15">Stage 1: scanning market structure, volume and relative strength…</td></tr>';
 try{
  const interval=window.ATLAS_APP_STATE?.interval||'D';
  const pairs=await Promise.all(universe.map(async a=>{try{return [a,await getCandles(a,interval),null]}catch(e){return [a,null,e.message]}}));
  const bp=pairs.find(([a,c])=>a.symbol==='BTCUSDT'&&c);if(!bp)throw new Error('BTC benchmark unavailable.');const btc=bp[1];let rows=[];
  for(const [a,c,error] of pairs){
   if(error||!c){rows.push({...a,error});continue;}
   const base=analyzeMarket(c),confluence=analyzeAtlasConfluence(c,base),regime=detectMarketRegime(c),relative=a.symbol==='BTCUSDT'?{available:true,score:50,label:'BENCHMARK',weighted_relative_pct:0,horizons:{}}:ATLAS_REGIME_RELATIVE.relativeStrength(c,btc);
   const opp=ATLAS_REGIME_RELATIVE.opportunityScore({base,confluence,regime,relative});
   const anomaly=ATLAS_ANOMALY.candleAnomaly(c,confluence);
   rows.push({...a,base,confluence,regime,relative,opp,anomaly});
  }
  rows.sort((a,b)=>(b.opp?.score??-999)-(a.opp?.score??-999));
  badge.textContent='ENRICHING TOP 3';body.innerHTML='<tr><td colspan="15">Stage 2: enriching the top 3 with Futures + Liquidity + Pattern Memory…</td></tr>';
  const candidates=rows.filter(x=>x.opp&&!x.error).sort((a,b)=>((b.opp?.score||0)+(b.anomaly?.score>=55?6:0))-((a.opp?.score||0)+(a.anomaly?.score>=55?6:0))).slice(0,3);
  const enriched=await Promise.all(candidates.map(enrich));const map=new Map(enriched.map(x=>[x.symbol,x]));rows=rows.map(x=>map.get(x.symbol)||x);
  rows.sort((a,b)=>(b.final?.score??b.opp?.score??-999)-(a.final?.score??a.opp?.score??-999));
  body.innerHTML=rows.map((r,i)=>r.error?`<tr><td>${i+1}</td><td>${r.name}<small>${r.symbol}</small></td><td colspan="10">ERROR: ${r.error}</td></tr>`:
   `<tr><td>${i+1}</td><td>${r.name}<small>${r.symbol}</small></td><td>${r.base.signal}</td><td>${regimeLabel(r.regime)}</td><td>${fmt(r.relative.weighted_relative_pct,2)}%</td><td>${fmt(r.confluence.volume?.quality_score)}</td><td>${r.anomaly?.score>=55?`🔥 ${fmt(r.anomaly.score)}`:fmt(r.anomaly?.score)}</td><td>${fmt(r.opp.score)}</td><td>${r.enriched?fmt(r.futures?.score):'—'}</td><td>${r.enriched?fmt(r.liquidity?.score):'—'}</td><td>${r.enriched?fmt(r.final?.historical?.hit_rate_pct,1)+'%':'—'}</td><td>${fmt(r.final?.score??r.opp.score)}</td><td>${r.enriched?fmt(r.plan?.rr_tp2,2):'—'}</td><td>${r.enriched?(r.playbook?.primary?`${r.playbook.primary.id}<small>${r.playbook.primary.score}/100</small>`:'—'):'—'}</td><td>${r.execution_decision??r.final?.decision??r.opp.action}</td></tr>`).join('');
  const valid=rows.filter(x=>x.opp),best=valid[0];badge.textContent=best?`#1 ${best.symbol} ${best.final?.score??best.opp.score}/100`:'NO DATA';badge.className=`pill ${(best.final?.score??best?.opp?.score)>=80?'buy':(best.final?.score??best?.opp?.score)>=68?'working':'neutral'}`;
  meta.textContent=`${valid.length} assets · ${interval} · broad scan first, then top-3 Futures + observed liquidity + sample-weighted Pattern Memory. Research-only; ranking is not a probability.`;
  window.ATLAS_OPPORTUNITY_ROWS=rows;
  window.dispatchEvent(new CustomEvent('atlas:opportunity-scan-complete',{detail:{rows}}));
 }catch(e){badge.textContent='ERROR';badge.className='pill sell';body.innerHTML=`<tr><td colspan="15">${e.message}</td></tr>`;}finally{btn.disabled=false;}
}
window.runAtlasOpportunityScan=run;
$('opportunityScanBtn')?.addEventListener('click',run);
$('opportunityExportBtn')?.addEventListener('click',()=>{const payload={project:'ATLAS',stage:'V5_FINAL_OPPORTUNITY_RANKING_ALPHA6',generated_at:new Date().toISOString(),research_only:true,live_execution:false,rows:window.ATLAS_OPPORTUNITY_ROWS||[]};const b=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='ATLAS_FINAL_OPPORTUNITY_ALPHA6.json';a.click();URL.revokeObjectURL(u);});
})();
