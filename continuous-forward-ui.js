(() => {
const $=id=>document.getElementById(id);
const UNIVERSE=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT'];
const SETTINGS_KEY='atlas.continuousForwardSettings';
let timer=null,lastRun=0;
function getSettings(){
 try{return {...{enabled:false,intervalMinutes:60,minScore:68,maxPerScan:3,requirePlan:true},...JSON.parse(localStorage.getItem(SETTINGS_KEY)||'{}')}}catch{return {enabled:false,intervalMinutes:60,minScore:68,maxPerScan:3,requirePlan:true}}
}
function saveSettings(s){localStorage.setItem(SETTINGS_KEY,JSON.stringify(s));}
function rowPayload(r){
 if(!r?.enriched)return null;
 const dir=r.plan?.direction||r.final?.direction;
 if(!['LONG','SHORT'].includes(dir))return null;
 const score=Number(r.final?.score??r.opp?.score??0);
 const decision=r.execution_decision??r.final?.decision??r.opp?.action;
 if(decision==='NO_TRADE'||!r.plan?.available)return null;
 return {
  symbol:r.symbol,direction:dir,entry:r.plan.entry,champion_score:score,champion_take:score>=60,
  final_score:score,opportunity_score:r.opp?.score,execution_decision:decision,
  trade_plan_status:r.plan?.status,rr_tp1:r.plan?.rr_tp1,rr_tp2:r.plan?.rr_tp2,
  anomaly_score:r.anomaly?.score,futures_score:r.futures?.score,liquidity_score:r.liquidity?.score,
  volume_quality:r.confluence?.volume?.quality_score,relative_volume:r.confluence?.volume?.relative_volume,
  base_signal:r.confluence?.base_signal,signal:r.confluence?.signal,
  resistance_strength:r.confluence?.nearest_resistance?.strength,resistance_distance_pct:r.confluence?.nearest_resistance?.distance_pct,
  support_strength:r.confluence?.nearest_support?.strength,support_distance_pct:r.confluence?.nearest_support?.distance_pct,
  breakout_score:r.confluence?.breakout_up?.score,breakdown_score:r.confluence?.breakout_down?.score,
  funding_rate:r.futures?.funding_rate,oi_change_pct:r.futures?.oi_change_pct,taker_ratio:r.futures?.taker_ratio,
  orderbook_imbalance:r.futures?.orderbook_imbalance,futures_crowding:r.futures?.crowding,futures_squeeze:r.futures?.squeeze,
  relative_strength_score:r.relative?.score,regime:r.regime?.regime,
  playbook_primary:r.playbook?.primary?.id,playbook_score:r.playbook?.primary?.score,
  playbook_all:(r.playbook?.playbooks||[]).map(x=>x.id),
  auto_source:'CONTINUOUS_FORWARD_ALPHA17',dedup_minutes:50
 };
}
async function recordRows(rows){
 const s=getSettings(),candidates=(rows||[]).filter(r=>r?.enriched&&(r.final?.score??r.opp?.score??0)>=s.minScore)
   .sort((a,b)=>(b.final?.score??b.opp?.score??0)-(a.final?.score??a.opp?.score??0)).slice(0,s.maxPerScan);
 let stored=0,dedup=0,errors=0;
 for(const r of candidates){
  const payload=rowPayload(r);if(!payload)continue;
  try{
   const res=await fetch('/api/forward/observe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
   const j=await res.json();if(!res.ok)throw new Error(j.error||`HTTP ${res.status}`);
   if(j.stored===false)dedup++;else stored++;
  }catch(e){errors++;}
 }
 return {stored,dedup,errors,candidates:candidates.length};
}
async function runCycle(){
 const s=getSettings();if(!s.enabled)return;
 const badge=$('continuousBadge'),note=$('continuousNotes');lastRun=Date.now();
 if(badge){badge.textContent='SCANNING';badge.className='pill working';}
 try{
  if(!window.runAtlasOpportunityScan)throw new Error('Opportunity scanner is not ready.');
  await window.runAtlasOpportunityScan();
  const result=await recordRows(window.ATLAS_OPPORTUNITY_ROWS||[]);
  await fetch('/api/forward/update',{method:'POST'}).catch(()=>null);
  if(note)note.innerHTML=`Last cycle: ${new Date().toLocaleString()} · ${result.stored} stored · ${result.dedup} deduped · ${result.errors} errors · ${result.candidates} qualifying candidates.`;
  if(badge){badge.textContent='ACTIVE';badge.className='pill buy';}
  if(window.refreshPerformanceDashboard)window.refreshPerformanceDashboard();
 }catch(e){
  if(note)note.textContent=e.message;if(badge){badge.textContent='ERROR';badge.className='pill sell';}
 }
}
function schedule(){
 if(timer)clearInterval(timer);
 const s=getSettings();if(!s.enabled)return;
 const ms=Math.max(15,Number(s.intervalMinutes||60))*60*1000;
 timer=setInterval(()=>runCycle(),ms);
}
function loadUI(){
 const s=getSettings();
 if($('continuousEnabled'))$('continuousEnabled').checked=!!s.enabled;
 if($('continuousInterval'))$('continuousInterval').value=s.intervalMinutes;
 if($('continuousMinScore'))$('continuousMinScore').value=s.minScore;
 if($('continuousMaxPerScan'))$('continuousMaxPerScan').value=s.maxPerScan;
 const badge=$('continuousBadge');if(badge){badge.textContent=s.enabled?'ACTIVE':'OFF';badge.className=`pill ${s.enabled?'buy':'neutral'}`;}
}
$('continuousSaveBtn')?.addEventListener('click',()=>{
 const s={enabled:!!$('continuousEnabled')?.checked,intervalMinutes:Number($('continuousInterval')?.value||60),
  minScore:Number($('continuousMinScore')?.value||68),maxPerScan:Number($('continuousMaxPerScan')?.value||3),requirePlan:true};
 saveSettings(s);loadUI();schedule();
 if(s.enabled)runCycle();
});
$('continuousRunNowBtn')?.addEventListener('click',runCycle);
loadUI();schedule();
window.runContinuousForwardCycle=runCycle;
})();