const ATLAS_ENGINE_VERSION = '2.0.0';

function sma(values, period){
  if(values.length < period) return null;
  const slice = values.slice(-period);
  return slice.reduce((a,b)=>a+b,0)/period;
}

function emaSeries(values, period){
  if(values.length < period) return [];
  const k = 2/(period+1);
  let ema = values.slice(0,period).reduce((a,b)=>a+b,0)/period;
  const out = Array(period-1).fill(null); out.push(ema);
  for(let i=period;i<values.length;i++){ ema = values[i]*k + ema*(1-k); out.push(ema); }
  return out;
}

function rsi(values, period=14){
  if(values.length <= period) return null;
  let gains=0, losses=0;
  for(let i=values.length-period;i<values.length;i++){
    const d=values[i]-values[i-1]; if(d>=0) gains+=d; else losses-=d;
  }
  if(losses===0) return 100;
  const rs=(gains/period)/(losses/period); return 100-(100/(1+rs));
}

function atr(candles, period=14){
  if(candles.length <= period) return null;
  const trs=[];
  for(let i=1;i<candles.length;i++){
    const c=candles[i], p=candles[i-1];
    trs.push(Math.max(c.high-c.low, Math.abs(c.high-p.close), Math.abs(c.low-p.close)));
  }
  return sma(trs, period);
}

function clamp(v,min,max){ return Math.max(min,Math.min(max,v)); }
function roundPrice(v){
  if(v == null || !Number.isFinite(v)) return null;
  if(Math.abs(v)>=1000) return Number(v.toFixed(2));
  if(Math.abs(v)>=1) return Number(v.toFixed(4));
  return Number(v.toFixed(8));
}

function analyzeMarket(candles){
  if(!Array.isArray(candles) || candles.length < 60) throw new Error('ATLAS needs at least 60 candles.');
  const close=candles.map(x=>x.close), volume=candles.map(x=>x.volume||0);
  const ema20s=emaSeries(close,20), ema50s=emaSeries(close,50);
  const last=candles.at(-1), prev=candles.at(-2);
  const ema20=ema20s.at(-1), ema50=ema50s.at(-1), rsi14=rsi(close,14), atr14=atr(candles,14);
  const avgVol=sma(volume,20);
  const recentHigh=Math.max(...candles.slice(-21,-1).map(x=>x.high));
  const recentLow=Math.min(...candles.slice(-21,-1).map(x=>x.low));

  let score=0;
  const checks={};

  if(last.close>ema20 && ema20>ema50){ score+=2; checks.trend='Bullish'; }
  else if(last.close<ema20 && ema20<ema50){ score-=2; checks.trend='Bearish'; }
  else checks.trend='Mixed';

  if(rsi14>=55 && rsi14<=75){ score+=1; checks.momentum='Bullish'; }
  else if(rsi14<=45 && rsi14>=25){ score-=1; checks.momentum='Bearish'; }
  else if(rsi14>75){ score-=0.5; checks.momentum='Overbought'; }
  else if(rsi14<25){ score+=0.5; checks.momentum='Oversold'; }
  else checks.momentum='Neutral';

  const volumeRatio = avgVol ? last.volume/avgVol : 1;
  if(volumeRatio>=1.15){ checks.volume='Confirmed'; score += Math.sign(score || (last.close-prev.close)) * 0.5; }
  else checks.volume='Normal';

  if(last.close>recentHigh){ score+=1.5; checks.structure='Breakout ↑'; }
  else if(last.close<recentLow){ score-=1.5; checks.structure='Breakdown ↓'; }
  else if(last.close>ema20){ checks.structure='Above mean'; score+=0.5; }
  else if(last.close<ema20){ checks.structure='Below mean'; score-=0.5; }
  else checks.structure='Range';

  let signal='WAIT';
  if(score>=3) signal='BUY';
  else if(score<=-3) signal='SELL';
  const confidence = signal==='WAIT' ? Math.round(clamp(45+Math.abs(score)*6,45,69)) : Math.round(clamp(58+Math.abs(score)*7,60,92));

  let entry=last.close, stop=null, target=null, rr=null;
  if(signal==='BUY' && atr14){ stop=entry-1.5*atr14; target=entry+3*atr14; rr=2; }
  if(signal==='SELL' && atr14){ stop=entry+1.5*atr14; target=entry-3*atr14; rr=2; }

  return {
    version:ATLAS_ENGINE_VERSION, signal, confidence,
    entry:roundPrice(entry), stop:roundPrice(stop), target:roundPrice(target), risk_reward:rr,
    score:Number(score.toFixed(2)),
    engine:checks,
    indicators:{ema20:roundPrice(ema20),ema50:roundPrice(ema50),rsi14:Number(rsi14.toFixed(2)),atr14:roundPrice(atr14),volume_ratio:Number(volumeRatio.toFixed(2))},
    last_candle_time:last.time, candle_count:candles.length
  };
}

function binanceInterval(interval){ return ({'15':'15m','60':'1h','240':'4h','D':'1d','W':'1w'})[interval] || '1d'; }
function twelveInterval(interval){ return ({'15':'15min','60':'1h','240':'4h','D':'1day','W':'1week'})[interval] || '1day'; }

function tvToBinanceSymbol(tvSymbol){
  const raw=tvSymbol.split(':').pop().replace(/[^A-Z0-9]/g,'');
  return raw.replace('USD','USDT').replace('USDTT','USDT');
}
function tvToTwelveSymbol(asset){
  let raw=asset.symbol.split(':').pop();
  if(asset.cls==='Forex' && !raw.includes('/')) raw=raw.replace(/^([A-Z]{3})([A-Z]{3})$/,'$1/$2');
  if(asset.cls==='Crypto' && !raw.includes('/')) raw=raw.replace(/USDT$/,'/USDT').replace(/USD$/,'/USD');
  if(asset.cls==='Index' && raw==='SPX') raw='SPX';
  return raw;
}

async function fetchBinanceCandles(asset, interval, limit=240){
  const symbol=tvToBinanceSymbol(asset.symbol);
  const url=`https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${binanceInterval(interval)}&limit=${limit}`;
  const res=await fetch(url); if(!res.ok) throw new Error(`Binance HTTP ${res.status}`);
  const data=await res.json();
  if(!Array.isArray(data)) throw new Error(data?.msg || 'Unexpected Binance response');
  return data.map(k=>({time:k[0],open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}));
}

async function fetchTwelveCandles(asset, interval, apiKey, limit=240){
  if(!apiKey) throw new Error('Twelve Data API key required for this asset class.');
  const params=new URLSearchParams({symbol:tvToTwelveSymbol(asset),interval:twelveInterval(interval),outputsize:String(limit),apikey:apiKey,format:'JSON'});
  const res=await fetch(`https://api.twelvedata.com/time_series?${params}`); if(!res.ok) throw new Error(`Twelve Data HTTP ${res.status}`);
  const data=await res.json(); if(data.status==='error' || !Array.isArray(data.values)) throw new Error(data.message || 'No Twelve Data candles returned');
  return data.values.slice().reverse().map(k=>({time:Date.parse(k.datetime),open:+k.open,high:+k.high,low:+k.low,close:+k.close,volume:+(k.volume||0)}));
}

async function fetchMarketCandles(asset, interval, apiKey){
  if(asset.cls==='Crypto' && asset.symbol.startsWith('BINANCE:')) return {provider:'Binance Public',candles:await fetchBinanceCandles(asset,interval)};
  return {provider:'Twelve Data',candles:await fetchTwelveCandles(asset,interval,apiKey)};
}
