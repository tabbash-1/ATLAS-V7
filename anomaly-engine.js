
const ATLAS_ANOMALY_VERSION='5.9.0-alpha.12';
function anClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function anN(v,d=3){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function mean(xs){return xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:0;}
function std(xs){const m=mean(xs);return xs.length?Math.sqrt(mean(xs.map(x=>(x-m)**2))):0;}
function zscore(v,xs){const s=std(xs);return s?((v-mean(xs))/s):0;}
function candleAnomaly(candles,confluence=null){
  if(!Array.isArray(candles)||candles.length<40)return {available:false};
  const last=candles.at(-1),prev=candles.at(-2),vols=candles.slice(-31,-1).map(x=>Number(x.volume||0));
  const ranges=candles.slice(-31,-1).map(x=>Math.abs(Number(x.high)-Number(x.low)));
  const rets=candles.slice(-31).map((x,i,a)=>i?Math.abs(Number(x.close)/Number(a[i-1].close)-1):0).slice(1);
  const vz=zscore(Number(last.volume||0),vols),rz=zscore(Math.abs(last.high-last.low),ranges);
  const ret=Math.abs(Number(last.close)/Number(prev.close)-1),retz=zscore(ret,rets);
  let score=0,reasons=[],bias='NEUTRAL';
  if(vz>=2){score+=25;reasons.push('VOLUME_SPIKE');}
  else if(vz>=1.2){score+=14;reasons.push('VOLUME_ELEVATED');}
  if(rz>=2){score+=22;reasons.push('RANGE_EXPANSION');}
  else if(rz>=1.2){score+=12;reasons.push('RANGE_ELEVATED');}
  if(retz>=2){score+=18;reasons.push('RETURN_SHOCK');}
  if(confluence?.volume?.flow==='BULLISH_DIVERGENCE'){score+=12;reasons.push('BULLISH_VOLUME_DIVERGENCE');bias='BULLISH';}
  if(confluence?.volume?.flow==='BEARISH_DIVERGENCE'){score+=12;reasons.push('BEARISH_VOLUME_DIVERGENCE');bias='BEARISH';}
  if(last.close>prev.close&&score>=20)bias=bias==='BEARISH'?'MIXED':'BULLISH';
  if(last.close<prev.close&&score>=20)bias=bias==='BULLISH'?'MIXED':'BEARISH';
  return {available:true,score:Math.round(anClamp(score,0,100)),bias,volume_z:anN(vz),range_z:anN(rz),return_z:anN(retz),reasons};
}
function futuresAnomaly(futures=null,snapshot=null,history=[]){
  if(!futures?.available&&!snapshot)return {available:false,score:0,bias:'NEUTRAL',reasons:[]};
  let score=0,reasons=[],bias='NEUTRAL';
  const oi=Number(futures?.oi_change_pct),taker=Number(futures?.taker_ratio),book=Number(futures?.orderbook_imbalance),funding=Number(futures?.funding_rate);
  if(Number.isFinite(oi)&&Math.abs(oi)>=5){score+=24;reasons.push('OI_SHOCK');}
  else if(Number.isFinite(oi)&&Math.abs(oi)>=3){score+=15;reasons.push('OI_EXPANSION');}
  if(Number.isFinite(taker)&&taker>=1.18){score+=18;reasons.push('AGGRESSIVE_BUYING');bias='BULLISH';}
  if(Number.isFinite(taker)&&taker<=.82){score+=18;reasons.push('AGGRESSIVE_SELLING');bias='BEARISH';}
  if(Number.isFinite(book)&&book>=.22){score+=16;reasons.push('BID_BOOK_IMBALANCE');bias=bias==='BEARISH'?'MIXED':'BULLISH';}
  if(Number.isFinite(book)&&book<=-.22){score+=16;reasons.push('ASK_BOOK_IMBALANCE');bias=bias==='BULLISH'?'MIXED':'BEARISH';}
  if(Number.isFinite(funding)&&Math.abs(funding)>=.0007){score+=14;reasons.push(funding>0?'EXTREME_POSITIVE_FUNDING':'EXTREME_NEGATIVE_FUNDING');}
  if(futures?.squeeze&&futures.squeeze!=='NONE'){score+=18;reasons.push(futures.squeeze);}
  return {available:true,score:Math.round(anClamp(score,0,100)),bias,reasons,
    oi_change_pct:anN(oi),taker_ratio:anN(taker),book_imbalance:anN(book),funding_rate:anN(funding,6)};
}
function combineAnomaly({candles,confluence=null,futures=null,snapshot=null}={}){
  const price=candleAnomaly(candles,confluence),deriv=futuresAnomaly(futures,snapshot);
  let score=(price.available?price.score*.55:0)+(deriv.available?deriv.score*.45:0);
  if(price.available&&!deriv.available)score=price.score;
  if(!price.available&&deriv.available)score=deriv.score;
  let bias='NEUTRAL';
  if(price.bias===deriv.bias&&price.bias!=='NEUTRAL')bias=price.bias;
  else if(price.bias==='NEUTRAL')bias=deriv.bias;
  else if(deriv.bias==='NEUTRAL')bias=price.bias;
  else if(price.bias!==deriv.bias)bias='MIXED';
  const reasons=[...(price.reasons||[]),...(deriv.reasons||[])];
  const level=score>=75?'HOT':score>=55?'ELEVATED':score>=35?'WATCH':'NORMAL';
  return {version:ATLAS_ANOMALY_VERSION,available:price.available||deriv.available,score:Math.round(anClamp(score,0,100)),level,bias,
    price,derivatives:deriv,reasons:[...new Set(reasons)],research_only:true,live_execution:false};
}
window.ATLAS_ANOMALY={candleAnomaly,futuresAnomaly,combineAnomaly,version:ATLAS_ANOMALY_VERSION};
