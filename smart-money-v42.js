(() => {
const $=id=>document.getElementById(id);
const fmt=(v,d=3)=>v==null||Number.isNaN(Number(v))?'—':Number(v).toFixed(d);
const pct=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(3)}%`;
function symbol(){ const a=(window.ATLAS_STATE&&window.ATLAS_STATE.selectedAsset)||null; const raw=a?.symbol||'BINANCE:BTCUSDT'; return raw.includes('ETH')?'ETHUSDT':'BTCUSDT';}
async function load(){
 try{
  const sym=symbol();
  const [st,tl,fs]=await Promise.all([
    fetch('/api/smart-money/status').then(r=>r.json()),
    fetch(`/api/smart-money/timeline?symbol=${sym}&limit=100`).then(r=>r.json()),
    fetch(`/api/smart-money/factor-stats?symbol=${sym}`).then(r=>r.json())
  ]);
  const rows=tl.records||[], mat=st.matured_forward_labels||{};
  $('v42Badge').textContent=rows.length?'COLLECTING':'WAITING FOR DATA';
  $('v42Badge').className='pill '+(rows.length?'working':'neutral');
  const vals=[rows.length,mat['1']||0,mat['4']||0,mat['12']||0,mat['24']||0,(mat['24']||0)>=30?'RESEARCH READY':'NOT READY'];
  [...$('v42Maturity').querySelectorAll('b')].forEach((b,i)=>b.textContent=vals[i]);
  $('v42TimelineBody').innerHTML=rows.length?rows.slice().reverse().map(r=>`<tr>
    <td>${new Date(r.captured_at).toLocaleString()}</td><td>${fmt(r.mark_price,2)}</td><td>${fmt((r.funding_rate||0)*100,4)}%</td>
    <td>${pct(r.oi_change_pct)}</td><td>${fmt(r.taker_ratio,3)}</td><td>${pct((r.orderbook_imbalance||0)*100)}</td><td>${r.experimental_score??'—'}</td>
    <td>${pct(r.forward_return_pct?.['1'])}</td><td>${pct(r.forward_return_pct?.['4'])}</td><td>${pct(r.forward_return_pct?.['12'])}</td><td>${pct(r.forward_return_pct?.['24'])}</td></tr>`).join('')
    :'<tr><td colspan="11">Waiting for snapshots…</td></tr>';
  const stats=fs.stats||[];
  $('v42FactorStats').innerHTML=stats.map(s=>`<div class="v42-factor"><b>${s.factor}</b> · `+
    [1,4,12,24].map(h=>{const z=s.horizons[String(h)]||{};return `${h}h: ${z.correlation==null?'—':`r=${z.correlation}`} (n=${z.n||0})`}).join(' · ')+'</div>').join('') || 'Waiting for matured observations.';
 }catch(e){ $('v42Badge').textContent='OFFLINE'; $('v42FactorStats').textContent='V4.2 collector unavailable: '+e.message; }
}
$('v42RefreshBtn')?.addEventListener('click',load);
document.addEventListener('click',e=>{ if(e.target.closest?.('.asset-item')) setTimeout(load,300);});
setTimeout(load,800); setInterval(load,60000);
})();