(function(){
  const VERSION='ATLAS_PRODUCTION_DECISION_UI_V4_AI_COUNCIL';
  const SUPPORTED=new Set(['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT']);

  function symbolOf(asset){return String(asset?.symbol||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');}
  function signed(v){const n=Number(v||0);return `${n>=0?'+':''}${Number.isInteger(n)?n:n.toFixed(1)}`;}
  function fmt(v,d=3){const n=Number(v);return Number.isFinite(n)?n.toLocaleString(undefined,{maximumFractionDigits:d}):'—';}
  function attributionText(d){const a=d?.score_attribution;if(!a)return'';return `base ${a.trend_base} · vol ${signed(a.volume_bonus)} · RS ${signed(a.relative_strength_adjustment)} · futures ${signed(a.futures_adjustment)} · obstacle ${signed(a.obstacle_adjustment)} = ${a.final_score}`;}
  function mapDecision(d,base={}){
    const signal=d.decision==='LONG'?'BUY':d.decision==='SHORT'?'SELL':'WAIT',candidate=d.candidate_direction||'NONE',reason=d.wait_reason||'SIGNAL_QUALIFIED',attr=attributionText(d);
    return {...base,signal,confidence:d.score,score:d.score,entry:d.entry,stop_loss:d.stop_loss,stop:d.stop_loss,target:d.take_profit,risk_reward:d.risk_reward,engine:{...(base.engine||{}),trend:d.regime||candidate,momentum:`Votes L${d.direction_votes_long}/S${d.direction_votes_short}`,volume:d.relative_volume==null?(base.engine?.volume||'—'):`RV ${Number(d.relative_volume).toFixed(2)}`,structure:signal==='WAIT'?(attr?`${reason} · ${attr}`:reason):(d.playbook||'SIGNAL_QUALIFIED')},indicators:{...(base.indicators||{}),...(d.indicators||{})},production_decision:d};
  }

  function ensureCouncilPanel(){
    let el=document.getElementById('atlasAiCouncilCard'); if(el) return el;
    const anchor=document.querySelector('.lower-grid')||document.querySelector('.metrics-card'); if(!anchor) return null;
    el=document.createElement('section'); el.id='atlasAiCouncilCard'; el.className='card metrics-card ai-council-card';
    el.innerHTML=`<div class="card-head"><div><strong>ATLAS AI TRADE COUNCIL</strong><div class="muted small">Production + Tactical 1–3H + Bull/Bear + Counterfactual + Hybrid Judge</div></div><span id="aiCouncilBadge" class="pill neutral">WAITING</span></div>
    <div class="ai-council-grid">
      <div class="ai-kpi"><span>Production</span><b id="aiProdDecision">—</b><small id="aiProdScore">—</small></div>
      <div class="ai-kpi"><span>Tactical 1–3H</span><b id="aiTactical">—</b><small id="aiTacticalRR">—</small></div>
      <div class="ai-kpi"><span>AI Judge</span><b id="aiJudge">—</b><small id="aiConfidence">—</small></div>
      <div class="ai-kpi"><span>Hybrid</span><b id="aiHybrid">—</b><small id="aiHybridSub">—</small></div>
    </div>
    <div class="ai-council-split">
      <div class="ai-case"><div class="panel-title">BULL CASE</div><div id="aiBullCase" class="muted small">Waiting for analysis.</div></div>
      <div class="ai-case"><div class="panel-title">BEAR CASE</div><div id="aiBearCase" class="muted small">Waiting for analysis.</div></div>
    </div>
    <div class="ai-counterfactual"><div class="panel-title">BEST ACTION / COUNTERFACTUAL</div><div id="aiBestAction" class="ai-best-action">—</div><div id="aiGeometry" class="muted small">—</div><div id="aiTrigger" class="muted tiny">—</div></div>
    <div id="aiEvidence" class="comparison-box muted small">Evidence will appear after Analyze Live.</div>`;
    anchor.parentNode.insertBefore(el,anchor); return el;
  }

  function setText(id,text){const el=document.getElementById(id);if(el)el.textContent=text??'—';}
  function renderCouncil(decision,ai){
    ensureCouncilPanel();
    const t=decision?.tactical_opportunity||{}, b=ai?.best_counterfactual||{}, h=ai?.hybrid_judge||{};
    setText('aiProdDecision',decision?.decision||'—'); setText('aiProdScore',decision?.score==null?`threshold ${decision?.signal_threshold??'—'}`:`score ${decision.score}/${decision.signal_threshold}`);
    setText('aiTactical',t.status||'—'); setText('aiTacticalRR',t.risk_reward==null?'RR —':`RR ${fmt(t.risk_reward,2)} · ${t.horizon||'1–3H'}`);
    setText('aiJudge',ai?.verdict?`${ai.direction||''} ${ai.verdict}`.trim():'—'); setText('aiConfidence',ai?.confidence==null?'—':`confidence ${ai.confidence}%`);
    setText('aiHybrid',h.decision||'—'); setText('aiHybridSub',h.agreement?'Production + AI agree':'Independent shadow review');
    setText('aiBullCase',(ai?.bull_analyst?.best_case||[]).join(' · ')||'No strong bullish evidence');
    setText('aiBearCase',(ai?.bear_analyst?.best_case||[]).join(' · ')||'No strong bearish evidence');
    setText('aiBestAction',b.scenario?`${b.scenario}${b.direction?` · ${b.direction}`:''}`:'—');
    setText('aiGeometry',b.entry==null?'No executable shadow geometry':`Entry ${fmt(b.entry,8)} · SL ${fmt(b.stop_loss,8)} · TP ${fmt(b.target,8)} · RR ${fmt(b.risk_reward,2)}`);
    setText('aiTrigger',b.trigger||b.thesis||'—');
    const evidence=(ai?.evidence||[]).slice(0,8).map(x=>`${x.name}: ${x.detail}`).join(' | '); setText('aiEvidence',evidence||'No structured evidence available.');
    const badge=document.getElementById('aiCouncilBadge'); if(window.setPill&&badge) window.setPill(badge,ai?.verdict||'WAIT',ai?.verdict==='TAKE_SHADOW'?'buy':ai?.verdict==='REJECT'?'sell':'neutral');
  }

  async function fetchCouncil(symbol,decision){
    try{const res=await fetch(`/api/ai/council?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'});const ai=await res.json();if(!res.ok||ai.error)throw new Error(ai.error||`AI council HTTP ${res.status}`);window.ATLAS_AI_COUNCIL=ai;renderCouncil(decision,ai);return ai;}
    catch(err){console.error('[ATLAS AI council]',err);ensureCouncilPanel();setText('aiBestAction',`AI Council unavailable: ${err.message}`);return null;}
  }

  async function productionVerify(){
    const state=window.ATLAS_APP_STATE,asset=state?.assets?.[state.active],symbol=symbolOf(asset); if(!SUPPORTED.has(symbol)) return false;
    const btn=document.getElementById('analyzeBtn'),badge=document.getElementById('engineBadge'),label=document.getElementById('providerLabel'); if(btn)btn.disabled=true;if(window.setPill&&badge)window.setPill(badge,'VERIFYING','working');if(label)label.textContent='Verifying final decision with ATLAS Production…';
    const key=window.resultKey?window.resultKey():`${asset.symbol}|${state.interval}`,existing=state.liveResults[key]||{},existingResult=existing.result||window.ATLAS_LATEST_BASE||{};
    try{
      const res=await fetch(`/api/decision/current?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'}),data=await res.json(); if(!res.ok||!data.ok)throw new Error(data.error||`Production decision HTTP ${res.status}`);
      const result=mapDecision(data,existingResult);window.ATLAS_LATEST_BASE=result;window.ATLAS_PRODUCTION_DECISION=data;state.liveResults[key]={...existing,provider:'ATLAS Production verified',result,confluence:existing.confluence||window.ATLAS_LATEST_CONFLUENCE||null,time:Date.now(),production:true};
      if(window.applySignal)window.applySignal(result,`ATLAS Production verified · ${data.scoring_version||data.source} · ${new Date(data.generated_at).toLocaleString()}`);if(window.refreshTradeManagement)setTimeout(()=>window.refreshTradeManagement(result,state.liveResults[key].confluence),30);
      if(label){const attr=attributionText(data),detail=data.decision==='WAIT'?`WAIT verified · ${data.wait_reason} · candidate ${data.candidate_direction||'none'} · score ${data.score??'—'}/${data.signal_threshold}${attr?` · ${attr}`:''}`:`${data.decision} verified · score ${data.score}/${data.signal_threshold} · ${data.playbook||'production signal'}${attr?` · ${attr}`:''}`;label.textContent=`ATLAS Production · ${detail}`;}
      if(window.setPill&&badge)window.setPill(badge,'VERIFIED',data.decision==='WAIT'?'neutral':'buy');
      await fetchCouncil(symbol,data); return true;
    }catch(err){console.error('[ATLAS production verification]',err);if(label)label.textContent=`Production verification unavailable · local analysis preserved · ${err.message}`;if(window.setPill&&badge)window.setPill(badge,'LOCAL ONLY','neutral');return false;}
    finally{if(btn)btn.disabled=false;}
  }

  function install(){
    ensureCouncilPanel(); const btn=document.getElementById('analyzeBtn'); if(!btn||btn.dataset.productionDecisionInstalled==='4')return;const original=btn.onclick;btn.dataset.productionDecisionInstalled='4';
    btn.onclick=async function(ev){const state=window.ATLAS_APP_STATE,asset=state?.assets?.[state.active];if(typeof original==='function')await original.call(this,ev);else if(typeof window.analyzeActive==='function')await window.analyzeActive();if(SUPPORTED.has(symbolOf(asset)))await productionVerify();};
    window.ATLAS_PRODUCTION_DECISION_UI={version:VERSION,verify:productionVerify,supported:[...SUPPORTED]};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
