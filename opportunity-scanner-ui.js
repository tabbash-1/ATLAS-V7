(() => {
const $=id=>document.getElementById(id);
const SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT'];
const names={BTCUSDT:'Bitcoin',ETHUSDT:'Ethereum',SOLUSDT:'Solana',XRPUSDT:'XRP',BNBUSDT:'BNB',DOGEUSDT:'Dogecoin',ZECUSDT:'Zcash',HYPEUSDT:'Hyperliquid'};
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function cleanSymbol(value){return String(value||'').toUpperCase().split(':').pop();}
function activeSymbol(){return cleanSymbol(window.ATLAS_STATE?.selectedAsset?.symbol||$('tvSymbolLabel')?.textContent);}
function decisionOf(row){return String(row?.decision||'WAIT').toUpperCase();}
function tone(row){const d=decisionOf(row);return d==='LONG'?'buy':d==='SHORT'?'sell':row?.analysis_ready?'working':'neutral';}
function stateRank(row){const d=decisionOf(row);return d==='LONG'||d==='SHORT'?0:row?.candidate_direction&&row.candidate_direction!=='NONE'?1:2;}
function paintTile(id,text){
 const el=$(id);if(!el)return;el.textContent=text;
 const tile=el.closest('.command-tile'),upper=String(text).toUpperCase();if(!tile)return;
 tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');
 const kind=/LONG|SHORT|ANALYSIS READY/.test(upper)?'positive':/UNAVAILABLE|STALE|ERROR|BLOCK/.test(upper)?'negative':/WAIT|WATCH|PENDING/.test(upper)?'warning':'neutral';
 tile.classList.add(`tone-${kind}`);
}
function normalize(payload){
 const a=payload?.analyst_output;
 if(!payload?.ok||payload?.canonical_product_contract!=='analyst_output'||!a) throw new Error('CANONICAL_ANALYST_OUTPUT_UNAVAILABLE');
 if(a.horizon!=='4-12H'||a.analysis_only!==true||a.live_execution!==false) throw new Error('CANONICAL_ANALYST_CONTRACT_INVALID');
 return {
   symbol:cleanSymbol(payload.symbol||a.symbol),
   decision:decisionOf(a),
   candidate_direction:String(a.candidate_plan?.direction||payload.candidate_direction||'NONE').toUpperCase(),
   analysis_ready:a.analysis_ready===true,
   score:a.confidence,
   threshold:a.signal_threshold,
   entry:a.entry,
   stop_loss:a.stop_loss,
   tp1:a.tp1,
   tp2:a.take_profit,
   rr_tp2:a.risk_reward,
   playbook:a.playbook,
   regime:a.regime,
   primary_reason:a.primary_reason,
   reasons:Array.isArray(a.reasons)?a.reasons:[],
   invalidation:a.invalidation,
   what_changes_status:Array.isArray(a.what_changes_status)?a.what_changes_status:[],
   production_qualified_raw:a.production_qualified_raw===true,
   geometry_ready_raw:a.geometry_ready_raw===true,
   data_degraded:a.data_degraded===true,
   data_timestamp:a.data_timestamp,
   setup_quality_gate:a.setup_quality_gate||null,
   contract_version:a.contract_version,
   horizon:a.horizon,
   analysis_only:true,
   live_execution:false,
   raw:payload
 };
}
async function fetchCanonical(symbol){
 const response=await fetch(`/api/decision/current?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'});
 const payload=await response.json();
 if(!response.ok) throw new Error(payload?.error||`HTTP ${response.status}`);
 return normalize(payload);
}
function syncProductionCommand(){
 const row=(window.ATLAS_OPPORTUNITY_ROWS||[]).find(r=>cleanSymbol(r.symbol)===activeSymbol());
 if(!row)return;
 const score=row.score==null?'—':fmt(row.score,0),threshold=row.threshold==null?'—':fmt(row.threshold,0),decision=decisionOf(row);
 paintTile('cmdMasterValue',`${decision} · ${score}/${threshold} · 4–12H`);
 const masterSub=$('cmdMasterSub');if(masterSub)masterSub.textContent=`Canonical analyst · ${row.primary_reason||'No qualified directional analysis'}`;
 paintTile('cmdPlanValue',row.analysis_ready?'ANALYSIS READY':'WAIT · NO SETUP');
 const planSub=$('cmdPlanSub');if(planSub)planSub.textContent=row.analysis_ready?`Entry ${fmt(row.entry,8)} · SL ${fmt(row.stop_loss,8)} · TP ${fmt(row.tp2,8)} · R:R ${fmt(row.rr_tp2,2)}`:`${row.candidate_direction||'NONE'} candidate · ${row.what_changes_status?.[0]||'new verified evidence required'}`;
 const signal=$('signalState');if(signal){signal.textContent=decision;signal.className=`pill ${tone(row)}`;}
 if($('confidence'))$('confidence').textContent=row.score==null?'—':`${fmt(row.score,0)}%`;
 if($('entry'))$('entry').textContent=row.analysis_ready?fmt(row.entry,8):'—';
 if($('stop'))$('stop').textContent=row.analysis_ready?fmt(row.stop_loss,8):'—';
 if($('target'))$('target').textContent=row.analysis_ready?fmt(row.tp2,8):'—';
 if($('rr'))$('rr').textContent=row.analysis_ready?fmt(row.rr_tp2,2):'—';
}
function renderRow(row,index){
 const decision=decisionOf(row);
 const plan=row.analysis_ready?`${fmt(row.entry,8)}<small>4–12H</small>`:'—';
 const targets=row.analysis_ready?`${fmt(row.tp1,8)}<small>TP ${fmt(row.tp2,8)}</small>`:'—';
 const score=row.score==null?'—':`${fmt(row.score,0)}<small>/ ${fmt(row.threshold,0)}</small>`;
 const state=row.analysis_ready?'ANALYSIS READY':row.setup_quality_gate?.status==='BLOCK'?'QUALITY BLOCK':'WAIT';
 const reason=row.primary_reason||row.reasons?.[0]||'—';
 return `<tr><td>${index+1}</td><td>${names[row.symbol]||row.symbol}<small>${row.symbol}</small></td><td><span class="pill ${tone(row)}">${decision}</span></td><td>${state}</td><td>${row.candidate_direction||'—'}</td><td>${score}</td><td>${row.production_qualified_raw?'PASS':'NO'}</td><td>${row.geometry_ready_raw?'PASS':'NO'}</td><td>${plan}</td><td>${row.analysis_ready?fmt(row.stop_loss,8):'—'}</td><td>${targets}</td><td>${row.analysis_ready?fmt(row.rr_tp2,2):'—'}</td><td>${reason}</td></tr>`;
}
async function run(){
 const btn=$('opportunityScanBtn'),badge=$('opportunityBadge'),body=$('opportunityBody'),meta=$('opportunityMeta');if(!btn||!body)return;
 btn.disabled=true;badge.textContent='SCANNING ANALYSES';badge.className='pill working';body.innerHTML='<tr><td colspan="13">Loading the canonical 4–12H analyst output for all eight crypto assets…</td></tr>';
 try{
  const settled=await Promise.allSettled(SYMBOLS.map(fetchCanonical));
  const rows=settled.filter(x=>x.status==='fulfilled').map(x=>x.value).sort((a,b)=>stateRank(a)-stateRank(b)||(Number(b.score)||-1)-(Number(a.score)||-1));
  const errors=settled.filter(x=>x.status==='rejected').map(x=>String(x.reason?.message||x.reason));
  if(!rows.length) throw new Error(errors[0]||'NO_CANONICAL_ANALYST_OUTPUT');
  body.innerHTML=rows.map(renderRow).join('');
  const ready=rows.filter(r=>r.analysis_ready&&['LONG','SHORT'].includes(decisionOf(r)));
  const waits=rows.filter(r=>decisionOf(r)==='WAIT');
  badge.textContent=ready.length?`${ready.length} ANALYSIS READY`:`WAIT · ${waits.length} ASSETS`;
  badge.className=`pill ${ready.some(r=>decisionOf(r)==='SHORT')?'sell':ready.length?'buy':'neutral'}`;
  meta.textContent=`${rows.length}/${SYMBOLS.length} canonical assets · LONG ${rows.filter(r=>decisionOf(r)==='LONG').length} · SHORT ${rows.filter(r=>decisionOf(r)==='SHORT').length} · WAIT ${waits.length} · 4–12H · analyst_output is the only visible decision authority${errors.length?` · ${errors.length} unavailable`:''}.`;
  window.ATLAS_OPPORTUNITY_ROWS=rows;
  window.ATLAS_PRODUCTION_OPPORTUNITY_SCAN={ok:true,source:'CANONICAL_ANALYST_OUTPUT',rows,errors,analysis_only:true,live_execution:false};
  syncProductionCommand();
  window.dispatchEvent(new CustomEvent('atlas:opportunity-scan-complete',{detail:{rows,source:'CANONICAL_ANALYST_OUTPUT',summary:{ready:ready.length,wait:waits.length,errors:errors.length}}}));
 }catch(error){badge.textContent='ANALYSIS UNAVAILABLE';badge.className='pill sell';body.innerHTML=`<tr><td colspan="13">${error.message}</td></tr>`;meta.textContent='No fallback decision was generated. ATLAS fails closed to WAIT until the canonical analyst output recovers.';paintTile('cmdMasterValue','WAIT · DATA UNAVAILABLE');paintTile('cmdPlanValue','WAIT');}
 finally{btn.disabled=false;}
}
window.runAtlasOpportunityScan=run;
window.addEventListener('atlas:active-asset-change',syncProductionCommand);
$('opportunityScanBtn')?.addEventListener('click',run);
$('opportunityExportBtn')?.addEventListener('click',()=>{
 const payload={project:'ATLAS',stage:'CANONICAL_ANALYST_OUTPUT_SCAN_V1',generated_at:new Date().toISOString(),canonical_contract:'analyst_output',product_horizon:'4-12H',analysis_only:true,live_execution:false,rows:window.ATLAS_OPPORTUNITY_ROWS||[]};
 const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ATLAS_CANONICAL_ANALYSES.json';a.click();URL.revokeObjectURL(url);
});
setTimeout(run,1200);
})();
