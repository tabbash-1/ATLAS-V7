(() => {
const $=id=>document.getElementById(id);
const names={BTCUSDT:'Bitcoin',ETHUSDT:'Ethereum',SOLUSDT:'Solana',XRPUSDT:'XRP',BNBUSDT:'BNB',DOGEUSDT:'Dogecoin',ZECUSDT:'Zcash',HYPEUSDT:'Hyperliquid'};
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function tone(row){return row.action==='ENTER_LONG'?'buy':row.action==='ENTER_SHORT'?'sell':row.opportunity_state==='ARMED'?'working':'neutral';}
function actionLabel(row){return row.action==='ENTER_LONG'?'ENTER LONG':row.action==='ENTER_SHORT'?'ENTER SHORT':'WAIT';}
function stateRank(row){return row.opportunity_state==='ACTIONABLE'?0:row.opportunity_state==='ARMED'?1:row.opportunity_state==='WATCH'?2:row.opportunity_state==='NO_SETUP'?3:4;}
function renderRow(row,index){
 const plan=row.entry==null?'—':`${fmt(row.entry,8)}<small>${row.entry_mode||'—'}</small>`;
 const targets=row.tp1==null&&row.tp2==null?'—':`${fmt(row.tp1,8)}<small>TP2 ${fmt(row.tp2,8)}</small>`;
 const score=row.score==null?'—':`${fmt(row.score,0)}<small>/ ${fmt(row.threshold,0)}</small>`;
 return `<tr><td>${index+1}</td><td>${names[row.symbol]||row.symbol}<small>${row.symbol}</small></td><td><span class="pill ${tone(row)}">${actionLabel(row)}</span></td><td>${row.opportunity_state||'—'}</td><td>${row.direction||'—'}</td><td>${score}</td><td>${row.production_signal_qualified?'PASS':'NO'}</td><td>${row.geometry_valid?'PASS':'NO'}</td><td>${plan}</td><td>${fmt(row.stop_loss,8)}</td><td>${targets}</td><td>${fmt(row.rr_tp2,2)}</td><td>${row.entry_trigger||row.reason||'—'}</td></tr>`;
}
async function run(){
 const btn=$('opportunityScanBtn'),badge=$('opportunityBadge'),body=$('opportunityBody'),meta=$('opportunityMeta');if(!btn||!body)return;
 btn.disabled=true;badge.textContent='SCANNING PRODUCTION';badge.className='pill working';body.innerHTML='<tr><td colspan="13">Running the same Production decision engine for all eight crypto assets…</td></tr>';
 try{
  const response=await fetch(`/api/production/opportunities?t=${Date.now()}`,{cache:'no-store'});
  const payload=await response.json();if(!response.ok||!payload.ok)throw new Error(payload.error||`HTTP ${response.status}`);
  const rows=(payload.rows||[]).sort((a,b)=>stateRank(a)-stateRank(b)||(Number(b.score)||-1)-(Number(a.score)||-1));
  body.innerHTML=rows.length?rows.map(renderRow).join(''):'<tr><td colspan="13">No Production decisions returned.</td></tr>';
  const actionable=rows.filter(r=>['ENTER_LONG','ENTER_SHORT'].includes(r.action));
  const armed=rows.filter(r=>r.opportunity_state==='ARMED');
  badge.textContent=actionable.length?`${actionable.length} EXECUTABLE NOW`:armed.length?`${armed.length} ARMED · WAIT TRIGGER`:'WAIT · NO EXECUTABLE TRADE';
  badge.className=`pill ${actionable.some(r=>r.action==='ENTER_SHORT')?'sell':actionable.length?'buy':armed.length?'working':'neutral'}`;
  const freshness=payload.snapshot_stale?'STALE — forced WAIT':payload.source==='LIVE_PRODUCTION_SCAN'?'LIVE':`cached ${fmt(payload.snapshot_age_minutes,0)}m`;
  meta.textContent=`${rows.length} Production assets · ACTIONABLE ${actionable.length} · ARMED ${armed.length} · ${freshness} · ${payload.refreshing?'live refresh running in background · ':''}One authority: Production score + Geometry Gate. AI fallback and legacy Research /100 cannot create an entry.`;
  window.ATLAS_OPPORTUNITY_ROWS=rows;
  window.ATLAS_PRODUCTION_OPPORTUNITY_SCAN=payload;
  window.dispatchEvent(new CustomEvent('atlas:opportunity-scan-complete',{detail:{rows,source:'PRODUCTION',summary:payload.summary}}));
 }catch(error){badge.textContent='PRODUCTION UNAVAILABLE';badge.className='pill sell';body.innerHTML=`<tr><td colspan="13">${error.message}</td></tr>`;meta.textContent='No fallback signal was generated. Production must recover before a trade can be shown.';}
 finally{btn.disabled=false;}
}
window.runAtlasOpportunityScan=run;
$('opportunityScanBtn')?.addEventListener('click',run);
$('opportunityExportBtn')?.addEventListener('click',()=>{
 const payload={project:'ATLAS',stage:'PRODUCTION_OPPORTUNITY_SCAN_V1',generated_at:new Date().toISOString(),single_source_of_truth:'Production',fallback_signals_allowed:false,research_only:true,live_execution:false,rows:window.ATLAS_OPPORTUNITY_ROWS||[]};
 const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ATLAS_PRODUCTION_OPPORTUNITIES.json';a.click();URL.revokeObjectURL(url);
});
})();
