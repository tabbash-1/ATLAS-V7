(() => {
  const VERSION='ATLAS_PRODUCTION_WEB_AUTOLOAD_V5_CANONICAL_FINAL_TRUTH';
  const $=id=>document.getElementById(id);
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=2)=>finite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const human=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const norm=v=>String(v||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  const setText=(id,v)=>{const el=$(id);if(el)el.textContent=v==null?'—':String(v);};
  let acceptedDecision=null,acceptedSymbol='',verifyEpoch=0;

  function currentUiSymbol(){const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active],raw=norm(a?.symbol);if(raw)return raw;const t=($('activeTitle')?.textContent||'').toUpperCase();for(const x of ['BTC','ETH','SOL','XRP','BNB','DOGE','ZEC','HYPE'])if(t.includes(x))return x+'USDT';return'';}
  function canonical(d){const c=d?.canonical_decision;return c?.schema==='ATLAS_CANONICAL_DECISION_TRUTH_V1'&&c?.canonical_source_present===true&&c?.source_of_truth==='FINAL_TRADE_GATE'&&c?.product_horizon==='4-12H'&&Array.isArray(c?.evaluation_horizons_h)&&c.evaluation_horizons_h.join(',')==='4,8,12'?c:null;}
  function analyst(d){const a=d?.analyst_output;return a?.horizon==='4-12H'&&a?.analysis_only===true&&a?.live_execution===false?a:null;}
  function canonicalState(d){const c=canonical(d);return c?.trade_ready===true&&(c.decision==='LONG'||c.decision==='SHORT')?'ACTIONABLE':'WAIT';}
  function plan(d){return d?.trade_plan||{};}
  function tone(el,kind){if(!el)return;const tile=el.closest('.command-tile');if(!tile)return;tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');tile.classList.add(`tone-${kind}`);}

  function acceptSnapshot(d,symbol=currentUiSymbol()){
    const normalized=norm(symbol),c=canonical(d);
    if(!d||!d.ok||!c||!normalized||normalized!==currentUiSymbol()||norm(c.symbol)!==normalized)return false;
    acceptedDecision=d;acceptedSymbol=normalized;window.ATLAS_PRODUCTION_DECISION=d;window.ATLAS_CANONICAL_DECISION=c;window.ATLAS_ANALYST_OUTPUT=analyst(d);return true;
  }
  function invalidateSnapshot(){verifyEpoch++;acceptedDecision=null;acceptedSymbol='';window.ATLAS_CANONICAL_DECISION=null;window.ATLAS_ANALYST_OUTPUT=null;}

  function syncProductShell(d){
    const c=canonical(d);if(!c)return;const a=analyst(d)||{},p=plan(d),actionable=canonicalState(d)==='ACTIONABLE';
    const score=finite(c.score)?Math.round(Number(c.score)):null,threshold=finite(c.threshold)?Math.round(Number(c.threshold)):68,decision=actionable?c.decision:'WAIT';
    setText('apsDecision',decision);const de=$('apsDecision');if(de)de.className='aps-value '+(actionable?decision.toLowerCase():'wait');
    setText('apsConfidence',`${score===null?'—':score}/${threshold}`);
    setText('apsEntry',actionable?fmt(p.entry):'—');setText('apsStop',actionable?fmt(p.stop_loss):'—');
    const target=p.tp2??p.take_profit??p.target;setText('apsTarget',actionable?`${fmt(target)}${finite(p.rr_tp2??d.risk_reward)?` · R:R ${fmt(p.rr_tp2??d.risk_reward,2)}`:''}`:'—');
    setText('apsRegime',a.regime||d.regime||'MIXED');setText('apsTrend',actionable?decision:(d.product_direction||d.candidate_direction||'NONE'));
    setText('apsStructure',`${human(actionable?(a.primary_reason||'Final gate approved'):c.wait_reason||c.raw_wait_reason||a.primary_reason||'WAIT')} · 4–12H`);
    setText('apsStatus',actionable?'TRADE READY · Final Trade Gate':'WAIT · Final Trade Gate');
    setText('apsAiProd',`${decision}${score===null?'':` · ${score}/${threshold}`}`);setText('apsAiBest',decision);
    setText('apsAiGeometry',actionable?`Entry ${fmt(p.entry)} · Stop ${fmt(p.stop_loss)} · TP ${fmt(target)} · canonical Final Gate`:'No user-facing trade geometry while canonical decision is WAIT');
    setText('apsAiTrigger',(a.what_changes_status||[]).map(human).join(' · ')||human(c.raw_wait_reason||c.wait_reason||a.invalidation||'New verified Final Gate decision required.'));
    setText('apsAiState',actionable?'FINAL TRADE GATE · TRADE READY':'FINAL TRADE GATE · WAIT');
    setText('apsWhy',actionable?(a.reasons||[]).map(human).join(' · ')||'Final Trade Gate approved the 4–12H setup':human(c.wait_reason||c.raw_wait_reason||'WAIT'));
    const risks=[];if(a.setup_quality_gate?.status==='BLOCK')risks.push(`Evidence: ${human(a.setup_quality_gate.reason)}`);if(d.geometry_gate?.status==='BLOCK')risks.push(`Geometry: ${human(d.geometry_gate.reason)}`);if(a.data_degraded)risks.push('Data degraded');setText('apsRisks',risks.length?risks.join(' · '):'No additional analysis-layer warning.');
    setText('apsChanges',(a.what_changes_status||[]).map(human).join(' · ')||'Wait for the canonical Final Trade Gate decision to change.');
  }

  function render(d){
    if(!acceptSnapshot(d))return false;const c=canonical(d),actionable=canonicalState(d)==='ACTIONABLE';
    const master=$('cmdMasterValue'),sub=$('cmdMasterSub'),score=finite(c.score)?Math.round(Number(c.score)):null,threshold=finite(c.threshold)?Math.round(Number(c.threshold)):68,decision=actionable?c.decision:'WAIT';
    if(master)master.textContent=`${decision} · ${score===null?'—':score}/${threshold}`;
    if(sub)sub.textContent=`4–12H · Final Trade Gate · ${human(c.wait_reason||'verified')}`;
    tone(master,actionable?(decision==='LONG'?'positive':'negative'):'neutral');
    const a=analyst(d)||{},regime=$('cmdRegimeValue');if(regime)regime.textContent=a.regime||d.regime||'MIXED';tone(regime,(a.regime||d.regime)==='TREND_UP'?'positive':(a.regime||d.regime)==='TREND_DOWN'?'negative':'neutral');
    const p=plan(d),target=p.tp2??p.take_profit??p.target,planEl=$('cmdPlanValue'),planSub=$('cmdPlanSub');if(planEl)planEl.textContent=actionable?'TRADE READY':'WAIT';
    if(planSub)planSub.textContent=actionable?`Entry ${fmt(p.entry)} · SL ${fmt(p.stop_loss)} · TP ${fmt(target)}`:`${human(c.wait_reason||c.raw_wait_reason||'Final Gate blocked')}`;
    tone(planEl,actionable?'positive':'neutral');syncProductShell(d);
    const cloud=$('cmdCloudValue');if(cloud){cloud.textContent='OFF-WEB';const small=cloud.closest('.command-tile')?.querySelector('small');if(small)small.textContent='Scheduled evidence: GitHub Actions';tone(cloud,'neutral');}
    return true;
  }

  function restoreAcceptedSnapshot(){if(!acceptedDecision||currentUiSymbol()!==acceptedSymbol)return;if(window.ATLAS_PRODUCTION_DECISION!==acceptedDecision)window.ATLAS_PRODUCTION_DECISION=acceptedDecision;window.ATLAS_CANONICAL_DECISION=canonical(acceptedDecision);window.ATLAS_ANALYST_OUTPUT=analyst(acceptedDecision);syncProductShell(acceptedDecision);}
  function hookVerify(ui){if(!ui||typeof ui.verify!=='function'||ui.__commandStripHooked)return;const original=ui.verify.bind(ui);ui.verify=async(...args)=>{const epoch=++verifyEpoch,symbol=currentUiSymbol(),previous=acceptedDecision,previousSymbol=acceptedSymbol,ok=await original(...args);if(epoch!==verifyEpoch||currentUiSymbol()!==symbol){if(previous&&currentUiSymbol()===previousSymbol){acceptedDecision=previous;acceptedSymbol=previousSymbol;restoreAcceptedSnapshot();}return false;}if(ok&&window.ATLAS_PRODUCTION_DECISION)render(window.ATLAS_PRODUCTION_DECISION);return ok;};ui.__commandStripHooked=true;}
  let refreshTimer=null;function scheduleVerify(delay=140){clearTimeout(refreshTimer);refreshTimer=setTimeout(async()=>{const ui=window.ATLAS_PRODUCTION_DECISION_UI;if(ui?.verify)await ui.verify();},delay);}
  function watchAssetChanges(){const title=$('activeTitle');if(!title||title.dataset.productionAssetWatcher==='1')return;title.dataset.productionAssetWatcher='1';let previous=title.textContent.trim();new MutationObserver(()=>{const current=title.textContent.trim();if(current&&current!==previous){previous=current;invalidateSnapshot();setText('cmdMasterSub',`Verifying ${current}…`);scheduleVerify();}}).observe(title,{subtree:true,childList:true,characterData:true});}
  function watchProductShellConsistency(){const shell=$('atlasProductShell');if(!shell||shell.dataset.productionSnapshotGuard==='1')return;shell.dataset.productionSnapshotGuard='1';let queued=false;new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;restoreAcceptedSnapshot();});}).observe(shell,{subtree:true,childList:true,characterData:true});}
  async function boot(attempt=0){const ui=window.ATLAS_PRODUCTION_DECISION_UI;if(!ui?.verify){if(attempt<40)return setTimeout(()=>boot(attempt+1),250);setText('cmdMasterSub','Production UI failed to load');return;}hookVerify(ui);watchAssetChanges();watchProductShellConsistency();setText('cmdMasterSub','Verifying canonical Final Trade Gate…');const ok=await ui.verify();if(ok&&window.ATLAS_PRODUCTION_DECISION)render(window.ATLAS_PRODUCTION_DECISION);else setText('cmdMasterSub','Production API unavailable — retry Analyze Live');setTimeout(watchProductShellConsistency,900);}

  window.ATLAS_RENDER_PRODUCTION_STATUS=render;window.ATLAS_SYNC_PRODUCT_SHELL=syncProductShell;window.ATLAS_CANONICAL_STATE=canonicalState;window.ATLAS_PRODUCTION_SNAPSHOT_GUARD={restore:restoreAcceptedSnapshot,current:()=>acceptedDecision,symbol:()=>acceptedSymbol,accept:acceptSnapshot,invalidate:invalidateSnapshot};window.ATLAS_PRODUCT_AUTHORITY={version:VERSION,contract:'canonical_decision',sourceOfTruth:'FINAL_TRADE_GATE',horizon:'4-12H',evaluationHorizons:[4,8,12],analysisOnly:true};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,350),{once:true});else setTimeout(boot,350);
})();