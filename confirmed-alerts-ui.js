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

function toast(a){
  const host=$('atlasAlertToastHost');if(!host)return;
  const el=document.createElement('div');
  el.className=`atlas-alert-toast ${tone(a.direction)}`;
  el.innerHTML=`<div class="alert-toast-top"><strong>ATLAS CONFIRMED ${a.direction}</strong><span>${a.score}/100</span></div>
    <div class="alert-toast-symbol">${a.symbol}</div>
    <div class="alert-toast-meta">Entry ${fmt(a.entry)} · R:R ${fmt(a.rr_tp2)} · ${a.playbook||'Confirmed setup'}</div>`;
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
  try{new Notification(`ATLAS CONFIRMED ${a.direction} · ${a.symbol}`,{body:`Score ${a.score}/100 · Entry ${fmt(a.entry)} · R:R ${fmt(a.rr_tp2)} · ${a.playbook||''}`,tag:`atlas-${a.symbol}-${a.direction}`});}catch{}
}
function announce(a){
  if(!a?.id||seen.has(a.id))return;
  seen.add(a.id);saveSeen();toast(a);beep();browserNotify(a);
}
function rowPayload(r){
  if(!r?.enriched)return null;
  const dir=r.plan?.direction||r.final?.direction;
  if(!['LONG','SHORT'].includes(dir))return null;
  const pa=window.ATLAS_PORTFOLIO_ASSESSMENT;
  const portfolioAllowed=(pa?.assessment?.blockers?.length===0 || pa==null) ? true : false;
  return {
    symbol:r.symbol,direction:dir,entry:r.plan?.entry,
    final_score:r.final?.score??r.opp?.score??0,champion_score:r.final?.score??r.opp?.score??0,
    execution_decision:r.execution_decision??r.final?.decision,
    trade_plan_status:r.plan?.status,rr_tp2:r.plan?.rr_tp2,
    volume_quality:r.confluence?.volume?.quality_score,
    futures_score:r.futures?.score??0,
    playbook_primary:r.playbook?.primary?.id,
    regime:r.regime?.regime,
    portfolio_allowed:portfolioAllowed,
    store:true,source:'BROWSER_ALPHA25'
  };
}
async function evaluateRows(rows){
  const candidates=(rows||[]).filter(x=>x?.enriched).sort((a,b)=>(b.final?.score??b.opp?.score??0)-(a.final?.score??a.opp?.score??0)).slice(0,3);
  for(const r of candidates){
    const payload=rowPayload(r);if(!payload)continue;
    try{
      const a=await fetch('/api/alerts/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());
      if(a.status==='CONFIRMED')announce(a);
    }catch{}
  }
  refresh();
}
async function refresh(){
  const badge=$('confirmedAlertBadge'),grid=$('confirmedAlertMetrics'),body=$('confirmedAlertBody'),note=$('confirmedAlertNotes');
  if(!grid||!body)return;
  try{
    const j=await fetch('/api/alerts/status').then(r=>r.json()),p=j.policy||{},rows=j.recent||[];
    grid.innerHTML=[
      ['Confirmed alerts',j.total_alerts||0],['Min score',p.min_score??'—'],['Min R:R',p.min_rr_tp2??'—'],
      ['Min Volume',p.min_volume_quality??'—'],['Cooldown',p.cooldown_minutes?`${p.cooldown_minutes} min`:'—'],
      ['Browser alerts',settings.browser?'ON':'OFF']
    ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    body.innerHTML=rows.length?rows.slice(0,10).map(a=>`<tr><td>${a.created_at?.replace('T',' ').slice(0,16)||'—'}</td><td>${a.symbol}</td><td><span class="pill ${tone(a.direction)}">${a.direction}</span></td><td>${fmt(a.score,0)}</td><td>${fmt(a.entry)}</td><td>${fmt(a.rr_tp2)}</td><td>${a.playbook||'—'}</td></tr>`).join(''):'<tr><td colspan="7">No confirmed opportunity has fired yet.</td></tr>';
    note.innerHTML=`<div><b>Alert rule:</b> high score + valid plan + R:R + volume confirmation + no strong Futures conflict + no risk/data/drift block.</div><div class="muted tiny">Confirmed means ATLAS conditions are satisfied, not guaranteed profit. Same symbol + direction is suppressed during cooldown.</div>`;
    badge.textContent='ARMED';badge.className='pill buy';
    rows.slice().reverse().forEach(a=>announce(a));
  }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';note.textContent=e.message;}
}
async function enableBrowser(){
  if(!('Notification' in window)){alert('Browser notifications are not supported here. In-app alerts will still work.');return;}
  const p=await Notification.requestPermission();
  settings.browser=p==='granted';save();refresh();
}
$('alertEnableBrowserBtn')?.addEventListener('click',enableBrowser);
$('alertSoundBtn')?.addEventListener('click',()=>{settings.sound=!settings.sound;save();$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';});
$('alertRefreshBtn')?.addEventListener('click',refresh);
if($('alertSoundBtn'))$('alertSoundBtn').textContent=settings.sound?'Sound: ON':'Sound: OFF';
window.addEventListener('atlas:opportunity-scan-complete',e=>evaluateRows(e.detail?.rows||[]));
window.refreshConfirmedAlerts=refresh;
setTimeout(refresh,8200);setInterval(refresh,60000);
})();