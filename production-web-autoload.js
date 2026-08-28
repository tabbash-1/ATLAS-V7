(() => {
  const $ = id => document.getElementById(id);
  const tone = (el, kind) => {
    if (!el) return;
    const tile = el.closest('.command-tile');
    if (!tile) return;
    tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');
    tile.classList.add(`tone-${kind}`);
  };
  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  function consensusText(d) {
    const l = Number(d?.direction_votes_long);
    const s = Number(d?.direction_votes_short);
    if (Number.isFinite(l) && Number.isFinite(s)) {
      if (l === s) return `MIXED · L${l}/S${s}`;
      return l > s ? `LONG BIAS · L${l}/S${s}` : `SHORT BIAS · L${l}/S${s}`;
    }
    return d?.candidate_direction || 'MIXED';
  }
  function render(d) {
    if (!d || !d.ok) return;
    const state = d.opportunity_state || (d.execution_ready ? 'ACTIONABLE' : d.production_signal_qualified ? 'ARMED' : d.candidate_direction ? 'WATCH' : 'NO_SETUP');
    const score = finite(d.score) ? Math.round(Number(d.score)) : null;
    const threshold = finite(d.signal_threshold) ? Math.round(Number(d.signal_threshold)) : 68;
    const direction = d.candidate_direction || 'NONE';
    const decision = d.actionable_decision && d.actionable_decision !== 'WAIT' ? d.actionable_decision : state;
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

    const p = d.trade_plan || {};
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
    tone(plan, d.execution_ready ? 'positive' : state === 'ARMED' ? 'warning' : 'neutral');

    const cloud = $('cmdCloudValue');
    if (cloud && String(cloud.textContent || '').toUpperCase() === 'DISABLED') {
      cloud.textContent = 'OFF-WEB';
      const small = cloud.closest('.command-tile')?.querySelector('small');
      if (small) small.textContent = 'Scheduled research runs in GitHub Actions';
      tone(cloud, 'neutral');
    }
  }
  function hookVerify(ui) {
    if (!ui || typeof ui.verify !== 'function' || ui.__commandStripHooked) return;
    const original = ui.verify.bind(ui);
    ui.verify = async (...args) => {
      const ok = await original(...args);
      if (ok && window.ATLAS_PRODUCTION_DECISION) render(window.ATLAS_PRODUCTION_DECISION);
      return ok;
    };
    ui.__commandStripHooked = true;
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
    const sub = $('cmdMasterSub');
    if (sub) sub.textContent = 'Verifying live Production…';
    const ok = await ui.verify();
    if (ok && window.ATLAS_PRODUCTION_DECISION) render(window.ATLAS_PRODUCTION_DECISION);
    else if (sub) sub.textContent = 'Production API unavailable — retry Analyze Live';
  }
  window.ATLAS_RENDER_PRODUCTION_STATUS = render;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 350), {once:true});
  else setTimeout(boot, 350);
})();
