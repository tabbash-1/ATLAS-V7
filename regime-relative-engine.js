const ATLAS_REGIME_RELATIVE_VERSION='5.3.0-alpha.5';
function rrClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function rrRet(closes,n){if(!Array.isArray(closes)||closes.length<=n)return null;const a=Number(closes.at(-1)),b=Number(closes.at(-1-n));return b?100*(a/b-1):null;}
function rrNum(v,d=2){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function relativeStrength(assetCandles,benchmarkCandles){
  if(!assetCandles?.length||!benchmarkCandles?.length)return {available:false,score:50,label:'NO_BENCHMARK'};
  const ac=assetCandles.map(x=>+x.close),bc=benchmarkCandles.map(x=>+x.close);
  const horizons=[12,48,120].filter(n=>ac.length>n&&bc.length>n);
  if(!horizons.length)return {available:false,score:50,label:'INSUFFICIENT_HISTORY'};
  const spreads={}; let weighted=0,weightSum=0;
  const ws={12:.25,48:.35,120:.40};
  for(const n of horizons){const ar=rrRet(ac,n),br=rrRet(bc,n),sp=ar-br;spreads[n]={asset_return_pct:rrNum(ar),btc_return_pct:rrNum(br),relative_pct:rrNum(sp)};weighted+=sp*ws[n];weightSum+=ws[n];}
  const edge=weightSum?weighted/weightSum:0;
  const score=Math.round(rrClamp(50+edge*3.2,0,100));
  return {available:true,score,label:score>=65?'OUTPERFORMING_BTC':score<=35?'UNDERPERFORMING_BTC':'IN_LINE_WITH_BTC',weighted_relative_pct:rrNum(edge),horizons:spreads};
}
function regimeFit(base,regime){
  const sig=base?.signal||'WAIT',r=regime?.regime||'TRANSITION',vol=regime?.volatility||'NORMAL'; let score=50,notes=[];
  if(sig==='BUY'){if(r==='TREND_UP'){score+=30;notes.push('LONG_WITH_UPTREND');}else if(r==='TREND_DOWN'){score-=35;notes.push('LONG_AGAINST_DOWNTREND');}else if(r==='RANGE'){score-=18;notes.push('LONG_IN_RANGE');}}
  else if(sig==='SELL'){if(r==='TREND_DOWN'){score+=30;notes.push('SHORT_WITH_DOWNTREND');}else if(r==='TREND_UP'){score-=35;notes.push('SHORT_AGAINST_UPTREND');}else if(r==='RANGE'){score-=18;notes.push('SHORT_IN_RANGE');}}
  else score=40;
  if(vol==='HIGH'){score-=5;notes.push('HIGH_VOLATILITY');} if(vol==='LOW'){score-=2;notes.push('LOW_VOLATILITY');}
  return {score:Math.round(rrClamp(score,0,100)),notes};
}
function roomScore(confluence){
  const sig=confluence?.base_signal; const res=confluence?.nearest_resistance,sup=confluence?.nearest_support; let d=null,strength=null;
  if(sig==='BUY'&&res){d=Number(res.distance_pct);strength=Number(res.strength||0);} if(sig==='SELL'&&sup){d=Number(sup.distance_pct);strength=Number(sup.strength||0);}
  if(!Number.isFinite(d))return {score:55,distance_pct:null,strength:null,label:'NO_NEAR_OBSTACLE'};
  let s=50+rrClamp((d-1)*13,-25,30)-rrClamp((strength-60)*.45,-10,18); s=rrClamp(s,0,100);
  return {score:Math.round(s),distance_pct:rrNum(d),strength:rrNum(strength,0),label:s>=65?'GOOD_ROOM':s<=35?'TIGHT_ROOM':'MODERATE_ROOM'};
}
function opportunityScore({base,confluence,regime,relative}){
  const dir=base?.signal==='BUY'?1:base?.signal==='SELL'?-1:0;
  const fit=regimeFit(base,regime),room=roomScore(confluence),vol=Number(confluence?.volume?.quality_score||50);
  const breakout=dir>0?Number(confluence?.breakout_up?.score||50):dir<0?Number(confluence?.breakout_down?.score||50):50;
  const relRaw=Number(relative?.score||50); const relativeDirectional=dir>=0?relRaw:100-relRaw;
  let score=Number(base?.confidence||50)*.16+Number(confluence?.confidence||50)*.20+fit.score*.18+relativeDirectional*.18+vol*.10+room.score*.10+breakout*.08;
  const blockers=[],cautions=[],confirmations=[];
  if(!dir)blockers.push('NO_DIRECTIONAL_SIGNAL'); if(confluence?.gate?.state==='BLOCK')blockers.push(confluence.gate.reason||'CONFLUENCE_BLOCK');
  if(fit.score>=70)confirmations.push('REGIME_ALIGNED'); else if(fit.score<=30)cautions.push('REGIME_CONFLICT');
  if(relativeDirectional>=65)confirmations.push('RELATIVE_STRENGTH_ALIGNED'); else if(relativeDirectional<=35)cautions.push('RELATIVE_STRENGTH_WEAK');
  if(vol>=68)confirmations.push('VOLUME_CONFIRMED'); if(room.score<=35)cautions.push('LIMITED_ROOM_TO_OBSTACLE');
  if(blockers.length)score=Math.min(score,54); if(cautions.includes('REGIME_CONFLICT'))score-=6; score=Math.round(rrClamp(score,0,100));
  let action='NO_TRADE'; if(!blockers.length){if(score>=80)action=dir>0?'LONG_CANDIDATE':'SHORT_CANDIDATE';else if(score>=68)action=dir>0?'LONG_WATCH':'SHORT_WATCH';else if(score>=58)action='WATCH';}
  return {version:ATLAS_REGIME_RELATIVE_VERSION,score,action,direction:dir>0?'LONG':dir<0?'SHORT':'NONE',regime_fit:fit,relative_strength:relative,room,components:{base:rrNum(base?.confidence,0),confluence:rrNum(confluence?.confidence,0),regime_fit:fit.score,relative_directional:rrNum(relativeDirectional,0),volume:rrNum(vol,0),room:room.score,breakout_breakdown:rrNum(breakout,0)},blockers,cautions,confirmations,research_only:true,live_execution:false};
}
window.ATLAS_REGIME_RELATIVE={relativeStrength,regimeFit,roomScore,opportunityScore,version:ATLAS_REGIME_RELATIVE_VERSION};
