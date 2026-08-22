const ATLAS_TF_VERSION = '1.0.0';

function atlasNormalizeCandle(c){
  return {time:+c.time, open:+c.open, high:+c.high, low:+c.low, close:+c.close, volume:+(c.volume||0)};
}

function atlasBucketMs(tf){
  const map={'15M':15*60e3,'30M':30*60e3,'1H':60*60e3,'4H':4*60*60e3,'6H':6*60*60e3,'12H':12*60*60e3,'1D':24*60*60e3,'1W':7*24*60*60e3};
  return map[String(tf).toUpperCase()]||null;
}

function atlasResample(candles,tf){
  const bucket=atlasBucketMs(tf); if(!bucket) throw new Error(`Unsupported timeframe ${tf}`);
  const rows=(candles||[]).map(atlasNormalizeCandle).filter(c=>Number.isFinite(c.time)).sort((a,b)=>a.time-b.time);
  const out=[]; let cur=null;
  for(const c of rows){
    const key=Math.floor(c.time/bucket)*bucket;
    if(!cur || cur.time!==key){
      if(cur) out.push(cur);
      cur={time:key,open:c.open,high:c.high,low:c.low,close:c.close,volume:c.volume};
    }else{
      cur.high=Math.max(cur.high,c.high); cur.low=Math.min(cur.low,c.low); cur.close=c.close; cur.volume+=c.volume;
    }
  }
  if(cur) out.push(cur); return out;
}

async function atlasFetchBinance1h(asset,limit=1000){
  const symbol=tvToBinanceSymbol(asset.symbol);
  const url=`https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=1h&limit=${Math.min(1000,limit)}`;
  const res=await fetch(url); if(!res.ok) throw new Error(`Binance HTTP ${res.status}`);
  const data=await res.json();
  return data.map(k=>({time:k[0],open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}));
}

async function atlasBuildCryptoTimeframes(asset){
  const base=await atlasFetchBinance1h(asset,1000);
  const direct={};
  const daily=await fetchBinanceCandles(asset,'D',1000);
  const weekly=await fetchBinanceCandles(asset,'W',1000);
  direct['1W']=weekly; direct['1D']=daily;
  direct['12H']=atlasResample(base,'12H'); direct['6H']=atlasResample(base,'6H'); direct['4H']=atlasResample(base,'4H');
  direct['1H']=base; direct['30M']=[]; direct['15M']=[];
  try{ direct['15M']=await fetchBinanceCandles(asset,'15',1000); direct['30M']=atlasResample(direct['15M'],'30M'); }catch(_e){}
  return direct;
}

if(typeof window!=='undefined') window.ATLAS_TIMEFRAME_ENGINE={version:ATLAS_TF_VERSION,atlasResample,atlasBuildCryptoTimeframes};
if(typeof module!=='undefined') module.exports={atlasResample};
