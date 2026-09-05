(() => {
  const VERSION='ATLAS_PRODUCTION_WEB_AUTOLOAD_V4_ANALYST_OUTPUT';
  const $=id=>document.getElementById(id);
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=2)=>finite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const human=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const norm=v=>String(v||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  const setText=(id,v)=>{const el=$(id);if(el)el.textContent=v==null?'—':String(v);};
  let acceptedDecision=null,acceptedSymbol='',verifyEpoch=0;

  function currentUiSymbol(){const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active],raw=norm(a?.symbol);if(raw)return raw;const t=($('activeTitle')?.textContent||'').toUpperCase();for(const x of ['BTC','ETH','SOL','XRP','BNB','DOGE','ZEC','HYPE'])if(t.includes(x))return x+'USDT';return'';}
  function output(d){return d?.analyst_output&&d?.canonical_product_contract==='analyst_output'?d.analyst_output:null;}
  function canonicalState(d){const o=output(d);return o?.decision==='LONG'||o?.decision==='SHORT'?'ACTIONABLE':'WAIT';}
  function tone(el,kind){if(!el)return;const tile=el.closest('.command-tile');if(!tile)return;tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');tile.classList.add(`tone-${kind}`);}

  function acceptSnapshot(d,symbol=currentUiSymbol()){
    const normalized=norm(symbol),o=output(d);
    if(!d||!d.ok||!o||o.horizon!=='4-12H'||o.analysis_only!==true||o.live_execution!==false||!normalized||normalized!==currentUiSymbol())return false;
    acceptedDecision=d;acceptedSymbol=normalized;window.ATLAS_PRODUCTION_DECISION=d;window.ATLAS_ANALYST_OUTPUT=o;return true;
  }
  function invalidateSnapshot(){verifyEpoch++;acceptedDecision=null;acceptedSymbol='';window.ATLAS_ANALYST_OUTPUT=null;}

  function syncProductShell(d){
    const o=output(d);if(!o)return;
    const actionable=o.decision==='LONG'||o.decision==='SHORT';
    const score=finite(o.confidence)?Math.round(Number(o.confidence)):null,threshold=finite(o.signal_threshold)?Math.round(Number(o.signal_threshold)):68;
    setText('apsDecision',o.decision);const de=$('apsDecision');if(de)de.className='aps-value '+(actionable?o.decision.toLowerCase():'wait');
    setText('apsConfidence',`${score===null?'—':score}/${threshold}`);
    setText('apsEntry',actionable?fmt(o.entry):'—');setText('apsStop',actionable?fmt(o.stop_loss):'—');
    setText('apsTarget',actionable?`${fmt(o.take_profit)}${finite(o.risk_reward)?` · R:R ${fmt(o.risk_reward,2)}`:''}`:'—');
    setText('apsRegime',o.regime||'MIXED');setText('apsTrend',o.decision==='WAIT'?(d.candidate_direction||'NONE'):o.decision);
    setText('apsStructure',`${human(o.primary_reason||'Verified analysis')} · 4–12H`);
    setText('apsStatus',actionable?'4–12H analysis ready':'WAIT · no actionable 4–12H setup');
    setText('apsAiProd',`${o.decision}${score===null?'':` · ${score}/${threshold}`}`);setText('apsAiBest',actionable?`${o.decision} · 4–12H`:'WAIT');
    const cp=o.candidate_plan||{};
    setText('apsAiGeometry',actionable?`Entry ${fmt(o.entry)} · Stop ${fmt(o.stop_loss)} · TP ${fmt(o.take_profit)} · R:R ${fmt(o.risk_reward,2)}`:(cp.entry!=null?`Candidate only · Entry ${fmt(cp.entry)} · Stop ${fmt(cp.stop_loss)} · TP ${fmt(cp.take_profit)} · not actionable`:'No actionable trade geometry'));
    setText('apsAiTrigger',(o.what_changes_status||[]).map(human).join(' · ')||o.invalidation||'Reassess on new verified evidence.');
    setText('apsAiState',actionable?'Canonical 4–12H analyst decision':'Canonical WAIT');
    setText('apsWhy',(o.reasons||[]).map(human).join(' · ')||human(o.primary_reason||'WAIT'));
    setText('apsChanges',(o.what_changes_status||[]).map(human).join(' · ')||'Wait for new verified evidence.');
    const risks=[];if(o.setup_quality_gate?.status==='BLOCK')risks.push(`Evidence quarantine: ${human(o.setup_quality_gate.reason)}`);if(d.geometry_gate?.status==='BLOCK')risks.push(`Geometry: ${human(d.geometry_gate.reason)}`);if(o.data_degraded)risks.push('Data degraded');setText('apsRisks',risks.length?risks.join(' · '):'No additional canonical product block.');
  }

  function render(d){
    if(!acceptSnapshot(d))return false;const o=output(d),actionable=canonicalState(d)==='ACTIONABLE';
    const master=$('cmdMasterValue'),sub=$('cmdMasterSub'),score=finite(o.confidence)?Math.round(Number(o.confidence)):null,threshold=finite(o.signal_threshold)?Math.round(Number(o.signal_threshold)):68;
    if(master)master.textContent=`${o.decision} · ${score===null?'—':score}/${threshold}`;
    if(sub)sub.textContent=`4–12H · ${human(o.primary_reason||'Verified analysis')}`;
    tone(master,actionable?(o.decision==='LONG'?'positive':'negative'):'neutral');
    const regime=$('cmdRegimeValue');if(regime)regime.textContent=o.regime||'MIXED';tone(regime,o.regime==='TREND_UP'?'positive':o.regime==='TREND_DOWN'?'negative':'neutral');
    const plan=$('cmdPlanValue'),planSub=$('cmdPlanSub');if(plan)plan.textContent=actionable?'ANALYSIS READY':'WAIT';
    if(planSub)planSub.textContent=actionable?`Entry ${fmt(o.entry)} · SL ${fmt(o.stop_loss)} · TP ${fmt(o.take_profit)} · R:R ${fmt(o.risk_reward,2)}`:((o.what_changes_status||[]).map(human).join(' · ')||'No actionable 4–12H geometry');
    tone(plan,actionable?'positive':'neutral');syncProductShell(d);
    const cloud=$('cmdCloudValue');if(cloud){cloud.textContent='OFF-WEB';const small=cloud.closest('.command-tile')?.querySelector('small');if(small)small.textContent='Scheduled evidence: GitHub Actions';tone(cloud,'neutral');}
    return true;
  }

  function restoreAcceptedSnapshot(){if(!acceptedDecision||currentUiSymbol()!==acceptedSymbol)return;if(window.ATLAS_PRODUCTION_DECISION!==acceptedDecision)window.ATLAS_PRODUCTION_DECISION=acceptedDecision;window.ATLAS_ANALYST_OUTPUT=output(acceptedDecision);syncProductShell(acceptedDecision);}
  function hookVerify(ui){if(!ui||typeof ui.verify!=='function'||ui.__commandStripHooked)return;const original=ui.verify.bind(ui);ui.verify=async(...args)=>{const epoch=++verifyEpoch,symbol=currentUiSymbol(),previous=acceptedDecision,previousSymbol=acceptedSymbol,ok=await original(...args);if(epoch!==verifyEpoch||currentUiSymbol()!==symbol){if(previous&&currentUiSymbol()===previousSymbol){acceptedDecision=previous;acceptedSymbol=previousSymbol;restoreAcceptedSnapshot();}return false;}if(ok&&window.ATLAS_PRODUCTION_DECISION)render(window.ATLAS_PRODUCTION_DECISION);return ok;};ui.__commandStripHooked=true;}
  let refreshTimer=null;function scheduleVerify(delay=140){clearTimeout(refreshTimer);refreshTimer=setTimeout(async()=>{const ui=window.ATLAS_PRODUCTION_DECISION_UI;if(ui?.verify)await ui.verify();},delay);}
  function watchAssetChanges(){const title=$('activeTitle');if(!title||title.dataset.productionAssetWatcher==='1')return;title.dataset.productionAssetWatcher='1';let previous=title.textContent.trim();new MutationObserver(()=>{const current=title.textContent.trim();if(current&&current!==previous){previous=current;invalidateSnapshot();setText('cmdMasterSub',`Verifying ${current}…`);scheduleVerify();}}).observe(title,{subtree:true,childList:true,characterData:true});}
  function watchProductShellConsistency(){const shell=$('atlasProductShell');if(!shell||shell.dataset.productionSnapshotGuard==='1')return;shell.dataset.productionSnapshotGuard='1';let queued=false;new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;restoreAcceptedSnapshot();});}).observe(shell,{subtree:true,childList:true,characterData:true});}
  async function boot(attempt=0){const ui=window.ATLAS_PRODUCTION_DECISION_UI;if(!ui?.verify){if(attempt<40)return setTimeout(()=>boot(attempt+1),250);setText('cmdMasterSub','Production UI failed to load');return;}hookVerify(ui);watchAssetChanges();watchProductShellConsistency();setText('cmdMasterSub','Verifying live 4–12H analysis…');const ok=await ui.verify();if(ok&&window.ATLAS_PRODUCTION_DECISION)render(window.ATLAS_PRODUCTION_DECISION);else setText('cmdMasterSub','Production API unavailable — retry Analyze Live');setTimeout(watchProductShellConsistency,900);}

  window.ATLAS_RENDER_PRODUCTION_STATUS=render;window.ATLAS_SYNC_PRODUCT_SHELL=syncProductShell;window.ATLAS_CANONICAL_STATE=canonicalState;window.ATLAS_PRODUCTION_SNAPSHOT_GUARD={restore:restoreAcceptedSnapshot,current:()=>acceptedDecision,symbol:()=>acceptedSymbol,accept:acceptSnapshot,invalidate:invalidateSnapshot};window.ATLAS_PRODUCT_AUTHORITY={version:VERSION,contract:'analyst_output',horizon:'4-12H',analysisOnly:true};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,350),{once:true});else setTimeout(boot,350);
})();