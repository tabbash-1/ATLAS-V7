
const ATLAS_SURPRISE_VERSION='5.6.0-alpha.9-shadow';
function esClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function esN(v,d=3){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
const EVENT_DIRECTION_RULES={
  MACRO_CPI:'LOWER_IS_RISK_ON',
  MACRO_JOBS:'CONTEXT_DEPENDENT',
  MACRO_RATE:'LOWER_IS_RISK_ON'
};
function normalizeSurprise({actual,consensus,scale=null}={}){
  const a=Number(actual),c=Number(consensus); if(!Number.isFinite(a)||!Number.isFinite(c))return {available:false};
  const raw=a-c;
  let denom=Number(scale);
  if(!Number.isFinite(denom)||denom<=0)denom=Math.max(Math.abs(c)*0.25,0.1);
  return {available:true,raw:esN(raw),normalized:esN(raw/denom),actual:a,consensus:c,scale:denom};
}
function scoreEconomicSurprise({eventType,actual,consensus,previous=null,scale=null}={}){
  const type=String(eventType||'OTHER').toUpperCase(),s=normalizeSurprise({actual,consensus,scale});
  if(!s.available)return {available:false,type,version:ATLAS_SURPRISE_VERSION};
  let riskDirection='UNCLEAR', directionalScore=0;
  if(type==='MACRO_CPI'||type==='MACRO_RATE'){
    directionalScore=-s.normalized; riskDirection=directionalScore>=.25?'RISK_ON':directionalScore<=-.25?'RISK_OFF':'MIXED';
  }else if(type==='MACRO_JOBS'){
    // Jobs surprise is deliberately not assigned a simple bullish/bearish direction.
    riskDirection='CONTEXT_DEPENDENT'; directionalScore=0;
  }
  const magnitude=Math.round(esClamp(Math.abs(s.normalized)*35,0,100));
  const prev=Number(previous);
  return {available:true,version:ATLAS_SURPRISE_VERSION,type,actual:s.actual,consensus:s.consensus,previous:Number.isFinite(prev)?prev:null,
    raw_surprise:s.raw,normalized_surprise:s.normalized,surprise_magnitude:magnitude,risk_direction:riskDirection,
    directional_score:esN(directionalScore),rule:EVENT_DIRECTION_RULES[type]||'NO_SIMPLE_RULE',shadow_mode:true,research_only:true,live_execution:false};
}
function compareSurpriseReaction({surprise,reaction}={}){
  if(!surprise?.available||!reaction?.available)return {available:false,label:'WAITING_FOR_REACTION'};
  const move=Number(reaction.early_return_pct); if(!Number.isFinite(move))return {available:false,label:'WAITING_FOR_REACTION'};
  let expected=0;if(surprise.risk_direction==='RISK_ON')expected=1;if(surprise.risk_direction==='RISK_OFF')expected=-1;
  const actual=Math.sign(move);
  const label=!expected?'CONTEXT_ONLY':actual===expected?'REACTION_CONFIRMS_SURPRISE':actual===-expected?'REACTION_REJECTS_SURPRISE':'AMBIGUOUS';
  return {available:true,label,early_return_pct:esN(move),surprise_magnitude:surprise.surprise_magnitude,shadow_mode:true,research_only:true};
}
window.ATLAS_EVENT_SURPRISE={scoreEconomicSurprise,compareSurpriseReaction,version:ATLAS_SURPRISE_VERSION};
