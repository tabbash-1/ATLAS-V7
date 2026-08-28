(() => {
  const $ = id => document.getElementById(id);
  const tone = (el, kind) => {
    if (!el) return;
    const tile = el.closest('.command-tile');
    if (!tile) return;
    tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');
    tile.classList.add(`tone-${kind}`);
  };
  function render(d) {
    if (!d || !d.ok) return;
    const state = d.opportunity_state || (d.execution_ready ? 'ACTIONABLE' : d.production_signal_qualified ? 'ARMED' : d.candidate_direction ? 'WATCH' : 'NO_SETUP');
    const score = Number.isFinite(Number(d.score)) ? Math.round(Number(d.score)) : '—';
    const threshold = Number.isFinite(Number(d.signal_threshold)) ? Math.round(Number(d.signal_threshold)) : 68;
    const direction = d.candidate_direction || 'NONE';
    const decision = d.actionable_decision && d.actionable_decision !== 'WAIT' ? d.actionable_decision : state;
    const master = $('cmdMasterValue');
    const masterSub = $('cmdMasterSub');
    if (master) master.textContent = `${decision}${score !== '—' ? ` · ${score}/${threshold}` : ''}`;
    if (masterSub) masterSub.textContent = `${direction} · ${d.actionable_reason || d.wait_reason || d.opportunity_state_reason || 'Production verified'}`;
    tone(master, state === 'ACTIONABLE' ? 'positive' : state === 'ARMED' || state === 'WATCH' ? 'warning' : 'neutral');

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
      planSub.textContent = parts.length ? parts.join(' · ') : (p.entry_trigger || 'No executable geometry yet');
    }
    tone(plan, d.execution_ready ? 'positive' : state === 'ARMED' ? 'warning' : 'neutral');
  }
  async function boot(attempt = 0) {
    const ui = window.ATLAS_PRODUCTION_DECISION_UI;
    if (!ui || typeof ui.verify !== 'function') {
      if (attempt < 40) return setTimeout(() => boot(attempt + 1), 250);
      const sub = $('cmdMasterSub');
      if (sub) sub.textContent = 'Production UI failed to load';
      return;
    }
    const sub = $('cmdMasterSub');
    if (sub) sub.textContent = 'Verifying live Production…';
    const ok = await ui.verify();
    if (ok) render(window.ATLAS_PRODUCTION_DECISION);
    else if (sub) sub.textContent = 'Production API unavailable — retry Analyze Live';
  }
  window.ATLAS_RENDER_PRODUCTION_STATUS = render;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 350), {once:true});
  else setTimeout(boot, 350);
})();
