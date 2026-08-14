const ATLAS_FUTURES_INTEL_VERSION='5.0.0-alpha.2';
function fiClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function fiNum(v){const n=Number(v);return Number.isFinite(n)?n:null;}
function analyzeFuturesIntelligence(s){
  if(!s) return {available:false,score:0,bias:'NO_DATA',crowding:'UNKNOWN',squeeze:'NONE',version:ATLAS_FUTURES_INTEL_VERSION};
  const funding=fiNum(s.funding_rate), oi=fiNum(s.oi_change_pct), taker=fiNum(s.taker_ratio), book=fiNum(s.orderbook_imbalance);
  let score=0, notes=[];
  if(taker!=null){const x=fiClamp((taker-1)*70,-25,25);score+=x;if(taker>=1.08)notes.push('TAKER_BUY_PRESSURE');else if(taker<=0.92)notes.push('TAKER_SELL_PRESSURE');}
  if(book!=null){score+=fiClamp(book*45,-22,22);if(book>=.12)notes.push('BID_DEPTH_DOMINANT');else if(book<=-.12)notes.push('ASK_DEPTH_DOMINANT');}
  if(oi!=null){score+=fiClamp(oi*1.8,-15,15);if(Math.abs(oi)>=3)notes.push('OI_EXPANSION');}
  let crowding='BALANCED';
  if(funding!=null){
    if(funding>=0.0005){crowding='LONG_CROWDED';score-=18;notes.push('HIGH_POSITIVE_FUNDING');}
    else if(funding<=-0.0005){crowding='SHORT_CROWDED';score+=18;notes.push('HIGH_NEGATIVE_FUNDING');}
    else if(funding>=0.0002){crowding='LONG_LEANING';score-=7;}
    else if(funding<=-0.0002){crowding='SHORT_LEANING';score+=7;}
  }
  let squeeze='NONE';
  if(crowding.includes('LONG') && taker!=null && taker<0.95 && book!=null && book<0) squeeze='LONG_SQUEEZE_RISK';
  if(crowding.includes('SHORT') && taker!=null && taker>1.05 && book!=null && book>0) squeeze='SHORT_SQUEEZE_RISK';
  const final=Math.round(fiClamp(score,-100,100));
  const bias=final>=25?'BULLISH':final<=-25?'BEARISH':'NEUTRAL';
  return {available:true,version:ATLAS_FUTURES_INTEL_VERSION,score:final,bias,crowding,squeeze,notes,
    funding_rate:funding,oi_change_pct:oi,taker_ratio:taker,orderbook_imbalance:book,
    research_only:true,live_execution:false};
}
function futuresAlignment(confluence,futures){
  if(!futures?.available) return {state:'NO_DATA',adjustment:0};
  const sig=confluence?.base_signal;
  if(sig==='BUY'&&futures.bias==='BULLISH') return {state:'CONFIRMS_LONG',adjustment:6};
  if(sig==='SELL'&&futures.bias==='BEARISH') return {state:'CONFIRMS_SHORT',adjustment:6};
  if(sig==='BUY'&&futures.bias==='BEARISH') return {state:'CONFLICTS_LONG',adjustment:-8};
  if(sig==='SELL'&&futures.bias==='BULLISH') return {state:'CONFLICTS_SHORT',adjustment:-8};
  return {state:'NEUTRAL',adjustment:0};
}
