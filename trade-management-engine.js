
const ATLAS_TRADE_MANAGEMENT_VERSION='5.7.0-alpha.10';
function tmClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function tmN(v,d=8){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function tmDir(x){
  const d=x?.direction||x?.decision||x?.signal||x?.base_signal;
  if(String(d).includes('LONG')||d==='BUY')return 1;
  if(String(d).includes('SHORT')||d==='SELL')return -1;
  return 0;
}
function directionalObstacles({direction,entry,confluence,liquidity}){
  const obs=[];
  for(const z of (confluence?.zones||[])){
    const px=Number(z.price);if(!Number.isFinite(px))continue;
    if(direction>0&&px>entry)obs.push({price:px,strength:Number(z.strength||50),type:'S/R_RESISTANCE'});
    if(direction<0&&px<entry)obs.push({price:px,strength:Number(z.strength||50),type:'S/R_SUPPORT'});
  }
  const o=liquidity?.observed_liquidity;
  if(direction>0)for(const w of (o?.asks||[])){const px=Number(w.price);if(px>entry)obs.push({price:px,strength:Number(w.strength||50),type:'ASK_LIQUIDITY'});}
  if(direction<0)for(const w of (o?.bids||[])){const px=Number(w.price);if(px<entry)obs.push({price:px,strength:Number(w.strength||50),type:'BID_LIQUIDITY'});}
  obs.sort((a,b)=>direction>0?a.price-b.price:b.price-a.price);
  return obs;
}
function buildTradePlan({base,confluence,liquidity=null,final=null}={}){
  const direction=tmDir(final)||tmDir(confluence)||tmDir(base);
  const entry=Number(base?.entry),atr=Number(base?.indicators?.atr14);
  if(!direction||!Number.isFinite(entry)||!Number.isFinite(atr)||atr<=0)
    return {available:false,version:ATLAS_TRADE_MANAGEMENT_VERSION,status:'NO_DIRECTION_OR_ATR',research_only:true,live_execution:false};
  const entryHalf=.22*atr;
  const entryZone=direction>0?[entry-entryHalf,entry+entryHalf]:[entry-entryHalf,entry+entryHalf];
  const support=Number(confluence?.nearest_support?.price),resistance=Number(confluence?.nearest_resistance?.price);
  let stopAtr=entry-direction*1.5*atr,stop=stopAtr,stopSource='ATR_1_5';
  if(direction>0&&Number.isFinite(support)&&support<entry&&(entry-support)<=2.5*atr){
    const structural=support-.25*atr; if(structural<stop){stop=structural;stopSource='BELOW_SUPPORT';}
  }
  if(direction<0&&Number.isFinite(resistance)&&resistance>entry&&(resistance-entry)<=2.5*atr){
    const structural=resistance+.25*atr; if(structural>stop){stop=structural;stopSource='ABOVE_RESISTANCE';}
  }
  // Cap pathological structural risk at 3 ATR.
  if(Math.abs(entry-stop)>3*atr){stop=entry-direction*3*atr;stopSource+='|CAPPED_3ATR';}
  const risk=Math.abs(entry-stop);
  const obstacles=directionalObstacles({direction,entry,confluence,liquidity});
  const first=obstacles[0]||null,second=obstacles[1]||null;
  const before=(px)=>entry+direction*Math.max(.15*atr,Math.abs(px-entry)-.18*atr);
  let tp1=first?before(first.price):entry+direction*1.5*risk;
  if(Math.abs(tp1-entry)<.9*risk)tp1=entry+direction*.9*risk;
  let tp2=second?before(second.price):entry+direction*2.5*risk;
  if(Math.abs(tp2-entry)<1.6*risk)tp2=entry+direction*1.6*risk;
  // Ensure ordering.
  if(direction>0&&tp2<=tp1)tp2=tp1+Math.max(risk,.7*atr);
  if(direction<0&&tp2>=tp1)tp2=tp1-Math.max(risk,.7*atr);
  const rr1=Math.abs(tp1-entry)/risk,rr2=Math.abs(tp2-entry)/risk;
  let quality=50+tmClamp((rr1-1)*16,-15,20)+tmClamp((rr2-2)*12,-15,20);
  if(first?.strength>=80&&Math.abs(first.price-entry)<risk){quality-=18;}
  if(final?.score>=82)quality+=8; else if(final?.score<60)quality-=8;
  const blockers=[],cautions=[];
  if(confluence?.gate?.state==='BLOCK')blockers.push(confluence.gate.reason||'CONFLUENCE_BLOCK');
  if(rr1<1)cautions.push('TP1_BELOW_1R');
  if(rr2<1.8)cautions.push('TP2_BELOW_1_8R');
  if(first&&first.strength>=80&&Math.abs(first.price-entry)/risk<1)cautions.push('STRONG_OBSTACLE_INSIDE_1R');
  quality=Math.round(tmClamp(quality,0,100));
  let status='PLAN_READY';
  if(blockers.length||rr2<1.25)status='NO_TRADE_RISK_GEOMETRY';
  else if(rr1<1||rr2<1.8)status='WATCH_POOR_RR';
  const management={
    tp1_action:'TAKE_PARTIAL_35_TO_50_PERCENT',
    after_tp1:'MOVE_STOP_TO_BREAKEVEN_OR_STRUCTURE',
    trailing:'TRAIL_REMAINDER_BY_1_2_ATR_AFTER_TP1',
    time_stop:'REASSESS_IF_NO_PROGRESS_AFTER_8_BARS',
    note:'Research template only; percentages and trailing rules require forward validation.'
  };
  return {available:true,version:ATLAS_TRADE_MANAGEMENT_VERSION,status,quality_score:quality,direction:direction>0?'LONG':'SHORT',
    entry:tmN(entry),entry_zone_low:tmN(Math.min(...entryZone)),entry_zone_high:tmN(Math.max(...entryZone)),
    stop:tmN(stop),stop_source:stopSource,risk_per_unit:tmN(risk),tp1:tmN(tp1),tp2:tmN(tp2),
    rr_tp1:tmN(rr1,2),rr_tp2:tmN(rr2,2),first_obstacle:first,second_obstacle:second,
    management,blockers,cautions,research_only:true,live_execution:false};
}
window.ATLAS_TRADE_MANAGEMENT={buildTradePlan,version:ATLAS_TRADE_MANAGEMENT_VERSION};
