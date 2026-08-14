
const ATLAS_EVENT_VERSION='5.5.0-alpha.7-shadow';
function evClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function evNum(v,d=2){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
const EVENT_WEIGHTS={
  MACRO_RATE:95, MACRO_CPI:90, MACRO_JOBS:80, REGULATION:85, ETF:85,
  EXCHANGE_SECURITY:95, EXCHANGE_OUTAGE:80, TOKEN_UNLOCK:72, LISTING:60,
  NETWORK_UPGRADE:55, WHALE_TRANSFER:45, GEOPOLITICAL:82, COMPANY_CRYPTO:55, OTHER:40
};
function classifyEvent(e={}){
  const text=String(`${e.title||''} ${e.summary||''}`).toLowerCase();
  if(/interest rate|fomc|fed|ecb|central bank|rate decision/.test(text))return 'MACRO_RATE';
  if(/\bcpi\b|inflation|ppi/.test(text))return 'MACRO_CPI';
  if(/jobs|payroll|unemployment|nfp/.test(text))return 'MACRO_JOBS';
  if(/hack|exploit|breach|stolen|security incident/.test(text))return 'EXCHANGE_SECURITY';
  if(/outage|withdrawal.*halt|trading.*halt/.test(text))return 'EXCHANGE_OUTAGE';
  if(/etf|exchange.traded fund/.test(text))return 'ETF';
  if(/regulat|sec\b|cftc|law|ban|approval|license/.test(text))return 'REGULATION';
  if(/unlock|vesting/.test(text))return 'TOKEN_UNLOCK';
  if(/listing|listed on|delisting/.test(text))return 'LISTING';
  if(/upgrade|hard fork|mainnet|network update/.test(text))return 'NETWORK_UPGRADE';
  if(/whale|large transfer|wallet transfer/.test(text))return 'WHALE_TRANSFER';
  if(/war|attack|missile|sanction|geopolit/.test(text))return 'GEOPOLITICAL';
  return String(e.type||'OTHER').toUpperCase();
}
function eventSentiment(e={}){
  if(Number.isFinite(Number(e.sentiment)))return evClamp(Number(e.sentiment),-1,1);
  const t=String(`${e.title||''} ${e.summary||''}`).toLowerCase();
  let s=0;
  const pos=['approval','approved','inflow','adoption','partnership','launch','upgrade successful','rate cut','cuts rates','cuts interest rate','lowers rates','easing','record demand'];
  const neg=['hack','exploit','breach','ban','lawsuit','outage','halt','liquidation','war','attack','sanction','rate hike','hikes rates','hikes interest rate','raises rates','raises interest rate','rejection','rejected'];
  pos.forEach(x=>{if(t.includes(x))s+=.18}); neg.forEach(x=>{if(t.includes(x))s-=.20});
  return evClamp(s,-1,1);
}
function scoreEvent(e={}){
  const type=classifyEvent(e), base=EVENT_WEIGHTS[type]||40;
  const source=String(e.source_tier||'UNKNOWN').toUpperCase();
  const sourceAdj=source==='PRIMARY'?6:source==='TIER1'?3:source==='UNKNOWN'?-6:0;
  const confirmed=e.confirmed===false?-12:e.confirmed===true?4:0;
  const scope=String(e.scope||'MARKET').toUpperCase();
  const scopeAdj=scope==='MARKET'?4:scope==='ASSET'?0:-2;
  const impact=Math.round(evClamp(base+sourceAdj+confirmed+scopeAdj,0,100));
  const sentiment=eventSentiment(e);
  return {version:ATLAS_EVENT_VERSION,type,impact_score:impact,sentiment_score:evNum(sentiment,3),
    direction:sentiment>=.18?'POSITIVE':sentiment<=-.18?'NEGATIVE':'UNCLEAR',
    source_quality:source,confirmed:e.confirmed??null,shadow_mode:true,research_only:true,live_execution:false};
}
function reactionScore({event,pre=null,post=null,futures=null}={}){
  if(!event)return {available:false};
  const er=scoreEvent(event);
  const preP=Number(pre?.price),postP=Number(post?.price),preV=Number(pre?.volume),postV=Number(post?.volume);
  const priceMove=Number.isFinite(preP)&&Number.isFinite(postP)&&preP?100*(postP/preP-1):null;
  const volumeRatio=Number.isFinite(preV)&&Number.isFinite(postV)&&preV?postV/preV:null;
  let confirmation='NO_MARKET_REACTION_DATA',score=50;
  if(priceMove!=null){
    const expected=Math.sign(er.sentiment_score||0);
    const actual=Math.sign(priceMove);
    if(expected&&actual===expected){confirmation='PRICE_CONFIRMS_EVENT';score+=15;}
    else if(expected&&actual===-expected){confirmation='PRICE_REJECTS_EVENT';score-=12;}
    else confirmation='PRICE_REACTION_AMBIGUOUS';
    score+=evClamp(Math.abs(priceMove)*5,0,15);
  }
  if(volumeRatio!=null){if(volumeRatio>=1.5){score+=10;confirmation+=' + VOLUME_EXPANSION';}else if(volumeRatio<.8)score-=5;}
  if(futures?.available&&Math.abs(Number(futures.score||0))>=25)score+=4;
  return {available:priceMove!=null||volumeRatio!=null,score:Math.round(evClamp(score,0,100)),price_move_pct:evNum(priceMove),volume_ratio:evNum(volumeRatio),
    confirmation,event:er,shadow_mode:true,research_only:true,live_execution:false};
}
window.ATLAS_EVENT_INTELLIGENCE={scoreEvent,reactionScore,classifyEvent,version:ATLAS_EVENT_VERSION};
