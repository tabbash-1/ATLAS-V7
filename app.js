const DEFAULT_ASSETS = [
  { name: 'Bitcoin / USDT', symbol: 'BINANCE:BTCUSDT', cls: 'Crypto' },
  { name: 'Ethereum / USDT', symbol: 'BINANCE:ETHUSDT', cls: 'Crypto' },
  { name: 'Solana / USDT', symbol: 'BINANCE:SOLUSDT', cls: 'Crypto' },
  { name: 'XRP / USDT', symbol: 'BINANCE:XRPUSDT', cls: 'Crypto' },
  { name: 'BNB / USDT', symbol: 'BINANCE:BNBUSDT', cls: 'Crypto' },
  { name: 'Dogecoin / USDT', symbol: 'BINANCE:DOGEUSDT', cls: 'Crypto' },
  { name: 'Zcash / USDT', symbol: 'BINANCE:ZECUSDT', cls: 'Crypto' },
  { name: 'Hyperliquid / USDT', symbol: 'BYBIT:HYPEUSDT', cls: 'Crypto', apiSymbol: 'HYPEUSDT' }
];

const savedAssets = JSON.parse(localStorage.getItem('atlas.assets') || 'null');
const savedCrypto = Array.isArray(savedAssets)
  ? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))
  : [];
const assetMap = new Map(DEFAULT_ASSETS.map(a => [a.name, a]));
savedCrypto.forEach(a => {
  const name = String(a.name || '');
  if (name === 'Hyperliquid / USDT') return; // migrate stale BINANCE:HYPEUSDT mapping
  assetMap.set(name || String(a.symbol).toUpperCase(), {...a, cls: 'Crypto'});
});
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

function resultKey(){ const a=state.assets[state.active]; return `${a.apiSymbol || a.symbol}|${state.interval}`; }
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
