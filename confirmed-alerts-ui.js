(() => {
const $=id=>document.getElementById(id);
const KEY='atlas.alerts.settings', SEEN='atlas.alerts.seen';
let settings={browser:false,sound:true};
try{settings={...settings,...JSON.parse(localStorage.getItem(KEY)||'{}')}}catch{}
let seen=new Set();
try{seen=new Set(JSON.parse(localStorage.getItem(SEEN)||'[]'))}catch{}

function save(){localStorage.setItem(KEY,JSON.stringify(settings));}
function saveSeen(){localStorage.setItem(SEEN,JSON.stringify([...seen].slice(-200)));}
function fmt(v,d=2){return v==null?'—':Number(v).toFixed(d);}
function tone(direction){return direction==='LONG'?'buy':'sell';}
function markResearchLane(){
  const badge=$('confirmedAlertBadge');
  const card=badge?.closest('.card');
  const title=card?.querySelector('.card-head strong');
  const sub=card?.querySelector('.card-head .muted.small');
  if(title)title.textContent='ATLAS PRODUCTION EXECUTION ALERTS';
  if(sub)sub.textContent='Alerts only for ACTIONABLE Production + valid Geometry · ARMED and WATCH remain silent.';
}

function toast(a){
  const host=$('atlasAlertToastHost');if(!host)return;
  const el=document.createElement('div');
  el.className=`atlas-alert-toast ${tone(a.direction)}`;
  el.innerHTML=`<div class="alert-toast-top"><strong>ATLAS ENTER ${a.direction}</strong><span>Production ${a.score}/${a.threshold||68}</span></div>
    <div class="alert-toast-symbol">${a.symbol}</div>
    <div class="alert-toast-meta">Entry ${fmt(a.entry)} · Stop ${fmt(a.stop_loss)} · TP2 ${fmt(a.tp2)} · R:R ${fmt(a.rr_tp2)}</div>`;
  host.prepend(el);setTimeout(()=>el.classList.add('show'),20);setTimeout(()=>{el.classList.remove('show');setTimeout(()=>el.remove(),300)},9000);
}
function beep(){
  if(!settings.sound)return;
  try{
    const A=window.AudioContext||window.webkitAudioContext;if(!A)return;
    const ctx=new A(),o=ctx.createOscillator(),g=ctx.createGain();
    o.frequency.value=740;g.gain.setValueAtTime(.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.08,ctx.currentTime+.02);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.28);
    o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+.3);
  }catch{}
}
function browserNotify(a){
  if(!settings.browser || !('Notification' in window) || Notification.permission!=='granted')return;
  try{new Notification(`ATLAS ENTER ${a.direction} · ${a.symbol}`,{body:`Production ${a.score}/${a.threshold||68} · Entry ${fmt(a.entry)} · Stop ${fmt(a.stop_loss)} · TP2 ${fmt(a.tp2)}`,tag:`atlas-production-${a.symbol}-${a.direction}`});}catch{}
}
function announce(a){
  if(!a?.id||seen.has(a.id))return;
  seen.add(a.id);saveSeen();toast(a);beep();browserNotify(a);
}
function rowPayload(r){
  if(!r||!['ENTER_LONG','ENTER_SHORT'].includes(r.action)||r.opportunity_state!=='ACTIONABLE')return null;
  return {id:`${r.symbol}-${r.direction}-${r.generated_at||r.entry}`,symbol:r.symbol,direction:r.direction,
    score:r.score,threshold:r.threshold,entry:r.entry,stop_loss:r.stop_loss,tp1:r.tp1,tp2:r.tp2,rr_tp2:r.rr_tp2};
}
async function evaluateRows(rows){
  for(const r of (rows||[])){const payload=rowPayload(r);if(payload)announce(payload);}
  refresh();
}
async function refresh(){
  markResearchLane();
  const badge=$('confirmedAlertBadge'),grid=$('confirmedAlertMetrics'),body=$('confirmedAlertBody'),note=$('confirmedAlertNotes');
  if(!grid||!body)return;
  try{
    const j=await fetch('/api/production/paper-trades?limit=20',{cache:'no-store'}).then(r=>r.json()),rows=j.rows||[];
    grid.innerHTML=[
      ['Qualified paper entries',j.count||0],['Required state','ACTIONABLE'],['Production threshold','68+'],
      ['Geometry','PASS'],['Fallback signals','BLOCKED'],['Browser execution alerts',settings.browser?'ON':'OFF']
    ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    body.innerHTML=rows.length?rows.slice(0,10).map(a=>`<tr><td>${a.captured_at?.replace('T',' ').slice(0,16)||'—'}</td><td>${a.symbol}</td><td><span class="pill ${tone(a.direction)}">${a.direction}</span></td><td>${fmt(a.score,0)}</td><td>${fmt(a.entry)}</td><td>${fmt(a.rr_tp2)}</td><td>Production ACTIONABLE</td></tr>`).join(''):'<tr><td colspan="7">No qualified Production paper entry has fired yet.</td></tr>';
    note.innerHTML=`<div><b>Alert rule:</b> Production-qualified + ACTIONABLE now + complete Entry/Stop/TP1/TP2 + Geometry PASS.</div><div class="muted tiny">ARMED, WATCH, AI fallback and legacy Research scores cannot create an alert.</div>`;
    badge.textContent='PRODUCTION ARMED';badge.className='pill working';
  }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
async function enableBrowser(){
  if(!('Notification' in window)){alert('Browser notifications are not supported here. In-app research alerts will still work.');return;}
  const p=await Notification.requestPermission();
  settings.browser=p==='granted';save();refresh();
}
$('alertEnableBrowserBtn')?.addEventListener('click',enableBrowser);
$('alertSoundBtn')?.addEventListener('click',()=>{settings.sound=!settings.sound;save();$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';});
$('alertRefreshBtn')?.addEventListener('click',refresh);
if($('alertSoundBtn'))$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';
markResearchLane();
window.addEventListener('atlas:opportunity-scan-complete',e=>evaluateRows(e.detail?.rows||[]));
window.refreshConfirmedAlerts=refresh;
setTimeout(refresh,8200);setInterval(refresh,60000);

// Production-safe bootstrap for the AI Council UI. This file is already part of
// the original page, so the new panel no longer depends on cloud_start HTML mutation.
function bootstrapAiCouncil(){
  if(!document.getElementById('atlasAiCouncilCard')){
    const anchor=document.querySelector('.lower-grid')||document.querySelector('.metrics-card');
    if(anchor){
      const panel=document.createElement('section');
      panel.id='atlasAiCouncilCard'; panel.className='card metrics-card ai-council-card';
      panel.innerHTML='<div class="card-head"><div><strong>ATLAS AI TRADE COUNCIL</strong><div class="muted small">Production + Tactical 1–3H + Bull/Bear + Counterfactual + Hybrid Judge</div></div><span id="aiCouncilBadge" class="pill neutral">WAITING</span></div><div class="ai-council-grid"><div class="ai-kpi"><span>Production</span><b id="aiProdDecision">—</b><small id="aiProdScore">—</small></div><div class="ai-kpi"><span>Tactical 1–3H</span><b id="aiTactical">—</b><small id="aiTacticalRR">—</small></div><div class="ai-kpi"><span>AI Judge</span><b id="aiJudge">—</b><small id="aiConfidence">—</small></div><div class="ai-kpi"><span>Hybrid</span><b id="aiHybrid">—</b><small id="aiHybridSub">—</small></div></div><div class="ai-council-split"><div class="ai-case"><div class="panel-title">BULL CASE</div><div id="aiBullCase" class="muted small">Waiting for analysis.</div></div><div class="ai-case"><div class="panel-title">BEAR CASE</div><div id="aiBearCase" class="muted small">Waiting for analysis.</div></div></div><div class="ai-counterfactual"><div class="panel-title">BEST ACTION / COUNTERFACTUAL</div><div id="aiBestAction" class="ai-best-action">—</div><div id="aiGeometry" class="muted small">—</div><div id="aiTrigger" class="muted tiny">—</div></div><div id="aiEvidence" class="comparison-box muted small">Evidence will appear after Analyze Live.</div>';
      anchor.parentNode.insertBefore(panel,anchor);
    }
  }
  if(!window.ATLAS_PRODUCTION_DECISION_UI && !document.querySelector('script[data-atlas-production-ui]')){
    const s=document.createElement('script');s.src='/atlas-production-decision.js?v=ai-council-v4';s.dataset.atlasProductionUi='1';document.body.appendChild(s);
  }
}
setTimeout(bootstrapAiCouncil,50);
})();
