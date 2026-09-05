(() => {
const $=id=>document.getElementById(id);
const KEY='atlas.analysis.alerts.settings', SEEN='atlas.analysis.alerts.seen';
let settings={browser:false,sound:true};
try{settings={...settings,...JSON.parse(localStorage.getItem(KEY)||'{}')}}catch{}
let seen=new Set();
try{seen=new Set(JSON.parse(localStorage.getItem(SEEN)||'[]'))}catch{}
let latestRows=[];
function save(){localStorage.setItem(KEY,JSON.stringify(settings));}
function saveSeen(){localStorage.setItem(SEEN,JSON.stringify([...seen].slice(-200)));}
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function tone(direction){return direction==='LONG'?'buy':direction==='SHORT'?'sell':'neutral';}
function markAnalysisLane(){
  const badge=$('confirmedAlertBadge'),card=badge?.closest('.card');
  const title=card?.querySelector('.card-head strong'),sub=card?.querySelector('.card-head .muted.small');
  if(title)title.textContent='ATLAS CANONICAL ANALYSIS ALERTS';
  if(sub)sub.textContent='Alerts for new 4–12H LONG/SHORT analyst_output decisions only · no order routing or execution.';
  const note=$('confirmedAlertNotes');if(note&&!note.dataset.atlasCanonical)note.textContent='Only canonical analyst_output LONG/SHORT decisions can create an analysis alert.';
}
function payloadOf(r){
  const direction=String(r?.decision||'').toUpperCase();
  if(!r||!r.analysis_ready||!['LONG','SHORT'].includes(direction)||r.analysis_only!==true||r.live_execution!==false)return null;
  const stamp=r.data_timestamp||r.raw?.generated_at||r.entry||'snapshot';
  return {id:`${r.symbol}-${direction}-${stamp}`,symbol:r.symbol,direction,score:r.score,threshold:r.threshold,entry:r.entry,stop_loss:r.stop_loss,tp1:r.tp1,tp2:r.tp2,rr_tp2:r.rr_tp2,reason:r.primary_reason||r.reasons?.[0]||'Canonical 4–12H analysis ready'};
}
function toast(a){
  const host=$('atlasAlertToastHost');if(!host)return;
  const el=document.createElement('div');el.className=`atlas-alert-toast ${tone(a.direction)}`;
  el.innerHTML=`<div class="alert-toast-top"><strong>ATLAS ${a.direction} ANALYSIS</strong><span>4–12H · ${fmt(a.score,0)}/${fmt(a.threshold,0)}</span></div><div class="alert-toast-symbol">${a.symbol}</div><div class="alert-toast-meta">Entry ${fmt(a.entry)} · Stop ${fmt(a.stop_loss)} · TP ${fmt(a.tp2)} · R:R ${fmt(a.rr_tp2)}</div>`;
  host.prepend(el);setTimeout(()=>el.classList.add('show'),20);setTimeout(()=>{el.classList.remove('show');setTimeout(()=>el.remove(),300)},9000);
}
function beep(){
  if(!settings.sound)return;
  try{const A=window.AudioContext||window.webkitAudioContext;if(!A)return;const ctx=new A(),o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=740;g.gain.setValueAtTime(.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.08,ctx.currentTime+.02);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.28);o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+.3);}catch{}
}
function browserNotify(a){
  if(!settings.browser||!('Notification' in window)||Notification.permission!=='granted')return;
  try{new Notification(`ATLAS ${a.direction} analysis · ${a.symbol}`,{body:`4–12H · Entry ${fmt(a.entry)} · Stop ${fmt(a.stop_loss)} · TP ${fmt(a.tp2)} · R:R ${fmt(a.rr_tp2)}`,tag:`atlas-analysis-${a.symbol}-${a.direction}`});}catch{}
}
function announce(a){if(!a?.id||seen.has(a.id))return;seen.add(a.id);saveSeen();toast(a);beep();browserNotify(a);}
function render(){
  markAnalysisLane();
  const badge=$('confirmedAlertBadge'),grid=$('confirmedAlertMetrics'),body=$('confirmedAlertBody'),note=$('confirmedAlertNotes');if(!grid||!body)return;
  const ready=latestRows.map(payloadOf).filter(Boolean);
  grid.innerHTML=[['Canonical analyses',latestRows.length],['Analysis ready',ready.length],['Horizon','4–12H'],['Contract','analyst_output'],['Live execution','OFF'],['Browser alerts',settings.browser?'ON':'OFF']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
  body.innerHTML=ready.length?ready.slice(0,10).map(a=>`<tr><td>LIVE</td><td>${a.symbol}</td><td><span class="pill ${tone(a.direction)}">${a.direction}</span></td><td>${fmt(a.score,0)}</td><td>${fmt(a.entry)}</td><td>${fmt(a.rr_tp2)}</td><td>ANALYSIS READY</td></tr>`).join(''):'<tr><td colspan="7">No canonical LONG/SHORT analysis is ready now.</td></tr>';
  if(note){note.dataset.atlasCanonical='1';note.innerHTML='<div><b>Alert rule:</b> canonical analyst_output + 4–12H + analysis_ready + LONG/SHORT.</div><div class="muted tiny">This is an analysis notification only. ATLAS does not place or route orders.</div>';}
  if(badge){badge.textContent=ready.length?`${ready.length} ANALYSIS READY`:'WAIT';badge.className=`pill ${ready.length?'working':'neutral'}`;}
}
function evaluateRows(rows){latestRows=Array.isArray(rows)?rows:[];for(const r of latestRows){const p=payloadOf(r);if(p)announce(p);}render();}
async function enableBrowser(){if(!('Notification' in window)){alert('Browser notifications are not supported here. In-app analysis alerts still work.');return;}settings.browser=(await Notification.requestPermission())==='granted';save();render();}
$('alertEnableBrowserBtn')?.addEventListener('click',enableBrowser);
$('alertSoundBtn')?.addEventListener('click',()=>{settings.sound=!settings.sound;save();$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';});
$('alertRefreshBtn')?.addEventListener('click',()=>{if(window.runAtlasOpportunityScan)window.runAtlasOpportunityScan();else render();});
if($('alertSoundBtn'))$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';
window.addEventListener('atlas:opportunity-scan-complete',e=>evaluateRows(e.detail?.rows||[]));
window.refreshConfirmedAlerts=render;
markAnalysisLane();render();

function bootstrapAiCouncil(){
  if(!document.getElementById('atlasAiCouncilCard')){
    const anchor=document.querySelector('.lower-grid')||document.querySelector('.metrics-card');
    if(anchor){const panel=document.createElement('section');panel.id='atlasAiCouncilCard';panel.className='card metrics-card ai-council-card';panel.innerHTML='<div class="card-head"><div><strong>ATLAS AI ANALYSIS COUNCIL</strong><div class="muted small">Supporting evidence only · canonical 4–12H analyst_output remains the visible authority</div></div><span id="aiCouncilBadge" class="pill neutral">WAITING</span></div><div class="ai-council-grid"><div class="ai-kpi"><span>Canonical</span><b id="aiProdDecision">—</b><small id="aiProdScore">—</small></div><div class="ai-kpi"><span>Context 1–3H</span><b id="aiTactical">—</b><small id="aiTacticalRR">—</small></div><div class="ai-kpi"><span>AI Judge</span><b id="aiJudge">—</b><small id="aiConfidence">—</small></div><div class="ai-kpi"><span>Evidence</span><b id="aiHybrid">—</b><small id="aiHybridSub">—</small></div></div><div class="ai-council-split"><div class="ai-case"><div class="panel-title">BULL CASE</div><div id="aiBullCase" class="muted small">Waiting for analysis.</div></div><div class="ai-case"><div class="panel-title">BEAR CASE</div><div id="aiBearCase" class="muted small">Waiting for analysis.</div></div></div><div class="ai-counterfactual"><div class="panel-title">COUNTERFACTUAL / INVALIDATION</div><div id="aiBestAction" class="ai-best-action">—</div><div id="aiGeometry" class="muted small">—</div><div id="aiTrigger" class="muted tiny">—</div></div><div id="aiEvidence" class="comparison-box muted small">Evidence will appear after analysis.</div>';anchor.parentNode.insertBefore(panel,anchor);}
  }
  if(!window.ATLAS_PRODUCTION_DECISION_UI&&!document.querySelector('script[data-atlas-production-ui]')){const s=document.createElement('script');s.src='/atlas-production-decision.js?v=canonical-analyst-v1';s.dataset.atlasProductionUi='1';document.body.appendChild(s);}
}
setTimeout(bootstrapAiCouncil,50);
})();
