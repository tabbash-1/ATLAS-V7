const DEFAULT_ASSETS = [
  { name: 'Bitcoin / USDT', symbol: 'BINANCE:BTCUSDT', cls: 'Crypto' },
  { name: 'Ethereum / USDT', symbol: 'BINANCE:ETHUSDT', cls: 'Crypto' },
  { name: 'Solana / USDT', symbol: 'BINANCE:SOLUSDT', cls: 'Crypto' },
  { name: 'XRP / USDT', symbol: 'BINANCE:XRPUSDT', cls: 'Crypto' },
  { name: 'BNB / USDT', symbol: 'BINANCE:BNBUSDT', cls: 'Crypto' },
  { name: 'Dogecoin / USDT', symbol: 'BINANCE:DOGEUSDT', cls: 'Crypto' },
  { name: 'Zcash / USDT', symbol: 'BINANCE:ZECUSDT', cls: 'Crypto' },
  { name: 'Hyperliquid / USDT', symbol: 'BINANCE:HYPEUSDT', cls: 'Crypto' }
];

const savedAssets = JSON.parse(localStorage.getItem('atlas.assets') || 'null');
const savedCrypto = Array.isArray(savedAssets)
  ? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))
  : [];
const assetMap = new Map(DEFAULT_ASSETS.map(a => [a.symbol, a]));
savedCrypto.forEach(a => assetMap.set(String(a.symbol).toUpperCase(), {...a, cls: 'Crypto'}));
const cryptoAssets = [...assetMap.values()];
localStorage.setItem('atlas.assets', JSON.stringify(cryptoAssets));

const state = {
  assets: cryptoAssets,
  active: 0,
  interval: 'D',
  trial: null,
  liveResults: {},
  apiKey: localStorage.getItem('atlas.twelveApiKey') || '',
  backtests: {},
  v4Backtests: {},
  v4Live: {}
};

const $ = (id) => document.getElementById(id);
const watchlist = $('watchlist');
const assetTable = $('assetTable');
const dialog = $('assetDialog');
const settingsDialog = $('settingsDialog');

function resultKey(){ const a=state.assets[state.active]; return `${a.symbol}|${state.interval}`; }
function backtestKey(){ return resultKey(); }
function saveAssets(){ localStorage.setItem('atlas.assets', JSON.stringify(state.assets)); }
function cleanDisplayName(asset){ return asset.name.replace('Bitcoin','BTC').replace('Ethereum','ETH'); }

function renderWatchlist(){
  watchlist.innerHTML = '';
  state.assets.forEach((a,i) => {
    const el = document.createElement('div');
    el.className = 'watch-item' + (i === state.active ? ' active' : '');
    el.innerHTML = `<div><div class="watch-name">${cleanDisplayName(a)}</div><div class="watch-symbol">${a.symbol}</div></div><span class="class-tag">${a.cls}</span>`;
    el.onclick = () => { state.active = i; renderAll(); };
    watchlist.appendChild(el);
  });
}

function renderAssetTable(){
  assetTable.innerHTML = '';
  state.assets.forEach((a,i) => {
    const row = document.createElement('div');
    row.className = 'asset-row';
    row.innerHTML = `<strong>${a.name}</strong><span class="sym">${a.symbol}</span><span>${a.cls}</span><button class="remove" data-i="${i}">Remove</button>`;
    row.querySelector('button').onclick = () => {
      if(state.assets.length === 1) return alert('ATLAS needs at least one asset.');
      state.assets.splice(i,1); state.active = Math.min(state.active, state.assets.length - 1);
      saveAssets(); renderAll();
    };
    assetTable.appendChild(row);
  });
}

function loadTradingView(symbol){
  const host = $('tradingview-host');
  host.innerHTML = '<div class="tradingview-widget-container" style="height:100%;width:100%"><div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div></div>';
  const script = document.createElement('script');
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  script.async = true;
  script.innerHTML = JSON.stringify({autosize:true,symbol,interval:state.interval,timezone:'exchange',theme:'dark',style:'1',locale:'en',backgroundColor:'rgba(8, 11, 16, 1)',gridColor:'rgba(32, 41, 56, 0.6)',allow_symbol_change:true,withdateranges:true,hide_side_toolbar:false,save_image:false,calendar:false,support_host:'https://www.tradingview.com'});
  host.firstElementChild.appendChild(script);
}

function setPill(el,text,kind='neutral'){ el.textContent=text; el.className=`pill ${kind}`; }
function resetSignal(){
  setPill($('signalState'),'WAIT','neutral');
  $('confidence').textContent='—'; $('entry').textContent='—'; $('stop').textContent='—'; $('target').textContent='—'; $('rr').textContent='—';
  ['trendState','momentumState','volumeState','structureState'].forEach(id=>$(id).textContent='Pending');
  $('providerLabel').textContent='No analysis yet';
  $('metricsGrid').innerHTML=[['EMA 20','—'],['EMA 50','—'],['RSI 14','—'],['ATR 14','—'],['Volume ratio','—'],['Engine score','—']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
}

function pick(obj, keys){ for(const k of keys){ if(obj && obj[k] !== undefined && obj[k] !== null) return obj[k]; } return null; }
function fmt(v){ if(v===null||v===undefined) return '—'; if(typeof v==='number') return Number.isInteger(v)?String(v):v.toFixed(2); return String(v); }
function priceFmt(v){ if(v==null) return '—'; return typeof v==='number' ? v.toLocaleString(undefined,{maximumFractionDigits:8}) : String(v); }

function applySignal(r, provider='Imported trial'){
  if(!r) return resetSignal();
  const verdict=String(pick(r,['signal','verdict','decision','status','result'])||'WAIT').toUpperCase();
  setPill($('signalState'),verdict,verdict==='BUY'?'buy':verdict==='SELL'?'sell':'neutral');
  const conf=pick(r,['confidence','confidence_pct','score']);
  $('confidence').textContent=conf===null?'—':(String(conf).includes('%')?conf:`${fmt(conf)}%`);
  $('entry').textContent=priceFmt(pick(r,['entry','entry_price','price']));
  $('stop').textContent=priceFmt(pick(r,['stop','stop_loss','sl']));
  $('target').textContent=priceFmt(pick(r,['target','take_profit','tp']));
  $('rr').textContent=fmt(pick(r,['risk_reward','rr','r_multiple']));
  const engine=pick(r,['engine','checks','components'])||{};
  $('trendState').textContent=fmt(pick(engine,['trend'])??pick(r,['trend']));
  $('momentumState').textContent=fmt(pick(engine,['momentum'])??pick(r,['momentum']));
  $('volumeState').textContent=fmt(pick(engine,['volume'])??pick(r,['volume']));
  $('structureState').textContent=fmt(pick(engine,['structure'])??pick(r,['structure']));
  $('providerLabel').textContent=provider;
  const ind=r.indicators||{};
  const items=[['EMA 20',ind.ema20],['EMA 50',ind.ema50],['RSI 14',ind.rsi14],['ATR 14',ind.atr14],['Volume ratio',ind.volume_ratio],['Engine score',r.score]];
  $('metricsGrid').innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${priceFmt(v)}</b></div>`).join('');
}

function locateAssetTrial(data, asset){
  const hay=[asset.symbol,asset.name,asset.symbol.split(':').pop(),asset.symbol.replace(/[^A-Z0-9]/gi,'')].map(x=>x.toLowerCase());
  const candidates=[];
  if(Array.isArray(data)) candidates.push(...data);
  if(data&&typeof data==='object'){
    for(const [k,v] of Object.entries(data)){ if(v&&typeof v==='object'&&!Array.isArray(v)) candidates.push({...v,__key:k}); }
    ['assets','symbols','results','trials','markets','summary'].forEach(k=>{ const v=data[k]; if(Array.isArray(v)) candidates.push(...v); else if(v&&typeof v==='object') for(const [kk,vv] of Object.entries(v)) if(vv&&typeof vv==='object') candidates.push({...vv,__key:kk}); });
  }
  return candidates.find(c=>{ const s=[c.symbol,c.asset,c.market,c.pair,c.ticker,c.__key].filter(Boolean).join(' ').toLowerCase(); return hay.some(h=>s.includes(h)||h.includes(s)); })||null;
}

function renderTrial(){
  if(!state.trial){ $('trialBadge').textContent='NO DATA'; $('trialContent').className='trial-empty'; $('trialContent').innerHTML='Import <code>FINAL_REAL_MARKET_TRIAL_SUMMARY.json</code> to inspect actual results.'; return; }
  const active=state.assets[state.active], r=locateAssetTrial(state.trial,active);
  $('trialBadge').textContent=r?'MATCHED':'IMPORTED'; $('trialContent').className='trial-grid';
  const source=r||state.trial;
  const items=[['Verdict',pick(source,['verdict','status','result','signal'])],['Trades',pick(source,['trades','trade_count','n_trades','total_trades'])],['Win rate',pick(source,['win_rate','winrate','win_rate_pct'])],['P&L / Return',pick(source,['pnl','return','return_pct','net_return','net_pnl'])],['Max DD',pick(source,['max_drawdown','drawdown','max_dd'])],['Sharpe',pick(source,['sharpe','sharpe_ratio'])]];
  $('trialContent').innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${fmt(v)}</b></div>`).join('');
}

function renderActiveSignal(){
  const cached=state.liveResults[resultKey()];
  if(cached){
    applySignal(cached.result,`${cached.provider} · ${new Date(cached.time).toLocaleString()}`);
    if(cached.confluence && typeof renderConfluence === 'function') renderConfluence(cached.confluence);
    else if(typeof resetConfluence === 'function') resetConfluence();
  } else {
    resetSignal();
    if(typeof resetConfluence === 'function') resetConfluence();
  }
}

async function analyzeActive(){
  const asset=state.assets[state.active];
  setPill($('engineBadge'),'FETCHING','working');
  $('providerLabel').textContent='Loading candles…';
  $('analyzeBtn').disabled=true;
  try{
    const {provider,candles}=await fetchMarketCandles(asset,state.interval,state.apiKey);
    window.ATLAS_LATEST_CANDLES=candles;
    const result=analyzeMarket(candles);
    window.ATLAS_LATEST_BASE=result;
    const confluence=analyzeAtlasConfluence(candles,result);
    window.ATLAS_LATEST_CONFLUENCE=confluence;
    state.liveResults[resultKey()]={provider,result,confluence,time:Date.now()};
    applySignal(result,`${provider} · ${candles.length} candles · ${new Date().toLocaleString()}`);
    renderConfluence(confluence);
    if(window.refreshTradeManagement) setTimeout(()=>window.refreshTradeManagement(result,confluence),50);
    if(window.refreshAnomaly) setTimeout(()=>window.refreshAnomaly(candles,confluence),80);
    if(window.computeMasterConviction) window.computeMasterConviction(result,confluence,asset.symbol).catch(console.warn);
    if(window.recordConfluenceObservation) window.recordConfluenceObservation(asset,candles,confluence);
    setPill($('engineBadge'),'ANALYZED','buy');
  }catch(err){
    console.error(err); setPill($('engineBadge'),'ERROR','sell');
    $('providerLabel').textContent=err.message; $('providerLabel').className='muted small engine-error';
    if(String(err.message).includes('API key')) settingsDialog.showModal();
  }finally{ $('analyzeBtn').disabled=false; }
}

function renderAll(){
  const asset=state.assets[state.active];
  window.ATLAS_APP_STATE=state; window.ATLAS_STATE={selectedAsset:asset};
  $('activeTitle').textContent=asset.name; $('tvSymbolLabel').textContent=asset.symbol;
  $('providerLabel').className='muted small';
  renderWatchlist(); renderAssetTable(); loadTradingView(asset.symbol); renderTrial(); renderActiveSignal(); renderBacktest(); renderV4();
  setPill($('engineBadge'),state.liveResults[resultKey()]?'CACHED':'READY',state.liveResults[resultKey()]?'buy':'neutral');
}


function pctFmt(v){ return v==null ? '—' : `${Number(v).toFixed(2)}%`; }
function moneyFmt(v){ return v==null ? '—' : Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }

function renderBacktest(){
  const cached = state.backtests[backtestKey()];
  const metrics = $('backtestMetrics');
  $('tradeLog').hidden = true;
  if(!cached){
    setPill($('backtestBadge'),'NOT RUN','neutral');
    $('backtestMeta').textContent='Run a historical test for the selected asset and timeframe.';
    metrics.innerHTML=[['Verdict','—'],['Trades','—'],['Win rate','—'],['Net return','—'],['Profit factor','—'],['Max DD','—'],['Sharpe*','—'],['Avg R','—'],['Final equity','—']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    $('exportBacktestBtn').disabled=true; $('showTradesBtn').disabled=true; return;
  }
  const r=cached.result;
  setPill($('backtestBadge'),r.verdict,r.verdict==='PASS'?'buy':'sell');
  $('backtestMeta').textContent=`${cached.provider} · ${cached.candles} candles · ${new Date(cached.time).toLocaleString()} · Engine ${r.engine_version}`;
  const items=[['Verdict',r.verdict],['Trades',r.trades],['Win rate',pctFmt(r.win_rate)],['Net return',pctFmt(r.return_pct)],['Profit factor',r.profit_factor],['Max DD',pctFmt(r.max_drawdown)],['Sharpe*',r.sharpe_ratio],['Avg R',r.avg_r],['Final equity',moneyFmt(r.final_equity)]];
  metrics.innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  $('exportBacktestBtn').disabled=false; $('showTradesBtn').disabled=false;
}

async function runBacktestActive(){
  const asset=state.assets[state.active];
  const desired=Number($('backtestCandles').value || 1000);
  $('backtestBtn').disabled=true; setPill($('backtestBadge'),'FETCHING','working');
  $('backtestMeta').textContent='Loading historical candles…';
  try{
    const {provider,candles}=await fetchBacktestCandles(asset,state.interval,state.apiKey,desired);
    if(candles.length < 120) throw new Error(`Only ${candles.length} candles returned; at least 120 are required.`);
    setPill($('backtestBadge'),'TESTING','working'); $('backtestMeta').textContent=`Testing ${candles.length} candles with frozen V2 rules…`;
    await new Promise(r=>setTimeout(r,20));
    const result=runAtlasBacktest(candles,{initialCapital:Number($('backtestCapital').value||10000),riskPct:Number($('backtestRisk').value||1),feePct:Number($('backtestFee').value||0.1)});
    state.backtests[backtestKey()]={provider,candles:candles.length,result,time:Date.now(),asset:{...asset},interval:state.interval};
    renderBacktest();
  }catch(err){
    console.error(err); setPill($('backtestBadge'),'ERROR','sell'); $('backtestMeta').textContent=err.message;
    if(String(err.message).includes('API key')) settingsDialog.showModal();
  }finally{ $('backtestBtn').disabled=false; }
}

function showTradeLog(){
  const cached=state.backtests[backtestKey()]; if(!cached) return;
  const box=$('tradeLog');
  if(!box.hidden){ box.hidden=true; return; }
  const rows=cached.result.trade_log;
  box.innerHTML=`<div class="trade-row head"><span>#</span><span>Side</span><span>Entry</span><span>Exit</span><span>Net P&L</span><span>R</span></div>`+rows.map(t=>`<div class="trade-row ${t.net_pnl>0?'trade-win':'trade-loss'}"><span>${t.id}</span><span>${t.side}</span><span>${priceFmt(t.entry)}</span><span>${priceFmt(t.exit)}</span><span>${moneyFmt(t.net_pnl)}</span><span>${Number(t.r_multiple).toFixed(2)}</span></div>`).join('');
  box.hidden=false;
}

function exportBacktest(){
  const cached=state.backtests[backtestKey()]; if(!cached) return;
  const payload={
    generated_at:new Date().toISOString(),
    project:'ATLAS',
    stage:'V3_BACKTEST',
    symbol:cached.asset.symbol,
    asset:cached.asset.name,
    asset_class:cached.asset.cls,
    timeframe:cached.interval,
    provider:cached.provider,
    candle_count:cached.candles,
    ...cached.result
  };
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='FINAL_REAL_MARKET_TRIAL_SUMMARY.json'; a.click(); URL.revokeObjectURL(url);
}

$('backtestBtn').onclick=runBacktestActive;
$('exportBacktestBtn').onclick=exportBacktest;
$('showTradesBtn').onclick=showTradeLog;

$('intervalSelect').onchange=e=>{ state.interval=e.target.value; renderAll(); };
$('analyzeBtn').onclick=analyzeActive;
$('settingsBtn').onclick=()=>{ $('twelveApiKey').value=state.apiKey; settingsDialog.showModal(); };
$('settingsForm').addEventListener('submit',e=>{ if(e.submitter&&e.submitter.value==='cancel') return; e.preventDefault(); state.apiKey=$('twelveApiKey').value.trim(); localStorage.setItem('atlas.twelveApiKey',state.apiKey); settingsDialog.close(); });
$('addAssetBtn').onclick=()=>dialog.showModal();
$('assetForm').addEventListener('submit',e=>{ if(e.submitter&&e.submitter.value==='cancel') return; e.preventDefault(); const a={name:$('assetName').value.trim(),symbol:$('assetSymbol').value.trim().toUpperCase(),cls:$('assetClass').value}; if(!a.name||!a.symbol)return; state.assets.push(a);state.active=state.assets.length-1;saveAssets();dialog.close();e.target.reset();renderAll(); });
$('importBtn').onclick=()=>$('fileInput').click();
$('fileInput').onchange=async e=>{ const f=e.target.files[0];if(!f)return;try{state.trial=JSON.parse(await f.text());renderTrial();}catch(err){alert('Invalid JSON file: '+err.message);}e.target.value=''; };


function v4Key(){ return resultKey(); }
function numFmt(v,d=2){ return v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d); }
function fundingFmt(v){ return v==null?'—':`${(Number(v)*100).toFixed(4)}%`; }
function compactNum(v){
  if(v==null||!Number.isFinite(Number(v))) return '—';
  const n=Number(v), a=Math.abs(n);
  if(a>=1e9) return `${(n/1e9).toFixed(2)}B`;
  if(a>=1e6) return `${(n/1e6).toFixed(2)}M`;
  if(a>=1e3) return `${(n/1e3).toFixed(2)}K`;
  return n.toFixed(2);
}
function renderRegime(regime, riskScalar='—'){
  const items=regime?[
    ['Regime',regime.regime],['Volatility',regime.volatility],['ADX 14',regime.adx14],
    ['ATR %',`${regime.atr_pct}%`],['EMA spread %',`${regime.ema_spread_pct}%`],['Risk scalar',riskScalar]
  ]:[['Regime','—'],['Volatility','—'],['ADX 14','—'],['ATR %','—'],['EMA spread %','—'],['Risk scalar','—']];
  $('regimeGrid').innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
}
function renderDerivatives(d){
  if(!d){
    $('derivativesGrid').innerHTML=[['Funding','—'],['Open interest','—'],['Taker ratio','—'],['Crowding','—'],['Flow','—'],['Score','—']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    return;
  }
  const items=[['Funding',fundingFmt(d.latest_funding)],['Open interest',compactNum(d.open_interest)],['Taker ratio',numFmt(d.taker_ratio_latest)],['Crowding',d.crowding],['Flow',d.flow],['Score',d.score]];
  $('derivativesGrid').innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
}
function renderV4(){
  if(!$('v4Badge')) return;
  const live=state.v4Live[v4Key()], bt=state.v4Backtests[v4Key()];
  if(live){ renderRegime(live.regime,live.riskScalar); renderDerivatives(live.derivatives); $('derivativesMeta').textContent=live.derivatives?`Binance USDⓈ-M snapshot · ${new Date(live.time).toLocaleString()} · observational only`:(live.derivativesError||'Derivatives not available for this asset.'); }
  else { renderRegime(null); renderDerivatives(null); $('derivativesMeta').textContent='Not fetched. Binance derivatives factor is kept out of long-history backtests until ATLAS builds its own archive.'; }
  if(!bt){
    setPill($('v4Badge'),'NOT RUN','neutral');
    $('v4BacktestMetrics').innerHTML=[['Verdict','—'],['Trades','—'],['Win rate','—'],['Net return','—'],['Profit factor','—'],['Max DD','—'],['Sharpe*','—'],['Avg R','—'],['Blocked signals','—']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    $('compareV4Btn').disabled=true; $('exportV4Btn').disabled=true; $('v4Comparison').hidden=true;
    return;
  }
  const r=bt.v4, blocked=Object.values(r.blocked_signals||{}).reduce((a,b)=>a+b,0);
  setPill($('v4Badge'),r.verdict,r.verdict==='PASS'?'buy':'sell');
  $('v4Meta').textContent=`${bt.provider} · ${bt.candles} candles · same data tested by V3 and V4 · ${new Date(bt.time).toLocaleString()}`;
  const items=[['Verdict',r.verdict],['Trades',r.trades],['Win rate',pctFmt(r.win_rate)],['Net return',pctFmt(r.return_pct)],['Profit factor',r.profit_factor],['Max DD',pctFmt(r.max_drawdown)],['Sharpe*',r.sharpe_ratio],['Avg R',r.avg_r],['Blocked signals',blocked]];
  $('v4BacktestMetrics').innerHTML=items.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  $('compareV4Btn').disabled=false; $('exportV4Btn').disabled=false;
}
async function analyzeV4Live(){
  const asset=state.assets[state.active]; $('analyzeV4Btn').disabled=true; setPill($('v4Badge'),'ANALYZING','working');
  try{
    const {provider,candles}=await fetchMarketCandles(asset,state.interval,state.apiKey);
    const base=analyzeMarket(candles), gated=applyRegimeGate(candles,base);
    let derivatives=null, derivativesError=null;
    try{ derivatives=await fetchDerivativesSnapshot(asset,state.interval); }catch(e){ derivativesError=e.message; }
    state.v4Live[v4Key()]={provider,regime:gated.regime,riskScalar:gated.regime_gate.risk_scalar,baseSignal:base.signal,gatedSignal:gated.signal,derivatives,derivativesError,time:Date.now()};
    renderV4(); setPill($('v4Badge'),'LIVE READY','buy');
  }catch(err){ console.error(err); setPill($('v4Badge'),'ERROR','sell'); $('v4Meta').textContent=err.message; }
  finally{$('analyzeV4Btn').disabled=false;}
}
async function runV4BacktestActive(){
  const asset=state.assets[state.active], desired=Number($('backtestCandles').value||1000), opts={initialCapital:Number($('backtestCapital').value||10000),riskPct:Number($('backtestRisk').value||1),feePct:Number($('backtestFee').value||0.1)};
  $('runV4Btn').disabled=true; setPill($('v4Badge'),'FETCHING','working'); $('v4Meta').textContent='Loading one historical dataset for an apples-to-apples V3 ↔ V4 comparison…';
  try{
    const {provider,candles}=await fetchBacktestCandles(asset,state.interval,state.apiKey,desired);
    if(candles.length<160) throw new Error(`Only ${candles.length} candles returned; V4 requires at least 160.`);
    setPill($('v4Badge'),'TESTING','working'); await new Promise(r=>setTimeout(r,20));
    const baseline=runAtlasBacktest(candles,opts), v4=runAtlasV4Backtest(candles,opts);
    state.v4Backtests[v4Key()]={provider,candles:candles.length,asset:{...asset},interval:state.interval,time:Date.now(),v3:baseline,v4};
    renderV4(); showV4Comparison();
  }catch(err){console.error(err);setPill($('v4Badge'),'ERROR','sell');$('v4Meta').textContent=err.message;}
  finally{$('runV4Btn').disabled=false;}
}
function deltaClass(v,goodWhenPositive=true){ const good=goodWhenPositive?v>=0:v<=0; return good?'delta-positive':'delta-negative'; }
function showV4Comparison(){
  const bt=state.v4Backtests[v4Key()]; if(!bt)return;
  const a=bt.v3,b=bt.v4, ret=b.return_pct-a.return_pct, pf=Number(b.profit_factor)-Number(a.profit_factor), dd=b.max_drawdown-a.max_drawdown;
  const rows=[
    ['Trades',a.trades,b.trades,b.trades-a.trades,'neutral'],
    ['Return %',a.return_pct,b.return_pct,ret,deltaClass(ret,true)],
    ['Profit factor',a.profit_factor,b.profit_factor,pf,deltaClass(pf,true)],
    ['Max DD %',a.max_drawdown,b.max_drawdown,dd,deltaClass(dd,false)],
    ['Sharpe*',a.sharpe_ratio,b.sharpe_ratio,b.sharpe_ratio-a.sharpe_ratio,deltaClass(b.sharpe_ratio-a.sharpe_ratio,true)]
  ];
  $('v4Comparison').innerHTML=`<div class="compare-grid"><div class="compare-head">Metric</div><div class="compare-head">V3 frozen</div><div class="compare-head">V4 regime</div><div class="compare-head">Δ V4−V3</div>${rows.map(r=>`<div>${r[0]}</div><div>${numFmt(r[1])}</div><div>${numFmt(r[2])}</div><div class="${r[4]}">${r[3]>=0?'+':''}${numFmt(r[3])}</div>`).join('')}</div>`;
  $('v4Comparison').hidden=false;
}
function exportV4(){
  const bt=state.v4Backtests[v4Key()]; if(!bt)return;
  const live=state.v4Live[v4Key()]||null;
  const payload={generated_at:new Date().toISOString(),project:'ATLAS',stage:'V4_MULTI_FACTOR_RESEARCH',asset:bt.asset,timeframe:bt.interval,provider:bt.provider,candle_count:bt.candles,methodology:{v3:'frozen V2 rules',v4:'V3 + price-based market regime gate + volatility risk scalar',derivatives:'shadow/live only; excluded from long-history backtest because public OI/taker history is limited'},v3_baseline:bt.v3,v4_regime:bt.v4,live_factor_snapshot:live};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a'); a.href=url;a.download='ATLAS_V4_FACTOR_RESEARCH.json';a.click();URL.revokeObjectURL(url);
}
$('analyzeV4Btn').onclick=analyzeV4Live;
$('runV4Btn').onclick=runV4BacktestActive;
$('compareV4Btn').onclick=showV4Comparison;
$('exportV4Btn').onclick=exportV4;

renderAll();
