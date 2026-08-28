from pathlib import Path


def test_product_shell_sync_is_installed():
    js=Path('atlas-production-decision.js').read_text()
    assert 'syncProductShell' in js
    assert 'Verified Production plan' in js
    assert 'Conditional Production plan' in js
    assert "canonicalPlan:true" in js
    assert "singleDecisionAuthority:true" in js


def test_actionable_plan_wins_over_stale_watch_state():
    js=Path('atlas-production-decision.js').read_text()
    assert "if(p.status==='ACTIONABLE'&&qualified&&ready)return'ACTIONABLE'" in js
    assert "return d?.candidate_direction?'WATCH':'NO_SETUP'" in js
    assert "return d?.opportunity_state||" not in js


def test_visible_signal_uses_resolved_production_state():
    js=Path('atlas-production-decision.js').read_text()
    assert "signal=state==='ACTIONABLE'" in js
    assert "opp==='ACTIONABLE'?(p.action||'WAIT'):'WAIT'" in js


def test_ai_cannot_replace_production_trade_plan_geometry():
    js=Path('atlas-production-decision.js').read_text()
    assert 'function canonicalPlan(d,a)' in js
    assert "return Object.keys(p).length?p:(a?.canonical_action||{})" in js


def test_product_shell_reads_only_canonical_trade_plan_for_visible_geometry():
    js=Path('atlas-product-shell.js').read_text()
    assert "const p=production(),plan=p?.trade_plan||{},d=decision()" in js
    assert "fmt(plan.entry)" in js
    assert "fmt(plan.stop_loss)" in js
    assert "fmt(plan.tp2)" in js
    assert "fmt(plan.rr_tp2,2)" in js
    assert "const tp=p?.take_profit" not in js


def test_product_shell_best_action_uses_canonical_plan_not_counterfactual_geometry():
    js=Path('atlas-product-shell.js').read_text()
    assert "canonical=Object.keys(plan).length?plan:(ai?.canonical_action||{})" in js
    assert "Verified Production plan" in js
    assert "best=ai?.best_counterfactual" not in js
    assert "Conditional breakout plan · Entry" not in js
