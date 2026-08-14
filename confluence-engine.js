const ATLAS_CONFLUENCE_VERSION = '5.0.0-alpha.1';

function cClamp(v,min,max){ return Math.max(min,Math.min(max,v)); }
function cMean(xs){ return xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:0; }
function cStd(xs){ const m=cMean(xs); return xs.length?Math.sqrt(cMean(xs.map(x=>(x-m)**2))):0; }
function cRound(v,d=2){ return Number.isFinite(v)?Number(v.toFixed(d)):null; }

function obvSeries(candles){
  let v=0; const out=[0];
  for(let i=1;i<candles.length;i++){
    if(candles[i].close>candles[i-1].close) v += Number(candles[i].volume||0);
    else if(candles[i].close<candles[i-1].close) v -= Number(candles[i].volume||0);
    out.push(v);
  }
  return out;
}

function pivotPoints(candles, left=3, right=3){
  const pivots=[];
  for(let i=left;i<candles.length-right;i++){
    const c=candles[i];
    const hs=candles.slice(i-left,i+right+1).map(x=>x.high);
    const ls=candles.slice(i-left,i+right+1).map(x=>x.low);
    if(c.high===Math.max(...hs)) pivots.push({type:'R',price:c.high,index:i,time:c.time,volume:Number(c.volume||0),candle:c});
    if(c.low===Math.min(...ls)) pivots.push({type:'S',price:c.low,index:i,time:c.time,volume:Number(c.volume||0),candle:c});
  }
  return pivots;
}

function clusterZones(candles, atrValue){
  const last=candles.at(-1), px=last.close;
  const pivots=pivotPoints(candles.slice(-220));
  const tolerance=Math.max((atrValue||px*0.01)*0.35,px*0.0025);
  const globalAvgVol=cMean(candles.slice(-120).map(x=>Number(x.volume||0)))||1;
  const zones=[];
  for(const p of pivots){
    let z=zones.find(x=>Math.abs(x.price-p.price)<=tolerance);
    if(!z){ z={price:p.price,points:[],types:{S:0,R:0}}; zones.push(z); }
    z.points.push(p); z.types[p.type]++; z.price=cMean(z.points.map(x=>x.price));
  }
  return zones.map(z=>{
    const touches=z.points.length;
    const latestIndex=Math.max(...z.points.map(x=>x.index));
    const age=Math.max(0,220-latestIndex);
    const recency=cClamp(1-age/220,0,1);
    const volRatio=cMean(z.points.map(x=>x.volume))/globalAvgVol;
    const wickEvidence=cMean(z.points.map(p=>{
      const c=p.candle,range=Math.max(1e-12,c.high-c.low);
      const upper=(c.high-Math.max(c.open,c.close))/range;
      const lower=(Math.min(c.open,c.close)-c.low)/range;
      return p.type==='R'?upper:lower;
    }));
    const touchScore=Math.min(38,touches*9.5);
    const volScore=Math.min(22,Math.max(0,(volRatio-0.6)*18));
    const recencyScore=recency*18;
    const rejectionScore=Math.min(17,wickEvidence*34);
    const mixedBonus=(z.types.S>0&&z.types.R>0)?5:0;
    const strength=Math.round(cClamp(touchScore+volScore+recencyScore+rejectionScore+mixedBonus,0,100));
    return {
      price:cRound(z.price,8), strength, touches, volume_ratio:cRound(volRatio,2), rejection:cRound(wickEvidence,2),
      role:z.price>=px?'RESISTANCE':'SUPPORT', distance_pct:cRound(Math.abs(z.price/px-1)*100,2),
      last_touch_time:z.points.sort((a,b)=>b.index-a.index)[0]?.time||null
    };
  }).filter(z=>z.distance_pct<=12).sort((a,b)=>a.distance_pct-b.distance_pct);
}

function analyzeVolumeIntelligence(candles){
  const vols=candles.map(x=>Number(x.volume||0)), closes=candles.map(x=>x.close), last=candles.at(-1);
  const base20=vols.slice(-21,-1), avg20=cMean(base20)||1, sd20=cStd(base20);
  const rel=Number(last.volume||0)/avg20;
  const fast=cMean(vols.slice(-5)), slow=cMean(vols.slice(-20))||1;
  const trendRatio=fast/slow;
  const z=sd20?(Number(last.volume||0)-avg20)/sd20:0;
  const obv=obvSeries(candles), now=obv.at(-1), old=obv[Math.max(0,obv.length-11)];
  const obvDelta=now-old;
  const priceDelta=closes.at(-1)-closes[Math.max(0,closes.length-11)];
  let flow='BALANCED';
  if(obvDelta>0&&priceDelta>=0) flow='BUY_CONFIRMED';
  else if(obvDelta<0&&priceDelta<=0) flow='SELL_CONFIRMED';
  else if(obvDelta>0&&priceDelta<0) flow='BULLISH_DIVERGENCE';
  else if(obvDelta<0&&priceDelta>0) flow='BEARISH_DIVERGENCE';
  let quality=50;
  quality += cClamp((rel-1)*22,-20,25);
  quality += cClamp((trendRatio-1)*25,-15,15);
  quality += cClamp(Math.abs(z)*5,0,10);
  return {relative_volume:cRound(rel,2),volume_zscore:cRound(z,2),volume_trend_ratio:cRound(trendRatio,2),obv_10_delta:cRound(obvDelta,2),flow,quality_score:Math.round(cClamp(quality,0,100))};
}

function analyzeBreakout(last, zone, volume, atrValue, side){
  if(!zone) return {state:'NO_ZONE',score:50};
  const atrPct=atrValue?atrValue/last.close*100:1;
  const proximity=zone.distance_pct;
  let score=50;
  if(volume.relative_volume>=1.5) score+=18; else if(volume.relative_volume<0.8) score-=15;
  if(volume.volume_trend_ratio>=1.15) score+=10; else if(volume.volume_trend_ratio<0.9) score-=8;
  if(side==='UP' && ['BUY_CONFIRMED','BULLISH_DIVERGENCE'].includes(volume.flow)) score+=12;
  if(side==='DOWN' && ['SELL_CONFIRMED','BEARISH_DIVERGENCE'].includes(volume.flow)) score+=12;
  score -= Math.max(0,(zone.strength-70)*0.35);
  if(proximity<=Math.max(atrPct*0.35,0.25)) score+=5;
  const state=score>=72?'BREAKOUT_FAVORED':score<=38?'REJECTION_RISK':'UNCONFIRMED';
  return {state,score:Math.round(cClamp(score,0,100))};
}

function analyzeAtlasConfluence(candles, baseResult=null){
  if(!Array.isArray(candles)||candles.length<80) throw new Error('ATLAS Confluence needs at least 80 candles.');
  const base=baseResult||analyzeMarket(candles), last=candles.at(-1), atrValue=base?.indicators?.atr14||atr(candles,14);
  const zones=clusterZones(candles,atrValue);
  const support=zones.find(z=>z.role==='SUPPORT')||null;
  const resistance=zones.find(z=>z.role==='RESISTANCE')||null;
  const volume=analyzeVolumeIntelligence(candles);
  const up=analyzeBreakout(last,resistance,volume,atrValue,'UP');
  const down=analyzeBreakout(last,support,volume,atrValue,'DOWN');
  const atrPct=atrValue?atrValue/last.close*100:1;
  const dangerPct=Math.max(0.8,atrPct*0.8);
  let gate='ALLOW', reason='NO_DIRECTIONAL_BLOCK', adjusted=base.confidence||50;
  if(base.signal==='BUY' && resistance && resistance.strength>=70 && resistance.distance_pct<=dangerPct && up.state!=='BREAKOUT_FAVORED'){
    gate='BLOCK'; reason='STRONG_RESISTANCE_TOO_CLOSE'; adjusted-=18;
  } else if(base.signal==='SELL' && support && support.strength>=70 && support.distance_pct<=dangerPct && down.state!=='BREAKOUT_FAVORED'){
    gate='BLOCK'; reason='STRONG_SUPPORT_TOO_CLOSE'; adjusted-=18;
  } else if(base.signal==='BUY' && up.state==='BREAKOUT_FAVORED'){
    gate='ALLOW'; reason='VOLUME_CONFIRMED_BREAKOUT'; adjusted+=8;
  } else if(base.signal==='SELL' && down.state==='BREAKOUT_FAVORED'){
    gate='ALLOW'; reason='VOLUME_CONFIRMED_BREAKDOWN'; adjusted+=8;
  }
  if(base.signal==='BUY' && volume.flow==='BEARISH_DIVERGENCE'){ adjusted-=8; reason += '+BEARISH_VOLUME_DIVERGENCE'; }
  if(base.signal==='SELL' && volume.flow==='BULLISH_DIVERGENCE'){ adjusted-=8; reason += '+BULLISH_VOLUME_DIVERGENCE'; }
  const finalSignal=gate==='BLOCK'?'WAIT':base.signal;
  return {
    version:ATLAS_CONFLUENCE_VERSION, signal:finalSignal, base_signal:base.signal,
    confidence:Math.round(cClamp(adjusted,35,96)), gate:{state:gate,reason,danger_distance_pct:cRound(dangerPct,2)},
    nearest_support:support, nearest_resistance:resistance, volume,
    breakout_up:up, breakout_down:down, zones:zones.slice(0,10),
    research_only:true, live_execution:false
  };
}
