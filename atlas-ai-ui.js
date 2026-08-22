(function(){
  function esc(x){return String(x??'—').replace(/[&<>]/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[s]));}
  function ensureCard(){if(document.getElementById('atlasAiAnalystCard'))return;const card=document.createElement('section');card.id='atlasAiAnalystCard';card.className='card metrics-card';card.innerHTML=`<div class="card-head"><div><strong>ATLAS AI ANALYST</strong><div class="muted small">Multi-timeframe · historical structure · liquidity · smart money · server-side AI · research only</div></div><span id="atlasAiBadge" class="pill neutral">READY</span></div><div class="backtest-actions"><button id="atlasAiRunBtn" class="analyze-btn">Analyze with ATLAS AI</button></div><div id="atlasAiDecision" class="trial-grid"><div><span>Decision</span><b>WAITING</b></div><div><span>Confidence</span><b>—</b></div><div><span>Regime</span><b>—</b></div><div><span>R:R</span><b>—</b></div></div><div id="atlasAiPlan" class="comparison-box muted small">Waiting for structured multi-timeframe analysis.</div>`;const anchor=document.querySelector('.metrics-card');(anchor?.parentNode||document.querySelector('main')||document.body).insertBefore(card,anchor||null);document.getElementById('atlasAiRunBtn').addEventListener('click',run);}
  function activeAsset(){const label=document.getElementById('tvSymbolLabel')?.textContent?.trim()||'BINANCE:BTCUSDT';return {name:document.getElementById('activeTitle')?.textContent?.trim()||label,symbol:label,cls:'Crypto'};}
  async function getJson(path){try{const r=await fetch(path);return r.ok?await r.json():null;}catch(_e){return null;}}
  async function evidence(asset){
    const symbol=String(asset?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'');
    const [sm,memory,events]=await Promise.all([
      getJson(`/api/smart-money/latest?symbol=${encodeURIComponent(symbol)}`),
      getJson(`/api/confluence/memory-stats?symbol=${encodeURIComponent(symbol)}`),
      getJson('/api/events/latest')
    ]);
    const relevantEvents=(events?.events||[]).filter(x=>(x.scope||'MARKET')==='MARKET'||x.symbol===symbol).slice(-12);
    return {
      smartMoney:sm?.snapshot||null,
      futures:window.ATLAS_LATEST_FUTURES||null,
      liquidity:window.ATLAS_LIQUIDITY||null,
      confluence:window.ATLAS_LATEST_CONFLUENCE||null,
      masterConviction:window.ATLAS_MASTER||null,
      patternMemory:memory?{observations:memory.observations||0,matured:memory.matured||{},setups:(memory.setups||[]).slice(0,8)}:null,
      eventIntelligence:relevantEvents.length?{events:relevantEvents}:null,
      portfolioRisk:window.ATLAS_PORTFOLIO_ASSESSMENT||null
    };
  }
  async function callAI(packet){try{const r=await fetch('/api/ai/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(packet)});if(!r.ok)throw new Error(`AI gateway HTTP ${r.status}`);const j=await r.json();if(j?.ok&&j?.thesis)return {...j.thesis,_provider:j.provider||'AI',_model:j.model||''};throw new Error(j?.error||'AI unavailable');}catch(e){const f=packet.fallback_thesis;return {...f,_provider:'ATLAS deterministic fallback',_model:'',_fallback_error:e.message};}}
  function render(x){document.getElementById('atlasAiDecision').innerHTML=`<div><span>Decision</span><b>${esc(x.decision)}</b></div><div><span>Confidence</span><b>${esc(x.confidence)}%</b></div><div><span>Regime</span><b>${esc(x.market_regime)}</b></div><div><span>R:R</span><b>${esc(x.risk_reward)}</b></div>`;const sup=(x.supporting_factors||[]).slice(0,5).join(' · '),opp=(x.opposing_factors||[]).slice(0,5).join(' · ');document.getElementById('atlasAiPlan').innerHTML=`<b>Entry:</b> ${esc(x.entry_zone?.join(' – '))} · <b>SL:</b> ${esc(x.stop_loss)} · <b>TP1:</b> ${esc(x.take_profit_1)} · <b>TP2:</b> ${esc(x.take_profit_2)} · <b>TP3:</b> ${esc(x.take_profit_3)}<br><b>Thesis:</b> ${esc(x.thesis)}${sup?`<br><b>For:</b> ${esc(sup)}`:''}${opp?`<br><b>Against:</b> ${esc(opp)}`:''}${x.no_trade_reason?`<br><b>WAIT reason:</b> ${esc(x.no_trade_reason)}`:''}${x.decision_quality?`<br><b>Quality:</b> ${esc(x.decision_quality.quality_score)} / 100 · ${esc(x.decision_quality.gate)}`:''}<br><span class="muted tiny">Source: ${esc(x._provider)} ${esc(x._model)}</span>${x._fallback_error?`<br><span class="muted tiny">AI fallback reason: ${esc(x._fallback_error)}</span>`:''}`;document.getElementById('atlasAiBadge').textContent=x.decision;}
  async function run(){const badge=document.getElementById('atlasAiBadge'),plan=document.getElementById('atlasAiPlan');try{badge.textContent='ANALYZING';const asset=activeAsset();if(!window.ATLAS_TIMEFRAME_ENGINE||!window.ATLAS_AI_ANALYSIS_LAYER)throw new Error('ATLAS AI modules not loaded');if(asset.cls!=='Crypto')throw new Error('AI multi-timeframe aggregation currently requires crypto market data.');const tfs=await window.ATLAS_TIMEFRAME_ENGINE.atlasBuildCryptoTimeframes(asset);const ev=await evidence(asset);const packet=window.ATLAS_AI_ANALYSIS_LAYER.buildAtlasAIAnalysisPacket({asset,timeframes:tfs,...ev});let x=await callAI(packet);if(window.ATLAS_DECISION_QUALITY)x=window.ATLAS_DECISION_QUALITY.atlasApplyDecisionGate(packet,x);render(x);window.ATLAS_LAST_AI_PACKET=packet;window.ATLAS_LAST_AI_THESIS=x;}catch(e){badge.textContent='ERROR';plan.textContent=e.message;}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ensureCard);else ensureCard();
})();
