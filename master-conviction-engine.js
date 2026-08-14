const ATLAS_MASTER_VERSION='5.2.0-alpha.4';
function mcClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function mcNum(v,d=1){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function mcDir(signal){return signal==='BUY'?1:signal==='SELL'?-1:0;}
function evidenceWeight(n){n=Number(n||0);if(n<10)return 0;if(n<30)return .20;if(n<100)return .45;if(n<200)return .70;return 1;}
function historicalEvidence(similarity){
  const h=similarity?.horizons?.['24']||{}; const n=Number(h.n||0),hit=Number(h.hit_rate_pct),avg=Number(h.avg_directional_return_pct);
  if(!n||!Number.isFinite(hit)||!Number.isFinite(avg))return {available:false,n,score:50,weight:0,label:'INSUFFICIENT'};
  const w=evidenceWeight(n); let score=50+mcClamp((hit-50)*.85,-25,25)+mcClamp(avg*5,-15,15); score=mcClamp(score,0,100);
  return {available:true,n,hit_rate_pct:hit,avg_directional_return_pct:avg,score:Math.round(score),weight:w,label:w>=.7?'MATURE':'EARLY'};
}
function analyzeMasterConviction({base,confluence,futures=null,liquidity=null,similarity=null}={}){
  if(!base||!confluence)throw new Error('Master Conviction needs base + confluence results.');
  const direction=mcDir(confluence.base_signal||base.signal),baseScore=mcClamp(Number(base.confidence||50),0,100),confluenceScore=mcClamp(Number(confluence.confidence||baseScore),0,100);
  const volScore=mcClamp(Number(confluence.volume?.quality_score||50),0,100),srGate=confluence.gate?.state==='BLOCK'?0:100;
  const breakout=direction>0?Number(confluence.breakout_up?.score||50):direction<0?Number(confluence.breakout_down?.score||50):50;
  let futuresScore=50,futuresWeight=0;if(futures?.available){const signed=direction?direction*Number(futures.score||0):0;futuresScore=mcClamp(50+signed*.5,0,100);futuresWeight=.08;}
  let liquidityScore=50,liquidityWeight=0;if(liquidity?.available){liquidityScore=mcClamp(Number(liquidity.score||50),0,100);liquidityWeight=.07;}
  const hist=historicalEvidence(similarity),histWeight=.15*hist.weight;
  const weights={base:.18,confluence:.20,volume:.12,breakout:.10,sr_gate:.10,futures:futuresWeight,liquidity:liquidityWeight,historical:histWeight};
  const used=Object.values(weights).reduce((a,b)=>a+b,0),neutralWeight=Math.max(0,1-used);
  let score=baseScore*weights.base+confluenceScore*weights.confluence+volScore*weights.volume+breakout*weights.breakout+srGate*weights.sr_gate+futuresScore*weights.futures+liquidityScore*weights.liquidity+hist.score*weights.historical+50*neutralWeight;
  const blockers=[],cautions=[],confirmations=[];
  if(confluence.gate?.state==='BLOCK')blockers.push(confluence.gate.reason||'CONFLUENCE_GATE_BLOCKED'); if(direction===0)blockers.push('NO_DIRECTIONAL_BASE_SIGNAL');
  if(futures?.available){const aligned=(direction>0&&futures.bias==='BULLISH')||(direction<0&&futures.bias==='BEARISH'),conflict=(direction>0&&futures.bias==='BEARISH')||(direction<0&&futures.bias==='BULLISH');if(aligned)confirmations.push('FUTURES_ALIGNED');if(conflict){cautions.push('FUTURES_CONFLICT');score-=6;}if(futures.squeeze&&futures.squeeze!=='NONE')cautions.push(futures.squeeze);}
  if(liquidity?.available){
    if(liquidity.score>=65)confirmations.push('LIQUIDITY_CONTEXT_SUPPORTIVE'); if(liquidity.score<=40){cautions.push('LIQUIDITY_CONTEXT_ADVERSE');score-=5;}
    if(liquidity.source_quality?.liquidations==='ESTIMATED_NOT_OBSERVED')cautions.push('LIQUIDATIONS_ESTIMATED_NOT_OBSERVED');
  } else cautions.push('LIQUIDITY_LEVELS_NOT_READY');
  if(volScore>=68)confirmations.push('VOLUME_CONFIRMED');else if(volScore<=38){cautions.push('WEAK_VOLUME');score-=5;}
  if(breakout>=72)confirmations.push(direction>0?'BREAKOUT_QUALITY_HIGH':'BREAKDOWN_QUALITY_HIGH');
  if(hist.available){if(hist.weight<.45)cautions.push('HISTORICAL_SAMPLE_SMALL');if(hist.score>=65&&hist.weight>=.45)confirmations.push('HISTORICAL_EDGE_POSITIVE');if(hist.score<=40&&hist.weight>=.45){cautions.push('HISTORICAL_EDGE_NEGATIVE');score-=8;}}else cautions.push('HISTORICAL_EVIDENCE_NOT_READY');
  score=Math.round(mcClamp(score,0,100)); let decision='NO_TRADE',tier='LOW';if(!blockers.length){if(score>=82){decision=direction>0?'LONG_CANDIDATE':'SHORT_CANDIDATE';tier='HIGH';}else if(score>=70){decision=direction>0?'LONG_WATCH':'SHORT_WATCH';tier='MEDIUM';}else if(score>=60){decision='WATCH';tier='LOW';}}
  const validated=hist.weight>=.7&&(similarity?.horizons?.['24']?.n||0)>=100; const capitalStatus=validated?'FORWARD_VALIDATION_REQUIRED':'RESEARCH_ONLY_NOT_VALIDATED';
  return {version:ATLAS_MASTER_VERSION,score,decision,tier,direction:direction>0?'LONG':direction<0?'SHORT':'NONE',components:{base:mcNum(baseScore),confluence:mcNum(confluenceScore),volume:mcNum(volScore),breakout_or_breakdown:mcNum(breakout),sr_gate:srGate,futures:mcNum(futuresScore),liquidity:mcNum(liquidityScore),historical:hist.score},weights,weight_sum:mcNum(used,3),neutral_weight:mcNum(neutralWeight,3),historical:hist,blockers,cautions,confirmations,capital_status:capitalStatus,research_only:true,live_execution:false};
}
