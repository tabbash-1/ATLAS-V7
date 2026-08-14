const ATLAS_BACKTEST_VERSION = '3.0.0';

function maxDrawdownPct(curve){
  let peak = curve[0] || 1, maxDD = 0;
  for(const v of curve){
    if(v > peak) peak = v;
    const dd = peak ? (peak - v) / peak : 0;
    if(dd > maxDD) maxDD = dd;
  }
  return maxDD * 100;
}

function mean(xs){ return xs.length ? xs.reduce((a,b)=>a+b,0)/xs.length : 0; }
function std(xs){
  if(xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((s,x)=>s + (x-m)*(x-m),0)/(xs.length-1));
}

function runAtlasBacktest(candles, options={}){
  if(!Array.isArray(candles) || candles.length < 120) throw new Error('Backtest needs at least 120 candles.');
  const initialCapital = Number(options.initialCapital || 10000);
  const riskPct = Number(options.riskPct || 1) / 100;
  const feePct = Number(options.feePct ?? 0.1) / 100;
  const warmup = 60;

  let equity = initialCapital;
  const equityCurve = [equity];
  const trades = [];
  let pending = null;

  for(let i=warmup; i<candles.length-1; i++){
    // The signal uses information available only through candle i close.
    const history = candles.slice(0, i+1);
    const signal = analyzeMarket(history);
    if(signal.signal === 'WAIT' || !signal.indicators.atr14) continue;

    // Enter on the NEXT candle open to avoid same-candle look-ahead.
    const entryCandle = candles[i+1];
    const direction = signal.signal;
    const entry = entryCandle.open;
    const atrValue = signal.indicators.atr14;
    const stop = direction === 'BUY' ? entry - 1.5*atrValue : entry + 1.5*atrValue;
    const target = direction === 'BUY' ? entry + 3*atrValue : entry - 3*atrValue;
    const stopDistance = Math.abs(entry-stop);
    if(!Number.isFinite(stopDistance) || stopDistance <= 0) continue;

    const riskCash = equity * riskPct;
    const qty = riskCash / stopDistance;
    let exit = null, exitIndex = null, outcome = 'OPEN';

    for(let j=i+1; j<candles.length; j++){
      const c = candles[j];
      const hitStop = direction === 'BUY' ? c.low <= stop : c.high >= stop;
      const hitTarget = direction === 'BUY' ? c.high >= target : c.low <= target;

      if(hitStop && hitTarget){
        // Conservative ambiguity rule: stop first.
        exit = stop; exitIndex = j; outcome = 'LOSS'; break;
      }
      if(hitStop){ exit = stop; exitIndex = j; outcome = 'LOSS'; break; }
      if(hitTarget){ exit = target; exitIndex = j; outcome = 'WIN'; break; }
    }

    if(exit === null){
      exitIndex = candles.length-1;
      exit = candles[exitIndex].close;
      const raw = direction === 'BUY' ? exit-entry : entry-exit;
      outcome = raw >= 0 ? 'WIN' : 'LOSS';
    }

    const grossPnl = direction === 'BUY' ? (exit-entry)*qty : (entry-exit)*qty;
    const notionalEntry = Math.abs(entry*qty), notionalExit = Math.abs(exit*qty);
    const fees = (notionalEntry + notionalExit) * feePct;
    const netPnl = grossPnl - fees;
    const equityBefore = equity;
    equity += netPnl;
    const rMultiple = riskCash ? netPnl/riskCash : 0;

    trades.push({
      id: trades.length+1,
      signal_time: candles[i].time,
      entry_time: entryCandle.time,
      exit_time: candles[exitIndex].time,
      side: direction,
      confidence: signal.confidence,
      score: signal.score,
      entry: roundPrice(entry),
      stop: roundPrice(stop),
      target: roundPrice(target),
      exit: roundPrice(exit),
      qty,
      fees,
      net_pnl: netPnl,
      r_multiple: rMultiple,
      outcome,
      equity_before: equityBefore,
      equity_after: equity
    });
    equityCurve.push(equity);

    // Skip all candles consumed by this position. One position at a time.
    i = Math.max(i, exitIndex-1);
    if(equity <= 0) break;
  }

  const wins = trades.filter(t=>t.net_pnl>0);
  const losses = trades.filter(t=>t.net_pnl<=0);
  const grossProfit = wins.reduce((s,t)=>s+t.net_pnl,0);
  const grossLoss = Math.abs(losses.reduce((s,t)=>s+t.net_pnl,0));
  const rSeries = trades.map(t=>t.r_multiple);
  const sharpePerTrade = std(rSeries) ? mean(rSeries)/std(rSeries)*Math.sqrt(rSeries.length) : 0;
  const netReturnPct = (equity/initialCapital - 1) * 100;
  const winRate = trades.length ? wins.length/trades.length*100 : 0;
  const profitFactor = grossLoss ? grossProfit/grossLoss : (grossProfit>0 ? Infinity : 0);
  const maxDD = maxDrawdownPct(equityCurve);
  const avgR = mean(rSeries);

  // Research qualification: enough sample + profitability + controlled drawdown.
  const pass = trades.length >= 20 && netReturnPct > 0 && profitFactor >= 1.2 && maxDD <= 25;

  return {
    backtest_version: ATLAS_BACKTEST_VERSION,
    engine_version: typeof ATLAS_ENGINE_VERSION !== 'undefined' ? ATLAS_ENGINE_VERSION : 'unknown',
    assumptions: {
      signal_at: 'candle close',
      entry_at: 'next candle open',
      intrabar_both_hit: 'stop-first (conservative)',
      one_position_at_a_time: true,
      initial_capital: initialCapital,
      risk_per_trade_pct: riskPct*100,
      fee_each_side_pct: feePct*100
    },
    verdict: pass ? 'PASS' : 'FAIL',
    trades: trades.length,
    wins: wins.length,
    losses: losses.length,
    win_rate: Number(winRate.toFixed(2)),
    net_pnl: Number((equity-initialCapital).toFixed(2)),
    return_pct: Number(netReturnPct.toFixed(2)),
    profit_factor: Number.isFinite(profitFactor) ? Number(profitFactor.toFixed(2)) : 'Infinity',
    max_drawdown: Number(maxDD.toFixed(2)),
    sharpe_ratio: Number(sharpePerTrade.toFixed(2)),
    avg_r: Number(avgR.toFixed(2)),
    final_equity: Number(equity.toFixed(2)),
    trade_log: trades,
    equity_curve: equityCurve.map(v=>Number(v.toFixed(2)))
  };
}

async function fetchBinanceHistory(asset, interval, desired=1000){
  const symbol = tvToBinanceSymbol(asset.symbol);
  const intv = binanceInterval(interval);
  const all = [];
  let endTime = Date.now();
  while(all.length < desired){
    const need = Math.min(1000, desired-all.length);
    const url = `https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${intv}&limit=${need}&endTime=${endTime}`;
    const res = await fetch(url);
    if(!res.ok) throw new Error(`Binance history HTTP ${res.status}`);
    const data = await res.json();
    if(!Array.isArray(data) || !data.length) break;
    const batch = data.map(k=>({time:k[0],open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}));
    all.unshift(...batch);
    endTime = batch[0].time - 1;
    if(batch.length < need) break;
  }
  const dedup = [...new Map(all.map(c=>[c.time,c])).values()].sort((a,b)=>a.time-b.time);
  return dedup.slice(-desired);
}

async function fetchBacktestCandles(asset, interval, apiKey, desired=1000){
  if(asset.cls==='Crypto' && asset.symbol.startsWith('BINANCE:')){
    return {provider:'Binance Public', candles: await fetchBinanceHistory(asset, interval, desired)};
  }
  // Twelve Data supports larger outputsize depending on plan; request desired and use what is returned.
  if(!apiKey) throw new Error('Twelve Data API key required for this asset class.');
  const params = new URLSearchParams({symbol:tvToTwelveSymbol(asset),interval:twelveInterval(interval),outputsize:String(desired),apikey:apiKey,format:'JSON'});
  const res = await fetch(`https://api.twelvedata.com/time_series?${params}`);
  if(!res.ok) throw new Error(`Twelve Data HTTP ${res.status}`);
  const data = await res.json();
  if(data.status==='error' || !Array.isArray(data.values)) throw new Error(data.message || 'No Twelve Data history returned');
  return {provider:'Twelve Data',candles:data.values.slice().reverse().map(k=>({time:Date.parse(k.datetime),open:+k.open,high:+k.high,low:+k.low,close:+k.close,volume:+(k.volume||0)}))};
}
