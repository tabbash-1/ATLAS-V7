const ATLAS_V4_VERSION = '4.0.0-alpha.1';

function median(xs){
  if(!xs.length) return 0;
  const a=[...xs].sort((x,y)=>x-y), m=Math.floor(a.length/2);
  return a.length%2?a[m]:(a[m-1]+a[m])/2;
}
function wilder(values, period){
  if(values.length < period) return [];
  const out=Array(values.length).fill(null);
  let v=values.slice(0,period).reduce((a,b)=>a+b,0)/period;
  out[period-1]=v;
  for(let i=period;i<values.length;i++){ v=((v*(period-1))+values[i])/period; out[i]=v; }
  return out;
}
function adx(candles, period=14){
  if(candles.length < period*2+2) return null;
  const tr=[], plusDM=[], minusDM=[];
  for(let i=1;i<candles.length;i++){
    const c=candles[i], p=candles[i-1];
    tr.push(Math.max(c.high-c.low,Math.abs(c.high-p.close),Math.abs(c.low-p.close)));
    const up=c.high-p.high, down=p.low-c.low;
    plusDM.push(up>down && up>0?up:0);
    minusDM.push(down>up && down>0?down:0);
  }
  const atrS=wilder(tr,period), plusS=wilder(plusDM,period), minusS=wilder(minusDM,period);
  const dx=[];
  for(let i=0;i<tr.length;i++){
    if(atrS[i]==null){ dx.push(null); continue; }
    const pdi=atrS[i] ? 100*plusS[i]/atrS[i] : 0;
    const mdi=atrS[i] ? 100*minusS[i]/atrS[i] : 0;
    const den=pdi+mdi;
    dx.push(den?100*Math.abs(pdi-mdi)/den:0);
  }
  const valid=dx.filter(v=>v!=null);
  if(valid.length<period) return null;
  return wilder(valid,period).filter(v=>v!=null).at(-1) ?? null;
}
function atrPctSeries(candles, period=14){
  const out=[];
  for(let i=Math.max(period+1,30); i<candles.length; i++){
    const a=atr(candles.slice(0,i+1),period), c=candles[i].close;
    if(a && c) out.push(100*a/c);
  }
  return out;
}

function detectMarketRegime(candles){
  if(!Array.isArray(candles)||candles.length<80) throw new Error('V4 regime engine needs at least 80 candles.');
  const closes=candles.map(c=>c.close), e20=emaSeries(closes,20), e50=emaSeries(closes,50);
  const last=candles.at(-1), ema20=e20.at(-1), ema50=e50.at(-1), a=atr(candles,14), adx14=adx(candles,14);
  const atrPct=a/last.close*100;
  const hist=atrPctSeries(candles.slice(-160));
  const med=median(hist.slice(-100))||atrPct;
  const volRatio=med?atrPct/med:1;
  const volatility=volRatio>=1.35?'HIGH':volRatio<=0.75?'LOW':'NORMAL';
  const emaSpreadPct=Math.abs(ema20-ema50)/last.close*100;
  const prev20=e20[Math.max(0,e20.length-6)] ?? ema20;
  const slope5Pct=(ema20-prev20)/last.close*100;
  let regime='TRANSITION';
  if(adx14>=22 && ema20>ema50 && slope5Pct>0) regime='TREND_UP';
  else if(adx14>=22 && ema20<ema50 && slope5Pct<0) regime='TREND_DOWN';
  else if(adx14<18 && emaSpreadPct<1.25) regime='RANGE';
  return {
    regime, volatility,
    adx14:Number(adx14.toFixed(2)), atr_pct:Number(atrPct.toFixed(2)), atr_regime_ratio:Number(volRatio.toFixed(2)),
    ema_spread_pct:Number(emaSpreadPct.toFixed(2)), ema20_slope_5_pct:Number(slope5Pct.toFixed(2))
  };
}

function applyRegimeGate(candles, base){
  const r=detectMarketRegime(candles);
  let allowed=base.signal!=='WAIT', reason='BASE_WAIT';
  if(base.signal==='BUY'){
    if(r.regime==='TREND_DOWN') { allowed=false; reason='BLOCK_BUY_IN_DOWN_TREND'; }
    else if(r.regime==='RANGE') { allowed=false; reason='BLOCK_DIRECTIONAL_IN_RANGE'; }
    else { reason='BUY_ALLOWED'; }
  } else if(base.signal==='SELL'){
    if(r.regime==='TREND_UP') { allowed=false; reason='BLOCK_SELL_IN_UP_TREND'; }
    else if(r.regime==='RANGE') { allowed=false; reason='BLOCK_DIRECTIONAL_IN_RANGE'; }
    else { reason='SELL_ALLOWED'; }
  }
  const riskScalar=r.volatility==='HIGH'?0.5:r.volatility==='LOW'?0.75:1;
  return {...base, signal:allowed?base.signal:'WAIT', regime:r, regime_gate:{allowed,reason,risk_scalar:riskScalar}};
}

function derivativesPeriod(interval){ return ({'15':'15m','60':'1h','240':'4h','D':'1d','W':'1d'})[interval]||'1h'; }
async function getJson(url){ const res=await fetch(url); if(!res.ok) throw new Error(`Binance Futures HTTP ${res.status}`); return res.json(); }
async function fetchDerivativesSnapshot(asset, interval){
  if(asset.cls!=='Crypto' || !asset.symbol.startsWith('BINANCE:')) throw new Error('Derivatives factor is currently available for Binance crypto only.');
  const symbol=tvToBinanceSymbol(asset.symbol), period=derivativesPeriod(interval);
  const [funding,oi,taker]=await Promise.all([
    getJson(`https://fapi.binance.com/fapi/v1/fundingRate?symbol=${encodeURIComponent(symbol)}&limit=24`),
    getJson(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${encodeURIComponent(symbol)}`),
    getJson(`https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=${encodeURIComponent(symbol)}&period=${period}&limit=30`)
  ]);
  const fr=(Array.isArray(funding)?funding:[]).map(x=>+x.fundingRate).filter(Number.isFinite);
  const tr=(Array.isArray(taker)?taker:[]).map(x=>+x.buySellRatio).filter(Number.isFinite);
  const latestFunding=fr.at(-1)??null, avgFunding=fr.length?mean(fr):null, latestTaker=tr.at(-1)??null, avgTaker=tr.length?mean(tr):null;
  let score=0, crowding='BALANCED', flow='BALANCED';
  if(latestFunding!=null){
    if(latestFunding>=0.0005){ score-=1; crowding='LONG_CROWDED'; }
    else if(latestFunding<=-0.0005){ score+=1; crowding='SHORT_CROWDED'; }
  }
  if(latestTaker!=null){
    if(latestTaker>=1.15){ score+=1; flow='BUY_DOMINANT'; }
    else if(latestTaker<=0.87){ score-=1; flow='SELL_DOMINANT'; }
  }
  return {
    symbol, latest_funding:latestFunding, avg_funding_24:avgFunding,
    open_interest:+oi.openInterest, open_interest_time:oi.time,
    taker_ratio_latest:latestTaker, taker_ratio_avg_30:avgTaker,
    crowding, flow, score, mode:'SHADOW_LIVE_ONLY', fetched_at:Date.now()
  };
}

function runAtlasV4Backtest(candles, options={}){
  if(!Array.isArray(candles)||candles.length<160) throw new Error('V4 backtest needs at least 160 candles.');
  const initialCapital=Number(options.initialCapital||10000), baseRiskPct=Number(options.riskPct||1)/100, feePct=Number(options.feePct??0.1)/100;
  let equity=initialCapital; const curve=[equity], trades=[]; const blocks={range:0,opposite:0,base_wait:0};
  for(let i=80;i<candles.length-1;i++){
    const history=candles.slice(0,i+1), base=analyzeMarket(history), gated=applyRegimeGate(history,base);
    if(base.signal==='WAIT'){ blocks.base_wait++; continue; }
    if(gated.signal==='WAIT'){
      if(gated.regime.regime==='RANGE') blocks.range++; else blocks.opposite++;
      continue;
    }
    const entryCandle=candles[i+1], direction=gated.signal, entry=entryCandle.open, atrValue=base.indicators.atr14;
    if(!atrValue) continue;
    const stop=direction==='BUY'?entry-1.5*atrValue:entry+1.5*atrValue, target=direction==='BUY'?entry+3*atrValue:entry-3*atrValue;
    const stopDistance=Math.abs(entry-stop); if(!stopDistance) continue;
    const effectiveRiskPct=baseRiskPct*gated.regime_gate.risk_scalar, riskCash=equity*effectiveRiskPct, qty=riskCash/stopDistance;
    let exit=null,exitIndex=null,outcome='OPEN';
    for(let j=i+1;j<candles.length;j++){
      const c=candles[j], hitStop=direction==='BUY'?c.low<=stop:c.high>=stop, hitTarget=direction==='BUY'?c.high>=target:c.low<=target;
      if(hitStop&&hitTarget){exit=stop;exitIndex=j;outcome='LOSS';break;}
      if(hitStop){exit=stop;exitIndex=j;outcome='LOSS';break;}
      if(hitTarget){exit=target;exitIndex=j;outcome='WIN';break;}
    }
    if(exit==null){exitIndex=candles.length-1;exit=candles[exitIndex].close; const raw=direction==='BUY'?exit-entry:entry-exit; outcome=raw>=0?'WIN':'LOSS';}
    const gross=direction==='BUY'?(exit-entry)*qty:(entry-exit)*qty, fees=(Math.abs(entry*qty)+Math.abs(exit*qty))*feePct, net=gross-fees, before=equity;
    equity+=net; trades.push({id:trades.length+1,side:direction,entry_time:entryCandle.time,exit_time:candles[exitIndex].time,entry:roundPrice(entry),exit:roundPrice(exit),net_pnl:net,r_multiple:riskCash?net/riskCash:0,regime:gated.regime.regime,volatility:gated.regime.volatility,risk_scalar:gated.regime_gate.risk_scalar,equity_before:before,equity_after:equity}); curve.push(equity);
    i=Math.max(i,exitIndex-1); if(equity<=0) break;
  }
  const wins=trades.filter(t=>t.net_pnl>0), losses=trades.filter(t=>t.net_pnl<=0), gp=wins.reduce((s,t)=>s+t.net_pnl,0), gl=Math.abs(losses.reduce((s,t)=>s+t.net_pnl,0));
  const rs=trades.map(t=>t.r_multiple), sr=std(rs)?mean(rs)/std(rs)*Math.sqrt(rs.length):0, ret=(equity/initialCapital-1)*100, pf=gl?gp/gl:(gp>0?Infinity:0), dd=maxDrawdownPct(curve), wr=trades.length?wins.length/trades.length*100:0, avg=mean(rs);
  const pass=trades.length>=20&&ret>0&&pf>=1.2&&dd<=25;
  return {backtest_version:'4.0.0',engine_version:ATLAS_V4_VERSION,variant:'REGIME_GATE_ONLY',verdict:pass?'PASS':'FAIL',trades:trades.length,wins:wins.length,losses:losses.length,win_rate:+wr.toFixed(2),net_pnl:+(equity-initialCapital).toFixed(2),return_pct:+ret.toFixed(2),profit_factor:Number.isFinite(pf)?+pf.toFixed(2):'Infinity',max_drawdown:+dd.toFixed(2),sharpe_ratio:+sr.toFixed(2),avg_r:+avg.toFixed(2),final_equity:+equity.toFixed(2),blocked_signals:blocks,trade_log:trades,equity_curve:curve.map(x=>+x.toFixed(2)),assumptions:{...options,regime_gate:true,derivatives_in_backtest:false,derivatives_reason:'Public OI/taker history limited to ~30 days; kept shadow-only to avoid false long-history backtest.'}};
}
