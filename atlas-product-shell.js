(() => {
  const $=id=>document.getElementById(id);
  const main=document.querySelector('main.main');
  if(!main||$('atlasProductShell')) return;

  const style=document.createElement('style');
  style.textContent=`body.atlas-product-focus .topbar,body.atlas-product-focus .command-strip,body.atlas-product-focus .signal-card{display:none!important}body.atlas-product-focus:not(.atlas-advanced-open) .atlas-workspace-nav,body.atlas-product-focus:not(.atlas-advanced-open) .atlas-workspace-panels{display:none!important}#atlasProductShell{margin:18px 0;padding:18px;border:1px solid #253047;border-radius:20px;background:#0a0e16}.aps-top,.aps-controls,.aps-actions{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}.aps-eyebrow,.aps-label{font-size:10px;letter-spacing:.12em;color:#9d7cff;text-transform:uppercase}.aps-title{font-size:clamp(25px,5vw,40px);margin:5px 0}.aps-sub,.aps-note{color:#8c9ab3;font-size:12px}.aps-control,.aps-secondary{border:1px solid #2a3851;background:#0d1320;color:#dce5f4;border-radius:11px;padding:10px}.aps-grid{display:grid;grid-template-columns:1.15fr repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.aps-card,.aps-packet{border:1px solid #253047;border-radius:15px;padding:13px;background:#0d1320}.aps-value{font-size:20px;font-weight:800}.long{color:#55d68b}.short{color:#ff6b7a}.wait{color:#f4c95d}.aps-analyze{border:1px solid #2d8f69;background:#0e2a20;color:#6fe5ad;border-radius:12px;padding:12px 18px;font-weight:800}.aps-summary-grid,.aps-packet-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px}.aps-summary,.aps-packet-item{border-top:1px solid #253047;padding-top:11px;color:#c9d4e7;font-size:12px;line-height:1.55}.aps-summary strong,.aps-packet-item strong{display:block;color:#9d7cff;font-size:10px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:5px}.aps-hidden-noncrypto{display:none!important}.aps-wait-geometry{opacity:.5}.aps-ai{margin-top:16px;border:1px solid #513d83;background:#0f1320;border-radius:16px;padding:14px}.aps-ai-title{font-weight:900;font-size:18px}.aps-ai-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}.aps-ai-card,.aps-ai-best{border:1px solid #28364d;background:#0b111b;border-radius:11px;padding:12px}.aps-ai-card span{display:block;color:#8c9ab3;font-size:10px;margin-bottom:6px}.aps-ai-card b{font-size:15px}.aps-ai-best{margin-top:10px;border-color:#385d52;background:#0a1714}.aps-ai-best b{font-size:18px}.aps-ai-best .meta{margin-top:7px;color:#b6c2d5;font-size:12px;line-height:1.55}.aps-ai-reason{margin-top:10px;color:#c9d4e7;font-size:12px;line-height:1.6}.aps-rr-tag{display:inline-block;margin-right:5px;color:#9d7cff;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}@media(max-width:820px){.aps-grid{grid-template-columns:repeat(2,1fr)}.aps-grid .primary{grid-column:1/-1}.aps-summary-grid,.aps-packet-grid,.aps-ai-grid{grid-template-columns:1fr}}`;
  document.head.appendChild(style);

  const shell=document.createElement('section');
  shell.id='atlasProductShell';
  shell.innerHTML=`<div class="aps-top"><div><div class="aps-eyebrow">ATLAS · CRYPTO TRADE INTELLIGENCE</div><div id="apsAsset" class="aps-title">Current asset</div></div><div class="aps-controls"><select id="apsTimeframe" class="aps-control"></select><button id="apsAdvanced" class="aps-secondary">Advanced Research</button></div></div><div class="aps-grid"><div class="aps-card primary"><div class="aps-label">Decision</div><div id="apsDecision" class="aps-value wait">WAIT</div></div><div class="aps-card"><div class="aps-label">Production score</div><div id="apsConfidence" class="aps-value">—</div></div><div id="apsEntryCard" class="aps-card"><div class="aps-label">Production Entry</div><div id="apsEntry" class="aps-value">—</div></div><div id="apsStopCard" class="aps-card"><div class="aps-label">Production Stop</div><div id="apsStop" class="aps-value">—</div></div><div id="apsTargetCard" class="aps-card"><div class="aps-label">Production Target / R:R</div><div id="apsTarget" class="aps-value">—</div></div></div><div class="aps-actions" style="margin-top:14px"><button id="apsAnalyze" class="aps-analyze">▶ ANALYZE</button><div id="apsStatus" class="aps-note">Ready</div></div><div class="aps-packet"><div class="aps-label">Market Analysis</div><div class="aps-packet-grid"><div class="aps-packet-item"><strong>Regime</strong><span id="apsRegime">—</span></div><div class="aps-packet-item"><strong>Trend</strong><span id="apsTrend">—</span></div><div class="aps-packet-item"><strong>Momentum</strong><span id="apsMomentum">—</span></div><div class="aps-packet-item"><strong>Volume</strong><span id="apsVolume">—</span></div><div class="aps-packet-item"><strong>Structure</strong><span id="apsStructure">—</span></div><div class="aps-packet-item"><strong>Liquidity / Smart Money</strong><span id="apsLiquidity">—</span></div></div></div><div class="aps-ai"><div class="aps-label">ATLAS AI</div><div class="aps-ai-title">What should I do?</div><div id="apsAiState" class="aps-note">Waiting for analysis</div><div class="aps-ai-grid"><div class="aps-ai-card"><span>ATLAS decision</span><b id="apsAiProd">—</b></div><div class="aps-ai-card"><span>AI view</span><b id="apsAiJudge">—</b></div><div class="aps-ai-card"><span>Conditional 1–3H opportunity</span><b id="apsAiTactical">—</b></div></div><div class="aps-ai-best"><span class="aps-label">Best action now</span><br><b id="apsAiBest">—</b><div id="apsAiGeometry" class="meta">—</div><div id="apsAiTrigger" class="meta">—</div></div><div id="apsAiReason" class="aps-ai-reason">Run analysis to see the reason.</div></div><div class="aps-summary-grid"><div class="aps-summary"><strong>Why</strong><div id="apsWhy">Run analysis to see evidence.</div></div><div class="aps-summary"><strong>Current Production Risks</strong><div id="apsRisks">Risk context will appear here.</div></div><div class="aps-summary"><strong>What changes</strong><div id="apsChanges">Missing confirmation will appear here.</div></div></div>`;
  main.insertBefore(shell,document.querySelector('.command-strip')||document.querySelector('.chart-grid')||main.firstElementChild);
  document.body.classList.add('atlas-product-focus');

  const text=(id,f='—')=>($(id)?.textContent||'').trim()||f;
  const humanize=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const normalizedSymbol=v=>String(v||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');

  function master(){return window.ATLAS_MASTER&&typeof window.ATLAS_MASTER==='object'?window.ATLAS_MASTER:null;}
  function production(){return window.ATLAS_PRODUCTION_DECISION&&typeof window.ATLAS_PRODUCTION_DECISION==='object'?window.ATLAS_PRODUCTION_DECISION:null;}
  function currentSymbol(){
    const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active],raw=normalizedSymbol(a?.symbol);
    if(raw)return raw;
    const t=text('activeTitle','').toUpperCase();
    for(const x of ['BTC','ETH','SOL','XRP','BNB','DOGE','ZEC','HYPE'])if(t.includes(x))return x+'USDT';
    return'';
  }
  function decision(){
    const p=production();
    const plan=p?.trade_plan||{};
    if(plan.status==='ACTIONABLE'&&p?.execution_ready&&plan.direction)return plan.direction;
    if(p)return 'WAIT';
    const d=String(master()?.decision||'').toUpperCase();
    return d==='LONG_CANDIDATE'?'LONG':d==='SHORT_CANDIDATE'?'SHORT':'WAIT';
  }
  function setupScore(){
    const p=production();
    if(Number.isFinite(Number(p?.score))&&Number.isFinite(Number(p?.signal_threshold)))return `${Number(p.score).toFixed(0)}/${Number(p.signal_threshold).toFixed(0)}`;
    const m=master();
    return Number.isFinite(Number(m?.score))?`${Number(m.score).toFixed(0)}/100 local`:'—';
  }
  function ensureHypeAsset(){
    const s=window.ATLAS_APP_STATE;
    if(!s||!Array.isArray(s.assets))return false;
    if(s.assets.some(a=>normalizedSymbol(a?.symbol)==='HYPEUSDT'))return false;
    s.assets.push({name:'HYPE / USDT',symbol:'BINANCE:HYPEUSDT',cls:'Crypto'});
    try{localStorage.setItem('atlas.assets',JSON.stringify(s.assets));}catch(_e){}
    if(typeof window.renderAll==='function')window.renderAll();
    return true;
  }

  const simpleDir=d=>String(d||'').toUpperCase()==='LONG'?'UP / LONG':String(d||'').toUpperCase()==='SHORT'?'DOWN / SHORT':'WAIT';
  function renderAi(ai,prod){
    const tac=prod?.tactical_opportunity||{},plan=prod?.trade_plan||{},canonical=Object.keys(plan).length?plan:(ai?.canonical_action||{});
    const actionable=canonical.status==='ACTIONABLE'&&!!prod?.execution_ready;
    const armed=canonical.status==='CONDITIONAL'&&!!prod?.production_signal_qualified;
    const dir=canonical.direction||prod?.candidate_direction;
    $('apsAiProd').textContent=actionable?`${simpleDir(dir)}${prod.score!=null?` · ${prod.score}/${prod.signal_threshold}`:''}`:armed?`ARMED · ${simpleDir(dir)}${prod.score!=null?` · ${prod.score}/${prod.signal_threshold}`:''}`:`WAIT${prod?.score!=null?` · ${prod.score}/${prod.signal_threshold}`:''}`;
    $('apsAiJudge').textContent=`${simpleDir(ai?.direction)}${ai?.confidence!=null?` · ${ai.confidence}% confidence`:''}`;
    $('apsAiTactical').textContent=tac?.direction?`${simpleDir(tac.direction)} · 1–3H${Number.isFinite(Number(tac.risk_reward))?` · Tactical R:R ${fmt(tac.risk_reward,2)}`:''}`:'No clear conditional short-term setup';
    const action=canonical.action||'WAIT';
    $('apsAiBest').textContent=actionable?`${action} NOW → ${simpleDir(dir)}`:armed?`ARMED · ${humanize(action)} → ${simpleDir(dir)}`:'WAIT';
    const entry=canonical.entry,stop=canonical.stop_loss,tp1=canonical.tp1,tp2=canonical.tp2,rr2=canonical.rr_tp2;
    $('apsAiGeometry').textContent=entry==null?'No canonical Production trade levels yet':`${actionable?'Verified Production plan':armed?'Armed conditional Production plan':'Production plan'} · Entry ${fmt(entry)} · Stop ${fmt(stop)} · TP1 ${fmt(tp1)} · TP2 ${fmt(tp2)} · R:R ${fmt(rr2,2)}`;
    $('apsAiTrigger').textContent=canonical.entry_trigger||canonical.invalidation||'Reassess if the verified Production structure changes.';
    const bull=(ai?.bull_analyst?.best_case||[])[0],bear=(ai?.bear_analyst?.best_case||[])[0];
    $('apsAiReason').textContent=`Why: ${bull?humanize(bull)+'. ':''}${bear?'Main risk: '+humanize(bear)+'.':''}`||'AI evidence is still limited.';
    $('apsAiState').textContent=actionable?'Production canonical decision':armed?'ARMED — verified trigger defined':'AI analysis ready';
  }
  function productionWhy(p){
    if(!p)return null;
    const candidate=p.candidate_direction&&p.candidate_direction!=='NONE'?` Candidate: ${p.candidate_direction}.`:'';
    if(p.production_signal_qualified&&p.execution_ready)return `Production signal qualified and current execution geometry passed.${candidate}`;
    if(p.production_signal_qualified&&!p.execution_ready)return `Production score qualified at ${fmt(p.score,0)}/${fmt(p.signal_threshold,0)}, but current execution is blocked by ${humanize(p.actionable_reason||p.geometry_gate?.reason||'geometry')}.${candidate}`;
    return `Production WAIT. Score ${fmt(p.score,0)}/${fmt(p.signal_threshold,0)}. Reason: ${humanize(p.wait_reason||'waiting for stronger confirmation')}.${candidate}`;
  }
  function productionRisk(p){
    if(!p)return text('cmdRiskValue','Risk context unavailable.');
    const bits=[],plan=p.trade_plan||{};
    if(p.geometry_gate?.status==='BLOCK')bits.push(`Current geometry blocked: ${humanize(p.geometry_gate.reason)}`);
    const rr=plan.rr_tp2??p.risk_reward;
    if(Number.isFinite(Number(rr)))bits.push(`Current Production R:R ${fmt(rr,2)}`);
    const obstacle=Number(p.score_attribution?.obstacle_adjustment);
    if(Number.isFinite(obstacle)&&obstacle<0)bits.push(`Obstacle penalty ${fmt(obstacle,0)}`);
    if(p.futures_available===false)bits.push('Futures confirmation unavailable');
    return bits.length?bits.join(' · '):'No additional current Production risk block.';
  }
  function productionChange(p){
    if(!p)return 'Wait for stronger direction, structure and risk/reward confirmation.';
    if(p.production_signal_qualified&&!p.execution_ready)return `Current Production execution needs valid Entry/SL/TP geometry and R:R of at least ${fmt(p.geometry_gate?.min_risk_reward??1,1)}. Conditional AI research does not override this gate.`;
    const gap=Number(p.score_gap_to_signal);
    if(!p.production_signal_qualified&&Number.isFinite(gap)&&gap>0)return `Needs ${fmt(gap,0)} more score points or stronger evidence / more room from the obstacle to reach Production qualification.`;
    if(p.execution_ready)return 'Exit or reassess if the Production trade structure is invalidated.';
    return 'Wait for the next Production confirmation.';
  }
  async function refreshAi(){
    const symbol=currentSymbol();if(!symbol)return;
    $('apsAiState').textContent='Analyzing…';
    try{
      const [pd,ai]=await Promise.all([
        fetch(`/api/decision/current?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'}).then(async r=>{const j=await r.json();if(!r.ok||j?.ok===false)throw new Error(j?.error||`Decision HTTP ${r.status}`);return j;}),
        fetch(`/api/ai/council?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'}).then(async r=>{const j=await r.json();if(!r.ok||j?.error)throw new Error(j?.error||`AI HTTP ${r.status}`);return j;})
      ]);
      window.ATLAS_PRODUCTION_DECISION=pd;
      renderAi(ai,pd);
      update();
    }catch(e){
      $('apsAiState').textContent='AI analysis unavailable';
      $('apsAiBest').textContent='WAIT';
    }
  }
  function update(){
    ensureHypeAsset();
    const p=production(),plan=p?.trade_plan||{},d=decision(),de=$('apsDecision');
    de.textContent=d;de.className='aps-value '+d.toLowerCase();
    $('apsAsset').textContent=text('activeTitle','Current asset');
    $('apsConfidence').textContent=setupScore();
    const w=d==='WAIT';
    $('apsEntry').textContent=w?'—':fmt(plan.entry);
    $('apsStop').textContent=w?'—':fmt(plan.stop_loss);
    $('apsTarget').textContent=w?'—':`${fmt(plan.tp2)}${Number.isFinite(Number(plan.rr_tp2))?` · R:R ${fmt(plan.rr_tp2,2)}`:''}`;
    $('apsRegime').textContent=p?.regime||text('cmdRegimeValue','—');
    $('apsTrend').textContent=p?.candidate_direction||text('trendState','—');
    $('apsMomentum').textContent=p?`Votes L${p.direction_votes_long??'—'}/S${p.direction_votes_short??'—'}`:text('momentumState','—');
    $('apsVolume').textContent=p?.relative_volume==null?text('volumeState','—'):`RV ${fmt(p.relative_volume,2)}`;
    $('apsStructure').textContent=p?(p.production_signal_qualified&&!p.execution_ready?`SCORE QUALIFIED · ${humanize(p.actionable_reason||p.geometry_gate?.reason)}`:`${humanize(p.wait_reason||p.playbook||'Production verified')} · score ${fmt(p.score,0)}/${fmt(p.signal_threshold,0)}`):text('structureState','—');
    $('apsLiquidity').textContent=text('liquidityNotes','No special liquidity condition.');
    $('apsWhy').textContent=productionWhy(p)||text('masterNotes',d==='WAIT'?'Waiting for stronger confirmation.':'Trade conditions aligned.');
    $('apsRisks').textContent=productionRisk(p);
    $('apsChanges').textContent=productionChange(p);
    $('apsStatus').textContent=$('analyzeBtn')?.disabled?'Analysis running…':w?'WAIT = no trade now':plan.status==='ACTIONABLE'?'Canonical Production trade plan ready':'Production plan not actionable';
    const s=$('intervalSelect'),tf=$('apsTimeframe');
    if(s&&tf&&!tf.options.length){[...s.options].forEach(o=>tf.add(new Option(o.textContent,o.value)));tf.onchange=()=>{s.value=tf.value;s.dispatchEvent(new Event('change',{bubbles:true}));};}
    if(s&&tf)tf.value=s.value;
  }
  async function waitForAnalysisReady(){
    $('apsAiState').textContent='Waiting for ATLAS analysis…';
    for(let i=0;i<48;i++){
      await new Promise(r=>setTimeout(r,250));
      const badge=text('engineBadge','').toUpperCase();
      const button=$('analyzeBtn');
      const ready=badge==='ANALYZED'||badge==='VERIFIED'||(!button?.disabled&&i>4);
      if(ready)return true;
    }
    return false;
  }
  async function runAnalysisAndCouncil(){
    const button=$('analyzeBtn');if(!button)return;
    window.ATLAS_MASTER=null;
    window.ATLAS_PRODUCTION_DECISION=null;
    $('apsAnalyze').disabled=true;
    $('apsStatus').textContent='Analysis running…';
    $('apsAiState').textContent='Waiting for ATLAS analysis…';
    $('analyzeBtn')?.click();
    await waitForAnalysisReady();
    await refreshAi();
    update();
    $('apsAnalyze').disabled=false;
  }

  $('apsAnalyze').onclick=runAnalysisAndCouncil;
  $('apsAdvanced').onclick=()=>{document.body.classList.toggle('atlas-advanced-open');};
  new MutationObserver(()=>requestAnimationFrame(update)).observe(document.body,{subtree:true,childList:true,characterData:true});
  ensureHypeAsset();
  update();
  setTimeout(refreshAi,1200);
  window.ATLAS_PRODUCT_SHELL={refresh:update,refreshAi,canonicalProductionPlan:true};
})();