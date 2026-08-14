
const ATLAS_PLAYBOOK_VERSION='6.0.0-alpha.16';
function pbClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function pbN(v,d=2){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function pbDir(ctx){
  const d=ctx?.final?.direction||ctx?.opp?.direction||ctx?.plan?.direction||ctx?.base?.signal;
  if(d==='LONG'||d==='BUY')return 1;if(d==='SHORT'||d==='SELL')return -1;return 0;
}
function detectPlaybooks(ctx={}){
  const dir=pbDir(ctx),c=ctx.confluence||{},f=ctx.futures||{},l=ctx.liquidity||{},r=ctx.regime||{},rel=ctx.relative||{},a=ctx.anomaly||{},p=ctx.plan||{};
  const vol=Number(c.volume?.quality_score||50),rv=Number(c.volume?.relative_volume||1);
  const br=Number(c.breakout_up?.score||50),bd=Number(c.breakout_down?.score||50);
  const resS=Number(c.nearest_resistance?.strength||0),resD=Number(c.nearest_resistance?.distance_pct||99);
  const supS=Number(c.nearest_support?.strength||0),supD=Number(c.nearest_support?.distance_pct||99);
  const oi=Number(f.oi_change_pct||0),fund=Number(f.funding_rate||0),taker=Number(f.taker_ratio||1),book=Number(f.orderbook_imbalance||0);
  const relScore=Number(rel.score||50),rr2=Number(p.rr_tp2||0);
  const found=[];
  function add(id,score,bias,why,management,avoid=[]){
    found.push({id,score:Math.round(pbClamp(score,0,100)),bias,why,management,avoid,research_only:true});
  }

  // 1) Breakout continuation: strength through a level backed by volume/flow.
  if(dir>0 && br>=68 && vol>=62 && rv>=1.15){
    let s=55+(br-68)*.7+(vol-62)*.35+(rv-1.15)*12;
    if(f.bias==='BULLISH')s+=8;if(r.regime==='TREND_UP')s+=8;if(rr2>=2)s+=6;
    add('BREAKOUT_CONTINUATION_LONG',s,'LONG',
      ['BREAKOUT_QUALITY','VOLUME_EXPANSION',f.bias==='BULLISH'?'FUTURES_ALIGNED':null,r.regime==='TREND_UP'?'UPTREND':null].filter(Boolean),
      'Prefer confirmed close/retest over chasing an extended candle.',
      ['STRONG_NEARBY_ASK_WALL','EXTREME_LONG_CROWDING']);
  }
  if(dir<0 && bd>=68 && vol>=62 && rv>=1.15){
    let s=55+(bd-68)*.7+(vol-62)*.35+(rv-1.15)*12;
    if(f.bias==='BEARISH')s+=8;if(r.regime==='TREND_DOWN')s+=8;if(rr2>=2)s+=6;
    add('BREAKDOWN_CONTINUATION_SHORT',s,'SHORT',
      ['BREAKDOWN_QUALITY','VOLUME_EXPANSION',f.bias==='BEARISH'?'FUTURES_ALIGNED':null,r.regime==='TREND_DOWN'?'DOWNTREND':null].filter(Boolean),
      'Prefer confirmed close/retest over chasing an extended candle.',
      ['STRONG_NEARBY_BID_WALL','EXTREME_SHORT_CROWDING']);
  }

  // 2) Trend pullback: trade with regime into a nearby structural support/resistance.
  if(dir>0 && r.regime==='TREND_UP' && supD<=2.2 && supS>=60 && relScore>=55 && vol>=45){
    let s=58+(supS-60)*.35+(2.2-supD)*8+(relScore-55)*.3;
    if(['BUY_CONFIRMED','BULLISH_DIVERGENCE'].includes(c.volume?.flow))s+=8;if(rr2>=2)s+=6;
    add('TREND_PULLBACK_LONG',s,'LONG',['UPTREND','NEAR_SUPPORT','RELATIVE_STRENGTH_OK'],
      'Entry should be near support/invalidation, not after price has already expanded away from it.',
      ['SUPPORT_FAILURE','BTC_REGIME_REVERSAL']);
  }
  if(dir<0 && r.regime==='TREND_DOWN' && resD<=2.2 && resS>=60 && relScore<=45 && vol>=45){
    let s=58+(resS-60)*.35+(2.2-resD)*8+(45-relScore)*.3;
    if(['SELL_CONFIRMED','BEARISH_DIVERGENCE'].includes(c.volume?.flow))s+=8;if(rr2>=2)s+=6;
    add('TREND_PULLBACK_SHORT',s,'SHORT',['DOWNTREND','NEAR_RESISTANCE','RELATIVE_WEAKNESS_OK'],
      'Entry should be near resistance/invalidation, not after price has already expanded away from it.',
      ['RESISTANCE_FAILURE','BTC_REGIME_REVERSAL']);
  }

  // 3) Leverage trap: price direction looks attractive but derivatives are crowded and spot/volume support is poor.
  if(dir>0 && oi>=3 && fund>=.00035 && (rv<1 || vol<50) && resD<=2){
    let s=62+pbClamp(oi*2,0,15)+pbClamp((fund-.00035)*30000,0,12)+(rv<.8?8:0)+(resS>=75?8:0);
    add('LEVERAGE_TRAP_LONG_RISK',s,'RISK_OFF_LONG',
      ['OI_EXPANSION','POSITIVE_FUNDING','WEAK_SPOT_VOLUME','NEAR_RESISTANCE'],
      'Do not chase the long; wait for deleveraging or clean acceptance above resistance.',
      ['FORCED_LONG_LIQUIDATIONS']);
  }
  if(dir<0 && oi>=3 && fund<=-.00035 && (rv<1 || vol<50) && supD<=2){
    let s=62+pbClamp(oi*2,0,15)+pbClamp((-fund-.00035)*30000,0,12)+(rv<.8?8:0)+(supS>=75?8:0);
    add('LEVERAGE_TRAP_SHORT_RISK',s,'RISK_OFF_SHORT',
      ['OI_EXPANSION','NEGATIVE_FUNDING','WEAK_SPOT_VOLUME','NEAR_SUPPORT'],
      'Do not chase the short; wait for deleveraging or clean acceptance below support.',
      ['FORCED_SHORT_LIQUIDATIONS']);
  }

  // 4) Squeeze / liquidation reversal watch.
  if(f.squeeze==='SHORT_SQUEEZE_RISK' && (a.score>=45 || taker>1.05 || book>.1)){
    let s=58+(a.score||0)*.18+pbClamp((taker-1)*80,0,15)+pbClamp(book*40,0,10);
    add('SHORT_SQUEEZE_REVERSAL_WATCH',s,'LONG_WATCH',
      ['SHORT_CROWDING','BUY_FLOW','ABNORMAL_ACTIVITY'],
      'Wait for structure reclaim/confirmation; squeeze potential alone is not an entry.',
      ['FAILED_RECLAIM']);
  }
  if(f.squeeze==='LONG_SQUEEZE_RISK' && (a.score>=45 || taker<.95 || book<-.1)){
    let s=58+(a.score||0)*.18+pbClamp((1-taker)*80,0,15)+pbClamp(-book*40,0,10);
    add('LONG_SQUEEZE_REVERSAL_WATCH',s,'SHORT_WATCH',
      ['LONG_CROWDING','SELL_FLOW','ABNORMAL_ACTIVITY'],
      'Wait for structure loss/confirmation; squeeze potential alone is not an entry.',
      ['FAILED_BREAKDOWN']);
  }

  // 5) Range rejection: strong wall + poor breakout quality.
  if(r.regime==='RANGE' && resD<=1.3 && resS>=75 && br<=42 && c.volume?.flow!=='BUY_CONFIRMED'){
    add('RANGE_RESISTANCE_REJECTION_WATCH',60+(resS-75)*.5+(42-br)*.4,'SHORT_WATCH',
      ['RANGE','STRONG_RESISTANCE','WEAK_BREAKOUT'],
      'Wait for rejection confirmation; avoid anticipating solely from the level.');
  }
  if(r.regime==='RANGE' && supD<=1.3 && supS>=75 && bd<=42 && c.volume?.flow!=='SELL_CONFIRMED'){
    add('RANGE_SUPPORT_REJECTION_WATCH',60+(supS-75)*.5+(42-bd)*.4,'LONG_WATCH',
      ['RANGE','STRONG_SUPPORT','WEAK_BREAKDOWN'],
      'Wait for rejection confirmation; avoid anticipating solely from the level.');
  }

  found.sort((x,y)=>y.score-x.score);
  const primary=found[0]||null;
  return {version:ATLAS_PLAYBOOK_VERSION,available:found.length>0,primary,playbooks:found,
    note:'Pattern labels are hypotheses to test, not proven strategies.',research_only:true,live_execution:false};
}
window.ATLAS_PLAYBOOK={detectPlaybooks,version:ATLAS_PLAYBOOK_VERSION};
