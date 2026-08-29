(() => {
  const $ = id => document.getElementById(id);
  let acceptedDecision = null;
  let acceptedSymbol = '';
  let verifyEpoch = 0;
  const tone = (el, kind) => {
    if (!el) return;
    const tile = el.closest('.command-tile');
    if (!tile) return;
    tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');
    tile.classList.add(`tone-${kind}`);
  };
  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const fmt = (v, d=2) => finite(v) ? Number(v).toLocaleString(undefined,{maximumFractionDigits:d}) : '—';
  const setText = (id, value) => {
    const el = $(id);
    const next = value == null ? '—' : String(value);
    if (el && el.textContent !== next) el.textContent = next;
  };
  const normalizedSymbol = v => String(v||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  function currentUiSymbol(){
    const s=window.ATLAS_APP_STATE,a=s?.assets?.[s.active],raw=normalizedSymbol(a?.symbol);
    if(raw)return raw;
    const t=($('activeTitle')?.textContent||'').toUpperCase();
    for(const x of ['BTC','ETH','SOL','XRP','BNB','DOGE','ZEC','HYPE'])if(t.includes(x))return x+'USDT';
    return '';
  }
  function consensusText(d) {
    const l = Number(d?.direction_votes_long);
    const s = Number(d?.direction_votes_short);
    if (Number.isFinite(l) && Number.isFinite(s)) {
      if (l === s) return `MIXED · L${l}/S${s}`;
      return l > s ? `LONG BIAS · L${l}/S${s}` : `SHORT BIAS · L${l}/S${s}`;
    }
    return d?.candidate_direction || 'MIXED';
  }
  function canonicalState(d) {
    const p = d?.trade_plan || {};
    const qualified = !!d?.production_signal_qualified;
    const ready = !!d?.execution_ready;
    if (p.status === 'ACTIONABLE' && qualified && ready && (p.direction === 'LONG' || p.direction === 'SHORT')) return 'ACTIONABLE';
    if (p.status === 'CONDITIONAL' && qualified) return 'ARMED';
    return d?.candidate_direction ? 'WATCH' : 'NO_SETUP';
  }
  function directional(dir) {
    return dir === 'LONG' ? 'UP / LONG' : dir === 'SHORT' ? 'DOWN / SHORT' : 'WAIT';
  }
  function syncProductShell(d) {
    if (!d || !d.ok) return;
    const p = d.trade_plan || {};
    const state = canonicalState(d);
    const dir = p.direction || d.candidate_direction;
    const isActionable = state === 'ACTIONABLE';
    const isArmed = state === 'ARMED';
    const finalDecision = isActionable ? dir : 'WAIT';
    const action = p.action || 'WAIT';
    const score = finite(d.score) ? Math.round(Number(d.score)) : null;
    const threshold = finite(d.signal_threshold) ? Math.round(Number(d.signal_threshold)) : 68;
    setText('apsDecision', finalDecision);
    const decisionEl = $('apsDecision');
    if (decisionEl) decisionEl.className = `aps-value ${String(finalDecision).toLowerCase()}`;
    setText('apsConfidence', `${score === null ? '—' : score}/${threshold}`);
    setText('apsEntry', isActionable ? fmt(p.entry) : '—');
    setText('apsStop', isActionable ? fmt(p.stop_loss) : '—');
    setText('apsTarget', isActionable ? `${fmt(p.tp2)}${finite(p.rr_tp2) ? ` · R:R ${fmt(p.rr_tp2,2)}` : ''}` : '—');
    setText('apsStatus', isActionable ? 'Canonical Production trade plan ready' : isArmed ? 'ARMED = wait for Production trigger' : 'WAIT = no trade now');
    const dirText = directional(dir);
    setText('apsAiProd', isActionable ? `${dirText}${score === null ? '' : ` · ${score}/${threshold}`}` : isArmed ? `ARMED · ${dirText}${score === null ? '' : ` · ${score}/${threshold}`}` : `WAIT${score === null ? '' : ` · ${score}/${threshold}`}`);
    setText('apsAiBest', isActionable ? `${action} NOW → ${dirText}` : isArmed ? `ARMED · ${String(action).replaceAll('_',' ')} → ${dirText}` : 'WAIT');
    setText('apsAiGeometry', p.entry == null ? 'No canonical Production trade geometry' : `${isActionable ? 'Verified Production plan' : isArmed ? 'Armed conditional Production plan' : 'Production plan'} · Entry ${fmt(p.entry)} · Stop ${fmt(p.stop_loss)} · TP1 ${fmt(p.tp1)} · TP2 ${fmt(p.tp2)} · R:R ${fmt(p.rr_tp2,2)}`);
    setText('apsAiTrigger', p.entry_trigger || p.invalidation || 'Reassess if the verified Production structure changes.');
    setText('apsAiState', isActionable ? 'Production canonical decision' : isArmed ? 'ARMED — verified trigger defined' : 'WAIT');
  }
  function render(d) {
    if (!d || !d.ok) return;
    acceptedDecision = d;
    acceptedSymbol = currentUiSymbol();
    window.ATLAS_PRODUCTION_DECISION = d;
    const state = canonicalState(d);
    const score = finite(d.score) ? Math.round(Number(d.score)) : null;
    const threshold = finite(d.signal_threshold) ? Math.round(Number(d.signal_threshold)) : 68;
    const direction = d.candidate_direction || 'NONE';
    const p = d.trade_plan || {};
    const decision = state === 'ACTIONABLE' ? direction : state;
    const master = $('cmdMasterValue');
    const masterSub = $('cmdMasterSub');
    if (master) master.textContent = `${decision} · ${score === null ? '—' : score}/${threshold}`;
    if (masterSub) {
      const reason = d.actionable_reason || d.wait_reason || d.opportunity_state_reason || 'Production verified';
      masterSub.textContent = direction === 'NONE' ? `${consensusText(d)} · ${reason}` : `${direction} · ${reason}`;
    }
    tone(master, state === 'ACTIONABLE' ? 'positive' : state === 'ARMED' || state === 'WATCH' ? 'warning' : 'neutral');
    const regime = $('cmdRegimeValue');
    if (regime) regime.textContent = d.regime || consensusText(d);
    tone(regime, d.candidate_direction === 'LONG' ? 'positive' : d.candidate_direction === 'SHORT' ? 'negative' : 'neutral');
    const plan = $('cmdPlanValue');
    const planSub = $('cmdPlanSub');
    if (plan) plan.textContent = p.status || (d.execution_ready ? 'ACTIONABLE' : 'WAITING');
    if (planSub) {
      const parts = [];
      if (p.entry != null) parts.push(`Entry ${p.entry}`);
      if (p.stop_loss != null) parts.push(`SL ${p.stop_loss}`);
      if (p.tp2 != null) parts.push(`TP2 ${p.tp2}`);
      if (p.rr_tp2 != null) parts.push(`R:R ${p.rr_tp2}`);
      planSub.textContent = parts.length ? parts.join(' · ') : (p.entry_trigger || (state === 'NO_SETUP' ? 'No directional setup — no geometry by design' : 'No executable geometry yet'));
    }
    tone(plan, state === 'ACTIONABLE' ? 'positive' : state === 'ARMED' ? 'warning' : 'neutral');
    syncProductShell(d);
    const cloud = $('cmdCloudValue');
    if (cloud) {
      cloud.textContent = 'OFF-WEB';
      const small = cloud.closest('.command-tile')?.querySelector('small');
      if (small) small.textContent = 'Scheduled research: GitHub Actions';
      tone(cloud, 'neutral');
    }
  }
  function restoreAcceptedSnapshot(){
    if(!acceptedDecision || currentUiSymbol()!==acceptedSymbol) return;
    if(window.ATLAS_PRODUCTION_DECISION!==acceptedDecision) window.ATLAS_PRODUCTION_DECISION=acceptedDecision;
    syncProductShell(acceptedDecision);
  }
  function hookVerify(ui) {
    if (!ui || typeof ui.verify !== 'function' || ui.__commandStripHooked) return;
    const original = ui.verify.bind(ui);
    ui.verify = async (...args) => {
      const requestEpoch=++verifyEpoch;
      const requestSymbol=currentUiSymbol();
      const previous=acceptedDecision;
      const previousSymbol=acceptedSymbol;
      const ok = await original(...args);
      if(requestEpoch!==verifyEpoch || currentUiSymbol()!==requestSymbol){
        if(previous && currentUiSymbol()===previousSymbol){acceptedDecision=previous;acceptedSymbol=previousSymbol;restoreAcceptedSnapshot();}
        return false;
      }
      if (ok && window.ATLAS_PRODUCTION_DECISION) render(window.ATLAS_PRODUCTION_DECISION);
      return ok;
    };
    ui.__commandStripHooked = true;
  }
  let refreshTimer = null;
  function scheduleCurrentAssetVerify(delay = 140) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      const ui = window.ATLAS_PRODUCTION_DECISION_UI;
      if (!ui || typeof ui.verify !== 'function') return;
      await ui.verify();
    }, delay);
  }
  function watchAssetChanges() {
    const title = $('activeTitle');
    if (!title || title.dataset.productionAssetWatcher === '1') return;
    title.dataset.productionAssetWatcher = '1';
    let previous = title.textContent.trim();
    new MutationObserver(() => {
      const current = title.textContent.trim();
      if (current && current !== previous) {
        previous = current;
        verifyEpoch++;
        acceptedDecision=null;
        acceptedSymbol='';
        const sub = $('cmdMasterSub');
        if (sub) sub.textContent = `Verifying ${current}…`;
        scheduleCurrentAssetVerify();
      }
    }).observe(title, {subtree:true, childList:true, characterData:true});
  }
  let shellSyncQueued = false;
  function watchProductShellConsistency() {
    const shell = $('atlasProductShell');
    if (!shell || shell.dataset.productionSnapshotGuard === '1') return;
    shell.dataset.productionSnapshotGuard = '1';
    new MutationObserver(() => {
      if (shellSyncQueued) return;
      shellSyncQueued = true;
      requestAnimationFrame(() => {
        shellSyncQueued = false;
        restoreAcceptedSnapshot();
      });
    }).observe(shell,{subtree:true,childList:true,characterData:true});
  }
  async function boot(attempt = 0) {
    const ui = window.ATLAS_PRODUCTION_DECISION_UI;
    if (!ui || typeof ui.verify !== 'function') {
      if (attempt < 40) return setTimeout(() => boot(attempt + 1), 250);
      const sub = $('cmdMasterSub');
      if (sub) sub.textContent = 'Production UI failed to load';
      return;
    }
    hookVerify(ui);
    watchAssetChanges();
    watchProductShellConsistency();
    const sub = $('cmdMasterSub');
    if (sub) sub.textContent = 'Verifying live Production…';
    const ok = await ui.verify();
    if (ok && window.ATLAS_PRODUCTION_DECISION) render(window.ATLAS_PRODUCTION_DECISION);
    else if (sub) sub.textContent = 'Production API unavailable — retry Analyze Live';
    setTimeout(watchProductShellConsistency, 900);
  }
  window.ATLAS_RENDER_PRODUCTION_STATUS = render;
  window.ATLAS_SYNC_PRODUCT_SHELL = syncProductShell;
  window.ATLAS_CANONICAL_STATE = canonicalState;
  window.ATLAS_PRODUCTION_SNAPSHOT_GUARD={restore:restoreAcceptedSnapshot,current:()=>acceptedDecision,symbol:()=>acceptedSymbol};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 350), {once:true});
  else setTimeout(boot, 350);
})();