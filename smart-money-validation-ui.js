(() => {
const $=id=>document.getElementById(id);
const fmt=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
const pct=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(3)}%`;
function sym(){
  const a=(window.ATLAS_STATE&&window.ATLAS_STATE.selectedAsset)||null;
  const raw=a?.symbol||'BINANCE:BTCUSDT';
  return raw.includes('ETH')?'ETHUSDT':'BTCUSDT';
}
async function load(){
 try{
  const s=sym();
  const [v,t]=await Promise.all([
    fetch(`/api/smart-money/validation?symbol=${s}`).then(r=>r.json()),
    fetch(`/api/smart-money/timeline?symbol=${s}&limit=50`).then(r=>r.json())
  ]);
  const m=v.matured||{},vals=[v.snapshots||0,m['1']||0,m['4']||0,m['12']||0,m['24']||0,v.readiness||'NOT_READY'];
  [...$('smvReadiness').querySelectorAll('b')].forEach((b,i)=>b.textContent=vals[i]);
  $('smvBadge').textContent=(v.readiness||'NOT_READY').replaceAll('_',' ');
  $('smvBadge').className='pill '+((v.readiness||'').includes('READY')&&v.readiness!=='NOT_READY'?'working':'neutral');
  const h=(s,n)=>s.horizons?.[String(n)]||{};
  $('smvFactorBody').innerHTML=(v.stats||[]).map(s=>`<tr><td>${s.factor}</td>
    <td>${fmt(h(s,1).correlation,4)}</td><td>${h(s,1).directional_hit_rate_pct==null?'—':fmt(h(s,1).directional_hit_rate_pct,1)+'%'}</td>
    <td>${fmt(h(s,4).correlation,4)}</td><td>${h(s,4).directional_hit_rate_pct==null?'—':fmt(h(s,4).directional_hit_rate_pct,1)+'%'}</td>
    <td>${fmt(h(s,12).correlation,4)}</td><td>${h(s,12).directional_hit_rate_pct==null?'—':fmt(h(s,12).directional_hit_rate_pct,1)+'%'}</td>
    <td>${fmt(h(s,24).correlation,4)}</td><td>${h(s,24).directional_hit_rate_pct==null?'—':fmt(h(s,24).directional_hit_rate_pct,1)+'%'}</td></tr>`).join('')||'<tr><td colspan="9">Waiting for matured observations…</td></tr>';
  const rows=t.records||[];
  $('smvTimelineBody').innerHTML=rows.slice().reverse().map(r=>`<tr>
    <td>${new Date(r.captured_at).toLocaleString()}</td><td>${fmt(r.mark_price,2)}</td><td>${r.experimental_score??'—'}</td>
    <td>${pct(r.forward_return_pct?.['1'])}</td><td>${pct(r.forward_return_pct?.['4'])}</td>
    <td>${pct(r.forward_return_pct?.['12'])}</td><td>${pct(r.forward_return_pct?.['24'])}</td></tr>`).join('')||'<tr><td colspan="7">Collecting…</td></tr>';
  window.__ATLAS_SMV=v;
 }catch(e){
  $('smvBadge').textContent='OFFLINE';
  $('smvFactorBody').innerHTML=`<tr><td colspan="9">${e.message}</td></tr>`;
 }
}
$('smvRefreshBtn')?.addEventListener('click',load);
$('smvExportBtn')?.addEventListener('click',()=>{
 const b=new Blob([JSON.stringify(window.__ATLAS_SMV||{},null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');
 a.href=u;a.download='ATLAS_SMART_MONEY_VALIDATION.json';a.click();URL.revokeObjectURL(u);
});
setTimeout(load,1000);setInterval(load,60000);
})();
