const ATLAS_LIQUIDITY_VERSION='5.2.0-alpha.4';
function liqClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function liqN(v){const n=Number(v);return Number.isFinite(n)?n:null;}
function normalizeWalls(rows=[],side='BID'){
  return (Array.isArray(rows)?rows:[]).map(x=>({
    side,price:liqN(x.price),notional:liqN(x.notional),distance_pct:liqN(x.distance_pct)
  })).filter(x=>x.price!=null&&x.notional!=null&&x.distance_pct!=null).sort((a,b)=>a.distance_pct-b.distance_pct);
}
function observedLiquidity(snapshot,markPrice){
  const bids=normalizeWalls(snapshot?.orderbook_bid_walls,'BID');
  const asks=normalizeWalls(snapshot?.orderbook_ask_walls,'ASK');
  const all=[...bids,...asks];
  const maxNotional=Math.max(1,...all.map(x=>x.notional));
  for(const x of all){x.strength=Math.round(liqClamp(100*x.notional/maxNotional,0,100));}
  return {available:all.length>0,bids,asks,nearest_bid:bids[0]||null,nearest_ask:asks[0]||null};
}
function estimatedLiquidationPressure(futures,confluence){
  if(!futures?.available) return {available:false,long_pressure:50,short_pressure:50,label:'NO_FUTURES_DATA'};
  let longP=50,shortP=50;
  const oi=Math.abs(Number(futures.oi_change_pct||0));
  const expansion=liqClamp(oi*3,0,18);
  if(futures.crowding?.includes('LONG')) longP+=20+expansion;
  if(futures.crowding?.includes('SHORT')) shortP+=20+expansion;
  if(futures.squeeze==='LONG_SQUEEZE_RISK') longP+=18;
  if(futures.squeeze==='SHORT_SQUEEZE_RISK') shortP+=18;
  const sup=Number(confluence?.nearest_support?.distance_pct), res=Number(confluence?.nearest_resistance?.distance_pct);
  if(Number.isFinite(sup)&&sup<1.5) longP-=6;
  if(Number.isFinite(res)&&res<1.5) shortP-=6;
  return {available:true,long_pressure:Math.round(liqClamp(longP,0,100)),short_pressure:Math.round(liqClamp(shortP,0,100)),label:'ESTIMATED_FROM_CROWDING_OI_NOT_TRUE_LIQUIDATION_MAP'};
}
function analyzeLiquidityLiquidation({snapshot=null,futures=null,confluence=null}={}){
  const mark=liqN(snapshot?.mark_price);
  const observed=observedLiquidity(snapshot,mark);
  const pressure=estimatedLiquidationPressure(futures,confluence);
  const sig=confluence?.base_signal;
  let score=50,notes=[],blockers=[];
  if(observed.available){
    const bid=observed.nearest_bid,ask=observed.nearest_ask;
    if(sig==='BUY'&&ask&&ask.distance_pct<=1&&ask.strength>=70){score-=12;notes.push('NEARBY_ASK_LIQUIDITY_WALL');}
    if(sig==='SELL'&&bid&&bid.distance_pct<=1&&bid.strength>=70){score-=12;notes.push('NEARBY_BID_LIQUIDITY_WALL');}
    if(sig==='BUY'&&bid&&bid.distance_pct<=1.5&&bid.strength>=65){score+=8;notes.push('BID_LIQUIDITY_SUPPORT');}
    if(sig==='SELL'&&ask&&ask.distance_pct<=1.5&&ask.strength>=65){score+=8;notes.push('ASK_LIQUIDITY_RESISTANCE');}
  } else notes.push('ORDERBOOK_WALL_LEVELS_NOT_YET_CAPTURED');
  if(pressure.available){
    if(sig==='BUY'&&pressure.short_pressure>=75){score+=9;notes.push('SHORT_LIQUIDATION_PRESSURE_FAVORS_UPSIDE');}
    if(sig==='SELL'&&pressure.long_pressure>=75){score+=9;notes.push('LONG_LIQUIDATION_PRESSURE_FAVORS_DOWNSIDE');}
    if(sig==='BUY'&&pressure.long_pressure>=82){score-=10;notes.push('LONG_CROWDING_DOWNSIDE_RISK');}
    if(sig==='SELL'&&pressure.short_pressure>=82){score-=10;notes.push('SHORT_CROWDING_UPSIDE_RISK');}
  }
  score=Math.round(liqClamp(score,0,100));
  return {version:ATLAS_LIQUIDITY_VERSION,available:observed.available||pressure.available,score,observed_liquidity:observed,liquidation_pressure:pressure,notes,blockers,
    source_quality:{orderbook_levels:observed.available?'OBSERVED_BINANCE_ORDERBOOK':'UNAVAILABLE',liquidations:'ESTIMATED_NOT_OBSERVED'},research_only:true,live_execution:false};
}
