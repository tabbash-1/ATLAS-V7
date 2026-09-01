(function(){
  const VERSION='ATLAS_RC10_1_DEEP_UI_V2_PRIMARY_4_12H';
  const SUPPORTED=new Set(['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT']);
  let requestEpoch=0;
  const $=id=>document.getElementById(id);
  function symbol(){const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active];return String(a?.symbol||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');}
  function fmt(v,d=4){const n=Number(v);return Number.isFinite(n)?n.toLocaleString(undefined,{maximumFractionDigits:d}):'—';}
  function txt(id,v){const e=$(id);if(e)e.textContent=v??'—';}
  function pill(id,v,good){const e=$(id);if(!e)return;e.textContent=v||'—';e.className=`pill ${good?'buy':'neutral'}`;}
  function human(v){return String(v||'').replaceAll('_',' ').replace(/\s+/g,' ').trim();}

  function installStyles(){
    if($('atlasDeepRc10Styles'))return;
    const s=document.createElement('style');s.id='atlasDeepRc10Styles';
    s.textContent=`
      #atlasDeepRc10{margin:14px 0;border:1px solid rgba(130,92,255,.52);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(16,17,32,.96),rgba(8,14,25,.96))}
      .atlas-deep-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.atlas-deep-head strong{font-size:15px}.atlas-deep-sub{margin-top:4px;color:#9aa8bd;font-size:11px;line-height:1.45}
      .atlas-deep-primary{display:grid;grid-template-columns:1.25fr .75fr;gap:9px;margin-top:12px}.atlas-deep-decision,.atlas-deep-score{border:1px solid #2b3850;border-radius:13px;padding:12px;background:#0b1220}.atlas-deep-decision b{display:block;font-size:28px;margin-top:4px}.atlas-deep-score b{display:block;font-size:22px;margin-top:4px}.atlas-deep-label{color:#a984ff;font-size:9px;text-transform:uppercase;letter-spacing:.12em}
      .atlas-deep-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:9px}.atlas-deep-kpi{border:1px solid #263448;border-radius:10px;padding:9px;background:#0b1220}.atlas-deep-kpi span{display:block;color:#8c9ab3;font-size:9px;text-transform:uppercase;letter-spacing:.06em}.atlas-deep-kpi b{display:block;margin-top:4px;font-size:13px;word-break:break-word}
      .atlas-deep-section{margin-top:9px;border:1px solid #263448;border-radius:11px;padding:10px;background:#0a111d}.atlas-deep-section strong{font-size:10px;color:#a984ff;letter-spacing:.08em}.atlas-deep-list{margin-top:6px;line-height:1.55;white-space:pre-wrap;font-size:11px;color:#c4cddd}
      .atlas-deep-mtf{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:8px}.atlas-deep-mtf div{border:1px solid #263448;border-radius:8px;padding:7px;text-align:center;font-size:10px;background:#0b1220}.atlas-deep-mtf b{color:#e8edf7}
      .atlas-deep-wait{color:#f4c95d}.atlas-deep-long{color:#55d68b}.atlas-deep-short{color:#ff6b7a}
      @media(max-width:900px){#atlasDeepRc10{padding:12px}.atlas-deep-primary{grid-template-columns:1fr 1fr}.atlas-deep-grid{grid-template-columns:repeat(2,1fr)}.atlas-deep-mtf{grid-template-columns:repeat(2,1fr)}.atlas-deep-head{align-items:center}}
    `;document.head.appendChild(s);
  }

  function ensure(){
    installStyles();
    let el=$('atlasDeepRc10');
    const shell=$('atlasProductShell');
    if(!el){
      el=document.createElement('section');el.id='atlasDeepRc10';
      el.innerHTML=`
        <div class="atlas-deep-head"><div><strong>ATLAS RC10.1 · FULL TRADE ANALYSIS</strong><div class="atlas-deep-sub">Primary thesis 4–12H · 1H is entry timing only · Production gate remains safety authority</div></div><span id="deepBadge" class="pill neutral">LOADING</span></div>
        <div class="atlas-deep-primary"><div class="atlas-deep-decision"><span class="atlas-deep-label">Best action now</span><b id="deepMainDecision" class="atlas-deep-wait">WAIT</b><div id="deepReason" class="atlas-deep-sub">Building multi-timeframe thesis…</div></div><div class="atlas-deep-score"><span class="atlas-deep-label">Technical depth</span><b id="deepTech">—/100</b><div id="deepScenarioShort" class="atlas-deep-sub">Scenario —</div></div></div>
        <div class="atlas-deep-grid"><div class="atlas-deep-kpi"><span>Candidate</span><b id="deepDirection">—</b></div><div class="atlas-deep-kpi"><span>Execution state</span><b id="deepExec">—</b></div><div class="atlas-deep-kpi"><span>Entry</span><b id="deepEntry">—</b></div><div class="atlas-deep-kpi"><span>Stop / invalidation</span><b id="deepStop">—</b></div><div class="atlas-deep-kpi"><span>TP1</span><b id="deepTp1">—</b></div><div class="atlas-deep-kpi"><span>TP2</span><b id="deepTp2">—</b></div><div class="atlas-deep-kpi"><span>TP3</span><b id="deepTp3">—</b></div><div class="atlas-deep-kpi"><span>R:R TP2</span><b id="deepRR">—</b></div></div>
        <div class="atlas-deep-section"><strong>MULTI-TIMEFRAME · 1D / 12H / 6H / 4H / 1H</strong><div id="deepMtf" class="atlas-deep-mtf"></div></div>
        <div class="atlas-deep-section"><strong>STRUCTURE / BOS-CHOCH / VWAP / VOLUME PROFILE</strong><div id="deepStructure" class="atlas-deep-list">—</div></div>
        <div class="atlas-deep-section"><strong>LIQUIDITY / DELTA-CVD / ORDER BLOCK / FVG</strong><div id="deepFlow" class="atlas-deep-list">—</div></div>
        <div class="atlas-deep-section"><strong>SCENARIO / EVIDENCE / TRIGGER</strong><div id="deepThesis" class="atlas-deep-list">—</div></div>
        <div class="atlas-deep-section"><strong>DECISION AUDIT / BLOCKERS</strong><div id="deepBlockers" class="atlas-deep-list">—</div></div>`;
    }
    if(shell){
      const actions=$('apsAnalyze')?.parentElement;
      if(el.parentElement!==shell){
        if(actions&&actions.parentElement===shell)actions.insertAdjacentElement('afterend',el);else shell.prepend(el);
      }
      txt('apsContextAuthority','Primary trade analysis: 4–12H · Entry timing: 1H · Production safety gate: 1H');
      const tacticalLabel=[...shell.querySelectorAll('.aps-ai-card span')].find(x=>/Conditional 1.?3H research/i.test(x.textContent||''));
      if(tacticalLabel)tacticalLabel.textContent='RC10.1 4–12H scenario';
    }else if(!el.isConnected){
      const anchor=$('atlasTradePlan')||$('atlasAiCouncilCard')||document.querySelector('.lower-grid')||document.querySelector('main');
      if(anchor)anchor.parentNode.insertBefore(el,anchor);
    }
    return el;
  }

  function updateProductShell(d){
    const shell=$('atlasProductShell');if(!shell||!d?.ok)return;
    txt('apsContextAuthority','Primary trade analysis: 4–12H · Entry timing: 1H · Production safety gate: 1H');
    const s=d.scenario||{};
    txt('apsAiTactical',`${s.name||'NO SCENARIO'} · ${fmt(s.score,0)}/100 · ${d.execution_state||'WAIT'}`);
    if($('apsLiquidity'))txt('apsLiquidity',`Sweep ${human(d.liquidity_4h?.sweep||'NONE')} · Delta ${human(d.delta_cvd_proxy_1h?.bias||'NEUTRAL')}`);
  }

  function render(d){
    ensure();
    if(!d?.ok){pill('deepBadge','UNAVAILABLE',false);txt('deepReason',d?.error||'Deep analysis unavailable.');return;}
    const p=d.entry_plan||{},s=d.scenario||{},st=d.structure_4h||{},bc=d.bos_choch_4h||{},vw=d.anchored_vwap_4h||{},vp=d.volume_profile_4h||{},fl=d.delta_cvd_proxy_1h||{},lq=d.liquidity_4h||{},hi=d.historical_context_4h||{};
    const decision=d.decision||'WAIT', candidate=d.candidate_direction||'NONE';
    pill('deepBadge',d.execution_state||decision,decision!=='WAIT');
    txt('deepMainDecision',decision);const dm=$('deepMainDecision');if(dm)dm.className=decision==='LONG'?'atlas-deep-long':decision==='SHORT'?'atlas-deep-short':'atlas-deep-wait';
    txt('deepReason',decision==='WAIT'?`WAIT until ${human(p.entry_trigger||'all required gates align')}`:`${decision} setup passed current decision audit`);
    txt('deepTech',`${fmt(d.technical_score,1)}/100`);txt('deepScenarioShort',`${s.name||'—'} · ${s.grade||'—'} · ${fmt(s.score,0)}/100`);
    txt('deepDirection',candidate);txt('deepExec',d.execution_state||'—');txt('deepEntry',fmt(p.entry,8));txt('deepStop',fmt(p.stop_loss,8));txt('deepTp1',fmt(p.tp1,8));txt('deepTp2',fmt(p.tp2,8));txt('deepTp3',fmt(p.tp3,8));txt('deepRR',p.rr_tp2==null?'—':`${fmt(p.rr_tp2,2)}R`);
    const mt=$('deepMtf');if(mt){mt.innerHTML='';for(const tf of ['1d','12h','6h','4h','1h']){const x=d.mtf_states?.[tf]||{};const z=document.createElement('div');z.innerHTML=`<b>${tf.toUpperCase()}</b><br>${x.bias||'—'}<br><span class="muted tiny">RSI ${fmt(x.rsi14,1)}</span>`;mt.appendChild(z);}}
    txt('deepStructure',`4H structure: ${st.state||'—'} · BOS/CHOCH: ${bc.event||'NONE'}\nAnchored VWAP: ${fmt(vw.value,8)} · price ${vw.position||'—'} VWAP\nVolume Profile: ${vp.location||'—'} · POC ${fmt(vp.poc,8)} · VAH ${fmt(vp.vah,8)} · VAL ${fmt(vp.val,8)}\nHistorical context: price pctl ${fmt(hi.price_percentile,1)} · volume pctl ${fmt(hi.volume_percentile,1)} · ATR pctl ${fmt(hi.atr_percentile,1)}`);
    txt('deepFlow',`Liquidity sweep: ${human(lq.sweep||'NONE')} · buy-side ${fmt(lq.buy_side_target,8)} · sell-side ${fmt(lq.sell_side_target,8)}\nDelta/CVD proxy: ${fl.bias||'—'} · divergence ${human(fl.divergence||'NONE')} · recent delta ${fmt(fl.recent_delta,2)}\nOrder block: ${d.order_block_4h?`${human(d.order_block_4h.type)} ${fmt(d.order_block_4h.low,8)}–${fmt(d.order_block_4h.high,8)}`:'NONE'} · FVG bull ${(d.fvg_4h?.bullish||[]).length} / bear ${(d.fvg_4h?.bearish||[]).length}`);
    const yes=(d.evidence_for||[]).map(human).join(' · ')||'No strong confirming evidence';const no=(d.evidence_against||[]).map(human).join(' · ')||'No material soft conflicts';
    txt('deepThesis',`Scenario: ${human(s.name||'NONE')} · score ${fmt(s.score,0)}/100 · grade ${s.grade||'—'}\nFOR: ${yes}\nAGAINST: ${no}\nTrigger: ${p.entry_trigger||'—'}\nExpected holding: ${p.expected_holding_hours||'4-12'} hours`);
    const blocks=(d.hard_blockers||[]).map(human).join(' · ')||'NONE';
    txt('deepBlockers',`Hard blockers: ${blocks}\nInvalidation: ${p.invalidation||'—'}\nAudit: technical ${d.decision_audit?.technical_depth_pass?'PASS':'FAIL'} · scenario ${d.decision_audit?.scenario_coherence_pass?'PASS':'FAIL'} · RR ${d.decision_audit?.rr_pass?'PASS':'FAIL'} · trigger ${d.decision_audit?.trigger_pass?'PASS':'FAIL'} · final ${d.decision_audit?.final_ready?'READY':'WAIT'}`);
    updateProductShell(d);
  }

  async function load(){
    const s=symbol();if(!SUPPORTED.has(s))return;
    const epoch=++requestEpoch;ensure();pill('deepBadge','ANALYZING',false);
    try{const r=await fetch(`/api/deep-analysis/current?symbol=${encodeURIComponent(s)}&t=${Date.now()}`,{cache:'no-store'});const d=await r.json();if(epoch!==requestEpoch||symbol()!==s)return;render(d);window.ATLAS_RC10_1_DEEP_ANALYSIS=d;}
    catch(e){if(epoch===requestEpoch)render({ok:false,error:e.message});}
  }

  function bind(){
    ensure();
    for(const id of ['apsAnalyze','analyzeBtn']){const b=$(id);if(b&&!b.dataset.deepRc10){b.dataset.deepRc10='2';b.addEventListener('click',()=>setTimeout(load,80));}}
  }
  function install(){bind();load();let attempts=0;const timer=setInterval(()=>{bind();attempts++;if(attempts>40)clearInterval(timer);},250);window.ATLAS_RC10_1_DEEP_UI={version:VERSION,refresh:load,primaryHorizon:'4-12H',entryTiming:'1H'};}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();