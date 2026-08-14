(function(){
  const $=id=>document.getElementById(id);
  if(!$('smServerBadge')) return;
  function fmt(v,d=2){return v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});}
  function pct(v,d=2){return v==null||!Number.isFinite(Number(v))?'—':`${Number(v).toFixed(d)}%`;}
  function funding(v){return v==null?'—':`${(Number(v)*100).toFixed(4)}%`;}
  function pill(text,cls){$('smServerBadge').textContent=text;$('smServerBadge').className=`pill ${cls}`;}
  function activeBinanceSymbol(){
    try{ const a=state.assets[state.active]; if(a?.cls==='Crypto'&&a.symbol?.startsWith('BINANCE:')) return tvToBinanceSymbol(a.symbol); }catch(e){}
    return 'BTCUSDT';
  }
  function renderSnapshot(s){
    const vals=s?[['Score*',fmt(s.experimental_score,0)],['Funding',funding(s.funding_rate)],['Open interest',fmt(s.open_interest,0)],['OI Δ',pct(s.oi_change_pct)],['Taker ratio',fmt(s.taker_ratio,3)],['Book imbalance',pct((s.orderbook_imbalance||0)*100)]]:[['Score*','—'],['Funding','—'],['Open interest','—'],['OI Δ','—'],['Taker ratio','—'],['Book imbalance','—']];
    $('smSnapshotGrid').innerHTML=vals.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    $('smMeta').textContent=s?`${s.symbol} · ${new Date(s.captured_at).toLocaleString()} · ${s.factor_label||'experimental/unvalidated'}`:'No snapshot yet.';
  }
  function renderStatus(d){
    const counts=d?.counts||{}, last=d?.last_capture;
    const vals=[['BTC snapshots',counts.BTCUSDT||0],['ETH snapshots',counts.ETHUSDT||0],['Interval',d?.interval||'1h'],['Last capture',last?new Date(last).toLocaleString():'—'],['Whale flow','NOT CONNECTED'],['Execution','DISABLED']];
    $('smArchiveGrid').innerHTML=vals.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  }
  async function api(path,opts){ const r=await fetch(path,opts); if(!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); }
  async function refresh(){
    try{
      const [status,latest]=await Promise.all([api('/api/smart-money/status'),api(`/api/smart-money/latest?symbol=${encodeURIComponent(activeBinanceSymbol())}`)]);
      pill('COLLECTOR ONLINE','buy'); renderStatus(status); renderSnapshot(latest.snapshot||null); $('smExportBtn').disabled=false;
    }catch(e){ pill('COLLECTOR OFFLINE','sell'); $('smMeta').textContent='Start ATLAS with: python3 collector_server.py'; $('smExportBtn').disabled=true; }
  }
  async function capture(){
    $('smCaptureBtn').disabled=true; pill('CAPTURING','working');
    try{ const d=await api(`/api/smart-money/capture?symbol=${encodeURIComponent(activeBinanceSymbol())}`,{method:'POST'}); renderSnapshot(d.snapshot); await refresh(); }
    catch(e){ pill('ERROR','sell'); $('smMeta').textContent=e.message; }
    finally{$('smCaptureBtn').disabled=false;}
  }
  $('smCaptureBtn').onclick=capture; $('smRefreshBtn').onclick=refresh; $('smExportBtn').onclick=()=>{window.location.href='/api/smart-money/export';};
  refresh(); setInterval(refresh,60000);
})();
